"""
Resale opportunity detector.

Identifies deals where the discount and absolute saving are large enough
to make buying and re-selling on MercadoLibre or Facebook Marketplace
potentially profitable.

Returns a :class:`ResaleOpportunity` dataclass with:
  - ``is_opportunity`` – bool, True when resale is viable
  - ``score``          – int 0–10
  - ``reason``         – short Spanish description of why
"""
from __future__ import annotations

from dataclasses import dataclass

from database.models import Offer, OfferType

# Categories with active second-hand markets in Mexico
_RESALE_CATEGORIES: frozenset[str] = frozenset(
    {
        "celulares y smartphones",
        "gaming y videojuegos",
        "laptops y computadoras",
        "televisores y audio",
        "tablets y e-readers",
        "fotografía y video",
        "juguetes y bebés",
    }
)

# Thresholds for a deal to be worth flipping
_MIN_DISCOUNT_PCT: float = 35.0
_MIN_SAVING_MXN: float = 500.0


@dataclass
class ResaleOpportunity:
    """Result from :func:`detect_resale_opportunity`."""

    is_opportunity: bool
    score: int  # 0–10
    reason: str


def detect_resale_opportunity(offer: Offer) -> ResaleOpportunity:
    """
    Analyse *offer* for resale potential and return a
    :class:`ResaleOpportunity`.
    """
    product = offer.product
    score = 0
    reasons: list[str] = []

    # Price error — almost always a good flip
    if offer.offer_type == OfferType.PRICE_ERROR:
        score += 5
        reasons.append("error de precio")

    # Large absolute saving covers shipping + platform fees
    absolute_saving = offer.original_price - offer.current_price
    if absolute_saving >= 2000:
        score += 3
        reasons.append(f"ahorro ${absolute_saving:,.0f}")
    elif absolute_saving >= _MIN_SAVING_MXN:
        score += 2
        reasons.append(f"ahorro ${absolute_saving:,.0f}")

    # Steep discount
    if offer.discount_pct >= _MIN_DISCOUNT_PCT:
        score += 2
        reasons.append(f"descuento {offer.discount_pct:.0f}%")

    # Category has active resale market
    category = (product.category or "").lower()
    if category in _RESALE_CATEGORIES:
        score += 2
        reasons.append("categoría con mercado de reventa activo")

    score = min(10, score)
    return ResaleOpportunity(
        is_opportunity=(score >= 5),
        score=score,
        reason=", ".join(reasons) if reasons else "sin oportunidad de reventa",
    )
