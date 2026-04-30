from flask import Flask, request, jsonify
import gzip
import csv
import os
import time
import math
import random
import requests

app = Flask(__name__)

# Zonas definidas según el dataset real (tile 969 de Google Open Buildings)
ZONAS = {
    "Z1": {"lat_min": -33.1346, "lat_max": -31.0291, "lon_min": -71.7349, "lon_max": -69.5575, "nombre": "Zona Norte-Oeste"},
    "Z2": {"lat_min": -33.1346, "lat_max": -31.0291, "lon_min": -69.5575, "lon_max": -67.3802, "nombre": "Zona Norte-Este"},
    "Z3": {"lat_min": -31.0291, "lat_max": -28.9236, "lon_min": -71.7349, "lon_max": -69.5575, "nombre": "Zona Centro-Oeste"},
    "Z4": {"lat_min": -31.0291, "lat_max": -28.9236, "lon_min": -69.5575, "lon_max": -67.3802, "nombre": "Zona Centro-Este"},
    "Z5": {"lat_min": -28.9236, "lat_max": -26.8182, "lon_min": -70.6462, "lon_max": -68.4689, "nombre": "Zona Sur"},
}

# Datos precargados en memoria por zona
datos_por_zona = {}

RUTA_CSV = "/datos/edificios.csv.gz"
URL_METRICAS = os.environ.get("METRICAS_URL", "http://metricas:8001")

def calcular_area_km2(zona_id):
    z = ZONAS[zona_id]
    # Aproximación simple: 1 grado lat ≈ 111 km, 1 grado lon ≈ 111*cos(lat) km
    lat_centro = (z["lat_min"] + z["lat_max"]) / 2
    alto_km = (z["lat_max"] - z["lat_min"]) * 111
    ancho_km = (z["lon_max"] - z["lon_min"]) * 111 * math.cos(math.radians(lat_centro))
    return abs(alto_km * ancho_km)

areas_km2 = {}

def cargar_datos():
    print("Cargando datos del CSV en memoria...", flush=True)
    contadores = {zona_id: 0 for zona_id in ZONAS}

    for zona_id in ZONAS:
        datos_por_zona[zona_id] = []
        areas_km2[zona_id] = calcular_area_km2(zona_id)

    if not os.path.exists(RUTA_CSV):
        print(f"ADVERTENCIA: No se encontró {RUTA_CSV}, usando datos simulados", flush=True)
        _generar_datos_simulados()
        return

    with gzip.open(RUTA_CSV, "rt", encoding="utf-8") as f:
        lector = csv.DictReader(f)
        for fila in lector:
            try:
                lat = float(fila["latitude"])
                lon = float(fila["longitude"])
                area = float(fila["area_in_meters"])
                confianza = float(fila["confidence"])
                for zona_id, z in ZONAS.items():
                    if z["lat_min"] <= lat <= z["lat_max"] and z["lon_min"] <= lon <= z["lon_max"]:
                        datos_por_zona[zona_id].append({
                            "lat": lat, "lon": lon,
                            "area": area, "confianza": confianza
                        })
                        contadores[zona_id] += 1
                        break
            except (ValueError, KeyError):
                continue

    for zona_id, cant in contadores.items():
        print(f"  {zona_id}: {cant} edificios cargados", flush=True)
    print("Carga completa.", flush=True)

def _generar_datos_simulados():
    """Fallback por si no hay CSV"""
    for zona_id, z in ZONAS.items():
        cantidad = random.randint(5000, 20000)
        for _ in range(cantidad):
            datos_por_zona[zona_id].append({
                "lat": random.uniform(z["lat_min"], z["lat_max"]),
                "lon": random.uniform(z["lon_min"], z["lon_max"]),
                "area": random.uniform(20, 500),
                "confianza": random.uniform(0.5, 1.0)
            })

# ----------- Consultas Q1 a Q5 -----------

def q1_conteo(zona_id, confianza_min=0.0):
    registros = datos_por_zona.get(zona_id, [])
    return sum(1 for r in registros if r["confianza"] >= confianza_min)

def q2_area(zona_id, confianza_min=0.0):
    areas = [r["area"] for r in datos_por_zona.get(zona_id, []) if r["confianza"] >= confianza_min]
    if not areas:
        return {"area_promedio": 0, "area_total": 0, "n": 0}
    return {
        "area_promedio": round(sum(areas) / len(areas), 2),
        "area_total": round(sum(areas), 2),
        "n": len(areas)
    }

def q3_densidad(zona_id, confianza_min=0.0):
    conteo = q1_conteo(zona_id, confianza_min)
    area_km2 = areas_km2.get(zona_id, 1)
    return round(conteo / area_km2, 4)

def q4_comparar(zona_a, zona_b, confianza_min=0.0):
    da = q3_densidad(zona_a, confianza_min)
    db = q3_densidad(zona_b, confianza_min)
    return {
        "zona_a": zona_a,
        "densidad_a": da,
        "zona_b": zona_b,
        "densidad_b": db,
        "ganador": zona_a if da > db else zona_b
    }

def q5_distribucion_confianza(zona_id, bins=5):
    scores = [r["confianza"] for r in datos_por_zona.get(zona_id, [])]
    if not scores:
        return []
    ancho = 1.0 / bins
    resultado = []
    for i in range(bins):
        limite_min = i * ancho
        limite_max = (i + 1) * ancho
        cantidad = sum(1 for s in scores if limite_min <= s < limite_max)
        resultado.append({
            "bucket": i,
            "min": round(limite_min, 2),
            "max": round(limite_max, 2),
            "cantidad": cantidad
        })
    return resultado

# ----------- Endpoints -----------

@app.route("/consulta", methods=["POST"])
def procesar_consulta():
    datos = request.get_json()
    tipo_consulta = datos.get("tipo")
    zona_id = datos.get("zona_id")
    confianza_min = float(datos.get("confianza_min", 0.0))
    bins = int(datos.get("bins", 5))
    zona_b = datos.get("zona_b")

    inicio = time.time()

    # Simular algo de tiempo de procesamiento (consulta geoespacial en memoria)
    time.sleep(random.uniform(0.01, 0.05))

    if tipo_consulta == "Q1":
        resultado = q1_conteo(zona_id, confianza_min)
    elif tipo_consulta == "Q2":
        resultado = q2_area(zona_id, confianza_min)
    elif tipo_consulta == "Q3":
        resultado = q3_densidad(zona_id, confianza_min)
    elif tipo_consulta == "Q4":
        resultado = q4_comparar(zona_id, zona_b, confianza_min)
    elif tipo_consulta == "Q5":
        resultado = q5_distribucion_confianza(zona_id, bins)
    else:
        return jsonify({"error": "tipo de consulta inválido"}), 400

    latencia_ms = round((time.time() - inicio) * 1000, 2)
    return jsonify({"resultado": resultado, "latencia_ms": latencia_ms})

@app.route("/zonas", methods=["GET"])
def listar_zonas():
    info = {}
    for zona_id, z in ZONAS.items():
        info[zona_id] = {
            **z,
            "edificios": len(datos_por_zona.get(zona_id, [])),
            "area_km2": round(areas_km2.get(zona_id, 0), 2)
        }
    return jsonify(info)

@app.route("/salud", methods=["GET"])
def salud():
    return jsonify({"estado": "ok", "zonas_cargadas": list(datos_por_zona.keys())})

if __name__ == "__main__":
    cargar_datos()
    app.run(host="0.0.0.0", port=8002)
