"""
Viral potential detector.

Computes a *viral score* (0–20) for a deal based on signals that suggest
it could spread widely on social media in Mexico:

* Large discount → up to 8 pts
* Price error → 5 pts (price errors always go viral)
* Popular / trending category → up to 5 pts
* Well-known brand keyword → 3 pts

The result is stored in ``Offer.viral_score`` and shown in the Telegram
message when the score is noteworthy.
"""
from __future__ import annotations

from database.models import Offer, OfferType

# Viral categories with their point values (most impactful first)
_VIRAL_CATEGORIES: dict[str, int] = {
    "celulares y smartphones": 5,
    "gaming y videojuegos": 5,
    "laptops y computadoras": 4,
    "televisores y audio": 4,
    "tablets y e-readers": 3,
    "fotografía y video": 3,
    "electrodomésticos": 3,
    "juguetes y bebés": 3,
    "deportes y fitness": 2,
    "hogar y muebles": 2,
    "ropa y accesorios": 2,
}

# Brand keywords that significantly boost virality
_VIRAL_BRAND_KEYWORDS: list[str] = [
    "apple", "iphone", "macbook", "ipad", "airpods",
    "samsung", "galaxy",
    "sony", "playstation", "ps5", "ps4", "ps3",
    "nintendo", "switch",
    "xbox", "microsoft",
    "dyson",
    "xiaomi", "redmi",
    "lg",
    "bose",
    "jbl",
]


def calculate_viral_score(offer: Offer) -> int:
    """
    Compute and return the viral score (0–20) for *offer*.

    Does **not** persist the value; the caller must assign it to
    ``offer.viral_score``.
    """
    score = 0
    product = offer.product

    # Price errors are extremely shareable
    if offer.offer_type == OfferType.PRICE_ERROR:
        score += 5

    # Bigger discount → more viral
    if offer.discount_pct >= 70:
        score += 8
    elif offer.discount_pct >= 50:
        score += 6
    elif offer.discount_pct >= 40:
        score += 4
    elif offer.discount_pct >= 30:
        score += 2

    # Viral category bonus
    category = (product.category or "").lower()
    score += _VIRAL_CATEGORIES.get(category, 0)

    # Brand keyword bonus
    name_lower = (product.name or "").lower()
    if any(brand in name_lower for brand in _VIRAL_BRAND_KEYWORDS):
        score += 3

    return min(20, score)


def viral_label(viral_score: int) -> str:
    """Return a human-readable Spanish label for a viral score."""
    if viral_score >= 15:
        return "🚀 MUY ALTO"
    if viral_score >= 10:
        return "🔥 ALTO"
    if viral_score >= 5:
        return "📣 MEDIO"
    return ""
