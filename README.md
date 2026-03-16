# RadardeOfertas 🔥

Sistema automatizado que detecta ofertas reales, errores de precio y oportunidades de compra en tiendas online de México y publica automáticamente las mejores oportunidades en un canal de Telegram.

---

## Características

- 🕷️ **Scrapers para 25+ tiendas**: Amazon MX, MercadoLibre, Walmart, Liverpool, Bodega Aurrerá, Costco, Coppel, Elektra, Sears, Sanborns, Sam's Club, Office Depot, OfficeMax, Soriana, Cyberpuerta, DDTech, PCEL, Intercompras, Gameplanet, Claro Shop, AliExpress, eBay, Newegg, Banggood, Gearbest.
- 📊 **Análisis histórico de precios** con PostgreSQL.
- ⚡ **Detección de caída rápida de precio** (configurable).
- 🎯 **Motor de scoring de ofertas** (0–100 pts).
- 🔗 **Generación automática de enlaces de afiliado** (Amazon, MercadoLibre, AliExpress, eBay).
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
│   ├── international.py     # AliExpress, eBay, Newegg, Banggood, Gearbest
│   └── manager.py           # ScraperManager – orquesta todos los scrapers
├── services/
│   ├── price_analyzer.py    # Análisis de precios + detección de caída rápida
│   ├── offer_scorer.py      # Scoring de ofertas (0–100)
│   ├── affiliate.py         # Conversión de URLs a enlaces de afiliado
│   └── offer_processor.py   # Pipeline completo: analizar → puntuar → generar enlace
├── workers/
│   ├── celery_app.py        # Instancia de Celery
│   ├── tasks.py             # Tareas Celery por tienda
│   └── scheduler.py         # Beat schedule (frecuencias por tienda)
├── telegram/
│   ├── publisher.py         # Envía mensajes/fotos al canal de Telegram
│   └── bot.py               # Bot con comandos /start y /status
├── tests/
│   └── test_radar.py        # 42 tests unitarios
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

## Variables de entorno

| Variable | Descripción | Valor por defecto |
|---|---|---|
| `DATABASE_URL` | URL de PostgreSQL | `postgresql://radar:radar@localhost:5432/radardeofertas` |
| `REDIS_URL` | URL de Redis | `redis://localhost:6379/0` |
| `TELEGRAM_BOT_TOKEN` | Token del bot de Telegram | — |
| `TELEGRAM_CHANNEL_ID` | ID o @username del canal | — |
| `AMAZON_AFFILIATE_TAG` | Tag de Amazon Associates | — |
| `MERCADOLIBRE_AFFILIATE_ID` | ID de afiliado de MercadoLibre | — |
| `ALIEXPRESS_AFFILIATE_KEY` | Key de AliExpress Portals | — |
| `EBAY_CAMPAIGN_ID` | Campaign ID de eBay Partner Network | — |
| `MIN_PUBLISH_SCORE` | Score mínimo para publicar (0–100) | `60` |
| `RAPID_DROP_THRESHOLD` | Caída mínima para alertar (0–1) | `0.30` |
| `RAPID_DROP_WINDOW_HOURS` | Ventana de tiempo para caída rápida | `2` |

---

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
| Resto de tiendas | Cada 15 min |

---

## Tests

```bash
pip install pytest
pytest tests/ -v
```

42 tests unitarios que cubren: limpieza de precios, clasificación de ofertas, scoring, generación de enlaces de afiliado, scraper manager y formateo de mensajes de Telegram.

---

## Licencia

MIT