"""
Product deduplication service.

Prevents publishing the same offer multiple times by maintaining a
*fingerprint* for every product.  The fingerprint is derived by normalising
the product title (lower-case, collapse whitespace, strip punctuation) and
optionally incorporating the store name to detect cross-store duplicates
when ``DEDUP_CROSS_STORE=true``.

A SHA-256 of the normalised string is stored in the ``products.fingerprint``
column and indexed for fast lookups.

Garbage-quality checks
----------------------
The :func:`passes_basic_quality` helper rejects products before they even
enter the pipeline:
* price == 0 or negative
* no image URL  (when ``REQUIRE_IMAGE=true``)
* title too short  (< ``MIN_TITLE_LENGTH`` chars)

Configuration (env vars)
------------------------
* ``DEDUP_CROSS_STORE``  – ``true`` to deduplicate across stores (default ``false``)
* ``REQUIRE_IMAGE``      – ``true`` to reject products without an image (default ``false``)
* ``MIN_TITLE_LENGTH``   – minimum product title length in chars (default ``10``)
"""
from __future__ import annotations

import hashlib
import logging
import os
import re
import unicodedata
from dataclasses import dataclass
from typing import Optional

from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

_CROSS_STORE: bool = os.getenv("DEDUP_CROSS_STORE", "false").lower() == "true"
_REQUIRE_IMAGE: bool = os.getenv("REQUIRE_IMAGE", "false").lower() == "true"
_MIN_TITLE_LEN: int = int(os.getenv("MIN_TITLE_LENGTH", "10"))

# Characters considered noise when normalising titles
_NOISE_RE = re.compile(r"[^\w\s]", re.UNICODE)
_WHITESPACE_RE = re.compile(r"\s+")


# ── normalisation ─────────────────────────────────────────────────────────────


def _normalise_title(title: str) -> str:
    """
    Return a canonical representation of *title* suitable for deduplication.

    Steps:
    1. Unicode NFKD normalisation + ASCII transliteration
    2. Lower-case
    3. Remove punctuation / special chars
    4. Collapse whitespace
    5. Strip leading/trailing whitespace
    """
    nfkd = unicodedata.normalize("NFKD", title)
    ascii_str = nfkd.encode("ascii", "ignore").decode("ascii")
    lower = ascii_str.lower()
    no_punct = _NOISE_RE.sub(" ", lower)
    collapsed = _WHITESPACE_RE.sub(" ", no_punct).strip()
    return collapsed


def compute_fingerprint(title: str, store: Optional[str] = None) -> str:
    """
    Compute a SHA-256 fingerprint for a product.

    When ``DEDUP_CROSS_STORE=true``, the store is **not** included so that
    the same product on different stores shares a fingerprint.
    When ``DEDUP_CROSS_STORE=false`` (default), the store is included so
    that the same product on different stores is treated as distinct.
    """
    normalised = _normalise_title(title)
    if not _CROSS_STORE and store:
        key = f"{store}::{normalised}"
    else:
        key = normalised
    return hashlib.sha256(key.encode("utf-8")).hexdigest()


# ── quality checks ────────────────────────────────────────────────────────────


@dataclass
class QualityResult:
    passed: bool
    reason: str


def passes_basic_quality(
    title: str,
    price: float,
    image_url: Optional[str] = None,
) -> QualityResult:
    """
    Return a :class:`QualityResult` for a raw product before DB upsert.

    Rejects:
    * Price ≤ 0
    * Title shorter than ``MIN_TITLE_LENGTH``
    * No image when ``REQUIRE_IMAGE=true``
    """
    if price <= 0:
        return QualityResult(passed=False, reason=f"precio inválido ({price})")
    if len(title.strip()) < _MIN_TITLE_LEN:
        return QualityResult(
            passed=False,
            reason=f"título demasiado corto ({len(title.strip())} chars < {_MIN_TITLE_LEN})",
        )
    if _REQUIRE_IMAGE and not image_url:
        return QualityResult(passed=False, reason="sin imagen")
    return QualityResult(passed=True, reason="ok")


# ── DB-based duplicate check ──────────────────────────────────────────────────


def is_duplicate(db: Session, fingerprint: str, store: Optional[str] = None) -> bool:
    """
    Return True if a product with *fingerprint* already exists in the DB.

    When ``DEDUP_CROSS_STORE=true`` the *store* parameter is ignored and
    any matching fingerprint is considered a duplicate.
    """
    from database.models import Product  # avoid circular import

    query = db.query(Product.id).filter(Product.fingerprint == fingerprint)
    if not _CROSS_STORE and store:
        query = query.filter(Product.store == store)
    return query.first() is not None
