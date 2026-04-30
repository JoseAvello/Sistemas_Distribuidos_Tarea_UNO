from flask import Flask, request, jsonify
import redis
import json
import os
import time
import requests

app = Flask(__name__)

REDIS_HOST = os.environ.get("REDIS_HOST", "redis")
REDIS_PORT = int(os.environ.get("REDIS_PORT", 6379))
URL_RESPUESTAS = os.environ.get("RESPUESTAS_URL", "http://generador_respuestas:8002")
URL_METRICAS = os.environ.get("METRICAS_URL", "http://metricas:8001")
CACHE_TTL = int(os.environ.get("CACHE_TTL", 120))

cliente_redis = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=True)

def generar_clave_cache(tipo, zona_id, confianza_min=0.0, bins=5, zona_b=None):
    if tipo == "Q1":
        return f"conteo:{zona_id}:conf={confianza_min}"
    elif tipo == "Q2":
        return f"area:{zona_id}:conf={confianza_min}"
    elif tipo == "Q3":
        return f"densidad:{zona_id}:conf={confianza_min}"
    elif tipo == "Q4":
        return f"comparar:densidad:{zona_id}:{zona_b}:conf={confianza_min}"
    elif tipo == "Q5":
        return f"conf_dist:{zona_id}:bins={bins}"
    return f"gen:{tipo}:{zona_id}"

def registrar_metrica(tipo_evento, clave, latencia_ms, tipo_consulta):
    try:
        requests.post(f"{URL_METRICAS}/registrar", json={
            "tipo": tipo_evento,
            "clave": clave,
            "latencia_ms": latencia_ms,
            "tipo_consulta": tipo_consulta,
        }, timeout=1)
    except Exception:
        pass  # No bloquear si métricas falla

@app.route("/consulta", methods=["POST"])
def manejar_consulta():
    datos = request.get_json()
    tipo = datos.get("tipo")
    zona_id = datos.get("zona_id")
    confianza_min = float(datos.get("confianza_min", 0.0))
    bins = int(datos.get("bins", 5))
    zona_b = datos.get("zona_b")

    clave = generar_clave_cache(tipo, zona_id, confianza_min, bins, zona_b)

    inicio = time.time()

    # Intentar obtener desde caché
    valor_cache = cliente_redis.get(clave)

    if valor_cache is not None:
        latencia_ms = round((time.time() - inicio) * 1000, 2)
        registrar_metrica("hit", clave, latencia_ms, tipo)
        return jsonify({
            "origen": "cache",
            "resultado": json.loads(valor_cache),
            "latencia_ms": latencia_ms
        })

    # Cache miss: delegar al generador de respuestas
    try:
        respuesta = requests.post(f"{URL_RESPUESTAS}/consulta", json=datos, timeout=30)
        respuesta.raise_for_status()
        datos_respuesta = respuesta.json()
    except Exception as e:
        return jsonify({"error": f"fallo al contactar generador de respuestas: {str(e)}"}), 503

    resultado = datos_respuesta.get("resultado")
    latencia_db_ms = datos_respuesta.get("latencia_ms", 0)

    # Guardar en caché con TTL
    cliente_redis.setex(clave, CACHE_TTL, json.dumps(resultado))

    latencia_ms = round((time.time() - inicio) * 1000, 2)
    registrar_metrica("miss", clave, latencia_ms, tipo)

    return jsonify({
        "origen": "base_de_datos",
        "resultado": resultado,
        "latencia_ms": latencia_ms
    })

@app.route("/estado_cache", methods=["GET"])
def estado_cache():
    info = cliente_redis.info("memory")
    claves_usadas = cliente_redis.dbsize()
    return jsonify({
        "claves_en_cache": claves_usadas,
        "memoria_usada_mb": round(info.get("used_memory", 0) / 1024 / 1024, 2),
        "memoria_maxima_mb": round(info.get("maxmemory", 0) / 1024 / 1024, 2),
        "politica_remocion": info.get("maxmemory_policy", "none"),
        "ttl_configurado_seg": CACHE_TTL,
    })

@app.route("/limpiar_cache", methods=["POST"])
def limpiar_cache():
    cliente_redis.flushdb()
    return jsonify({"ok": True, "mensaje": "caché limpiada"})

@app.route("/salud", methods=["GET"])
def salud():
    try:
        cliente_redis.ping()
        redis_ok = True
    except Exception:
        redis_ok = False
    return jsonify({"estado": "ok", "redis_conectado": redis_ok})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8003)
