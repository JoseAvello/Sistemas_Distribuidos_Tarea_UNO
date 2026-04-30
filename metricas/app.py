from flask import Flask, request, jsonify
import time
import json
import os

app = Flask(__name__)

# Almacenamiento simple en memoria de métricas
registro_eventos = []
resumen = {
    "hits": 0,
    "misses": 0,
    "evictions": 0,
    "latencias_cache": [],
    "latencias_db": [],
    "total_consultas": 0,
}

@app.route("/registrar", methods=["POST"])
def registrar_evento():
    datos = request.get_json()
    datos["timestamp"] = time.time()
    registro_eventos.append(datos)

    tipo = datos.get("tipo")
    if tipo == "hit":
        resumen["hits"] += 1
        if "latencia_ms" in datos:
            resumen["latencias_cache"].append(datos["latencia_ms"])
    elif tipo == "miss":
        resumen["misses"] += 1
        if "latencia_ms" in datos:
            resumen["latencias_db"].append(datos["latencia_ms"])
    elif tipo == "eviction":
        resumen["evictions"] += 1

    resumen["total_consultas"] = resumen["hits"] + resumen["misses"]
    return jsonify({"ok": True})

@app.route("/metricas", methods=["GET"])
def obtener_metricas():
    total = resumen["hits"] + resumen["misses"]
    hit_rate = resumen["hits"] / total if total > 0 else 0
    miss_rate = resumen["misses"] / total if total > 0 else 0

    lats_cache = resumen["latencias_cache"]
    lats_db = resumen["latencias_db"]

    def percentil(lista, p):
        if not lista:
            return 0
        ordenada = sorted(lista)
        indice = int(len(ordenada) * p / 100)
        return ordenada[min(indice, len(ordenada) - 1)]

    resultado = {
        "hits": resumen["hits"],
        "misses": resumen["misses"],
        "total_consultas": total,
        "hit_rate": round(hit_rate, 4),
        "miss_rate": round(miss_rate, 4),
        "evictions": resumen["evictions"],
        "latencia_cache_p50_ms": percentil(lats_cache, 50),
        "latencia_cache_p95_ms": percentil(lats_cache, 95),
        "latencia_db_p50_ms": percentil(lats_db, 50),
        "latencia_db_p95_ms": percentil(lats_db, 95),
    }
    return jsonify(resultado)

@app.route("/eventos", methods=["GET"])
def obtener_eventos():
    limite = int(request.args.get("limite", 100))
    return jsonify(registro_eventos[-limite:])

@app.route("/reiniciar", methods=["POST"])
def reiniciar():
    global registro_eventos, resumen
    registro_eventos = []
    resumen = {
        "hits": 0,
        "misses": 0,
        "evictions": 0,
        "latencias_cache": [],
        "latencias_db": [],
        "total_consultas": 0,
    }
    return jsonify({"ok": True, "mensaje": "métricas reiniciadas"})

@app.route("/salud", methods=["GET"])
def salud():
    return jsonify({"estado": "ok"})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8001)
