"""
Offer quality / garbage filter.

Checks an :class:`~database.models.Offer` against basic quality thresholds
*before* it is scored and published.  This prevents poor deals (tiny
discounts, products with almost no saving) from ever reaching the channel.

Thresholds
----------
* ``MIN_DISCOUNT_PCT``       – minimum percentage discount
* ``MIN_ABSOLUTE_SAVING_MXN`` – minimum MXN saved (filters cheap products)

Both thresholds are read from :mod:`config.settings` and are configurable
via environment variables.
"""
from __future__ import annotations

from dataclasses import dataclass

from config import settings
from database.models import Offer


@dataclass
class FilterResult:
    """Result from :func:`passes_quality_filter`."""

    passed: bool
    reason: str


def passes_quality_filter(offer: Offer) -> FilterResult:
    """
    Return a :class:`FilterResult` indicating whether *offer* passes
    minimum quality standards.

    Parameters
    ----------
    offer : Offer
        ORM instance with ``original_price``, ``current_price``, and
        ``discount_pct`` already set (by :class:`~services.price_analyzer.PriceAnalyzer`).
    """
    # 1. Minimum discount percentage
    if offer.discount_pct < settings.MIN_DISCOUNT_PCT:
        return FilterResult(
            passed=False,
            reason=(
                f"descuento {offer.discount_pct:.1f}% "
                f"< mínimo {settings.MIN_DISCOUNT_PCT:.0f}%"
            ),
        )

    # 2. Minimum absolute saving in MXN
    absolute_saving = offer.original_price - offer.current_price
    if absolute_saving < settings.MIN_ABSOLUTE_SAVING_MXN:
        return FilterResult(
            passed=False,
            reason=(
                f"ahorro ${absolute_saving:.0f} MXN "
                f"< mínimo ${settings.MIN_ABSOLUTE_SAVING_MXN:.0f} MXN"
            ),
        )

    return FilterResult(passed=True, reason="ok")
