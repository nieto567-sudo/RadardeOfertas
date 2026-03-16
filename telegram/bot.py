"""
Telegram bot entry point.

Starts a simple polling bot that responds to /start and /status commands.
This is separate from the publisher (which uses the Bot API directly).
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
            "tiendas de México y el mundo\\.",
            parse_mode="MarkdownV2",
        )

    async def status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        from database.connection import SessionLocal  # local import to avoid circular
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
            )
        finally:
            db.close()

    app = Application.builder().token(settings.TELEGRAM_BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("status", status))

    logger.info("Telegram bot started (polling)…")
    app.run_polling()
