"""
Mexican shopping season detector.

Returns the name of the current seasonal shopping event in Mexico when
the current date falls inside a known promotional window.  Used to add
a seasonal header to offer messages and the daily digest.

Supported events
----------------
* 🛒 Buen Fin          – 3rd weekend of November (≈ 14–18 Nov)
* 🔥 Hot Sale          – Last week of May + first days of June
* 💻 Cyber Monday      – First days of December
* 🎄 Temporada Navideña – December 15–25
* 💝 San Valentín       – February 1–14
* 💐 Día de las Madres  – May 1–10
* 🎒 Regreso a Clases   – July 15 – August 15
* 🌸 Día de Muertos     – October 28–31
* 🏖 Verano             – July 1–14

All windows are approximate; exact dates shift year to year.  Adjust via
environment variables when needed.
"""
from __future__ import annotations

from datetime import date
from typing import Optional


def get_current_season(today: date | None = None) -> Optional[str]:
    """
    Return the current Mexican shopping season name, or ``None`` when
    today falls outside every known promotional window.
    """
    d = today or date.today()
    month, day = d.month, d.day

    # ── Events ordered by priority (most impactful first) ──────────────────

    # Buen Fin — ~3rd weekend of November
    if month == 11 and 14 <= day <= 18:
        return "EL BUEN FIN"

    # Navidad
    if month == 12 and 15 <= day <= 25:
        return "NAVIDAD"

    # Cyber Monday (approximate first days of December)
    if month == 12 and 1 <= day <= 3:
        return "CYBER MONDAY"

    # Hot Sale — last week of May + first two days of June
    if (month == 5 and day >= 26) or (month == 6 and day <= 2):
        return "HOT SALE"

    # Día de las Madres — May 1–10
    if month == 5 and 1 <= day <= 10:
        return "DÍA DE LAS MADRES"

    # San Valentín — Feb 1–14
    if month == 2 and 1 <= day <= 14:
        return "SAN VALENTÍN"

    # Regreso a Clases — mid-July to mid-August
    if (month == 7 and day >= 15) or (month == 8 and day <= 15):
        return "REGRESO A CLASES"

    # Día de Muertos — Oct 28–31
    if month == 10 and day >= 28:
        return "DÍA DE MUERTOS"

    # Verano (summer shopping) — July 1–14
    if month == 7 and day <= 14:
        return "VERANO"

    return None


def get_season_emoji(season_name: str | None) -> str:
    """Return the emoji associated with *season_name*."""
    _MAP: dict[str, str] = {
        "EL BUEN FIN": "🛒",
        "NAVIDAD": "🎄",
        "CYBER MONDAY": "💻",
        "HOT SALE": "🔥",
        "DÍA DE LAS MADRES": "💐",
        "SAN VALENTÍN": "💝",
        "REGRESO A CLASES": "🎒",
        "DÍA DE MUERTOS": "🌸",
        "VERANO": "🏖",
    }
    return _MAP.get(season_name or "", "🎉")


def get_season_banner(today: date | None = None) -> str:
    """
    Return a complete season banner line (e.g. ``"🛒 ¡EL BUEN FIN! 🛒"``),
    or an empty string when outside any event window.
    """
    season = get_current_season(today)
    if not season:
        return ""
    emoji = get_season_emoji(season)
    return f"{emoji} ¡{season}! {emoji}"
