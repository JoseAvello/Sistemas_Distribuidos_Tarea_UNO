# Tarea 1 — Sistemas Distribuidos 2026-1

Sistema distribuido de caché para consultas geoespaciales sobre el dataset Google Open Buildings.

## Requisitos

- Docker y Docker Compose instalados
- El dataset debe estar en `datos/edificios.csv.gz` (Google Open Buildings)


## Consultas implementadas

- **Q1** — Conteo de edificios en una zona (con filtro de confianza mínima)
- **Q2** — Área promedio y área total de edificaciones
- **Q3** — Densidad de edificaciones por km²
- **Q4** — Comparación de densidad entre dos zonas
- **Q5** — Distribución del score de confianza en histograma


## Estructura del proyecto

```
tarea1/
├── datos/                        # Dataset CSV comprimido
│   └── edificios.csv.gz
├── generador_trafico/
│   ├── app.py                    # Genera consultas (Zipf o uniforme)
│   └── Dockerfile
├── cache_service/
│   ├── app.py                    # Intercepta consultas, usa Redis
│   └── Dockerfile
├── generador_respuestas/
│   ├── app.py                    # Procesa consultas Q1–Q5 en memoria
│   └── Dockerfile
├── metricas/
│   ├── app.py                    # Registra hits, misses, latencias
│   └── Dockerfile
├── docker-compose.yml
├── ejecutar_experimentos.sh      # Script para todos los experimentos
└── README.md
```

## Levantar el sistema base

```bash
# 1. Levantar todos los servicios (menos el generador de tráfico)
docker compose up -d redis metricas generador_respuestas cache_service

# 2. Esperar ~30 segundos a que el generador_respuestas cargue el CSV

# 3. Ver logs del generador_respuestas para confirmar carga de datos
docker logs generador_respuestas_servicio

# 4. Correr el generador de tráfico (con distribución Zipf por defecto)
docker compose run --rm generador_trafico

```

## Correr todos los experimentos automáticamente

```bash
chmod +x ejecutar_experimentos.sh
./ejecutar_experimentos.sh
```

Esto corre 8 experimentos y guarda los resultados en la carpeta `resultados/`.


# Configuracion manual de parametros --------


## Cambiar configuración del experimento

### Distribución de tráfico

```bash
# Zipf (ley de potencia — más cache hits)
docker compose run --rm -e DISTRIBUCION=zipf generador_trafico

# Uniforme (más miss rate)
docker compose run --rm -e DISTRIBUCION=uniforme generador_trafico
```

### Política de remoción y tamaño de caché

Editar `docker-compose.yml`, en el servicio `redis`, cambiar el comando:

```yaml
# LRU (Least Recently Used) — default
command: redis-server --maxmemory 50mb --maxmemory-policy allkeys-lru

# LFU (Least Frequently Used)
command: redis-server --maxmemory 50mb --maxmemory-policy allkeys-lfu

# Sin remoción (FIFO-like, Redis rechaza nuevas entradas al llenarse)
command: redis-server --maxmemory 50mb --maxmemory-policy noeviction
```

### TTL del caché

En `docker-compose.yml`, en el servicio `cache_service`:

```yaml
environment:
  - CACHE_TTL=120   # segundos (cambiar a 30 o 300 para los experimentos)
```


## Endpoints disponibles

| Servicio               | Puerto | Endpoints útiles                     |
|------------------------|--------|--------------------------------------|
| Métricas               | 8001   | GET /metricas, POST /reiniciar        |
| Generador Respuestas   | 8002   | GET /zonas, GET /salud               |
| Cache Service          | 8003   | GET /estado_cache, POST /limpiar_cache |

## Ver estado de la caché

```bash
curl http://localhost:8003/estado_cache
```

## Limpiar caché entre experimentos

```bash
curl -X POST http://localhost:8003/limpiar_cache
curl -X POST http://localhost:8001/reiniciar
```

## Bajar todo

```bash
docker compose down
```