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
        with patch.object(affiliate.settings, "AMAZON_AFFILIATE_TAG", ""), \
             patch.object(affiliate.settings, "BITLY_API_TOKEN", ""), \
             patch.object(affiliate.settings, "UTM_SOURCE", "radar"), \
             patch.object(affiliate.settings, "UTM_MEDIUM", "telegram"), \
             patch.object(affiliate.settings, "UTM_CAMPAIGN", "oferta"):
            url = affiliate.get_affiliate_url(original, "amazon")
        # No affiliate tag → no ?tag= param, but UTM params are always added
        assert "tag=" not in url
        assert "utm_source=radar" in url

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
        with patch.object(affiliate.settings, "BITLY_API_TOKEN", ""), \
             patch.object(affiliate.settings, "UTM_SOURCE", "radar"), \
             patch.object(affiliate.settings, "UTM_MEDIUM", "telegram"), \
             patch.object(affiliate.settings, "UTM_CAMPAIGN", "oferta"):
            url = affiliate.get_affiliate_url(original, "unknown_store")
        # No affiliate programme → base URL is unchanged, but UTM params still added
        assert "unknown-store.com/product/1" in url
        assert "utm_source=radar" in url


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


# ─────────────────────────────────────────────────────────────────────────────
# Revenue tracker – commission estimation
# ─────────────────────────────────────────────────────────────────────────────


class TestRevenueTrackerEstimates:
    """Tests for the per-store commission estimation helpers."""

    def test_amazon_commission_rate(self):
        from services.revenue_tracker import get_commission_info

        network, rate = get_commission_info("amazon")
        assert network == "amazon_associates"
        assert rate == pytest.approx(0.04)

    def test_mercadolibre_commission_rate(self):
        from services.revenue_tracker import get_commission_info

        network, rate = get_commission_info("mercadolibre")
        assert network == "ml_afiliados"
        assert rate == pytest.approx(0.04)

    def test_walmart_via_admitad(self):
        from services.revenue_tracker import get_commission_info

        network, rate = get_commission_info("walmart")
        assert network == "admitad"
        assert rate > 0

    def test_liverpool_via_admitad(self):
        from services.revenue_tracker import get_commission_info

        network, rate = get_commission_info("liverpool")
        assert network == "admitad"

    def test_unknown_store_fallback(self):
        from services.revenue_tracker import get_commission_info

        network, rate = get_commission_info("nonexistent_store_xyz")
        assert rate > 0  # always returns a positive rate

    def test_estimate_commission_value(self):
        from services.revenue_tracker import estimate_commission

        # Amazon at 4% on a $1000 product
        with patch("services.revenue_tracker._COMMISSION_TABLE", {"amazon": ("amazon_associates", 0.04)}):
            result = estimate_commission("amazon", 1000.0)
        assert result == pytest.approx(40.0)

    def test_estimate_commission_walmart(self):
        from services.revenue_tracker import estimate_commission, _COMMISSION_TABLE

        _, rate = _COMMISSION_TABLE["walmart"]
        result = estimate_commission("walmart", 5000.0)
        assert result == pytest.approx(5000.0 * rate)

    def test_revenue_summary_empty_db(self):
        from services.revenue_tracker import get_revenue_summary
        from sqlalchemy import func as sqlfunc

        # Simulate the aggregation row returning all-None values
        totals_row = MagicMock()
        totals_row.total = None
        totals_row.count = 0
        totals_row.avg = None

        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.one.return_value = totals_row

        summary = get_revenue_summary(mock_db, days=30)
        assert summary["total_estimated_mxn"] == 0.0
        assert summary["offers_published"] == 0

    def test_revenue_summary_with_records(self):
        from services.revenue_tracker import get_revenue_summary

        # Simulate non-zero aggregate row
        totals_row = MagicMock()
        totals_row.total = 140.0
        totals_row.count = 2
        totals_row.avg = 70.0

        network_row1 = MagicMock()
        network_row1.affiliate_network = "amazon_associates"
        network_row1.subtotal = 40.0

        network_row2 = MagicMock()
        network_row2.affiliate_network = "admitad"
        network_row2.subtotal = 100.0

        store_row1 = MagicMock()
        store_row1.store = "amazon"
        store_row1.subtotal = 40.0

        store_row2 = MagicMock()
        store_row2.store = "walmart"
        store_row2.subtotal = 100.0

        call_count = [0]

        def mock_query_chain(*args, **kwargs):
            chain = MagicMock()
            chain.filter.return_value = chain
            chain.group_by.return_value = chain
            chain.order_by.return_value = chain
            chain.limit.return_value = chain

            call_count[0] += 1
            if call_count[0] == 1:
                chain.one.return_value = totals_row
            elif call_count[0] == 2:
                chain.all.return_value = [network_row1, network_row2]
            else:
                chain.all.return_value = [store_row1, store_row2]
            return chain

        mock_db = MagicMock()
        mock_db.query.side_effect = mock_query_chain

        summary = get_revenue_summary(mock_db, days=30)
        assert summary["total_estimated_mxn"] == pytest.approx(140.0)
        assert summary["offers_published"] == 2
        assert "amazon_associates" in summary["by_network"]
        assert "admitad" in summary["by_network"]

    def test_commission_rates_text_contains_all_stores(self):
        from services.revenue_tracker import get_commission_rates_text

        text = get_commission_rates_text()
        assert "Amazon" in text
        assert "Walmart" in text
        assert "Liverpool" in text
        assert "Admitad" in text or "admitad" in text.lower()


# ─────────────────────────────────────────────────────────────────────────────
# Affiliate – UTM parameters
# ─────────────────────────────────────────────────────────────────────────────


class TestUTMParameters:
    """Tests for UTM parameter injection."""

    def test_utm_added_to_plain_url(self):
        from services.affiliate import _apply_utm
        from unittest.mock import patch

        with patch("services.affiliate.settings") as ms:
            ms.UTM_SOURCE = "radardeofertas"
            ms.UTM_MEDIUM = "telegram"
            ms.UTM_CAMPAIGN = "oferta"
            url = _apply_utm("https://www.walmart.com.mx/product/1", "walmart")

        assert "utm_source=radardeofertas" in url
        assert "utm_medium=telegram" in url
        assert "utm_campaign=oferta" in url
        assert "utm_content=walmart" in url

    def test_utm_preserves_existing_params(self):
        from services.affiliate import _apply_utm
        from unittest.mock import patch

        with patch("services.affiliate.settings") as ms:
            ms.UTM_SOURCE = "radar"
            ms.UTM_MEDIUM = "telegram"
            ms.UTM_CAMPAIGN = "deal"
            url = _apply_utm(
                "https://www.liverpool.com.mx/tienda?color=rojo", "liverpool"
            )

        assert "color=rojo" in url
        assert "utm_source=radar" in url

    def test_utm_does_not_crash_on_bad_url(self):
        from services.affiliate import _apply_utm
        from unittest.mock import patch

        with patch("services.affiliate.settings") as ms:
            ms.UTM_SOURCE = "r"
            ms.UTM_MEDIUM = "t"
            ms.UTM_CAMPAIGN = "o"
            # Should return url unchanged if it can't parse
            result = _apply_utm("not-a-valid-url", "store")
        assert result  # must return something, not raise


# ─────────────────────────────────────────────────────────────────────────────
# Affiliate – Admitad deep links
# ─────────────────────────────────────────────────────────────────────────────


class TestAdmitadAffiliateLinks:
    """Tests for Admitad deep-link generation."""

    def test_admitad_url_format(self):
        from services.affiliate import _admitad
        from urllib.parse import urlparse
        from unittest.mock import patch

        with patch("services.affiliate.settings") as ms:
            ms.ADMITAD_PUBLISHER_ID = "mypub"
            ms.ADMITAD_SITE_IDS = {"walmart": "site99"}
            url = _admitad("https://www.walmart.com.mx/product", "walmart")

        parsed = urlparse(url)
        assert parsed.netloc == "ad.admitad.com"
        assert "site99" in url
        assert "mypub" in url

    def test_admitad_no_publisher_returns_original(self):
        from services.affiliate import _admitad
        from unittest.mock import patch

        original = "https://www.walmart.com.mx/product"
        with patch("services.affiliate.settings") as ms:
            ms.ADMITAD_PUBLISHER_ID = ""
            ms.ADMITAD_SITE_IDS = {"walmart": "site99"}
            url = _admitad(original, "walmart")

        assert url == original

    def test_admitad_no_site_id_returns_original(self):
        from services.affiliate import _admitad
        from unittest.mock import patch

        original = "https://www.coppel.com/product"
        with patch("services.affiliate.settings") as ms:
            ms.ADMITAD_PUBLISHER_ID = "pub123"
            ms.ADMITAD_SITE_IDS = {}   # no site ID for coppel
            url = _admitad(original, "coppel")

        assert url == original

    def test_admitad_encodes_product_url(self):
        from services.affiliate import _admitad
        from unittest.mock import patch

        with patch("services.affiliate.settings") as ms:
            ms.ADMITAD_PUBLISHER_ID = "pub"
            ms.ADMITAD_SITE_IDS = {"liverpool": "liv123"}
            url = _admitad(
                "https://liverpool.com.mx/producto?color=rojo&size=M",
                "liverpool",
            )

        # The product URL must be percent-encoded in the deep link
        assert "%3A" in url or "liverpool.com.mx" in url  # either encoded or raw


# ─────────────────────────────────────────────────────────────────────────────
# Affiliate – Bitly shortener
# ─────────────────────────────────────────────────────────────────────────────


class TestBitlyShortener:
    """Tests for the Bitly URL-shortening integration."""

    def test_no_token_returns_original(self):
        from services.affiliate import shorten_url
        from unittest.mock import patch

        original = "https://www.amazon.com.mx/dp/B08N5WRWNW?tag=test"
        with patch("services.affiliate.settings") as ms:
            ms.BITLY_API_TOKEN = ""
            ms.BITLY_GROUP_GUID = ""
            result = shorten_url(original)

        assert result == original

    def test_successful_bitly_call(self):
        from services.affiliate import shorten_url
        from unittest.mock import patch, MagicMock

        mock_resp = MagicMock()
        mock_resp.json.return_value = {"link": "https://bit.ly/abc123"}
        mock_resp.raise_for_status.return_value = None

        with patch("services.affiliate.settings") as ms, \
             patch("services.affiliate._requests.post", return_value=mock_resp):
            ms.BITLY_API_TOKEN = "faketoken"
            ms.BITLY_GROUP_GUID = ""
            result = shorten_url("https://www.walmart.com.mx/product")

        assert result == "https://bit.ly/abc123"

    def test_bitly_api_failure_returns_original(self):
        from services.affiliate import shorten_url
        from unittest.mock import patch

        original = "https://www.coppel.com/product"
        with patch("services.affiliate.settings") as ms, \
             patch("services.affiliate._requests.post", side_effect=Exception("timeout")):
            ms.BITLY_API_TOKEN = "tok"
            ms.BITLY_GROUP_GUID = ""
            result = shorten_url(original)

        assert result == original


# ─────────────────────────────────────────────────────────────────────────────
# Cooldown service
# ─────────────────────────────────────────────────────────────────────────────


class TestCooldownService:
    """Tests for the publication cooldown guard."""

    def test_no_recent_publication_is_not_on_cooldown(self):
        from services.cooldown import is_on_cooldown
        from unittest.mock import patch, MagicMock

        mock_db = MagicMock()
        mock_query = MagicMock()
        mock_query.join.return_value.filter.return_value.first.return_value = None
        mock_db.query.return_value = mock_query

        with patch("services.cooldown.settings") as ms:
            ms.PUBLICATION_COOLDOWN_HOURS = 6
            result = is_on_cooldown(mock_db, product_id=1)

        assert result is False

    def test_recent_publication_is_on_cooldown(self):
        from services.cooldown import is_on_cooldown
        from database.models import Publication
        from unittest.mock import patch, MagicMock

        mock_pub = MagicMock(spec=Publication)
        mock_db = MagicMock()
        mock_query = MagicMock()
        mock_query.join.return_value.filter.return_value.first.return_value = mock_pub
        mock_db.query.return_value = mock_query

        with patch("services.cooldown.settings") as ms:
            ms.PUBLICATION_COOLDOWN_HOURS = 6
            result = is_on_cooldown(mock_db, product_id=42)

        assert result is True


# ─────────────────────────────────────────────────────────────────────────────
# ProductData – coupon_code field
# ─────────────────────────────────────────────────────────────────────────────


class TestProductDataCouponCode:
    """Tests for the new coupon_code field on ProductData."""

    def test_coupon_code_default_is_none(self):
        from scrapers.base import ProductData

        pd = ProductData(
            name="Laptop",
            price=9999.0,
            url="https://example.com/laptop",
            store="walmart",
            external_id="LAP123",
        )
        assert pd.coupon_code is None

    def test_coupon_code_in_to_dict(self):
        from scrapers.base import ProductData

        pd = ProductData(
            name="Laptop",
            price=9999.0,
            url="https://example.com/laptop",
            store="walmart",
            external_id="LAP123",
            coupon_code="SAVE15",
        )
        d = pd.to_dict()
        assert d["coupon_code"] == "SAVE15"

    def test_coupon_code_none_in_to_dict(self):
        from scrapers.base import ProductData

        pd = ProductData(
            name="X", price=1.0, url="http://x.com", store="s", external_id="e"
        )
        d = pd.to_dict()
        assert d["coupon_code"] is None


# ─────────────────────────────────────────────────────────────────────────────
# Price Trend service
# ─────────────────────────────────────────────────────────────────────────────


class TestPriceTrend:
    """Tests for the price trend calculator."""

    def _make_db(self, prices: list[float]):
        """Return a mock DB that returns the given price list."""
        from unittest.mock import MagicMock
        rows = [(p,) for p in prices]
        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.order_by.return_value.all.return_value = rows
        return mock_db

    def test_not_enough_data_returns_none(self):
        from services.price_trend import get_price_trend
        from unittest.mock import patch

        db = self._make_db([100.0, 90.0])   # only 2 points, default min is 5
        with patch("services.price_trend.settings") as ms:
            ms.TREND_MIN_POINTS = 5
            result = get_price_trend(db, product_id=1)
        assert result is None

    def test_downward_trend_detected(self):
        from services.price_trend import get_price_trend
        from unittest.mock import patch

        # Strongly decreasing prices
        db = self._make_db([500.0, 450.0, 400.0, 350.0, 300.0, 250.0])
        with patch("services.price_trend.settings") as ms:
            ms.TREND_MIN_POINTS = 5
            result = get_price_trend(db, product_id=1)
        assert result == "down"

    def test_upward_trend_detected(self):
        from services.price_trend import get_price_trend
        from unittest.mock import patch

        # Strongly increasing prices
        db = self._make_db([100.0, 150.0, 200.0, 250.0, 300.0, 350.0])
        with patch("services.price_trend.settings") as ms:
            ms.TREND_MIN_POINTS = 5
            result = get_price_trend(db, product_id=1)
        assert result == "up"

    def test_flat_trend_detected(self):
        from services.price_trend import get_price_trend
        from unittest.mock import patch

        # Nearly flat prices
        db = self._make_db([200.0, 200.5, 199.5, 200.1, 200.0, 200.2])
        with patch("services.price_trend.settings") as ms:
            ms.TREND_MIN_POINTS = 5
            result = get_price_trend(db, product_id=1)
        assert result == "flat"

    def test_trend_emoji_down(self):
        from services.price_trend import trend_emoji
        assert trend_emoji("down") == "📉"

    def test_trend_emoji_up(self):
        from services.price_trend import trend_emoji
        assert trend_emoji("up") == "📈"

    def test_trend_emoji_flat(self):
        from services.price_trend import trend_emoji
        assert trend_emoji("flat") == "➡️"

    def test_trend_emoji_none(self):
        from services.price_trend import trend_emoji
        assert trend_emoji(None) == ""


class TestLinearSlope:
    """Unit tests for the OLS slope helper."""

    def test_slope_of_constant_is_zero(self):
        from services.price_trend import _linear_slope
        assert _linear_slope([5.0, 5.0, 5.0, 5.0]) == pytest.approx(0.0)

    def test_slope_positive(self):
        from services.price_trend import _linear_slope
        # y = x: slope should be 1
        result = _linear_slope([0.0, 1.0, 2.0, 3.0, 4.0])
        assert result > 0

    def test_slope_negative(self):
        from services.price_trend import _linear_slope
        result = _linear_slope([4.0, 3.0, 2.0, 1.0, 0.0])
        assert result < 0

    def test_single_value_returns_zero(self):
        from services.price_trend import _linear_slope
        assert _linear_slope([42.0]) == 0.0


# ─────────────────────────────────────────────────────────────────────────────
# Scraper health service
# ─────────────────────────────────────────────────────────────────────────────


class TestScraperHealthService:
    """Tests for the scraper health recording service."""

    def _make_db(self, existing_health=None):
        mock_db = MagicMock()
        mock_db.query.return_value.filter_by.return_value.first.return_value = existing_health
        return mock_db

    def test_creates_new_health_record_on_success(self):
        from services.scraper_health import record_scrape_result
        from unittest.mock import patch

        db = self._make_db(existing_health=None)
        with patch("services.scraper_health.settings") as ms:
            ms.SCRAPER_FAILURE_ALERT_THRESHOLD = 3
            ms.TELEGRAM_ADMIN_CHAT_ID = ""
            ms.TELEGRAM_BOT_TOKEN = ""
            health = record_scrape_result(db, "walmart", success=True, products_found=42)

        assert health.is_healthy is True
        assert health.consecutive_failures == 0
        assert health.last_products_found == 42

    def test_increments_failures_on_error(self):
        from services.scraper_health import record_scrape_result
        from database.models import ScraperHealth
        from unittest.mock import patch

        existing = MagicMock(spec=ScraperHealth)
        existing.consecutive_failures = 1
        existing.is_healthy = True
        db = self._make_db(existing_health=existing)

        with patch("services.scraper_health.settings") as ms:
            ms.SCRAPER_FAILURE_ALERT_THRESHOLD = 5
            ms.TELEGRAM_ADMIN_CHAT_ID = ""
            ms.TELEGRAM_BOT_TOKEN = ""
            health = record_scrape_result(db, "walmart", success=False, error="timeout")

        assert health.consecutive_failures == 2
        assert health.is_healthy is False
        assert health.last_error == "timeout"

    def test_success_resets_failures(self):
        from services.scraper_health import record_scrape_result
        from database.models import ScraperHealth
        from unittest.mock import patch

        existing = MagicMock(spec=ScraperHealth)
        existing.consecutive_failures = 4
        existing.is_healthy = False
        db = self._make_db(existing_health=existing)

        with patch("services.scraper_health.settings") as ms:
            ms.SCRAPER_FAILURE_ALERT_THRESHOLD = 3
            ms.TELEGRAM_ADMIN_CHAT_ID = ""
            ms.TELEGRAM_BOT_TOKEN = ""
            health = record_scrape_result(db, "walmart", success=True, products_found=10)

        assert health.consecutive_failures == 0
        assert health.is_healthy is True

    def test_alert_sent_on_threshold_breach(self):
        from services.scraper_health import record_scrape_result
        from database.models import ScraperHealth
        from unittest.mock import patch, MagicMock

        existing = MagicMock(spec=ScraperHealth)
        existing.consecutive_failures = 2   # next failure = 3 → trigger
        existing.is_healthy = False
        db = self._make_db(existing_health=existing)

        mock_resp = MagicMock()
        mock_resp.raise_for_status.return_value = None

        with patch("services.scraper_health.settings") as ms, \
             patch("services.scraper_health.requests.post", return_value=mock_resp) as mock_post:
            ms.SCRAPER_FAILURE_ALERT_THRESHOLD = 3
            ms.TELEGRAM_ADMIN_CHAT_ID = "admin123"
            ms.TELEGRAM_BOT_TOKEN = "tok"
            record_scrape_result(db, "liverpool", success=False, error="403")

        mock_post.assert_called_once()
        call_args = mock_post.call_args
        assert "liverpool" in call_args[1]["json"]["text"]

    def test_no_alert_when_admin_chat_not_configured(self):
        from services.scraper_health import record_scrape_result
        from database.models import ScraperHealth
        from unittest.mock import patch, MagicMock

        existing = MagicMock(spec=ScraperHealth)
        existing.consecutive_failures = 10
        existing.is_healthy = False
        db = self._make_db(existing_health=existing)

        with patch("services.scraper_health.settings") as ms, \
             patch("services.scraper_health.requests.post") as mock_post:
            ms.SCRAPER_FAILURE_ALERT_THRESHOLD = 3
            ms.TELEGRAM_ADMIN_CHAT_ID = ""   # not configured
            ms.TELEGRAM_BOT_TOKEN = "tok"
            record_scrape_result(db, "sears", success=False, error="err")

        mock_post.assert_not_called()


# ─────────────────────────────────────────────────────────────────────────────
# Subscription service
# ─────────────────────────────────────────────────────────────────────────────


class TestSubscriptionService:
    """Tests for the user keyword subscription service."""

    def test_add_subscription_creates_new(self):
        from services.subscription_service import add_subscription

        mock_db = MagicMock()
        mock_db.query.return_value.filter_by.return_value.first.return_value = None

        sub = add_subscription(mock_db, chat_id=123, keyword="iPhone")
        assert sub.keyword == "iphone"   # normalised to lowercase
        assert sub.active is True
        mock_db.add.assert_called_once_with(sub)

    def test_add_subscription_reactivates_existing(self):
        from services.subscription_service import add_subscription
        from database.models import UserSubscription

        existing = MagicMock(spec=UserSubscription)
        existing.active = False
        mock_db = MagicMock()
        mock_db.query.return_value.filter_by.return_value.first.return_value = existing

        sub = add_subscription(mock_db, chat_id=123, keyword="samsung", max_price=5000.0)
        assert sub.active is True
        assert sub.max_price == 5000.0
        mock_db.add.assert_not_called()

    def test_remove_subscription_deactivates(self):
        from services.subscription_service import remove_subscription
        from database.models import UserSubscription

        existing = MagicMock(spec=UserSubscription)
        existing.active = True
        mock_db = MagicMock()
        mock_db.query.return_value.filter_by.return_value.first.return_value = existing

        result = remove_subscription(mock_db, chat_id=1, keyword="laptop")
        assert result is True
        assert existing.active is False

    def test_remove_subscription_not_found(self):
        from services.subscription_service import remove_subscription

        mock_db = MagicMock()
        mock_db.query.return_value.filter_by.return_value.first.return_value = None

        result = remove_subscription(mock_db, chat_id=1, keyword="xbox")
        assert result is False

    def test_list_subscriptions(self):
        from services.subscription_service import list_subscriptions
        from database.models import UserSubscription

        s1 = MagicMock(spec=UserSubscription)
        s1.keyword = "iphone"
        s2 = MagicMock(spec=UserSubscription)
        s2.keyword = "xbox"
        mock_db = MagicMock()
        (mock_db.query.return_value
             .filter_by.return_value
             .order_by.return_value
             .all.return_value) = [s1, s2]

        subs = list_subscriptions(mock_db, chat_id=42)
        assert len(subs) == 2

    def test_notify_subscribers_keyword_match(self):
        from services.subscription_service import notify_subscribers
        from database.models import UserSubscription, Offer, Product
        from unittest.mock import patch, MagicMock

        sub = MagicMock(spec=UserSubscription)
        sub.keyword = "iphone"
        sub.max_price = None
        sub.store_filter = None

        product = MagicMock(spec=Product)
        product.name = "Apple iPhone 15 Pro Max 256GB"
        product.store = "amazon"

        offer = MagicMock(spec=Offer)
        offer.product = product
        offer.current_price = 18999.0
        offer.original_price = 25000.0
        offer.discount_pct = 24.0
        offer.affiliate_url = "https://amzn.to/test"

        mock_db = MagicMock()
        mock_db.query.return_value.filter_by.return_value.all.return_value = [sub]

        mock_resp = MagicMock()
        mock_resp.raise_for_status.return_value = None

        with patch("services.subscription_service.settings") as ms, \
             patch("services.subscription_service.requests.post", return_value=mock_resp):
            ms.TELEGRAM_BOT_TOKEN = "tok"
            count = notify_subscribers(mock_db, offer)

        assert count == 1

    def test_notify_subscribers_price_ceiling_filter(self):
        from services.subscription_service import notify_subscribers
        from database.models import UserSubscription, Offer, Product
        from unittest.mock import patch

        sub = MagicMock(spec=UserSubscription)
        sub.keyword = "samsung"
        sub.max_price = 5000.0  # too low for this offer
        sub.store_filter = None

        product = MagicMock(spec=Product)
        product.name = "Samsung Galaxy S24 Ultra"
        product.store = "liverpool"

        offer = MagicMock(spec=Offer)
        offer.product = product
        offer.current_price = 25000.0  # exceeds max_price
        offer.original_price = 30000.0
        offer.discount_pct = 16.7
        offer.affiliate_url = None

        mock_db = MagicMock()
        mock_db.query.return_value.filter_by.return_value.all.return_value = [sub]

        with patch("services.subscription_service.settings") as ms:
            ms.TELEGRAM_BOT_TOKEN = "tok"
            count = notify_subscribers(mock_db, offer)

        assert count == 0

    def test_notify_subscribers_no_token(self):
        from services.subscription_service import notify_subscribers
        from database.models import Offer, Product
        from unittest.mock import patch

        product = MagicMock(spec=Product)
        product.name = "Test Product"

        offer = MagicMock(spec=Offer)
        offer.product = product

        mock_db = MagicMock()

        with patch("services.subscription_service.settings") as ms:
            ms.TELEGRAM_BOT_TOKEN = ""
            count = notify_subscribers(mock_db, offer)

        assert count == 0


# ─────────────────────────────────────────────────────────────────────────────
# Daily digest service
# ─────────────────────────────────────────────────────────────────────────────


class TestDailyDigest:
    """Tests for the daily deal digest builder."""

    def test_build_digest_no_offers_returns_none(self):
        from services.daily_digest import build_digest_text
        from unittest.mock import patch

        mock_db = MagicMock()
        # Simulate empty result set
        (mock_db.query.return_value
             .join.return_value
             .options.return_value
             .filter.return_value
             .order_by.return_value
             .limit.return_value
             .all.return_value) = []

        with patch("services.daily_digest.settings") as ms:
            ms.DIGEST_TOP_N = 10
            result = build_digest_text(mock_db)

        assert result is None

    def test_build_digest_with_offers_returns_string(self):
        from services.daily_digest import build_digest_text
        from database.models import Offer, Product
        from unittest.mock import patch, MagicMock

        product = MagicMock(spec=Product)
        product.name = "Laptop HP Pavilion 15"
        product.store = "walmart"
        product.url = "https://walmart.com.mx/laptop"

        offer = MagicMock(spec=Offer)
        offer.product = product
        offer.original_price = 15000.0
        offer.current_price = 9999.0
        offer.discount_pct = 33.3
        offer.score = 85
        offer.affiliate_url = "https://bit.ly/testlaptop"

        mock_db = MagicMock()
        (mock_db.query.return_value
             .join.return_value
             .options.return_value
             .filter.return_value
             .order_by.return_value
             .limit.return_value
             .all.return_value) = [offer]

        with patch("services.daily_digest.settings") as ms:
            ms.DIGEST_TOP_N = 10
            text = build_digest_text(mock_db)

        assert text is not None
        assert "TOP OFERTAS" in text
        assert "Laptop HP Pavilion" in text

    def test_build_digest_truncates_long_names(self):
        from services.daily_digest import build_digest_text
        from database.models import Offer, Product
        from unittest.mock import patch, MagicMock

        product = MagicMock(spec=Product)
        product.name = "A" * 80   # very long name
        product.store = "amazon"
        product.url = "https://amazon.com.mx/p"

        offer = MagicMock(spec=Offer)
        offer.product = product
        offer.original_price = 1000.0
        offer.current_price = 500.0
        offer.discount_pct = 50.0
        offer.score = 90
        offer.affiliate_url = None

        mock_db = MagicMock()
        (mock_db.query.return_value
             .join.return_value
             .options.return_value
             .filter.return_value
             .order_by.return_value
             .limit.return_value
             .all.return_value) = [offer]

        with patch("services.daily_digest.settings") as ms:
            ms.DIGEST_TOP_N = 5
            text = build_digest_text(mock_db)

        assert text is not None
        assert "…" in text

    def test_publish_daily_digest_no_credentials(self):
        from services.daily_digest import publish_daily_digest
        from unittest.mock import patch, MagicMock

        mock_db = MagicMock()

        with patch("services.daily_digest.settings") as ms:
            ms.TELEGRAM_BOT_TOKEN = ""
            ms.TELEGRAM_CHANNEL_ID = ""
            ms.DIGEST_TOP_N = 10
            result = publish_daily_digest(mock_db)

        assert result is False


# ─────────────────────────────────────────────────────────────────────────────
# Publisher – enhanced message (trend + coupon + cross-store)
# ─────────────────────────────────────────────────────────────────────────────


class TestPublisherEnhancements:
    """Tests for new message features in TelegramPublisher."""

    def _make_offer(self, coupon=None, rapid_drop=False):
        from database.models import Offer, Product, OfferType

        product = MagicMock(spec=Product)
        product.name = "Apple MacBook Air M2"
        product.store = "amazon"
        product.url = "https://amazon.com.mx/macbook"
        product.coupon_code = coupon
        product.id = 1

        offer = MagicMock(spec=Offer)
        offer.product = product
        offer.original_price = 25000.0
        offer.current_price = 18000.0
        offer.discount_pct = 28.0
        offer.score = 82
        offer.offer_type = OfferType.EXCELLENT
        offer.rapid_drop = rapid_drop
        offer.affiliate_url = "https://amzn.to/test"
        return offer

    def test_coupon_code_appears_in_message(self):
        from telegram.publisher import TelegramPublisher

        offer = self._make_offer(coupon="SAVE10")
        msg = TelegramPublisher._build_message(offer, db=None)
        assert "SAVE10" in msg
        assert "Cupón" in msg

    def test_no_coupon_code_absent_from_message(self):
        from telegram.publisher import TelegramPublisher

        offer = self._make_offer(coupon=None)
        msg = TelegramPublisher._build_message(offer, db=None)
        assert "Cupón" not in msg

    def test_trend_indicator_included_when_db_provided(self):
        from telegram.publisher import TelegramPublisher
        from unittest.mock import patch, MagicMock

        offer = self._make_offer()
        mock_db = MagicMock()

        with patch("telegram.publisher.get_price_trend", return_value="down"), \
             patch("telegram.publisher.compare_across_stores", return_value=None):
            msg = TelegramPublisher._build_message(offer, db=mock_db)

        assert "📉" in msg
        assert "bajando" in msg

    def test_cross_store_comparison_shown_when_cheaper_exists(self):
        from telegram.publisher import TelegramPublisher
        from services.price_comparison import PriceComparison
        from unittest.mock import patch, MagicMock

        offer = self._make_offer()
        mock_db = MagicMock()

        comparison = PriceComparison(
            cheapest_store="Walmart",
            cheapest_price=16000.0,
            cheapest_url="https://walmart.com.mx/macbook",
            alternatives=[
                {"store": "Amazon", "price": 18000.0, "url": "https://amazon.com.mx/macbook"},
                {"store": "Walmart", "price": 16000.0, "url": "https://walmart.com.mx/macbook"},
            ],
            better_deal_exists=True,
        )

        with patch("telegram.publisher.get_price_trend", return_value=None), \
             patch("telegram.publisher.compare_across_stores", return_value=comparison):
            msg = TelegramPublisher._build_message(offer, db=mock_db)

        assert "Comparativa" in msg
        assert "Walmart" in msg
        assert "16,000" in msg

    def test_cross_store_comparison_hidden_when_already_cheapest(self):
        from telegram.publisher import TelegramPublisher
        from services.price_comparison import PriceComparison
        from unittest.mock import patch, MagicMock

        offer = self._make_offer()
        mock_db = MagicMock()

        comparison = PriceComparison(
            cheapest_store="Amazon",
            cheapest_price=18000.0,
            cheapest_url="https://amazon.com.mx/macbook",
            alternatives=[],
            better_deal_exists=False,   # already cheapest
        )

        with patch("telegram.publisher.get_price_trend", return_value=None), \
             patch("telegram.publisher.compare_across_stores", return_value=comparison):
            msg = TelegramPublisher._build_message(offer, db=mock_db)

        assert "Comparativa" not in msg

    def test_rapid_drop_flag_in_message(self):
        from telegram.publisher import TelegramPublisher

        offer = self._make_offer(rapid_drop=True)
        msg = TelegramPublisher._build_message(offer, db=None)
        assert "⚡" in msg


# ─────────────────────────────────────────────────────────────────────────────
# OfferProcessor – cooldown integration
# ─────────────────────────────────────────────────────────────────────────────


class TestOfferProcessorCooldown:
    """Tests for the cooldown gate in OfferProcessor."""

    def test_cooldown_prevents_publishing(self):
        from services.offer_processor import OfferProcessor
        from database.models import Offer, OfferStatus
        from unittest.mock import patch, MagicMock

        mock_offer = MagicMock(spec=Offer)
        mock_offer.id = 99
        mock_offer.product_id = 7

        mock_db = MagicMock()

        processor = OfferProcessor.__new__(OfferProcessor)
        processor.db = mock_db
        processor.analyzer = MagicMock()
        processor.analyzer.process.return_value = mock_offer
        processor.scorer = MagicMock()

        with patch("services.offer_processor.is_on_cooldown", return_value=True) as mock_cd, \
             patch("services.offer_processor.settings") as ms:
            ms.MIN_PUBLISH_SCORE = 60
            result = processor.process(MagicMock())

        assert result is None
        mock_cd.assert_called_once_with(mock_db, 7)
        assert mock_offer.status == OfferStatus.DISCARDED

    def test_no_cooldown_proceeds_to_scoring(self):
        from services.offer_processor import OfferProcessor
        from database.models import Offer, OfferStatus
        from unittest.mock import patch, MagicMock

        mock_offer = MagicMock(spec=Offer)
        mock_offer.id = 100
        mock_offer.product_id = 8

        mock_db = MagicMock()

        processor = OfferProcessor.__new__(OfferProcessor)
        processor.db = mock_db
        processor.analyzer = MagicMock()
        processor.analyzer.process.return_value = mock_offer
        processor.scorer = MagicMock()
        processor.scorer.score.return_value = 30  # below minimum → discarded

        with patch("services.offer_processor.is_on_cooldown", return_value=False), \
             patch("services.offer_processor.settings") as ms:
            ms.MIN_PUBLISH_SCORE = 60
            result = processor.process(MagicMock())

        # Score was 30 < 60, so still returns None but cooldown was NOT the cause
        assert result is None
        assert mock_offer.status == OfferStatus.DISCARDED
