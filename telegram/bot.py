"""
Telegram bot entry point.

Starts a simple polling bot that responds to:
  /start        – welcome message
  /status       – system stats (products, offers)
  /ingresos     – estimated affiliate revenue summary
  /comisiones   – commission rate table per store
  /seguir       – subscribe to keyword alerts  (/seguir iphone)
  /dejar        – unsubscribe from keyword      (/dejar iphone)
  /mis_alertas  – list all active subscriptions
"""
from __future__ import annotations

import logging

from config import settings

logger = logging.getLogger(__name__)


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
            "Este bot publica automáticamente las mejores ofertas detectadas en "
            "tiendas de México y el mundo\\.\n\n"
            "Comandos disponibles:\n"
            "/status – estadísticas del sistema\n"
            "/ingresos – resumen de ingresos estimados\n"
            "/comisiones – tasas de comisión por tienda\n"
            "/seguir \\<palabra\\> – recibe alertas cuando aparezca esa oferta\n"
            "/dejar \\<palabra\\> – cancela una alerta\n"
            "/mis\\_alertas – ver tus alertas activas",
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

    app = Application.builder().token(settings.TELEGRAM_BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("status", status))
    app.add_handler(CommandHandler("ingresos", ingresos))
    app.add_handler(CommandHandler("comisiones", comisiones))
    app.add_handler(CommandHandler("seguir", seguir))
    app.add_handler(CommandHandler("dejar", dejar))
    app.add_handler(CommandHandler("mis_alertas", mis_alertas))

    logger.info("Telegram bot started (polling)…")
    app.run_polling()
