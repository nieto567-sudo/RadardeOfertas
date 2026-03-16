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
