"""
Unit tests for RadardeOfertas.

These tests are intentionally lightweight (no real DB, no real HTTP calls)
so they can run in any CI environment without external services.
"""
from __future__ import annotations

import sys
import os

# Ensure the project root is on sys.path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from unittest.mock import MagicMock, patch


# ─────────────────────────────────────────────────────────────────────────────
# BaseScraper.clean_price
# ─────────────────────────────────────────────────────────────────────────────


class TestCleanPrice:
    """Tests for the static price-parsing helper."""

    def setup_method(self):
        from scrapers.base import BaseScraper
        self.clean = BaseScraper.clean_price

    def test_plain_number(self):
        assert self.clean("1299") == 1299.0

    def test_currency_symbol(self):
        assert self.clean("$1,299.00") == 1299.0

    def test_mxn_suffix(self):
        assert self.clean("$ 3,499 MXN") == 3499.0

    def test_usd_suffix(self):
        assert self.clean("250.50 USD") == 250.50

    def test_empty_string(self):
        assert self.clean("") is None

    def test_non_numeric(self):
        assert self.clean("N/A") is None

    def test_spaces(self):
        assert self.clean("  12 000  ") == 12000.0


# ─────────────────────────────────────────────────────────────────────────────
# ProductData
# ─────────────────────────────────────────────────────────────────────────────


class TestProductData:
    def test_to_dict_includes_required_keys(self):
        from scrapers.base import ProductData

        pd = ProductData(
            name="Test Product",
            price=999.0,
            url="https://example.com/p/1",
            store="test_store",
            external_id="SKU123",
        )
        d = pd.to_dict()
        assert d["name"] == "Test Product"
        assert d["price"] == 999.0
        assert d["store"] == "test_store"
        assert d["external_id"] == "SKU123"

    def test_defaults(self):
        from scrapers.base import ProductData

        pd = ProductData(
            name="X", price=1.0, url="http://x.com", store="s", external_id="e"
        )
        assert pd.available is True
        assert pd.category is None
        assert pd.image_url is None
        assert pd.extra == {}


# ─────────────────────────────────────────────────────────────────────────────
# OfferScorer – discount_score
# ─────────────────────────────────────────────────────────────────────────────


class TestOfferScorerDiscountScore:
    """Test only the static discount component (no DB needed)."""

    def setup_method(self):
        from services.offer_scorer import OfferScorer
        self.cls = OfferScorer

    def test_zero_discount(self):
        assert self.cls._discount_score(0) == 0

    def test_50_percent_discount(self):
        # 50 * 0.6 = 30
        assert self.cls._discount_score(50) == 30

    def test_full_discount(self):
        # 100 * 0.6 = 60 (capped at 60)
        assert self.cls._discount_score(100) == 60

    def test_over_100_capped(self):
        assert self.cls._discount_score(200) == 60

    def test_73_percent(self):
        # 73 * 0.6 = 43 (int truncation)
        assert self.cls._discount_score(73) == 43


class TestOfferScorerClassifyScore:
    def setup_method(self):
        from services.offer_scorer import OfferScorer
        self.classify = OfferScorer.classify_score

    def test_error_de_precio(self):
        assert self.classify(97) == "error de precio"

    def test_oferta_excelente(self):
        assert self.classify(85) == "oferta excelente"

    def test_buena_oferta(self):
        assert self.classify(65) == "buena oferta"

    def test_regular(self):
        assert self.classify(40) == "regular"

    def test_boundary_95(self):
        assert self.classify(95) == "error de precio"

    def test_boundary_80(self):
        assert self.classify(80) == "oferta excelente"

    def test_boundary_60(self):
        assert self.classify(60) == "buena oferta"

    def test_boundary_59(self):
        assert self.classify(59) == "regular"


# ─────────────────────────────────────────────────────────────────────────────
# Affiliate link generation
# ─────────────────────────────────────────────────────────────────────────────


class TestAffiliateLinks:
    """Tests for the affiliate URL builder."""

    def test_amazon_adds_tag(self):
        from services import affiliate
        with patch.object(affiliate.settings, "AMAZON_AFFILIATE_TAG", "testtag-20"):
            url = affiliate.get_affiliate_url(
                "https://www.amazon.com.mx/dp/B08N5WRWNW", "amazon"
            )
        assert "tag=testtag-20" in url

    def test_amazon_no_tag_returns_original(self):
        from services import affiliate
        original = "https://www.amazon.com.mx/dp/B08N5WRWNW"
        with patch.object(affiliate.settings, "AMAZON_AFFILIATE_TAG", ""):
            url = affiliate.get_affiliate_url(original, "amazon")
        assert url == original

    def test_mercadolibre_adds_aff_id(self):
        from services import affiliate
        with patch.object(affiliate.settings, "MERCADOLIBRE_AFFILIATE_ID", "ml123"):
            url = affiliate.get_affiliate_url(
                "https://www.mercadolibre.com.mx/laptop", "mercadolibre"
            )
        assert "aff_id=ml123" in url

    def test_aliexpress_returns_portal_url(self):
        from urllib.parse import urlparse
        from services import affiliate
        with patch.object(affiliate.settings, "ALIEXPRESS_AFFILIATE_KEY", "alikey"):
            url = affiliate.get_affiliate_url(
                "https://www.aliexpress.com/item/123.html", "aliexpress"
            )
        parsed = urlparse(url)
        assert parsed.scheme == "https"
        assert parsed.netloc == "portals.aliexpress.com"
        assert "alikey" in url

    def test_ebay_returns_rover_url(self):
        from urllib.parse import urlparse
        from services import affiliate
        with patch.object(affiliate.settings, "EBAY_CAMPAIGN_ID", "5338-12345-6"):
            url = affiliate.get_affiliate_url(
                "https://www.ebay.com/itm/123", "ebay"
            )
        parsed = urlparse(url)
        assert parsed.scheme == "https"
        assert parsed.netloc == "rover.ebay.com"

    def test_unknown_store_returns_original(self):
        from services import affiliate
        original = "https://unknown-store.com/product/1"
        url = affiliate.get_affiliate_url(original, "unknown_store")
        assert url == original


# ─────────────────────────────────────────────────────────────────────────────
# PriceAnalyzer._classify
# ─────────────────────────────────────────────────────────────────────────────


class TestPriceAnalyzerClassify:
    def setup_method(self):
        # PriceAnalyzer requires a db session, but _classify is pure logic
        from services.price_analyzer import PriceAnalyzer
        from database.models import OfferType
        self.classify = PriceAnalyzer._classify
        self.OfferType = OfferType

    def test_price_error(self):
        # ratio = 0.30 (< 0.40)
        with patch("services.price_analyzer.settings") as mock_settings:
            mock_settings.PRICE_ERROR_THRESHOLD = 0.40
            mock_settings.OFFER_EXCELLENT_THRESHOLD = 0.60
            mock_settings.OFFER_GOOD_THRESHOLD = 0.80
            result = self.classify(0.30)
        assert result == self.OfferType.PRICE_ERROR

    def test_excellent(self):
        with patch("services.price_analyzer.settings") as mock_settings:
            mock_settings.PRICE_ERROR_THRESHOLD = 0.40
            mock_settings.OFFER_EXCELLENT_THRESHOLD = 0.60
            mock_settings.OFFER_GOOD_THRESHOLD = 0.80
            result = self.classify(0.50)
        assert result == self.OfferType.EXCELLENT

    def test_good(self):
        with patch("services.price_analyzer.settings") as mock_settings:
            mock_settings.PRICE_ERROR_THRESHOLD = 0.40
            mock_settings.OFFER_EXCELLENT_THRESHOLD = 0.60
            mock_settings.OFFER_GOOD_THRESHOLD = 0.80
            result = self.classify(0.70)
        assert result == self.OfferType.GOOD

    def test_regular(self):
        with patch("services.price_analyzer.settings") as mock_settings:
            mock_settings.PRICE_ERROR_THRESHOLD = 0.40
            mock_settings.OFFER_EXCELLENT_THRESHOLD = 0.60
            mock_settings.OFFER_GOOD_THRESHOLD = 0.80
            result = self.classify(0.90)
        assert result == self.OfferType.REGULAR


# ─────────────────────────────────────────────────────────────────────────────
# ScraperManager – run_store on missing store
# ─────────────────────────────────────────────────────────────────────────────


class TestScraperManager:
    def test_unknown_store_returns_empty_list(self):
        from scrapers.manager import ScraperManager

        manager = ScraperManager()
        result = manager.run_store("nonexistent_store_xyz")
        assert result == []

    def test_all_scrapers_instantiate(self):
        """Ensure every scraper class can be instantiated without error."""
        from scrapers.manager import ALL_SCRAPERS

        for cls in ALL_SCRAPERS:
            instance = cls()
            assert instance.store_name != "unknown", (
                f"{cls.__name__} must define a store_name"
            )


# ─────────────────────────────────────────────────────────────────────────────
# Telegram message builder
# ─────────────────────────────────────────────────────────────────────────────


class TestTelegramMessageBuilder:
    def _make_offer(self, rapid_drop=False, offer_type=None, image_url=None):
        from database.models import OfferType, Offer, Product

        product = MagicMock(spec=Product)
        product.name = "Xbox Series X"
        product.store = "walmart"
        product.url = "https://www.walmart.com.mx/xbox"
        product.image_url = image_url

        offer = MagicMock(spec=Offer)
        offer.product = product
        offer.offer_type = offer_type or OfferType.EXCELLENT
        offer.original_price = 12999.0
        offer.current_price = 3499.0
        offer.discount_pct = 73.0
        offer.score = 85
        offer.rapid_drop = rapid_drop
        offer.affiliate_url = "https://www.walmart.com.mx/xbox?aff=1"
        return offer

    def test_message_contains_product_name(self):
        from telegram.publisher import TelegramPublisher

        offer = self._make_offer()
        msg = TelegramPublisher._build_message(offer)
        assert "Xbox Series X" in msg

    def test_message_contains_prices(self):
        from telegram.publisher import TelegramPublisher

        offer = self._make_offer()
        msg = TelegramPublisher._build_message(offer)
        assert "12,999" in msg
        assert "3,499" in msg

    def test_message_contains_discount(self):
        from telegram.publisher import TelegramPublisher

        offer = self._make_offer()
        msg = TelegramPublisher._build_message(offer)
        assert "73%" in msg

    def test_message_contains_store(self):
        from telegram.publisher import TelegramPublisher

        offer = self._make_offer()
        msg = TelegramPublisher._build_message(offer)
        assert "Walmart" in msg

    def test_rapid_drop_flag_shown(self):
        from telegram.publisher import TelegramPublisher

        offer = self._make_offer(rapid_drop=True)
        msg = TelegramPublisher._build_message(offer)
        assert "Caída rápida" in msg or "caída rápida" in msg.lower()

    def test_rapid_drop_not_shown_when_false(self):
        from telegram.publisher import TelegramPublisher

        offer = self._make_offer(rapid_drop=False)
        msg = TelegramPublisher._build_message(offer)
        assert "caída rápida" not in msg.lower()

    def test_error_de_precio_label(self):
        from telegram.publisher import TelegramPublisher, _offer_label
        from database.models import OfferType

        label = _offer_label(OfferType.PRICE_ERROR)
        assert "ERROR" in label.upper()

    def test_affiliate_url_in_message(self):
        from telegram.publisher import TelegramPublisher

        offer = self._make_offer()
        msg = TelegramPublisher._build_message(offer)
        assert "?aff=1" in msg
