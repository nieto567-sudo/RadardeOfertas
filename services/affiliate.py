"""
Affiliate link module – placeholder for future monetisation.

Affiliate API integrations are intentionally disabled while the channel grows
its audience.  When the time comes to re-enable monetisation, implement the
desired affiliate programme here and set ``MONETIZED_LINKS_ENABLED=true`` in
the environment.  No other code changes are needed.

Current behavior
-----------------
``get_affiliate_url`` returns the canonical product URL unchanged.
No external APIs are called.  No affiliate tags, UTM parameters, or URL
shortening is applied.
"""
from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


def get_affiliate_url(url: str, store: str) -> str:  # noqa: ARG001
    """Return *url* unchanged (affiliate integrations are currently disabled)."""
    return url

