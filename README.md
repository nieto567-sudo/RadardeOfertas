# RadardeOfertas 🔥

Sistema automatizado que detecta ofertas reales, errores de precio y oportunidades de compra en tiendas online de México y publica automáticamente las mejores oportunidades en un canal de Telegram.

---

## Características

- 🕷️ **Scrapers para 21+ tiendas mexicanas**: Amazon MX, MercadoLibre, Walmart, Liverpool, Bodega Aurrerá, Costco, The Home Depot, Coppel, Elektra, Sears, Sanborns, Sam's Club, Office Depot, OfficeMax, Soriana, Cyberpuerta, DDTech, PCEL, Intercompras, Gameplanet, Claro Shop.
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
│   ├── homedepot.py         # The Home Depot Mexico
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

## Despliegue en Railway ☁️

RadardeOfertas corre en Railway como un **único servicio** (sin Redis ni Celery).  
El repo incluye `railway.toml` listo para usar: inicializa la DB y arranca el loop de publicación automáticamente.

### Variables de entorno requeridas

Configúralas en Railway → Service → Variables **antes** del primer deploy.  
El servicio arrancará con error si alguna de las dos primeras falta.

| Variable | Descripción | Obligatoria |
|---|---|---|
| `TELEGRAM_BOT_TOKEN` | Token del bot ([@BotFather](https://t.me/BotFather)) | ✅ |
| `TELEGRAM_CHANNEL_ID` | `@username` del canal público o ID numérico (`-100…`) | ✅ |
| `DATABASE_URL` | Railway lo inyecta automáticamente desde el plugin PostgreSQL | ✅ (auto) |
| `TELEGRAM_ADMIN_CHAT_ID` | Tu chat_id para alertas de admin | Opcional |
| `TELEGRAM_ADMIN_USER_IDS` | IDs de admins separados por coma | Opcional |
| `MAX_DAILY_PUBLICATIONS` | Máximo de publicaciones por día (defecto: `15`) | Opcional |
| `DRY_RUN` | `true` para modo prueba (no publica en Telegram) | Opcional |
| `LOG_FORMAT` | `json` para logs estructurados (recomendado en Railway) | Opcional |

> `DATABASE_URL` es inyectada automáticamente por el plugin PostgreSQL; **no** la añadas manualmente.  
> `REDIS_URL` **no es necesaria** en el modo loop (sin Celery).

### Paso a paso

**1. Crea el proyecto en Railway**

```bash
railway login
railway init          # en la raíz del repo clonado
```

**2. Añade PostgreSQL**

En el dashboard: **New Service → Database → PostgreSQL**.  
Railway inyecta `DATABASE_URL` automáticamente al servicio principal.

**3. Conecta el repositorio**

- **New Service → GitHub Repo → `RadardeOfertas`**.
- El `railway.toml` ya configura el build (Dockerfile) y el start command.
- En **Variables**, añade `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHANNEL_ID` y las opcionales que desees.

**4. Despliega**

```bash
railway up
# o haz click en "Deploy" en el dashboard
```

Railway construirá la imagen Docker y ejecutará:

```
python -u main.py init-db
python -u main.py run-loop --interval 300
```

### Logs esperados (servicio sano)

Al arrancar correctamente verás algo así:

```
INFO  __main__  Initialising database…
INFO  __main__  Database initialised.
INFO  __main__  run-loop starting – interval=300s, backoff_on_error=60s
INFO  __main__  run-loop heartbeat – iteration 1
INFO  __main__  Starting scrape cycle…
INFO  __main__  Scraped 42 products
INFO  __main__  Cycle complete. Offers published: 3
INFO  __main__  Sleeping 300 seconds until next cycle…
INFO  __main__  run-loop heartbeat – iteration 2
…
```

Si ves `run-loop heartbeat` el servicio está en funcionamiento. Si ves `Stopping Container` inmediatamente después de `Database initialised.`, consulta la sección de Troubleshooting.

### Notas importantes para Railway

- **`DATABASE_URL`**: Railway inyecta el formato `postgres://...`. El código lo normaliza automáticamente a `postgresql://` (requerido por SQLAlchemy).
- **Sin Redis**: el modo `run-loop` no requiere Redis. El `Procfile` y el `docker-compose.yml` incluyen entradas de Celery para uso local avanzado, pero Railway usa exclusivamente el `startCommand` de `railway.toml`.
- **Filesystem efímero**: `published_urls.json` se guarda en `/tmp` por defecto. El historial de 24 h se reinicia si el contenedor se recicla, lo que puede provocar duplicados momentáneos. Usa `PUBLISHED_URLS_FILE=/data/published_urls.json` con un volumen persistente para evitarlo.
- **Señales**: el loop responde a SIGTERM (Railway stop/redeploy) finalizando el ciclo actual antes de salir.

---

## Troubleshooting (Railway)

### El contenedor se detiene inmediatamente sin logs de `run-loop`

**Causa más común**: `TELEGRAM_BOT_TOKEN` o `TELEGRAM_CHANNEL_ID` no están configuradas.

El servicio imprimirá:

```
CRITICAL __main__  run-loop cannot start: required environment variable(s) not set: TELEGRAM_BOT_TOKEN, TELEGRAM_CHANNEL_ID.
          Set them in Railway → Service → Variables and redeploy.
```

**Solución**: añade las variables en Railway → Service → Variables → redeploy.

### El contenedor arranca pero no publica ofertas

1. Verifica que `DRY_RUN` **no** esté en `true`.
2. Revisa los logs en busca de errores de Telegram: `401 Unauthorized` (token incorrecto) o `403 Forbidden` (el bot no es admin del canal).
3. Asegúrate de que el bot tiene permisos de **Publicar mensajes** en el canal.
4. Confirma el formato de `TELEGRAM_CHANNEL_ID`: puede ser `@mi_canal` (canales públicos) o el ID numérico `-100XXXXXXXXXX` (canales privados).

### El contenedor muestra `Traceback` y se reinicia

El loop captura excepciones de ciclo individuales y reintenta automáticamente tras 60 segundos. Un traceback en los logs es informativo y **no detiene el servicio**. Solo un fallo en `init-db` o una variable faltante provocan una salida con código de error.

### Verificar que el loop está activo

Busca en los logs la línea `run-loop heartbeat – iteration N`. Si el número `N` sube con el tiempo (cada ~5 min), el servicio está corriendo correctamente.

---

## Variables de entorno

| Variable | Descripción | Valor por defecto |
|---|---|---|
| `DATABASE_URL` | URL de PostgreSQL — Railway lo inyecta automáticamente | `postgresql://radar:radar@localhost:5432/radardeofertas` |
| `REDIS_URL` | URL de Redis — Railway lo inyecta automáticamente | `redis://localhost:6379/0` |
| `TELEGRAM_BOT_TOKEN` | Token del bot ([@BotFather](https://t.me/BotFather)) | — |
| `TELEGRAM_CHANNEL_ID` | `@username` del canal público | — |
| `TELEGRAM_ADMIN_CHAT_ID` | Tu chat_id para alertas de admin | — |
| `TELEGRAM_ADMIN_USER_IDS` | IDs con permisos de admin (separados por coma) | — |
| `ALLOWED_CATEGORIES` | Categorías permitidas (separadas por coma) | 5 categorías por defecto |
| `MAX_DAILY_PUBLICATIONS` | Máximo de publicaciones por día | `15` |
| `MAX_PUBLICATIONS_PER_HOUR` | Máximo de publicaciones por hora | `15` |
| `MIN_SECONDS_BETWEEN_PUBLICATIONS` | Segundos mínimos entre publicaciones | `5` |
| `DRY_RUN` | Modo prueba (no publica en Telegram) | `false` |
| `PUBLISHED_URLS_FILE` | Archivo JSON para deduplicación 24h | `/tmp/published_urls.json` |
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

Los scrapers reintentan automáticamente hasta 3 veces con backoff exponencial + jitter aleatorio, **pero solo para errores transitorios** (429, 500, 502, 503, 504 y errores de red/timeout).

Los errores HTTP permanentes del lado del cliente **no se reintentan**:
- `400 Bad Request`, `401 Unauthorized`, `403 Forbidden`, `404 Not Found`

Esto evita desperdiciar tiempo y peticiones cuando una URL está mal configurada (p. ej. endpoint incorrecto → 404).

#### Circuit breaker por tienda

Si una tienda falla N veces consecutivas, su scraper se pausa automáticamente por un período de enfriamiento.

| Variable | Descripción | Valor por defecto |
|---|---|---|
| `CIRCUIT_BREAKER_FAILURE_THRESHOLD` | Fallos consecutivos antes de abrir el circuito | `5` |
| `CIRCUIT_BREAKER_COOLDOWN_SECONDS` | Segundos de pausa antes del siguiente intento | `300` |

---

### URLs de búsqueda por tienda

Cada scraper construye la URL de búsqueda a partir de un `query` (keyword). La tabla siguiente documenta el patrón de URL que usa cada tienda y el formato resultante para `query = "celulares"`:

| Tienda | Patrón de URL | Ejemplo con "celulares" |
|---|---|---|
| **Liverpool** | `https://www.liverpool.com.mx/tienda?s=<query>` | `https://www.liverpool.com.mx/tienda?s=celulares` |
| **Amazon MX** | `https://www.amazon.com.mx/s?k=<query>` | `https://www.amazon.com.mx/s?k=celulares` |
| **Walmart** | `https://www.walmart.com.mx/search?q=<query>` | `https://www.walmart.com.mx/search?q=celulares` |
| **Bodega Aurrerá** | `https://www.bodegaaurrera.com.mx/search?q=<query>` | `https://www.bodegaaurrera.com.mx/search?q=celulares` |
| **Costco** | `https://www.costco.com.mx/search?searchOption=mx-search-all&text=<query>` | `https://www.costco.com.mx/search?searchOption=mx-search-all&text=celulares` |
| **MercadoLibre** | API: `https://api.mercadolibre.com/sites/MLM/search?q=<query>` | `https://api.mercadolibre.com/sites/MLM/search?q=celulares` |
| **The Home Depot** | `https://www.homedepot.com.mx/s/<query>` (query en el path) | `https://www.homedepot.com.mx/s/celulares` |

> **Nota sobre Walmart y Bodega Aurrerá**: ambas plataformas también exponen URLs de navegación por departamento (`/browse/…`) que contienen IDs de categoría fijos. Esas URLs no son generalizables para búsquedas por keyword; los scrapers utilizan la búsqueda por texto como estrategia general.

> **Nota sobre Amazon MX**: Amazon bloquea activamente IPs de datacenter (Railway/cloud) con 503. Si experimentas bloqueos, considera añadir proxies residenciales (`HTTP_PROXY` / `HTTPS_PROXY`) o reducir la frecuencia de peticiones.

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
