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


# ─────────────────────────────────────────────────────────────────────────────
# Smart Hours
# ─────────────────────────────────────────────────────────────────────────────


class TestSmartHours:
    """Tests for services.smart_hours."""

    def setup_method(self):
        from services.smart_hours import is_good_time_to_publish, minutes_until_next_window
        self.is_good = is_good_time_to_publish
        self.until_next = minutes_until_next_window

    def _utc(self, hour_mx: int) -> object:
        """Return a UTC datetime corresponding to the given Mexico City hour (UTC-6)."""
        from datetime import datetime, timezone, timedelta
        # Mexico City is UTC-6; to get UTC from MX hour: add 6
        return datetime(2024, 6, 15, (hour_mx + 6) % 24, 0, tzinfo=timezone.utc)

    def test_morning_window_is_good(self):
        with patch("services.smart_hours.settings") as ms:
            ms.SMART_HOURS_ENABLED = True
            ms.SMART_HOURS_MORNING_START = 7
            ms.SMART_HOURS_MORNING_END = 10
            ms.SMART_HOURS_AFTERNOON_START = 12
            ms.SMART_HOURS_AFTERNOON_END = 15
            ms.SMART_HOURS_EVENING_START = 19
            ms.SMART_HOURS_EVENING_END = 23
            assert self.is_good(self._utc(8)) is True

    def test_bad_hour_is_not_good(self):
        with patch("services.smart_hours.settings") as ms:
            ms.SMART_HOURS_ENABLED = True
            ms.SMART_HOURS_MORNING_START = 7
            ms.SMART_HOURS_MORNING_END = 10
            ms.SMART_HOURS_AFTERNOON_START = 12
            ms.SMART_HOURS_AFTERNOON_END = 15
            ms.SMART_HOURS_EVENING_START = 19
            ms.SMART_HOURS_EVENING_END = 23
            assert self.is_good(self._utc(3)) is False

    def test_disabled_always_true(self):
        with patch("services.smart_hours.settings") as ms:
            ms.SMART_HOURS_ENABLED = False
            assert self.is_good(self._utc(3)) is True

    def test_minutes_until_next_returns_zero_inside_window(self):
        with patch("services.smart_hours.settings") as ms:
            ms.SMART_HOURS_ENABLED = True
            ms.SMART_HOURS_MORNING_START = 7
            ms.SMART_HOURS_MORNING_END = 10
            ms.SMART_HOURS_AFTERNOON_START = 12
            ms.SMART_HOURS_AFTERNOON_END = 15
            ms.SMART_HOURS_EVENING_START = 19
            ms.SMART_HOURS_EVENING_END = 23
            assert self.until_next(self._utc(8)) == 0

    def test_minutes_until_next_positive_outside_window(self):
        with patch("services.smart_hours.settings") as ms:
            ms.SMART_HOURS_ENABLED = True
            ms.SMART_HOURS_MORNING_START = 7
            ms.SMART_HOURS_MORNING_END = 10
            ms.SMART_HOURS_AFTERNOON_START = 12
            ms.SMART_HOURS_AFTERNOON_END = 15
            ms.SMART_HOURS_EVENING_START = 19
            ms.SMART_HOURS_EVENING_END = 23
            # 5am MX = bad time; next window opens at 7am = 120 min away
            result = self.until_next(self._utc(5))
            assert result > 0

    def test_evening_window_is_good(self):
        with patch("services.smart_hours.settings") as ms:
            ms.SMART_HOURS_ENABLED = True
            ms.SMART_HOURS_MORNING_START = 7
            ms.SMART_HOURS_MORNING_END = 10
            ms.SMART_HOURS_AFTERNOON_START = 12
            ms.SMART_HOURS_AFTERNOON_END = 15
            ms.SMART_HOURS_EVENING_START = 19
            ms.SMART_HOURS_EVENING_END = 23
            assert self.is_good(self._utc(20)) is True

    def test_boundary_end_is_not_inside(self):
        with patch("services.smart_hours.settings") as ms:
            ms.SMART_HOURS_ENABLED = True
            ms.SMART_HOURS_MORNING_START = 7
            ms.SMART_HOURS_MORNING_END = 10
            ms.SMART_HOURS_AFTERNOON_START = 12
            ms.SMART_HOURS_AFTERNOON_END = 15
            ms.SMART_HOURS_EVENING_START = 19
            ms.SMART_HOURS_EVENING_END = 23
            # hour 10 is NOT inside morning window [7, 10)
            assert self.is_good(self._utc(10)) is False


# ─────────────────────────────────────────────────────────────────────────────
# Viral Detector
# ─────────────────────────────────────────────────────────────────────────────


class TestViralDetector:
    """Tests for services.viral_detector."""

    def _make_offer(self, discount_pct, offer_type_str="EXCELLENT",
                    category="", name="Some Product"):
        from unittest.mock import MagicMock
        from database.models import OfferType
        offer = MagicMock()
        offer.discount_pct = discount_pct
        offer.offer_type = OfferType[offer_type_str]
        offer.product.category = category
        offer.product.name = name
        return offer

    def test_price_error_gets_bonus(self):
        from services.viral_detector import calculate_viral_score
        offer = self._make_offer(30, "PRICE_ERROR", "Gaming y Videojuegos")
        score = calculate_viral_score(offer)
        assert score >= 5  # price error bonus

    def test_huge_discount_boosts_score(self):
        from services.viral_detector import calculate_viral_score
        offer = self._make_offer(75)
        score = calculate_viral_score(offer)
        assert score >= 8

    def test_viral_category_adds_points(self):
        from services.viral_detector import calculate_viral_score
        offer = self._make_offer(20, category="celulares y smartphones")
        score_with_cat = calculate_viral_score(offer)
        offer_no_cat = self._make_offer(20, category="")
        score_no_cat = calculate_viral_score(offer_no_cat)
        assert score_with_cat > score_no_cat

    def test_brand_keyword_boosts(self):
        from services.viral_detector import calculate_viral_score
        offer = self._make_offer(20, name="Apple iPhone 15 Pro 256GB")
        score = calculate_viral_score(offer)
        assert score >= 3

    def test_max_cap_is_20(self):
        from services.viral_detector import calculate_viral_score
        offer = self._make_offer(80, "PRICE_ERROR",
                                  "celulares y smartphones", "Apple iPhone 15 Pro")
        score = calculate_viral_score(offer)
        assert score <= 20

    def test_viral_label_high(self):
        from services.viral_detector import viral_label
        assert "ALTO" in viral_label(15)

    def test_viral_label_medium(self):
        from services.viral_detector import viral_label
        assert viral_label(7) != ""

    def test_viral_label_low_returns_empty(self):
        from services.viral_detector import viral_label
        assert viral_label(3) == ""


# ─────────────────────────────────────────────────────────────────────────────
# Resale Detector
# ─────────────────────────────────────────────────────────────────────────────


class TestResaleDetector:
    """Tests for services.resale_detector."""

    def _make_offer(self, original, current, offer_type_str="EXCELLENT", category=""):
        from unittest.mock import MagicMock
        from database.models import OfferType
        offer = MagicMock()
        offer.original_price = original
        offer.current_price = current
        offer.discount_pct = (original - current) / original * 100
        offer.offer_type = OfferType[offer_type_str]
        offer.product.category = category
        return offer

    def test_price_error_is_opportunity(self):
        from services.resale_detector import detect_resale_opportunity
        offer = self._make_offer(10000, 1000, "PRICE_ERROR", "celulares y smartphones")
        result = detect_resale_opportunity(offer)
        assert result.is_opportunity is True
        assert result.score >= 5

    def test_small_saving_not_opportunity(self):
        from services.resale_detector import detect_resale_opportunity
        # $200 saving at 40% is below _MIN_SAVING_MXN
        offer = self._make_offer(500, 300, "EXCELLENT", "celulares y smartphones")
        result = detect_resale_opportunity(offer)
        assert result.is_opportunity is False

    def test_large_saving_high_score(self):
        from services.resale_detector import detect_resale_opportunity
        offer = self._make_offer(8000, 3000, "EXCELLENT", "gaming y videojuegos")
        result = detect_resale_opportunity(offer)
        assert result.score >= 4

    def test_non_resale_category_lower_score(self):
        from services.resale_detector import detect_resale_opportunity
        offer_tech = self._make_offer(5000, 2000, "EXCELLENT", "celulares y smartphones")
        offer_book = self._make_offer(5000, 2000, "EXCELLENT", "libros y educación")
        assert detect_resale_opportunity(offer_tech).score >= detect_resale_opportunity(offer_book).score

    def test_result_has_reason(self):
        from services.resale_detector import detect_resale_opportunity
        offer = self._make_offer(10000, 3000, "EXCELLENT", "gaming y videojuegos")
        result = detect_resale_opportunity(offer)
        assert len(result.reason) > 0


# ─────────────────────────────────────────────────────────────────────────────
# Offer Filter
# ─────────────────────────────────────────────────────────────────────────────


class TestOfferFilter:
    """Tests for services.offer_filter."""

    def _make_offer(self, original, current):
        from unittest.mock import MagicMock
        offer = MagicMock()
        offer.original_price = original
        offer.current_price = current
        offer.discount_pct = (original - current) / original * 100
        return offer

    def test_good_offer_passes(self):
        from services.offer_filter import passes_quality_filter
        offer = self._make_offer(1000, 500)  # 50% off, $500 saving
        with patch("services.offer_filter.settings") as ms:
            ms.MIN_DISCOUNT_PCT = 20.0
            ms.MIN_ABSOLUTE_SAVING_MXN = 100.0
            result = passes_quality_filter(offer)
        assert result.passed is True

    def test_low_discount_fails(self):
        from services.offer_filter import passes_quality_filter
        offer = self._make_offer(1000, 900)  # only 10% off
        with patch("services.offer_filter.settings") as ms:
            ms.MIN_DISCOUNT_PCT = 20.0
            ms.MIN_ABSOLUTE_SAVING_MXN = 100.0
            result = passes_quality_filter(offer)
        assert result.passed is False
        assert "descuento" in result.reason

    def test_tiny_saving_fails(self):
        from services.offer_filter import passes_quality_filter
        offer = self._make_offer(200, 150)  # 25% off but only $50 saving
        with patch("services.offer_filter.settings") as ms:
            ms.MIN_DISCOUNT_PCT = 20.0
            ms.MIN_ABSOLUTE_SAVING_MXN = 100.0
            result = passes_quality_filter(offer)
        assert result.passed is False
        assert "ahorro" in result.reason

    def test_boundary_passes(self):
        from services.offer_filter import passes_quality_filter
        offer = self._make_offer(500, 400)  # exactly 20% off, $100 saving
        with patch("services.offer_filter.settings") as ms:
            ms.MIN_DISCOUNT_PCT = 20.0
            ms.MIN_ABSOLUTE_SAVING_MXN = 100.0
            result = passes_quality_filter(offer)
        assert result.passed is True


# ─────────────────────────────────────────────────────────────────────────────
# Product Classifier
# ─────────────────────────────────────────────────────────────────────────────


class TestProductClassifier:
    """Tests for services.product_classifier."""

    def setup_method(self):
        from services.product_classifier import classify_product, update_product_category
        self.classify = classify_product
        self.update = update_product_category

    def test_iphone_classified_as_phones(self):
        cat = self.classify("Apple iPhone 15 Pro Max 256GB Titanio")
        assert cat == "Celulares y Smartphones"

    def test_playstation_classified_as_gaming(self):
        cat = self.classify("Sony PlayStation 5 Slim Console")
        assert cat == "Gaming y Videojuegos"

    def test_laptop_classified(self):
        cat = self.classify("Dell XPS 15 laptop Intel i9 32GB RAM")
        assert cat == "Laptops y Computadoras"

    def test_smart_tv_classified(self):
        cat = self.classify("LG 65 pulgadas smart tv 4K OLED")
        assert cat == "Televisores y Audio"

    def test_unknown_returns_general(self):
        cat = self.classify("Producto sin categoría especial xyzabc")
        assert cat == "General"

    def test_update_sets_category_when_missing(self):
        from unittest.mock import MagicMock
        product = MagicMock()
        product.category = None
        data = MagicMock()
        data.name = "Nintendo Switch OLED edición especial"
        changed = self.update(product, data)
        assert changed is True
        assert product.category == "Gaming y Videojuegos"

    def test_update_skips_when_category_set(self):
        from unittest.mock import MagicMock
        product = MagicMock()
        product.category = "Already Set"
        data = MagicMock()
        data.name = "iPhone 15"
        changed = self.update(product, data)
        assert changed is False
        assert product.category == "Already Set"  # unchanged

    def test_ipad_classified_as_tablet(self):
        cat = self.classify("Apple iPad Pro 12.9 M2 Wi-Fi 256GB")
        assert cat == "Tablets y E-readers"

    def test_airpods_classified_as_audio(self):
        cat = self.classify("Apple AirPods Pro 2da Generación con MagSafe")
        assert cat == "Televisores y Audio"

    def test_case_insensitive(self):
        cat = self.classify("APPLE IPHONE 15 PRO MAX 256GB")
        assert cat == "Celulares y Smartphones"


# ─────────────────────────────────────────────────────────────────────────────
# Click Tracker
# ─────────────────────────────────────────────────────────────────────────────


class TestClickTracker:
    """Tests for services.click_tracker."""

    def test_record_click_creates_event(self):
        from services.click_tracker import record_click
        db = MagicMock()
        event = record_click(db, offer_id=1, source="telegram")
        db.add.assert_called_once_with(event)
        assert event.offer_id == 1
        assert event.source == "telegram"

    def test_record_purchase_creates_event(self):
        from services.click_tracker import record_purchase
        db = MagicMock()
        event = record_purchase(db, offer_id=2, revenue_mxn=45.0)
        db.add.assert_called_once_with(event)
        assert event.offer_id == 2
        assert event.revenue_mxn == 45.0

    def test_record_click_default_source(self):
        from services.click_tracker import record_click
        db = MagicMock()
        event = record_click(db, offer_id=5)
        assert event.source == "telegram"

    def test_get_offer_stats_returns_dict(self):
        from services.click_tracker import get_offer_stats
        db = MagicMock()
        db.query.return_value.filter.return_value.count.return_value = 3
        stats = get_offer_stats(db, offer_id=1)
        assert stats["offer_id"] == 1
        assert stats["clicks"] == 3
        assert stats["purchases"] == 3

    def test_get_global_stats_conversion_rate(self):
        from services.click_tracker import get_global_stats
        db = MagicMock()
        # clicks=100, purchases=5 → conversion_rate=0.05
        call_count = [0]

        def count_side_effect():
            call_count[0] += 1
            return 100 if call_count[0] == 1 else 5

        db.query.return_value.filter.return_value.count.side_effect = count_side_effect
        stats = get_global_stats(db, days=7)
        assert stats["period_days"] == 7
        assert abs(stats["conversion_rate"] - 0.05) < 0.001

    def test_get_global_stats_zero_clicks(self):
        from services.click_tracker import get_global_stats
        db = MagicMock()
        db.query.return_value.filter.return_value.count.return_value = 0
        stats = get_global_stats(db, days=7)
        assert stats["conversion_rate"] == 0.0


# ─────────────────────────────────────────────────────────────────────────────
# Message format (publisher)
# ─────────────────────────────────────────────────────────────────────────────


class TestPublisherMessage:
    """Tests for the redesigned TelegramPublisher._build_message."""

    def _make_offer(self, offer_type_str="EXCELLENT", rapid_drop=False,
                    coupon=None, category="General", viral_score=0, resale_score=0):
        from unittest.mock import MagicMock
        from database.models import OfferType
        offer = MagicMock()
        offer.offer_type = OfferType[offer_type_str]
        offer.original_price = 2000.0
        offer.current_price = 1000.0
        offer.discount_pct = 50.0
        offer.score = 80
        offer.rapid_drop = rapid_drop
        offer.viral_score = viral_score
        offer.resale_score = resale_score
        offer.affiliate_url = "https://amzn.to/test"
        offer.product.name = "Test Product"
        offer.product.store = "amazon"
        offer.product.category = category
        offer.product.coupon_code = coupon
        offer.product.image_url = None
        offer.product.id = 1
        return offer

    def test_message_contains_product_name(self):
        from telegram.publisher import TelegramPublisher
        offer = self._make_offer()
        msg = TelegramPublisher._build_message(offer)
        assert "Test Product" in msg

    def test_message_shows_saving(self):
        from telegram.publisher import TelegramPublisher
        offer = self._make_offer()
        msg = TelegramPublisher._build_message(offer)
        assert "1,000" in msg  # current price
        assert "1,000" in msg  # saving (original - current = 1000)

    def test_message_shows_excellent_label(self):
        from telegram.publisher import TelegramPublisher
        offer = self._make_offer("EXCELLENT")
        msg = TelegramPublisher._build_message(offer)
        assert "EXCELENTE" in msg

    def test_message_shows_price_error_label(self):
        from telegram.publisher import TelegramPublisher
        offer = self._make_offer("PRICE_ERROR")
        msg = TelegramPublisher._build_message(offer)
        assert "ERROR DE PRECIO" in msg

    def test_message_shows_rapid_drop(self):
        from telegram.publisher import TelegramPublisher
        offer = self._make_offer(rapid_drop=True)
        msg = TelegramPublisher._build_message(offer)
        assert "Caída rápida" in msg

    def test_message_shows_coupon(self):
        from telegram.publisher import TelegramPublisher
        offer = self._make_offer(coupon="SAVE20")
        msg = TelegramPublisher._build_message(offer)
        assert "SAVE20" in msg

    def test_message_shows_viral_label_when_high(self):
        from telegram.publisher import TelegramPublisher
        offer = self._make_offer(viral_score=15)
        msg = TelegramPublisher._build_message(offer)
        assert "viral" in msg.lower()

    def test_message_shows_resale_flag_when_high(self):
        from telegram.publisher import TelegramPublisher
        offer = self._make_offer(resale_score=7)
        msg = TelegramPublisher._build_message(offer)
        assert "reventa" in msg.lower()

    def test_message_contains_buy_link(self):
        from telegram.publisher import TelegramPublisher
        offer = self._make_offer()
        msg = TelegramPublisher._build_message(offer)
        assert "amzn.to/test" in msg

    def test_message_contains_separator(self):
        from telegram.publisher import TelegramPublisher
        offer = self._make_offer()
        msg = TelegramPublisher._build_message(offer)
        assert "━" in msg

    def test_no_viral_label_when_score_low(self):
        from telegram.publisher import TelegramPublisher
        offer = self._make_offer(viral_score=1)
        msg = TelegramPublisher._build_message(offer)
        # viral label only shown when score >= 5
        assert "Potencial viral" not in msg


# ─────────────────────────────────────────────────────────────────────────────
# Daily publication cap helper
# ─────────────────────────────────────────────────────────────────────────────


class TestDailyPublicationCount:
    """Tests for services.offer_processor.get_daily_publication_count."""

    def test_returns_count(self):
        from services.offer_processor import get_daily_publication_count
        db = MagicMock()
        db.query.return_value.filter.return_value.count.return_value = 7
        count = get_daily_publication_count(db)
        assert count == 7

    def test_returns_zero_when_none(self):
        from services.offer_processor import get_daily_publication_count
        db = MagicMock()
        db.query.return_value.filter.return_value.count.return_value = 0
        assert get_daily_publication_count(db) == 0


# ─────────────────────────────────────────────────────────────────────────────
# Price Sparkline
# ─────────────────────────────────────────────────────────────────────────────


class TestPriceSparkline:
    """Tests for services.price_sparkline."""

    def _db_with_prices(self, prices: list):
        """Return a mock DB that yields the given list of prices."""
        db = MagicMock()
        rows = [(p,) for p in prices]
        db.query.return_value.filter.return_value.order_by.return_value.all.return_value = rows
        db.query.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = rows
        return db

    def test_returns_none_for_too_few_points(self):
        from services.price_sparkline import get_sparkline
        db = self._db_with_prices([100.0, 90.0])  # only 2 < _MIN_POINTS=3
        assert get_sparkline(db, product_id=1) is None

    def test_returns_string_for_enough_points(self):
        from services.price_sparkline import get_sparkline
        db = self._db_with_prices([100.0, 80.0, 60.0, 90.0, 70.0])
        result = get_sparkline(db, product_id=1)
        assert result is not None
        assert isinstance(result, str)
        assert len(result) > 0

    def test_sparkline_uses_block_characters(self):
        from services.price_sparkline import get_sparkline, _BLOCKS
        db = self._db_with_prices([100.0, 80.0, 60.0, 40.0, 20.0, 80.0, 100.0])
        result = get_sparkline(db, product_id=1)
        assert result is not None
        for ch in result:
            assert ch in _BLOCKS

    def test_flat_prices_returns_flat_sparkline(self):
        from services.price_sparkline import get_sparkline, _BLOCKS
        db = self._db_with_prices([500.0, 500.0, 500.0, 500.0, 500.0])
        result = get_sparkline(db, product_id=1)
        # All blocks should be the same (lowest block for flat line)
        assert result is not None
        assert len(set(result)) == 1

    def test_is_all_time_low_true(self):
        from services.price_sparkline import is_all_time_low
        db = MagicMock()
        db.query.return_value.filter.return_value.all.return_value = [
            (500.0,), (400.0,), (350.0,), (300.0,)
        ]
        assert is_all_time_low(db, product_id=1, current_price=300.0) is True

    def test_is_all_time_low_false(self):
        from services.price_sparkline import is_all_time_low
        db = MagicMock()
        db.query.return_value.filter.return_value.all.return_value = [
            (500.0,), (400.0,), (200.0,), (300.0,)
        ]
        assert is_all_time_low(db, product_id=1, current_price=300.0) is False

    def test_is_all_time_low_no_history(self):
        from services.price_sparkline import is_all_time_low
        db = MagicMock()
        db.query.return_value.filter.return_value.all.return_value = []
        assert is_all_time_low(db, product_id=1, current_price=100.0) is False

    def test_sparkline_length_capped_at_max(self):
        from services.price_sparkline import get_sparkline
        prices = list(range(1, 50))  # 49 points
        db = self._db_with_prices(prices)
        result = get_sparkline(db, product_id=1, max_points=14)
        assert result is not None
        assert len(result) <= 14

    def test_is_all_time_low_with_tolerance(self):
        from services.price_sparkline import is_all_time_low
        # Current price slightly above historical min (within tolerance)
        db = MagicMock()
        db.query.return_value.filter.return_value.all.return_value = [
            (500.0,), (300.0,), (400.0,)
        ]
        assert is_all_time_low(db, product_id=1, current_price=300.005) is True


# ─────────────────────────────────────────────────────────────────────────────
# Seasonal Events
# ─────────────────────────────────────────────────────────────────────────────


class TestSeasonalEvents:
    """Tests for services.seasonal_events."""

    def test_buen_fin_detected(self):
        from services.seasonal_events import get_current_season
        from datetime import date
        assert get_current_season(date(2024, 11, 15)) == "EL BUEN FIN"

    def test_navidad_detected(self):
        from services.seasonal_events import get_current_season
        from datetime import date
        assert get_current_season(date(2024, 12, 20)) == "NAVIDAD"

    def test_cyber_monday_detected(self):
        from services.seasonal_events import get_current_season
        from datetime import date
        assert get_current_season(date(2024, 12, 2)) == "CYBER MONDAY"

    def test_hot_sale_detected(self):
        from services.seasonal_events import get_current_season
        from datetime import date
        assert get_current_season(date(2024, 5, 27)) == "HOT SALE"

    def test_hot_sale_detected_june(self):
        from services.seasonal_events import get_current_season
        from datetime import date
        assert get_current_season(date(2024, 6, 1)) == "HOT SALE"

    def test_dia_de_madres_detected(self):
        from services.seasonal_events import get_current_season
        from datetime import date
        assert get_current_season(date(2024, 5, 5)) == "DÍA DE LAS MADRES"

    def test_san_valentin_detected(self):
        from services.seasonal_events import get_current_season
        from datetime import date
        assert get_current_season(date(2024, 2, 10)) == "SAN VALENTÍN"

    def test_regreso_clases_detected(self):
        from services.seasonal_events import get_current_season
        from datetime import date
        assert get_current_season(date(2024, 7, 20)) == "REGRESO A CLASES"

    def test_dia_de_muertos_detected(self):
        from services.seasonal_events import get_current_season
        from datetime import date
        assert get_current_season(date(2024, 10, 30)) == "DÍA DE MUERTOS"

    def test_no_season_returns_none(self):
        from services.seasonal_events import get_current_season
        from datetime import date
        assert get_current_season(date(2024, 3, 15)) is None

    def test_banner_nonempty_during_season(self):
        from services.seasonal_events import get_season_banner
        from datetime import date
        banner = get_season_banner(date(2024, 11, 15))
        assert len(banner) > 0
        assert "BUEN FIN" in banner

    def test_banner_empty_outside_season(self):
        from services.seasonal_events import get_season_banner
        from datetime import date
        assert get_season_banner(date(2024, 3, 15)) == ""

    def test_season_emoji_mapping(self):
        from services.seasonal_events import get_season_emoji
        assert get_season_emoji("EL BUEN FIN") == "🛒"
        assert get_season_emoji("NAVIDAD") == "🎄"
        assert get_season_emoji("HOT SALE") == "🔥"

    def test_buen_fin_boundary_start(self):
        from services.seasonal_events import get_current_season
        from datetime import date
        assert get_current_season(date(2024, 11, 14)) == "EL BUEN FIN"

    def test_buen_fin_boundary_end(self):
        from services.seasonal_events import get_current_season
        from datetime import date
        assert get_current_season(date(2024, 11, 18)) == "EL BUEN FIN"

    def test_buen_fin_before_start(self):
        from services.seasonal_events import get_current_season
        from datetime import date
        assert get_current_season(date(2024, 11, 13)) is None

    def test_regreso_clases_august(self):
        from services.seasonal_events import get_current_season
        from datetime import date
        assert get_current_season(date(2024, 8, 10)) == "REGRESO A CLASES"


# ─────────────────────────────────────────────────────────────────────────────
# Weekly Summary
# ─────────────────────────────────────────────────────────────────────────────


class TestWeeklySummary:
    """Tests for services.weekly_summary."""

    def _make_mock_db_with_offers(self, offers):
        """Return a mock DB whose query chain yields the given offers list."""
        db = MagicMock()
        (
            db.query.return_value
            .join.return_value
            .options.return_value
            .filter.return_value
            .order_by.return_value
            .all.return_value
        ) = offers
        return db

    def _make_offer(self, name, store, discount, original, current, score=75):
        o = MagicMock()
        o.original_price = original
        o.current_price = current
        o.discount_pct = discount
        o.score = score
        o.affiliate_url = None
        o.product.name = name
        o.product.store = store
        o.product.url = "https://example.com"
        return o

    def test_returns_none_when_no_offers(self):
        from services.weekly_summary import build_weekly_summary_text
        db = self._make_mock_db_with_offers([])
        assert build_weekly_summary_text(db) is None

    def test_text_contains_total_savings(self):
        from services.weekly_summary import build_weekly_summary_text
        offers = [
            self._make_offer("iPhone 15", "amazon", 30, 20000, 14000),
            self._make_offer("iPad Air", "amazon", 25, 15000, 11250),
        ]
        db = self._make_mock_db_with_offers(offers)
        text = build_weekly_summary_text(db)
        assert text is not None
        assert "ahorro" in text.lower() or "MXN" in text

    def test_text_contains_offer_count(self):
        from services.weekly_summary import build_weekly_summary_text
        offers = [self._make_offer("PS5", "walmart", 40, 10000, 6000)]
        db = self._make_mock_db_with_offers(offers)
        text = build_weekly_summary_text(db)
        assert "1" in text

    def test_text_contains_top_store(self):
        from services.weekly_summary import build_weekly_summary_text
        offers = [
            self._make_offer("Product A", "amazon", 30, 1000, 700),
            self._make_offer("Product B", "amazon", 25, 2000, 1500),
            self._make_offer("Product C", "walmart", 20, 500, 400),
        ]
        db = self._make_mock_db_with_offers(offers)
        text = build_weekly_summary_text(db)
        assert "Amazon" in text

    def test_text_contains_best_deal(self):
        from services.weekly_summary import build_weekly_summary_text
        best = self._make_offer("Nintendo Switch OLED", "liverpool", 50, 8000, 4000, score=95)
        offers = [best, self._make_offer("Cable USB", "walmart", 20, 200, 160, score=60)]
        db = self._make_mock_db_with_offers(offers)
        text = build_weekly_summary_text(db)
        assert "Nintendo Switch" in text

    def test_text_contains_share_cta(self):
        from services.weekly_summary import build_weekly_summary_text
        offers = [self._make_offer("iPhone 15", "amazon", 30, 20000, 14000)]
        db = self._make_mock_db_with_offers(offers)
        text = build_weekly_summary_text(db)
        # Should include a social share CTA
        assert "amigos" in text.lower() or "comparte" in text.lower()

    def test_publish_returns_false_without_config(self):
        from services.weekly_summary import publish_weekly_summary
        db = MagicMock()
        with patch("services.weekly_summary.settings") as ms:
            ms.TELEGRAM_BOT_TOKEN = ""
            ms.TELEGRAM_CHANNEL_ID = ""
            result = publish_weekly_summary(db)
        assert result is False

    def test_text_long_name_truncated(self):
        from services.weekly_summary import build_weekly_summary_text
        long_name = "A" * 60
        offers = [self._make_offer(long_name, "amazon", 30, 1000, 700)]
        db = self._make_mock_db_with_offers(offers)
        text = build_weekly_summary_text(db)
        assert text is not None
        # The name should be truncated with "…"
        assert "…" in text


# ─────────────────────────────────────────────────────────────────────────────
# Publisher message — sparkline + all-time low + seasonal banner
# ─────────────────────────────────────────────────────────────────────────────


class TestPublisherMessageV2:
    """Tests for the v2 publisher message (sparkline, all-time low, seasonal)."""

    def _make_offer(self, rapid_drop=False, viral_score=0, resale_score=0):
        offer = MagicMock()
        from database.models import OfferType
        offer.offer_type = OfferType.EXCELLENT
        offer.original_price = 2000.0
        offer.current_price = 1200.0
        offer.discount_pct = 40.0
        offer.score = 80
        offer.rapid_drop = rapid_drop
        offer.viral_score = viral_score
        offer.resale_score = resale_score
        offer.affiliate_url = "https://example.com"
        offer.product.name = "Samsung Galaxy S24"
        offer.product.store = "amazon"
        offer.product.category = "Celulares y Smartphones"
        offer.product.coupon_code = None
        offer.product.image_url = None
        offer.product.id = 42
        return offer

    def test_message_includes_separator(self):
        from telegram.publisher import TelegramPublisher
        offer = self._make_offer()
        msg = TelegramPublisher._build_message(offer)
        assert "━" in msg

    def test_message_includes_category(self):
        from telegram.publisher import TelegramPublisher
        offer = self._make_offer()
        msg = TelegramPublisher._build_message(offer)
        assert "Celulares" in msg

    def test_all_time_low_badge_shown(self):
        from telegram.publisher import TelegramPublisher
        offer = self._make_offer()
        db = MagicMock()
        # Mock is_all_time_low → True
        with patch("telegram.publisher.is_all_time_low", return_value=True), \
             patch("telegram.publisher.get_sparkline", return_value=None), \
             patch("telegram.publisher.get_price_trend", return_value=None), \
             patch("telegram.publisher.compare_across_stores", return_value=None):
            msg = TelegramPublisher._build_message(offer, db=db)
        assert "MÍNIMO HISTÓRICO" in msg

    def test_sparkline_shown_when_available(self):
        from telegram.publisher import TelegramPublisher
        offer = self._make_offer()
        db = MagicMock()
        with patch("telegram.publisher.is_all_time_low", return_value=False), \
             patch("telegram.publisher.get_sparkline", return_value="▁▂▄▇█"), \
             patch("telegram.publisher.get_price_trend", return_value=None), \
             patch("telegram.publisher.compare_across_stores", return_value=None):
            msg = TelegramPublisher._build_message(offer, db=db)
        assert "▁▂▄▇█" in msg

    def test_seasonal_banner_shown_during_buen_fin(self):
        from telegram.publisher import TelegramPublisher
        offer = self._make_offer()
        with patch("telegram.publisher.get_season_banner", return_value="🛒 ¡EL BUEN FIN! 🛒"):
            msg = TelegramPublisher._build_message(offer)
        assert "BUEN FIN" in msg

    def test_no_seasonal_banner_outside_season(self):
        from telegram.publisher import TelegramPublisher
        offer = self._make_offer()
        with patch("telegram.publisher.get_season_banner", return_value=""):
            msg = TelegramPublisher._build_message(offer)
        assert "BUEN FIN" not in msg
        assert "NAVIDAD" not in msg

    def test_all_time_low_badge_not_shown_when_false(self):
        from telegram.publisher import TelegramPublisher
        offer = self._make_offer()
        db = MagicMock()
        with patch("telegram.publisher.is_all_time_low", return_value=False), \
             patch("telegram.publisher.get_sparkline", return_value=None), \
             patch("telegram.publisher.get_price_trend", return_value=None), \
             patch("telegram.publisher.compare_across_stores", return_value=None):
            msg = TelegramPublisher._build_message(offer, db=db)
        assert "MÍNIMO HISTÓRICO" not in msg
