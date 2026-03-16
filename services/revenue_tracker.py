"""
Revenue tracker service.

Estimates affiliate commission for every published offer and persists
the result in the ``revenue_records`` table.

Commission rates
----------------
Rates are *typical industry averages* and will vary by category and network
performance.  Check your affiliate dashboard for your actual rates.

    Store / Network        Typical rate
    ─────────────────────  ────────────
    Amazon Associates      3 – 10 %   (avg ≈ 4 %)
    MercadoLibre Afiliados 2 – 5 %    (avg ≈ 4 %)
    AliExpress Portals     4 – 9 %    (avg ≈ 6 %)
    eBay Partner Network   1 – 4 %    (avg ≈ 2 %)
    Admitad – Walmart MX   1 – 3 %    (avg ≈ 2 %)
    Admitad – Liverpool    2 – 5 %    (avg ≈ 3 %)
    Admitad – Coppel       2 – 4 %    (avg ≈ 3 %)
    Admitad – Costco       1 – 3 %    (avg ≈ 2 %)
    Admitad – Sears/Sanborns 2 – 4 % (avg ≈ 3 %)
    Admitad – general      1 – 3 %    (avg ≈ 2 %)
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy.orm import Session

from config import settings
from database.models import Offer, RevenueRecord

logger = logging.getLogger(__name__)

# ── Commission rate table ────────────────────────────────────────────────────
# Maps store_name → (affiliate_network, commission_rate)
_COMMISSION_TABLE: dict[str, tuple[str, float]] = {
    # Direct affiliate programmes
    "amazon":        ("amazon_associates", 0.04),
    "mercadolibre":  ("ml_afiliados",      0.04),
    "aliexpress":    ("aliexpress_portals", 0.06),
    "ebay":          ("ebay_partner",      0.02),
    # Admitad network
    "walmart":        ("admitad", 0.02),
    "bodega_aurrera": ("admitad", 0.02),
    "liverpool":      ("admitad", 0.03),
    "costco":         ("admitad", 0.02),
    "coppel":         ("admitad", 0.03),
    "elektra":        ("admitad", 0.02),
    "sears":          ("admitad", 0.03),
    "sanborns":       ("admitad", 0.03),
    "sams_club":      ("admitad", 0.02),
    "office_depot":   ("admitad", 0.02),
    "officemax":      ("admitad", 0.02),
    "soriana":        ("admitad", 0.02),
    "cyberpuerta":    ("admitad", 0.03),
    "pcel":           ("admitad", 0.03),
    "ddtech":         ("admitad", 0.03),
    "intercompras":   ("admitad", 0.03),
    "gameplanet":     ("admitad", 0.03),
    "claro_shop":     ("admitad", 0.02),
    # International
    "newegg":    ("admitad", 0.02),
    "banggood":  ("admitad", 0.03),
    "gearbest":  ("admitad", 0.03),
}

# Fallback for stores not in the table
_DEFAULT_NETWORK = "admitad"
_DEFAULT_RATE = 0.02


def get_commission_info(store: str) -> tuple[str, float]:
    """Return (affiliate_network, commission_rate) for *store*."""
    return _COMMISSION_TABLE.get(store, (_DEFAULT_NETWORK, _DEFAULT_RATE))


def estimate_commission(store: str, price: float) -> float:
    """
    Estimate the affiliate commission in MXN for a product sold at *price*.

    This is the amount you earn *per conversion* (i.e., per purchase made
    through your affiliate link).  Actual earnings depend on your channel's
    conversion rate.
    """
    _, rate = get_commission_info(store)
    return round(price * rate, 2)


def record_revenue(
    db: Session,
    offer: Offer,
    store: str,
    price: float,
    short_url: Optional[str] = None,
) -> RevenueRecord:
    """
    Create and persist a :class:`RevenueRecord` for *offer*.

    Parameters
    ----------
    db:       Active SQLAlchemy session.
    offer:    The offer that was published.
    store:    Store name (e.g. ``"walmart"``).
    price:    Current product price in MXN.
    short_url: Bitly short link (if available).
    """
    network, rate = get_commission_info(store)
    estimated = round(price * rate, 2)

    record = RevenueRecord(
        offer_id=offer.id,
        store=store,
        affiliate_network=network,
        product_price=price,
        commission_rate=rate,
        estimated_commission_mxn=estimated,
        short_url=short_url,
    )
    db.add(record)
    logger.debug(
        "Revenue record: store=%s price=%.2f rate=%.0f%% estimated=%.2f MXN",
        store, price, rate * 100, estimated,
    )
    return record


def get_revenue_summary(db: Session, days: int = 30) -> dict:
    """
    Return a summary of estimated earnings over the last *days* days.

    Uses SQL-level aggregation so only summary rows are loaded into memory,
    regardless of how many individual revenue records exist.

    Returns
    -------
    dict with keys:
        total_estimated_mxn   – total estimated earnings in MXN
        offers_published       – number of offers that generated a record
        by_network             – breakdown by affiliate network
        by_store               – top 5 stores by estimated earnings
        avg_per_offer_mxn      – average per-offer commission
    """
    from sqlalchemy import func as sqlfunc

    cutoff = datetime.now(tz=timezone.utc) - timedelta(days=days)

    # Aggregate totals in the database
    totals = (
        db.query(
            sqlfunc.sum(RevenueRecord.estimated_commission_mxn).label("total"),
            sqlfunc.count(RevenueRecord.id).label("count"),
            sqlfunc.avg(RevenueRecord.estimated_commission_mxn).label("avg"),
        )
        .filter(RevenueRecord.created_at >= cutoff)
        .one()
    )

    total_mxn = float(totals.total or 0)
    count = int(totals.count or 0)
    avg_mxn = float(totals.avg or 0)

    if count == 0:
        return {
            "total_estimated_mxn": 0.0,
            "offers_published": 0,
            "by_network": {},
            "by_store": {},
            "avg_per_offer_mxn": 0.0,
        }

    # Aggregate by network
    by_network_rows = (
        db.query(
            RevenueRecord.affiliate_network,
            sqlfunc.sum(RevenueRecord.estimated_commission_mxn).label("subtotal"),
        )
        .filter(RevenueRecord.created_at >= cutoff)
        .group_by(RevenueRecord.affiliate_network)
        .all()
    )
    by_network = {
        (row.affiliate_network or "unknown"): round(float(row.subtotal), 2)
        for row in by_network_rows
    }

    # Top 5 stores by earnings
    by_store_rows = (
        db.query(
            RevenueRecord.store,
            sqlfunc.sum(RevenueRecord.estimated_commission_mxn).label("subtotal"),
        )
        .filter(RevenueRecord.created_at >= cutoff)
        .group_by(RevenueRecord.store)
        .order_by(sqlfunc.sum(RevenueRecord.estimated_commission_mxn).desc())
        .limit(5)
        .all()
    )
    by_store = {row.store: round(float(row.subtotal), 2) for row in by_store_rows}

    return {
        "total_estimated_mxn": round(total_mxn, 2),
        "offers_published": count,
        "by_network": by_network,
        "by_store": by_store,
        "avg_per_offer_mxn": round(avg_mxn, 2),
    }


def get_commission_rates_text() -> str:
    """
    Return a human-readable table of commission rates for all supported stores.
    Used by the /comisiones bot command.
    """
    lines = ["*📊 Tasas de comisión por tienda*\n"]
    for store, (network, rate) in sorted(
        _COMMISSION_TABLE.items(), key=lambda x: -x[1][1]
    ):
        store_name = store.replace("_", " ").title()
        lines.append(
            f"• *{store_name}* — {rate*100:.0f}% ({network.replace('_', ' ').title()})"
        )
    return "\n".join(lines)
