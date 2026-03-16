"""
Cross-store price comparison service.

When the same (or very similar) product is available in multiple stores,
this service finds the best current price across all of them and returns
a structured comparison so the Telegram message can highlight the cheapest
option.

Matching strategy
-----------------
Products are matched by name similarity: we extract significant words
(length >= 3) from the original product name and check how many appear in
each candidate's name.  Products that share at least
``settings.PRICE_COMPARISON_MIN_WORDS`` significant words are considered
the same product.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Optional

from sqlalchemy.orm import Session

from config import settings
from database.models import Product

logger = logging.getLogger(__name__)


@dataclass
class PriceComparison:
    """Summary of prices found across stores for a given product."""

    cheapest_store: str
    cheapest_price: float
    cheapest_url: str
    alternatives: list[dict] = field(default_factory=list)
    # True when the *original* product is NOT the cheapest
    better_deal_exists: bool = False


def compare_across_stores(
    db: Session, product: Product
) -> Optional[PriceComparison]:
    """
    Search for products with similar names in other stores and return a
    :class:`PriceComparison` if alternatives are found, otherwise *None*.

    Parameters
    ----------
    db:
        Active SQLAlchemy session.
    product:
        The product being analysed (the one an offer was just detected for).
    """
    try:
        min_words = settings.PRICE_COMPARISON_MIN_WORDS

        # Extract significant words (length >= 3) from the product name.
        words = [w.lower() for w in product.name.split() if len(w) >= 3]
        if len(words) < 2:
            return None

        # Query products in OTHER stores with a price.
        candidates = (
            db.query(Product)
            .filter(
                Product.id != product.id,
                Product.available.is_(True),
                Product.current_price.isnot(None),
                Product.current_price > 0,
            )
            .all()
        )

        matches: list[Product] = []
        for candidate in candidates:
            cand_lower = candidate.name.lower()
            shared = sum(1 for w in words if w in cand_lower)
            if shared >= min_words:
                matches.append(candidate)

        if not matches:
            return None

        # Combine the original product with all matches and sort by price.
        all_options: list[Product] = [product] + matches
        all_options.sort(key=lambda p: p.current_price or float("inf"))

        cheapest = all_options[0]
        alternatives = [
            {
                "store": p.store.replace("_", " ").title(),
                "price": p.current_price,
                "url": p.url,
            }
            for p in all_options[:5]  # cap at 5 to keep the message readable
        ]

        return PriceComparison(
            cheapest_store=cheapest.store.replace("_", " ").title(),
            cheapest_price=cheapest.current_price,
            cheapest_url=cheapest.url,
            alternatives=alternatives,
            better_deal_exists=(cheapest.id != product.id),
        )
    except Exception as exc:  # pylint: disable=broad-except
        logger.warning(
            "Cross-store comparison failed for product %d: %s", product.id, exc
        )
        return None
