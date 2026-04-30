#!/bin/bash
# ejecutar_experimentos.sh
# Corre todos los experimentos necesarios para el informe:
# - Distribuciones: zipf vs uniforme
# - Políticas: lru, lfu, noeviction (simula FIFO)
# - Tamaños de caché: 50mb, 200mb, 500mb

set -e

CONSULTAS=500
TASA=10

echo "========================================"
echo "  EXPERIMENTOS DE CACHÉ - TAREA 1"
echo "========================================"

# Función para correr un experimento
correr_experimento() {
    local nombre=$1
    local politica=$2
    local tamano=$3
    local distribucion=$4
    local ttl=$5

    echo ""
    echo "--- Experimento: $nombre ---"
    echo "Política: $politica | Tamaño: $tamano | Distribución: $distribucion | TTL: $ttl"

    # Bajar servicios anteriores
    docker compose down --remove-orphans 2>/dev/null || true

    # Levantar con la configuración del experimento
    REDIS_MAXMEMORY=$tamano \
    REDIS_POLICY=$politica \
    CACHE_TTL=$ttl \
    DISTRIBUCION=$distribucion \
    TOTAL_CONSULTAS=$CONSULTAS \
    CONSULTAS_POR_SEGUNDO=$TASA \
    docker compose up -d redis metricas generador_respuestas cache_service

    echo "Esperando que los servicios estén listos (30s)..."
    sleep 30

    # Correr generador de tráfico
    DISTRIBUCION=$distribucion \
    TOTAL_CONSULTAS=$CONSULTAS \
    CONSULTAS_POR_SEGUNDO=$TASA \
    docker compose run --rm \
        -e DISTRIBUCION=$distribucion \
        -e TOTAL_CONSULTAS=$CONSULTAS \
        -e CONSULTAS_POR_SEGUNDO=$TASA \
        generador_trafico

    # Guardar métricas
    mkdir -p resultados
    curl -s http://localhost:8001/metricas > resultados/${nombre}.json
    echo "Resultado guardado en resultados/${nombre}.json"
    cat resultados/${nombre}.json

    docker compose down
    sleep 5
}

# Crear docker-compose con variables de entorno configurables
cat > docker-compose.override.yml << 'EOF'
version: "3.8"
services:
  redis:
    command: redis-server --maxmemory ${REDIS_MAXMEMORY:-50mb} --maxmemory-policy ${REDIS_POLICY:-allkeys-lru}
  cache_service:
    environment:
      - CACHE_TTL=${CACHE_TTL:-120}
EOF

# === EXPERIMENTO 1: Distribuciones de tráfico (LRU, 50mb) ===
correr_experimento "zipf_lru_50mb_ttl120"     "allkeys-lru"    "50mb"  "zipf"     120
correr_experimento "uniforme_lru_50mb_ttl120"  "allkeys-lru"    "50mb"  "uniforme" 120

# === EXPERIMENTO 2: Políticas de remoción (Zipf, 50mb) ===
correr_experimento "zipf_lfu_50mb_ttl120"      "allkeys-lfu"    "50mb"  "zipf"     120
correr_experimento "zipf_noeviction_50mb_ttl120" "noeviction"   "50mb"  "zipf"     120

# === EXPERIMENTO 3: Tamaños de caché (Zipf, LRU) ===
correr_experimento "zipf_lru_200mb_ttl120"    "allkeys-lru"    "200mb" "zipf"     120
correr_experimento "zipf_lru_500mb_ttl120"    "allkeys-lru"    "500mb" "zipf"     120

# === EXPERIMENTO 4: Efecto del TTL ===
correr_experimento "zipf_lru_50mb_ttl30"      "allkeys-lru"    "50mb"  "zipf"     30
correr_experimento "zipf_lru_50mb_ttl300"     "allkeys-lru"    "50mb"  "zipf"     300

echo ""
echo "========================================"
echo "Todos los experimentos completados."
echo "Resultados en la carpeta: resultados/"
echo "========================================"

# Mostrar resumen
echo ""
echo "=== RESUMEN ==="
for archivo in resultados/*.json; do
    nombre=$(basename $archivo .json)
    hit_rate=$(cat $archivo | python3 -c "import sys,json; d=json.load(sys.stdin); print(f'{d[\"hit_rate\"]*100:.1f}%')")
    echo "$nombre -> hit_rate: $hit_rate"
done
