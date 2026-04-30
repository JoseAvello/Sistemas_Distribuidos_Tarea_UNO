# Tarea 1 — Sistemas Distribuidos 2026-1

Sistema distribuido de caché para consultas geoespaciales sobre el dataset **Google Open Buildings**.

---

## Consultas implementadas

- **Q1** — Conteo de edificios por zona (con filtro de confianza)
- **Q2** — Área promedio y total
- **Q3** — Densidad de edificaciones por km²
- **Q4** — Comparación de densidad entre zonas
- **Q5** — Histograma del score de confianza

---

## Requisitos

- Docker
- Docker Compose
- Archivo de datos:
  ```
  datos/edificios.csv.gz
  ```

---

## Estructura del proyecto

```
tarea1/
├── datos/                        # Dataset CSV comprimido
│   └── edificios.csv.gz
├── generador_trafico/
│   ├── app.py                    # Genera consultas (Zipf o uniforme)
│   └── Dockerfile
├── cache_service/
│   ├── app.py                    # Intercepta consultas, usando Redis
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

---

## Levantar el sistema base

### 1. Iniciar servicios

```bash
docker compose up -d redis metricas generador_respuestas cache_service
```

### 2. Esperar carga de datos

Esperar aproximadamente **30 segundos** para que el servicio `generador_respuestas` cargue el dataset en memoria.

### 3. Verificar carga

```bash
docker logs generador_respuestas_servicio
```

---

## Ejecutar consultas (generador de tráfico)

### Distribución Zipf (por defecto)

```bash
docker compose run --rm -e DISTRIBUCION=zipf generador_trafico
```

### Distribución uniforme

```bash
docker compose run --rm -e DISTRIBUCION=uniforme generador_trafico
```

---


## Ejecutar todos los experimentos

```bash
chmod +x ejecutar_experimentos.sh
./ejecutar_experimentos.sh
```

Esto ejecuta automáticamente todos los escenarios y guarda los resultados en:

```
resultados/
```

---

## Endpoints disponibles

| Servicio             | Puerto | Endpoints útiles                  |
|---------------------|--------|----------------------------------|
| Métricas            | 8001   | GET /metricas, POST /reiniciar   |
| Generador Respuestas| 8002   | GET /zonas, GET /salud           |
| Cache Service       | 8003   | GET /estado_cache, POST /limpiar_cache |

---
