import os
import time
import random
import math
import requests
import json
from datetime import datetime

URL_CACHE = os.environ.get("CACHE_URL", "http://cache_service:8003")
URL_METRICAS = os.environ.get("METRICAS_URL", "http://metricas:8001")
DISTRIBUCION = os.environ.get("DISTRIBUCION", "zipf")
TOTAL_CONSULTAS = int(os.environ.get("TOTAL_CONSULTAS", 500))
CONSULTAS_POR_SEGUNDO = float(os.environ.get("CONSULTAS_POR_SEGUNDO", 10))

ZONAS_IDS = ["Z1", "Z2", "Z3", "Z4", "Z5"]
TIPOS_CONSULTA = ["Q1", "Q2", "Q3", "Q4", "Q5"]
VALORES_CONFIANZA = [0.0, 0.5, 0.7, 0.9]
VALORES_BINS = [5, 10]

def muestrear_zipf(n_elementos, s=1.5):
    """
    Muestrea un índice siguiendo distribución Zipf (ley de potencia).
    Elementos más populares (índice bajo) se consultan con mucho más frecuencia.
    """
    pesos = [1.0 / (i ** s) for i in range(1, n_elementos + 1)]
    suma = sum(pesos)
    pesos_norm = [p / suma for p in pesos]
    r = random.random()
    acumulado = 0
    for i, p in enumerate(pesos_norm):
        acumulado += p
        if r <= acumulado:
            return i
    return n_elementos - 1

def generar_consulta_zipf():
    """
    Con Zipf: las zonas y tipos de consulta más populares se repiten mucho más.
    Esto favorece los cache hits.
    """
    idx_zona = muestrear_zipf(len(ZONAS_IDS))
    idx_tipo = muestrear_zipf(len(TIPOS_CONSULTA))
    zona_id = ZONAS_IDS[idx_zona]
    tipo = TIPOS_CONSULTA[idx_tipo]
    confianza_min = VALORES_CONFIANZA[muestrear_zipf(len(VALORES_CONFIANZA))]
    bins = VALORES_BINS[0]  # Con Zipf siempre usar el mismo bin para más hits

    consulta = {"tipo": tipo, "zona_id": zona_id, "confianza_min": confianza_min, "bins": bins}
    if tipo == "Q4":
        # Zona B diferente a zona A
        zonas_restantes = [z for z in ZONAS_IDS if z != zona_id]
        consulta["zona_b"] = zonas_restantes[muestrear_zipf(len(zonas_restantes))]
    return consulta

def generar_consulta_uniforme():
    """
    Distribución uniforme: todos los parámetros con igual probabilidad.
    Genera más misses porque hay más combinaciones únicas.
    """
    zona_id = random.choice(ZONAS_IDS)
    tipo = random.choice(TIPOS_CONSULTA)
    confianza_min = random.choice(VALORES_CONFIANZA)
    bins = random.choice(VALORES_BINS)

    consulta = {"tipo": tipo, "zona_id": zona_id, "confianza_min": confianza_min, "bins": bins}
    if tipo == "Q4":
        zonas_restantes = [z for z in ZONAS_IDS if z != zona_id]
        consulta["zona_b"] = random.choice(zonas_restantes)
    return consulta

def enviar_consulta(consulta):
    try:
        inicio = time.time()
        resp = requests.post(f"{URL_CACHE}/consulta", json=consulta, timeout=30)
        latencia = round((time.time() - inicio) * 1000, 2)
        datos = resp.json()
        return datos.get("origen", "desconocido"), latencia
    except Exception as e:
        print(f"  ERROR enviando consulta: {e}", flush=True)
        return "error", 0

def esperar_servicio(url, nombre, reintentos=30):
    for i in range(reintentos):
        try:
            r = requests.get(f"{url}/salud", timeout=5)
            if r.status_code == 200:
                print(f"{nombre} disponible.", flush=True)
                return True
        except Exception:
            pass
        print(f"Esperando {nombre}... ({i+1}/{reintentos})", flush=True)
        time.sleep(3)
    return False

def main():
    print(f"=== Generador de Tráfico ===", flush=True)
    print(f"Distribución: {DISTRIBUCION}", flush=True)
    print(f"Total consultas: {TOTAL_CONSULTAS}", flush=True)
    print(f"Tasa: {CONSULTAS_POR_SEGUNDO} consultas/seg", flush=True)

    # Esperar que el cache esté listo
    if not esperar_servicio(URL_CACHE, "Cache Service"):
        print("No se pudo conectar al cache. Saliendo.", flush=True)
        return

    # Reiniciar métricas antes de empezar
    try:
        requests.post(f"{URL_METRICAS}/reiniciar", timeout=5)
        print("Métricas reiniciadas.", flush=True)
    except Exception:
        pass

    intervalo = 1.0 / CONSULTAS_POR_SEGUNDO
    hits = 0
    misses = 0
    errores = 0

    print(f"\nIniciando generación de tráfico ({DISTRIBUCION})...\n", flush=True)

    for i in range(TOTAL_CONSULTAS):
        if DISTRIBUCION == "zipf":
            consulta = generar_consulta_zipf()
        else:
            consulta = generar_consulta_uniforme()

        origen, latencia = enviar_consulta(consulta)

        if origen == "cache":
            hits += 1
        elif origen == "base_de_datos":
            misses += 1
        else:
            errores += 1

        if (i + 1) % 50 == 0:
            total_hasta_ahora = hits + misses
            hr = hits / total_hasta_ahora if total_hasta_ahora > 0 else 0
            print(f"[{i+1}/{TOTAL_CONSULTAS}] hits={hits} misses={misses} hit_rate={hr:.2%}", flush=True)

        time.sleep(intervalo)

    # Resumen final
    total = hits + misses
    hr_final = hits / total if total > 0 else 0
    print(f"\n=== Resumen Final ===", flush=True)
    print(f"Total consultas: {total}", flush=True)
    print(f"Hits: {hits} | Misses: {misses} | Errores: {errores}", flush=True)
    print(f"Hit rate: {hr_final:.2%}", flush=True)

    # Obtener métricas del servidor
    try:
        resp = requests.get(f"{URL_METRICAS}/metricas", timeout=5)
        metricas = resp.json()
        print(f"\nMétricas del servidor:", flush=True)
        print(json.dumps(metricas, indent=2), flush=True)
    except Exception as e:
        print(f"No se pudieron obtener métricas del servidor: {e}", flush=True)

if __name__ == "__main__":
    main()
