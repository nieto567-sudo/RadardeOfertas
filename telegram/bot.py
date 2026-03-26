"""
Telegram bot entry point.

Starts a simple polling bot that responds to:
  /start        – welcome message
  /status       – system stats (products, offers)
  /ingresos     – estimated affiliate revenue summary
  /comisiones   – commission rate table per store
  /ranking      – top offers right now ranked by score + viral potential
  /estadisticas – click/purchase analytics
  /ahorro       – community total savings (social proof)
  /buscar       – search active deals for a keyword (/buscar iphone)
  /categorias   – deal count per category
  /seguir       – subscribe to keyword alerts  (/seguir iphone)
  /dejar        – unsubscribe from keyword      (/dejar iphone)
  /mis_alertas  – list all active subscriptions

Admin-only commands (restricted to TELEGRAM_ADMIN_USER_IDS):
  /pause <store>  – pause scraping for a store
  /resume <store> – resume a paused store
  /stats          – last 24 h stats (scraped, published, errors)
  /errors         – top recent scraper errors
  /health         – healthcheck summary
  /config         – show current non-sensitive config values
"""
from __future__ import annotations

import logging

from config import settings

logger = logging.getLogger(__name__)


def _is_admin(user_id: int) -> bool:
    """Return True if *user_id* is in TELEGRAM_ADMIN_USER_IDS."""
    return user_id in settings.TELEGRAM_ADMIN_USER_IDS


def run_bot() -> None:  # pragma: no cover
    """Start the Telegram bot in polling mode."""
    try:
        from telegram import Update  # type: ignore
        from telegram.ext import (  # type: ignore
            Application,
            CommandHandler,
            ContextTypes,
        )
    except ImportError:
        logger.error(
            "python-telegram-bot is not installed. "
            "Install it with: pip install python-telegram-bot"
        )
        return

    async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        await update.message.reply_text(
            "👋 Bienvenido a *RadardeOfertas*\\!\n\n"
            "Detectamos y publicamos automáticamente las *mejores ofertas* de "
            "tiendas de México y el mundo — ¡solo lo que realmente vale la pena\\!\n\n"
            "📌 *Comandos disponibles:*\n"
            "/status – estadísticas del sistema\n"
            "/ranking – top ofertas últimas 24 h\n"
            "/buscar \\<producto\\> – buscar ofertas activas\n"
            "/ahorro – ahorro total de la comunidad\n"
            "/estadisticas – clics, compras y análisis\n"
            "/categorias – ofertas por categoría\n"
            "/ingresos – resumen de ingresos estimados\n"
            "/comisiones – tasas de comisión por tienda\n"
            "/seguir \\<palabra\\> – alerta personalizada de oferta\n"
            "/dejar \\<palabra\\> – cancelar una alerta\n"
            "/mis\\_alertas – ver tus alertas activas\n\n"
            "💡 _Tip: Usa /seguir iphone para recibir alertas cada vez que aparezca una oferta de iphone_",
            parse_mode="MarkdownV2",
        )

    async def status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        from database.connection import SessionLocal
        from database.models import Offer, Product

        db = SessionLocal()
        try:
            total_products = db.query(Product).count()
            total_offers = db.query(Offer).count()
            await update.message.reply_text(
                f"📊 *Estado del sistema*\n\n"
                f"🛍️ Productos monitoreados: {total_products:,}\n"
                f"🎯 Ofertas detectadas: {total_offers:,}",
                parse_mode="Markdown",
                disable_web_page_preview=True,
            )
        finally:
            db.close()

    async def ingresos(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Show estimated affiliate revenue summary for the last 30 days."""
        from database.connection import SessionLocal
        from services.revenue_tracker import get_revenue_summary

        db = SessionLocal()
        try:
            summary = get_revenue_summary(db, days=30)
            total = summary["total_estimated_mxn"]
            count = summary["offers_published"]
            avg = summary["avg_per_offer_mxn"]
            by_network = summary["by_network"]
            by_store = summary["by_store"]

            network_lines = "\n".join(
                f"  • {net.replace('_', ' ').title()}: ${v:,.2f}"
                for net, v in by_network.items()
            ) or "  (sin datos)"

            store_lines = "\n".join(
                f"  • {s.replace('_', ' ').title()}: ${v:,.2f}"
                for s, v in by_store.items()
            ) or "  (sin datos)"

            text = (
                "💰 *Ingresos estimados — últimos 30 días*\n\n"
                f"📈 *Total estimado:* ${total:,.2f} MXN\n"
                f"🎯 *Ofertas publicadas:* {count:,}\n"
                f"📊 *Promedio por oferta:* ${avg:,.2f} MXN\n\n"
                f"🏦 *Por red de afiliados:*\n{network_lines}\n\n"
                f"🏬 *Top tiendas:*\n{store_lines}\n\n"
                "⚠️ _Estos valores son estimaciones basadas en tasas promedio de "
                "conversión de la industria. Los ingresos reales dependen de tu "
                "tasa de conversión y las ventas confirmadas en cada dashboard de "
                "afiliados._"
            )
            await update.message.reply_text(text, parse_mode="Markdown",
                                            disable_web_page_preview=True)
        finally:
            db.close()

    async def comisiones(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Show commission rate table for all supported stores."""
        from services.revenue_tracker import get_commission_rates_text

        text = get_commission_rates_text()
        text += (
            "\n\n"
            "📝 *Cómo activar cada red:*\n"
            "• *Amazon Associates* → [associates.amazon.com.mx](https://associates.amazon.com.mx)\n"
            "• *MercadoLibre Afiliados* → [afiliados.mercadolibre.com](https://afiliados.mercadolibre.com)\n"
            "• *AliExpress Portals* → [portals.aliexpress.com](https://portals.aliexpress.com)\n"
            "• *eBay Partner Network* → [partnernetwork.ebay.com](https://partnernetwork.ebay.com)\n"
            "• *Admitad (Walmart, Liverpool, etc.)* → [admitad.com](https://www.admitad.com/en/publisher/)\n"
            "• *Bitly (rastreo de clics)* → [bitly.com](https://bitly.com)"
        )
        await update.message.reply_text(text, parse_mode="Markdown",
                                        disable_web_page_preview=True)

    async def seguir(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Subscribe to keyword alerts: /seguir <keyword>"""
        from database.connection import SessionLocal
        from services.subscription_service import add_subscription

        if not context.args:
            await update.message.reply_text(
                "Uso: /seguir <palabra>\n"
                "Ejemplo: /seguir iphone\n\n"
                "Recibirás una alerta cada vez que aparezca esa oferta.",
                disable_web_page_preview=True,
            )
            return

        keyword = " ".join(context.args).strip().lower()
        chat_id = update.effective_chat.id

        db = SessionLocal()
        try:
            add_subscription(db, chat_id, keyword)
            db.commit()
            await update.message.reply_text(
                f"✅ Ahora recibirás alertas para *{keyword}*\\.",
                parse_mode="MarkdownV2",
            )
        finally:
            db.close()

    async def dejar(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Unsubscribe from keyword: /dejar <keyword>"""
        from database.connection import SessionLocal
        from services.subscription_service import remove_subscription

        if not context.args:
            await update.message.reply_text("Uso: /dejar <palabra>")
            return

        keyword = " ".join(context.args).strip().lower()
        chat_id = update.effective_chat.id

        db = SessionLocal()
        try:
            removed = remove_subscription(db, chat_id, keyword)
            db.commit()
            if removed:
                await update.message.reply_text(
                    f"🗑 Alerta para *{keyword}* cancelada\\.",
                    parse_mode="MarkdownV2",
                )
            else:
                await update.message.reply_text(
                    f"No tienes ninguna alerta activa para *{keyword}*\\.",
                    parse_mode="MarkdownV2",
                )
        finally:
            db.close()

    async def mis_alertas(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """List active subscriptions: /mis_alertas"""
        from database.connection import SessionLocal
        from services.subscription_service import list_subscriptions

        chat_id = update.effective_chat.id
        db = SessionLocal()
        try:
            subs = list_subscriptions(db, chat_id)
            if not subs:
                await update.message.reply_text(
                    "No tienes alertas activas\\. "
                    "Usa /seguir <palabra> para crear una\\.",
                    parse_mode="MarkdownV2",
                )
                return

            lines = ["🔔 *Tus alertas activas:*", ""]
            for sub in subs:
                extra = []
                if sub.max_price:
                    extra.append(f"máx ${sub.max_price:,.0f}")
                if sub.store_filter:
                    extra.append(sub.store_filter.replace("_", " ").title())
                detail = f" \\({', '.join(extra)}\\)" if extra else ""
                lines.append(f"• `{sub.keyword}`{detail}")

            lines += [
                "",
                "Usa /dejar <palabra> para cancelar una alerta\\.",
            ]
            await update.message.reply_text(
                "\n".join(lines),
                parse_mode="MarkdownV2",
                disable_web_page_preview=True,
            )
        finally:
            db.close()

    async def ranking(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Show top offers ranked by score + viral potential: /ranking"""
        from database.connection import SessionLocal
        from database.models import Offer, OfferStatus, Publication
        from sqlalchemy import desc
        from sqlalchemy.orm import joinedload
        from datetime import datetime, timedelta, timezone

        db = SessionLocal()
        try:
            cutoff = datetime.now(tz=timezone.utc) - timedelta(hours=24)
            offers = (
                db.query(Offer)
                .join(Publication, Offer.id == Publication.offer_id)
                .options(joinedload(Offer.product))
                .filter(
                    Offer.status == OfferStatus.PUBLISHED,
                    Publication.success.is_(True),
                    Publication.sent_at >= cutoff,
                )
                .order_by(desc(Offer.score), desc(Offer.viral_score))
                .limit(10)
                .all()
            )

            if not offers:
                await update.message.reply_text(
                    "📭 No hay ofertas publicadas en las últimas 24 horas.",
                    disable_web_page_preview=True,
                )
                return

            lines = ["🏆 *TOP OFERTAS — Últimas 24 h*", ""]
            for i, o in enumerate(offers, 1):
                p = o.product
                url = o.affiliate_url or p.url
                name = p.name[:45] + "…" if len(p.name) > 45 else p.name
                viral = f"  🚀{o.viral_score}" if o.viral_score >= 10 else ""
                lines.append(
                    f"{i}\\. [{name}]({url})\n"
                    f"   💸 \\-{o.discount_pct:.0f}% · ⭐{o.score}{viral}"
                )

            await update.message.reply_text(
                "\n".join(lines),
                parse_mode="MarkdownV2",
                disable_web_page_preview=True,
            )
        finally:
            db.close()

    async def estadisticas(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Show click/purchase analytics: /estadisticas"""
        from database.connection import SessionLocal
        from services.click_tracker import get_global_stats

        db = SessionLocal()
        try:
            stats_7 = get_global_stats(db, days=7)
            stats_30 = get_global_stats(db, days=30)

            text = (
                "📊 *Estadísticas de RadardeOfertas*\n\n"
                "📅 *Últimos 7 días:*\n"
                f"  👆 Clics: {stats_7['total_clicks']:,}\n"
                f"  🛒 Compras: {stats_7['total_purchases']:,}\n"
                f"  📈 Conversión: {stats_7['conversion_rate']:.1%}\n\n"
                "📅 *Últimos 30 días:*\n"
                f"  👆 Clics: {stats_30['total_clicks']:,}\n"
                f"  🛒 Compras: {stats_30['total_purchases']:,}\n"
                f"  📈 Conversión: {stats_30['conversion_rate']:.1%}"
            )
            await update.message.reply_text(
                text,
                parse_mode="Markdown",
                disable_web_page_preview=True,
            )
        finally:
            db.close()

    async def ahorro(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Community total savings stats: /ahorro"""
        from database.connection import SessionLocal
        from database.models import Offer, OfferStatus, Publication
        from datetime import datetime, timedelta, timezone

        db = SessionLocal()
        try:
            cutoff_7 = datetime.now(tz=timezone.utc) - timedelta(days=7)
            cutoff_30 = datetime.now(tz=timezone.utc) - timedelta(days=30)

            def _stats(cutoff):
                offers = (
                    db.query(Offer)
                    .join(Publication, Offer.id == Publication.offer_id)
                    .filter(
                        Offer.status == OfferStatus.PUBLISHED,
                        Publication.success.is_(True),
                        Publication.sent_at >= cutoff,
                    )
                    .all()
                )
                total_saving = sum(o.original_price - o.current_price for o in offers)
                return len(offers), total_saving

            count_7, saving_7 = _stats(cutoff_7)
            count_30, saving_30 = _stats(cutoff_30)

            text = (
                "💰 *AHORRO DE LA COMUNIDAD*\n\n"
                "📅 *Últimos 7 días:*\n"
                f"  🎯 Ofertas: *{count_7:,}*\n"
                f"  💸 Ahorro total: *${saving_7:,.0f} MXN*\n\n"
                "📅 *Últimos 30 días:*\n"
                f"  🎯 Ofertas: *{count_30:,}*\n"
                f"  💸 Ahorro total: *${saving_30:,.0f} MXN*\n\n"
                "_¡Comparte el canal con tus amigos para que también ahorren\\! 🤑_"
            )
            await update.message.reply_text(
                text, parse_mode="Markdown", disable_web_page_preview=True
            )
        finally:
            db.close()

    async def buscar(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Search for active deals: /buscar <producto>"""
        from database.connection import SessionLocal
        from database.models import Offer, OfferStatus, Publication
        from services.search import match_keywords, normalize_text
        from sqlalchemy import desc
        from sqlalchemy.orm import joinedload
        from datetime import datetime, timedelta, timezone

        if not context.args:
            await update.message.reply_text(
                "🔍 *Búsqueda de ofertas*\n\n"
                "Uso: /buscar <producto>\n"
                "Ejemplo: /buscar iphone\n\n"
                "Buscaré entre las ofertas publicadas en las últimas 24 horas.",
                parse_mode="Markdown",
            )
            return

        raw_query = " ".join(context.args).strip()
        keyword = normalize_text(raw_query)
        db = SessionLocal()
        try:
            cutoff = datetime.now(tz=timezone.utc) - timedelta(hours=24)
            offers = (
                db.query(Offer)
                .join(Publication, Offer.id == Publication.offer_id)
                .options(joinedload(Offer.product))
                .filter(
                    Offer.status == OfferStatus.PUBLISHED,
                    Publication.success.is_(True),
                    Publication.sent_at >= cutoff,
                )
                .order_by(desc(Offer.score))
                .all()
            )

            # Filter by keyword using token-based OR matching with accent-insensitive
            # normalization; structured filters (price, store) are applied separately.
            matches = [
                o for o in offers if match_keywords(o.product.name, raw_query)
            ]

            if not matches:
                await update.message.reply_text(
                    f"😔 No encontré ofertas para *{keyword}* en las últimas 24 h\\.\n\n"
                    f"Usa /seguir {keyword} para recibir una alerta cuando aparezca\\.",
                    parse_mode="MarkdownV2",
                )
                return

            lines = [f"🔍 *Resultados para «{keyword}»* ({len(matches)} encontrados)\n"]
            for o in matches[:5]:
                p = o.product
                url = o.affiliate_url or p.url
                name = p.name[:40] + "…" if len(p.name) > 40 else p.name
                saving = o.original_price - o.current_price
                lines.append(
                    f"• [{name}]({url})\n"
                    f"  💸 *{o.discount_pct:.0f}% OFF* — Ahorra *${saving:,.0f} MXN*\n"
                    f"  🏬 {p.store.replace('_', ' ').title()}"
                )

            await update.message.reply_text(
                "\n".join(lines),
                parse_mode="Markdown",
                disable_web_page_preview=True,
            )
        finally:
            db.close()

    async def categorias(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Show deals by category: /categorias"""
        from database.connection import SessionLocal
        from database.models import Offer, OfferStatus, Publication, Product
        from datetime import datetime, timedelta, timezone

        db = SessionLocal()
        try:
            cutoff = datetime.now(tz=timezone.utc) - timedelta(hours=24)
            offers = (
                db.query(Offer)
                .join(Publication, Offer.id == Publication.offer_id)
                .filter(
                    Offer.status == OfferStatus.PUBLISHED,
                    Publication.success.is_(True),
                    Publication.sent_at >= cutoff,
                )
                .all()
            )

            if not offers:
                await update.message.reply_text(
                    "📭 No hay ofertas publicadas en las últimas 24 h.",
                    disable_web_page_preview=True,
                )
                return

            # Build category → list of (saving, discount) map
            cat_data: dict[str, list[float]] = {}
            for o in offers:
                # Load the product
                product = db.query(Product).filter(Product.id == o.product_id).first()
                cat = (product.category if product else None) or "General"
                if cat not in cat_data:
                    cat_data[cat] = []
                cat_data[cat].append(o.discount_pct)

            # Sort by offer count desc
            sorted_cats = sorted(cat_data.items(), key=lambda x: len(x[1]), reverse=True)

            lines = ["📂 *OFERTAS POR CATEGORÍA — Hoy*\n"]
            for cat, discounts in sorted_cats[:10]:
                count = len(discounts)
                avg_disc = sum(discounts) / count
                lines.append(f"• *{cat}*: {count} oferta{'s' if count > 1 else ''} · promedio {avg_disc:.0f}%")

            lines.append("\n_Usa /buscar <producto> para buscar en estas categorías_")
            await update.message.reply_text(
                "\n".join(lines),
                parse_mode="Markdown",
                disable_web_page_preview=True,
            )
        finally:
            db.close()

    app = Application.builder().token(settings.TELEGRAM_BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("status", status))
    app.add_handler(CommandHandler("ranking", ranking))
    app.add_handler(CommandHandler("estadisticas", estadisticas))
    app.add_handler(CommandHandler("ahorro", ahorro))
    app.add_handler(CommandHandler("buscar", buscar))
    app.add_handler(CommandHandler("categorias", categorias))
    app.add_handler(CommandHandler("ingresos", ingresos))
    app.add_handler(CommandHandler("comisiones", comisiones))
    app.add_handler(CommandHandler("seguir", seguir))
    app.add_handler(CommandHandler("dejar", dejar))
    app.add_handler(CommandHandler("mis_alertas", mis_alertas))

    # ── Admin commands ────────────────────────────────────────────────────────

    async def _admin_guard(update: Update) -> bool:
        """Return True if the user is allowed to run admin commands."""
        uid = update.effective_user.id if update.effective_user else None
        if uid is None or not _is_admin(uid):
            await update.message.reply_text(
                "⛔ No tienes permisos para usar este comando.",
                disable_web_page_preview=True,
            )
            return False
        return True

    async def pause_store(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Pause scraping for a store: /pause <store>"""
        if not await _admin_guard(update):
            return
        if not context.args:
            await update.message.reply_text("Uso: /pause <store>")
            return
        store = context.args[0].lower()
        from services.circuit_breaker import CircuitBreaker
        cb = CircuitBreaker(store)
        cb.pause()
        await update.message.reply_text(
            f"⏸ Scraping pausado para *{store}*.",
            parse_mode="Markdown",
        )

    async def resume_store(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Resume a paused store: /resume <store>"""
        if not await _admin_guard(update):
            return
        if not context.args:
            await update.message.reply_text("Uso: /resume <store>")
            return
        store = context.args[0].lower()
        from services.circuit_breaker import CircuitBreaker
        cb = CircuitBreaker(store)
        cb.resume()
        await update.message.reply_text(
            f"▶️ Scraping reanudado para *{store}*.",
            parse_mode="Markdown",
        )

    async def admin_stats(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Show last 24 h stats: /stats"""
        if not await _admin_guard(update):
            return
        from database.connection import SessionLocal
        from database.models import Offer, OfferStatus, Publication, Product
        from database.models import ScraperHealth
        from datetime import datetime, timedelta, timezone

        db = SessionLocal()
        try:
            cutoff = datetime.now(tz=timezone.utc) - timedelta(hours=24)
            products_scraped = (
                db.query(Product)
                .filter(Product.updated_at >= cutoff)
                .count()
            )
            published = (
                db.query(Publication)
                .filter(
                    Publication.success.is_(True),
                    Publication.sent_at >= cutoff,
                )
                .count()
            )
            discarded = (
                db.query(Offer)
                .filter(
                    Offer.status == OfferStatus.DISCARDED,
                    Offer.detected_at >= cutoff,
                )
                .count()
            )
            errors = (
                db.query(Publication)
                .filter(
                    Publication.success.is_(False),
                    Publication.sent_at >= cutoff,
                )
                .count()
            )
            unhealthy = (
                db.query(ScraperHealth)
                .filter(ScraperHealth.is_healthy.is_(False))
                .count()
            )
            text = (
                "📊 *Estadísticas últimas 24 h*\n\n"
                f"🔍 Productos scrapeados: *{products_scraped:,}*\n"
                f"✅ Publicadas: *{published:,}*\n"
                f"🗑 Descartadas: *{discarded:,}*\n"
                f"❌ Errores de publicación: *{errors:,}*\n"
                f"⚠️ Scrapers con problemas: *{unhealthy:,}*"
            )
            await update.message.reply_text(text, parse_mode="Markdown",
                                            disable_web_page_preview=True)
        finally:
            db.close()

    async def admin_errors(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Show top recent scraper errors: /errors"""
        if not await _admin_guard(update):
            return
        from database.connection import SessionLocal
        from database.models import ScraperHealth

        db = SessionLocal()
        try:
            unhealthy = (
                db.query(ScraperHealth)
                .filter(ScraperHealth.last_error.isnot(None))
                .order_by(ScraperHealth.consecutive_failures.desc())
                .limit(10)
                .all()
            )
            if not unhealthy:
                await update.message.reply_text(
                    "✅ No hay errores recientes en los scrapers.",
                    disable_web_page_preview=True,
                )
                return
            lines = ["🚨 *Errores recientes de scrapers*\n"]
            for sh in unhealthy:
                lines.append(
                    f"🏬 *{sh.store}* — {sh.consecutive_failures} fallos\n"
                    f"   `{(sh.last_error or '')[:100]}`"
                )
            await update.message.reply_text(
                "\n".join(lines),
                parse_mode="Markdown",
                disable_web_page_preview=True,
            )
        finally:
            db.close()

    async def admin_health(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Show healthcheck summary: /health"""
        if not await _admin_guard(update):
            return
        from services.healthcheck import get_healthcheck_summary
        summary = get_healthcheck_summary()
        await update.message.reply_text(summary, parse_mode="Markdown",
                                        disable_web_page_preview=True)

    async def admin_config(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Show relevant non-sensitive config values: /config"""
        if not await _admin_guard(update):
            return
        text = (
            "⚙️ *Configuración actual*\n\n"
            f"📏 `MIN_PUBLISH_SCORE` = {settings.MIN_PUBLISH_SCORE}\n"
            f"⏱ `PUBLICATION_COOLDOWN_HOURS` = {settings.PUBLICATION_COOLDOWN_HOURS}\n"
            f"📅 `MAX_DAILY_PUBLICATIONS` = {settings.MAX_DAILY_PUBLICATIONS}\n"
            f"💰 `MIN_DISCOUNT_PCT` = {settings.MIN_DISCOUNT_PCT}%\n"
            f"💵 `MIN_ABSOLUTE_SAVING_MXN` = ${settings.MIN_ABSOLUTE_SAVING_MXN:,.0f}\n"
            f"🔄 `REQUEST_TIMEOUT` = {settings.REQUEST_TIMEOUT}s\n"
            f"🔁 `CIRCUIT_BREAKER_FAILURE_THRESHOLD` = {settings.CIRCUIT_BREAKER_FAILURE_THRESHOLD}\n"
            f"⏸ `CIRCUIT_BREAKER_COOLDOWN_SECONDS` = {settings.CIRCUIT_BREAKER_COOLDOWN_SECONDS}s\n"
            f"🏷 `DEDUP_CROSS_STORE` = {settings.DEDUP_CROSS_STORE}\n"
            f"📝 `LOG_FORMAT` = {settings.LOG_FORMAT}\n"
            f"📊 `PROMETHEUS_PORT` = {settings.PROMETHEUS_PORT}\n"
        )
        await update.message.reply_text(text, parse_mode="Markdown",
                                        disable_web_page_preview=True)

    app.add_handler(CommandHandler("pause", pause_store))
    app.add_handler(CommandHandler("resume", resume_store))
    app.add_handler(CommandHandler("stats", admin_stats))
    app.add_handler(CommandHandler("errors", admin_errors))
    app.add_handler(CommandHandler("health", admin_health))
    app.add_handler(CommandHandler("config", admin_config))

    logger.info("Telegram bot started (polling)…")
    app.run_polling()
