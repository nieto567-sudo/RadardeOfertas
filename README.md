# RadardeOfertas 🔥

Sistema automatizado que detecta ofertas reales, errores de precio y oportunidades de compra en tiendas online de México y publica automáticamente las mejores oportunidades en un canal de Telegram.

---

## Características

- 🕷️ **Scrapers para 20+ tiendas mexicanas**: Amazon MX, MercadoLibre, Walmart, Liverpool, Bodega Aurrerá, Costco, Coppel, Elektra, Sears, Sanborns, Sam's Club, Office Depot, OfficeMax, Soriana, Cyberpuerta, DDTech, PCEL, Intercompras, Gameplanet, Claro Shop.
- 📊 **Análisis histórico de precios** con PostgreSQL.
- ⚡ **Detección de caída rápida de precio** (configurable).
- 🎯 **Motor de scoring de ofertas** (0–100 pts).
- 🔗 **Generación de enlaces de oferta** con modo directo (por defecto) o de afiliado (activable con `MONETIZED_LINKS_ENABLED=true`).
- 📣 **Publicación automática en Telegram** con imagen, precio anterior/actual y enlace de afiliado.
- ⚙️ **Workers Celery** con programación por tienda.
- 🐳 **Docker Compose** para levantar todo con un solo comando.

---

## Estructura del proyecto

```
RadardeOfertas/
├── config/
│   └── settings.py          # Configuración desde variables de entorno
├── database/
│   ├── connection.py        # Engine y SessionLocal de SQLAlchemy
│   └── models.py            # Modelos ORM: Product, PriceHistory, Offer, Publication
├── scrapers/
│   ├── base.py              # BaseScraper + ProductData
│   ├── amazon.py            # Amazon Mexico
│   ├── mercadolibre.py      # MercadoLibre (API pública)
│   ├── walmart.py           # Walmart Mexico
│   ├── liverpool.py         # Liverpool Mexico
│   ├── bodega_aurrera.py    # Bodega Aurrerá
│   ├── retailers_mx.py      # Costco, Coppel, Elektra, Sears, Sanborns, Sam's, OD, OM, Soriana
│   ├── tech_stores.py       # Cyberpuerta, DDTech, PCEL, Intercompras, Gameplanet, ClaroShop
│   └── manager.py           # ScraperManager – orquesta todos los scrapers
├── services/
│   ├── price_analyzer.py    # Análisis de precios + detección de caída rápida
│   ├── offer_scorer.py      # Scoring de ofertas (0–100)
│   ├── affiliate.py         # Conversión de URLs a enlaces de afiliado
│   ├── link_builder.py      # build_offer_link: modo directo vs. monetizado
│   └── offer_processor.py   # Pipeline completo: analizar → puntuar → generar enlace
├── workers/
│   ├── celery_app.py        # Instancia de Celery
│   ├── tasks.py             # Tareas Celery por tienda
│   └── scheduler.py         # Beat schedule (frecuencias por tienda)
├── telegram/
│   ├── publisher.py         # Envía mensajes/fotos al canal de Telegram
│   └── bot.py               # Bot con comandos /start y /status
├── tests/
│   └── test_radar.py        # 157 tests unitarios
├── main.py                  # CLI: init-db | run-once | run-loop
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
└── .env.example
```

---

## Inicio rápido

### 1. Clonar y configurar

```bash
git clone https://github.com/nieto567-sudo/RadardeOfertas.git
cd RadardeOfertas
cp .env.example .env
# Edita .env con tus tokens y configuración
```

### 2. Levantar con Docker Compose

```bash
docker-compose up --build
```

Esto levanta PostgreSQL, Redis, el worker Celery y el beat scheduler.

### 3. Inicializar la base de datos manualmente (sin Docker)

```bash
pip install -r requirements.txt
python main.py init-db
```

### 4. Ejecutar un ciclo de scraping

```bash
python main.py run-once
```

### 5. Ejecutar en bucle continuo

```bash
python main.py run-loop --interval 300
```

### 6. Iniciar workers Celery

```bash
# Worker
celery -A workers.celery_app worker --loglevel=info

# Beat scheduler (en otra terminal)
celery -A workers.celery_app beat --loglevel=info
```

---

## Arranque en producción (paso a paso)

### ✅ Checklist previo: configurar el bot en Telegram

Antes de arrancar, asegúrate de completar los siguientes pasos en Telegram:

1. **Crea un bot** hablando con [@BotFather](https://t.me/BotFather) → `/newbot` → copia el token.
2. **Crea un canal público** (Nuevo Canal → Público) y elige un `@username` (ej. `@mis_ofertas_mx`).
3. **Agrega el bot como ADMIN del canal**:
   - Abre el canal → Administradores → Agregar administrador → busca tu bot → confirma.
   - Permisos mínimos requeridos: ✅ **Publicar mensajes** y ✅ **Publicar fotos** (o "Publicar contenido").
4. **Obtén tu chat_id personal** hablando con [@userinfobot](https://t.me/userinfobot) → úsalo en `TELEGRAM_ADMIN_CHAT_ID` y `TELEGRAM_ADMIN_USER_IDS`.
5. **Rellena `.env`** con el token, el `@username` del canal y tu chat_id.

### Pasos de arranque

```bash
# 1. Construir imágenes e iniciar PostgreSQL y Redis
docker-compose up --build -d db redis

# 2. Inicializar el esquema de la base de datos
docker-compose run --rm app python main.py init-db

# 3. Verificar que todos los servicios están sanos
docker-compose run --rm app python main.py healthcheck

# 4. Ejecutar un ciclo de prueba (DRY_RUN=true en .env para no publicar aún)
docker-compose run --rm app python main.py run-once

# 5. Levantar el worker de Celery y el beat scheduler en producción
docker-compose up -d worker beat
```

> 💡 **Tip**: activa `DRY_RUN=true` en `.env` para el paso 4 y revisa los logs antes de publicar en el canal real.  Una vez confirmado, cambia a `DRY_RUN=false` y reinicia con `docker-compose restart worker beat`.

---

## Variables de entorno

| Variable | Descripción | Valor por defecto |
|---|---|---|
| `DATABASE_URL` | URL de PostgreSQL (`db` = servicio docker-compose) | `postgresql://radar:radar@db:5432/radardeofertas` |
| `REDIS_URL` | URL de Redis (`redis` = servicio docker-compose) | `redis://redis:6379/0` |
| `TELEGRAM_BOT_TOKEN` | Token del bot ([@BotFather](https://t.me/BotFather)) | — |
| `TELEGRAM_CHANNEL_ID` | `@username` del canal público | — |
| `TELEGRAM_ADMIN_CHAT_ID` | Tu chat_id para alertas de admin | — |
| `TELEGRAM_ADMIN_USER_IDS` | IDs con permisos de admin (separados por coma) | — |
| `ALLOWED_CATEGORIES` | Categorías permitidas (separadas por coma) | 5 categorías por defecto |
| `MAX_DAILY_PUBLICATIONS` | Máximo de publicaciones por día | `15` |
| `MAX_PUBLICATIONS_PER_HOUR` | Máximo de publicaciones por hora | `15` |
| `MIN_SECONDS_BETWEEN_PUBLICATIONS` | Segundos mínimos entre publicaciones | `5` |
| `DRY_RUN` | Modo prueba (no publica en Telegram) | `false` |
| `PUBLISHED_URLS_FILE` | Archivo JSON para deduplicación 24h | `published_urls.json` |
| `MONETIZED_LINKS_ENABLED` | Activar links de afiliado/UTM | `false` |
| `MIN_PUBLISH_SCORE` | Score mínimo para publicar (0–100) | `60` |
| `RAPID_DROP_THRESHOLD` | Caída mínima para alertar (0–1) | `0.30` |
| `RAPID_DROP_WINDOW_HOURS` | Ventana de tiempo para caída rápida | `2` |
| `MIN_DISCOUNT_PCT` | Descuento mínimo requerido (%) | `20.0` |
| `MIN_ABSOLUTE_SAVING_MXN` | Ahorro mínimo en MXN | `100.0` |
| `PUBLICATION_COOLDOWN_HOURS` | Horas mínimas entre re-publicaciones del mismo producto | `6` |
| `PRICE_ERROR_NOTIFY_ADMIN` | DM al admin antes de publicar errores de precio | `true` |
| `LOG_FORMAT` | Formato de logs: `text` o `json` | `text` |
| `LOG_LEVEL` | Nivel de logging | `INFO` |
| `PROMETHEUS_PORT` | Puerto del servidor de métricas | `9090` |
| `CIRCUIT_BREAKER_FAILURE_THRESHOLD` | Fallos antes de abrir el circuit breaker | `5` |
| `CIRCUIT_BREAKER_COOLDOWN_SECONDS` | Segundos de enfriamiento del circuit breaker | `300` |



## Lógica de detección de ofertas

| Condición | Tipo | Score estimado |
|---|---|---|
| Precio actual < 40% del promedio histórico | 🚨 Error de precio | 95–100 |
| Precio actual < 60% del promedio histórico | 🔥 Oferta excelente | 80–94 |
| Precio actual < 80% del promedio histórico | ✅ Buena oferta | 60–79 |

### Componentes del score (0–100 pts)

- **Descuento** (hasta 60 pts): proporcional al % de descuento.
- **Historial** (hasta 20 pts): más observaciones históricas → más confiable.
- **Caída rápida** (+10 pts): bono si el precio cayó ≥30% en las últimas 2 horas.
- **Popularidad** (hasta 10 pts): basada en el número de observaciones del producto.

---

## Formato del mensaje de Telegram

```
🔥 OFERTA EXCELENTE

*Xbox Series X*

💰 Antes: $12,999
🔥 Ahora: $3,499
📉 Descuento: 73%

🏬 Tienda: Walmart
⭐ Score: 85/100 (oferta excelente)

🛒 Comprar aquí
```

---

## Frecuencias de scraping (Celery Beat)

| Tienda | Intervalo |
|---|---|
| Amazon, MercadoLibre | Cada 5 min |
| Walmart, Liverpool, Bodega Aurrerá | Cada 10 min |
| Resto de tiendas mexicanas | Cada 15 min |

---

## Modo de links: directo vs. monetizado

### Links directos (por defecto)

Por defecto el bot publica el link canónico de la oferta **sin ningún tipo de modificación**: sin tags de afiliado, sin parámetros UTM y sin acortamiento de URLs. Esto no requiere configurar ninguna API de monetización.

```env
MONETIZED_LINKS_ENABLED=false   # valor por defecto; no es necesario incluirlo
```

### Activar monetización en el futuro

Cuando quieras empezar a generar comisiones, basta con cambiar **una variable** en tu `.env` y añadir la lógica del programa de afiliado en `services/affiliate.py`:

```env
MONETIZED_LINKS_ENABLED=true
```

El flag `MONETIZED_LINKS_ENABLED=true` activa automáticamente la ruta `build_monetized_link` en `services/link_builder.py`.  Implementa el programa de afiliado que quieras usar en `services/affiliate.py` y el bot comenzará a usarlo sin más cambios de código.

---

## Tests

```bash
pip install pytest
pytest tests/ -v
```

262 tests unitarios que cubren: limpieza de precios, clasificación de ofertas, scoring, generación de enlaces, scraper manager, filtro de publicación (category whitelist, dedup, rate limiting, dry-run), formateo de mensajes de Telegram, tendencia de precio, salud de scrapers, suscripciones, resumen diario, horas inteligentes de publicación, detector viral, detector de reventa, filtro de calidad, clasificador de productos, seguimiento de clics/compras y límite diario de publicaciones.

---

## Licencia

MIT
---

## Nuevas funcionalidades (Super Bot)

### Observabilidad

#### Logging estructurado

Configura el formato y nivel de log mediante variables de entorno:

```bash
LOG_FORMAT=json   # "json" para log en JSON (ideal para log aggregators), "text" para consola
LOG_LEVEL=INFO    # DEBUG, INFO, WARNING, ERROR, CRITICAL
```

#### Métricas Prometheus

Inicia el servidor de métricas con `--metrics`:

```bash
python main.py run-loop --metrics
```

Accede a las métricas en `http://localhost:9090/metrics`. Métricas disponibles:

| Métrica | Tipo | Descripción |
|---|---|---|
| `radar_scrape_products_total` | Counter | Productos scrapeados por tienda |
| `radar_scrape_errors_total` | Counter | Errores de scraping por tienda |
| `radar_offers_processed_total` | Counter | Ofertas procesadas (por resultado: `published`, `discarded`, `error`) |
| `radar_scrape_duration_seconds` | Histogram | Latencia de scraping por tienda |
| `radar_cycle_duration_seconds` | Histogram | Latencia total del ciclo `run_once` |

Configura el puerto con `PROMETHEUS_PORT` (default: `9090`).

#### Healthcheck

```bash
python main.py healthcheck
```

Verifica PostgreSQL, Redis, Telegram API y estado de los circuit breakers. Retorna código de salida 0 si todo está sano, 1 si hay problemas.

---

### Resiliencia de scrapers

#### Reintentos con backoff + jitter

Todos los scrapers reintentan automáticamente las peticiones HTTP hasta 3 veces con backoff exponencial + jitter aleatorio.

#### Circuit breaker por tienda

Si una tienda falla N veces consecutivas, su scraper se pausa automáticamente por un período de enfriamiento.

| Variable | Descripción | Valor por defecto |
|---|---|---|
| `CIRCUIT_BREAKER_FAILURE_THRESHOLD` | Fallos consecutivos antes de abrir el circuito | `5` |
| `CIRCUIT_BREAKER_COOLDOWN_SECONDS` | Segundos de pausa antes del siguiente intento | `300` |

---

### Anti-spam y deduplicación mejorada

Cada producto recibe una huella digital (SHA-256) basada en su título normalizado.

| Variable | Descripción | Valor por defecto |
|---|---|---|
| `DEDUP_CROSS_STORE` | Deduplicar el mismo producto entre distintas tiendas | `false` |
| `REQUIRE_IMAGE` | Rechazar productos sin imagen | `false` |
| `MIN_TITLE_LENGTH` | Longitud mínima del título del producto | `10` |

---

### Nuevas variables de entorno

| Variable | Descripción | Valor por defecto |
|---|---|---|
| `TELEGRAM_ADMIN_USER_IDS` | IDs de Telegram con permisos de admin (separados por coma) | — |
| `LOG_FORMAT` | Formato de logs: `text` o `json` | `text` |
| `LOG_LEVEL` | Nivel de logging | `INFO` |
| `PROMETHEUS_PORT` | Puerto del servidor de métricas Prometheus | `9090` |
| `CIRCUIT_BREAKER_FAILURE_THRESHOLD` | Fallos antes de abrir el circuit breaker | `5` |
| `CIRCUIT_BREAKER_COOLDOWN_SECONDS` | Segundos de enfriamiento del circuit breaker | `300` |
| `DEDUP_CROSS_STORE` | Deduplicar cross-store | `false` |
| `REQUIRE_IMAGE` | Requerir imagen para publicar | `false` |
| `MIN_TITLE_LENGTH` | Longitud mínima del título | `10` |
| `PRICE_ERROR_NOTIFY_ADMIN` | Enviar notificación privada al admin antes de publicar errores de precio | `true` |

---

### Notificación de errores de precio al admin

Cuando el bot detecta un **error de precio** (oferta con score ≥ 95, precio < `PRICE_ERROR_THRESHOLD` × precio histórico, por defecto < 40%), **envía primero un mensaje privado al admin** (`TELEGRAM_ADMIN_CHAT_ID`) con todos los detalles antes de publicarlo en el canal.

**Flujo:**
1. 🤖 Bot detecta error de precio
2. 📩 Admin recibe DM privado con: producto, precio habitual, precio error, ahorro y enlace directo
3. 📢 El bot publica automáticamente en el canal de Telegram

**Configuración necesaria:**
```
TELEGRAM_ADMIN_CHAT_ID=tu_chat_id   # Obtén tu chat_id hablando con @userinfobot
PRICE_ERROR_NOTIFY_ADMIN=true       # true (default) = activado, false = desactivado
```

> 💡 Si la notificación al admin falla (ej. error de red), el bot **igual publica** en el canal sin interrupciones.

---

### Comandos admin de Telegram

Restringidos a usuarios en `TELEGRAM_ADMIN_USER_IDS`:

| Comando | Descripción |
|---|---|
| `/pause <store>` | Pausar scraping para una tienda |
| `/resume <store>` | Reanudar una tienda pausada |
| `/stats` | Estadísticas de las últimas 24 h |
| `/errors` | Top errores recientes de scrapers |
| `/health` | Resumen del healthcheck |
| `/config` | Valores de configuración (no sensibles) |

---

### CI/CD

Pipeline de GitHub Actions (`.github/workflows/ci.yml`):

- **Lint**: `ruff check` en cada push/PR
- **Tests**: `pytest tests/ -v` con Python 3.11
- **Docker Build**: verifica que el `Dockerfile` compile correctamente

---

## Runbook

### DB caída (PostgreSQL)

1. Verifica el contenedor: `docker-compose ps db`
2. Revisa logs: `docker-compose logs db`
3. Reinicia: `docker-compose restart db`
4. Si persiste, revisa disco lleno: `df -h`
5. El bot seguirá en ejecución pero sin guardar ofertas hasta que la DB vuelva

### Redis caído

1. `docker-compose restart redis`
2. Los circuit breakers volverán al estado "closed" (se usan contadores en memoria como fallback)
3. Las tareas Celery pendientes se perderán; se reanudarán en el siguiente ciclo

### Telegram 429 (Too Many Requests)

1. El publisher incluye manejo de `retry_after` automático
2. Reduce `MAX_DAILY_PUBLICATIONS` temporalmente
3. Espera el tiempo indicado por Telegram (usualmente < 1 min)

### Scraper caído / bloqueado

1. Desde Telegram: `/errors` para ver qué store está fallando
2. Verificar si el sitio está bloqueando: prueba la URL manualmente
3. Si está bloqueado: `/pause <store>` para pausar temporalmente
4. Cuando el sitio vuelva: `/resume <store>`
5. El circuit breaker se abrirá automáticamente después de `CIRCUIT_BREAKER_FAILURE_THRESHOLD` fallos

### Cómo ajustar umbrales

- Bajar score mínimo (más ofertas, menor calidad): `MIN_PUBLISH_SCORE=50`
- Subir descuento mínimo (solo grandes descuentos): `MIN_DISCOUNT_PCT=30`
- Cambiar cooldown (tiempo entre re-publicaciones del mismo producto): `PUBLICATION_COOLDOWN_HOURS=12`
- Cambiar cap diario: `MAX_DAILY_PUBLICATIONS=20`
