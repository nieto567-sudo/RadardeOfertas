"""
Search utility helpers.

Provides text normalization and flexible keyword matching used by the
Telegram ``/buscar`` command and the subscription-alert system.

Matching strategy
-----------------
* The query is split into individual tokens (words).
* Each token is compared against the normalised product name.
* A product *matches* when **at least one token** is found in its name
  (OR logic).  This is intentionally permissive so that multi-word queries
  like "iphone 15 pro 256" still return iPhone 15 Pro results even when the
  product name does not contain every token.
* Structured filters (price ceiling, store) are applied on top and always
  use AND logic.
"""
from __future__ import annotations

import logging
import re
import unicodedata

logger = logging.getLogger(__name__)

# Minimum token length to consider; very short tokens (1–2 chars) tend to
# create too many false positives.
_MIN_TOKEN_LEN = 2


def normalize_text(text: str) -> str:
    """Return a normalised, lowercase, accent-free version of *text*.

    Steps applied:
    1. Unicode NFKD decomposition → strip combining (accent) characters.
    2. Lower-case.
    3. Replace common punctuation / separators with a space.
    4. Collapse multiple consecutive spaces into one and strip leading/trailing
       whitespace.

    Examples::

        >>> normalize_text("Televisión")
        'television'
        >>> normalize_text("iPhone 15 Pro – 256 GB")
        'iphone 15 pro 256 gb'
        >>> normalize_text("  S/ 1,299.00  ")
        's/ 1 299 00'
    """
    # 1. Strip diacritics
    nfkd = unicodedata.normalize("NFKD", text)
    ascii_text = "".join(c for c in nfkd if not unicodedata.combining(c))
    # 2. Lower-case
    lower = ascii_text.lower()
    # 3. Replace punctuation / separators with space
    cleaned = re.sub(r"[^\w\s]", " ", lower)
    # 4. Collapse spaces
    return re.sub(r"\s+", " ", cleaned).strip()


def tokenize(query: str) -> list[str]:
    """Split a normalised query into meaningful tokens.

    Tokens shorter than :data:`_MIN_TOKEN_LEN` characters are discarded.

    Examples::

        >>> tokenize("iphone 15 pro 256")
        ['iphone', '15', 'pro', '256']
        >>> tokenize("TV")
        ['tv']
    """
    return [t for t in normalize_text(query).split() if len(t) >= _MIN_TOKEN_LEN]


def match_keywords(product_name: str, query: str) -> bool:
    """Return ``True`` when *product_name* matches *query*.

    Matching is performed at the token level with **OR** logic: the product
    matches if at least one token from the (normalised) query appears anywhere
    in the (normalised) product name.

    If the query produces no tokens after normalisation the function returns
    ``False``.

    Debug-level logs are emitted so that unexpected misses can be diagnosed
    without leaking sensitive data in production.

    Parameters
    ----------
    product_name:
        The raw product name as stored in the database.
    query:
        The raw search query entered by the user.
    """
    norm_name = normalize_text(product_name)
    norm_query = normalize_text(query)
    tokens = tokenize(query)

    logger.debug(
        "search | query_original=%r query_normalized=%r tokens=%r product_normalized=%r",
        query,
        norm_query,
        tokens,
        norm_name,
    )

    if not tokens:
        logger.debug("search | no tokens extracted — no match")
        return False

    matched = [t for t in tokens if t in norm_name]
    result = len(matched) > 0

    logger.debug(
        "search | matched_tokens=%r result=%s",
        matched,
        result,
    )
    return result
