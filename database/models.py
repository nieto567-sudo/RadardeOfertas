"""
SQLAlchemy ORM models for RadardeOfertas.

Tables
------
* products        – master catalogue of tracked products
* price_history   – every price observation for each product
* offers          – detected deals with their score
* publications    – telegram messages that have been sent
"""
from __future__ import annotations

import enum
from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    Column,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import relationship

from database.connection import Base


# ── Enums ─────────────────────────────────────────────────────────────────────


class OfferType(str, enum.Enum):
    PRICE_ERROR = "price_error"
    EXCELLENT = "excellent"
    GOOD = "good"
    REGULAR = "regular"


class OfferStatus(str, enum.Enum):
    PENDING = "pending"
    PUBLISHED = "published"
    DISCARDED = "discarded"


# ── Models ────────────────────────────────────────────────────────────────────


class Product(Base):
    """A product tracked across one or more stores."""

    __tablename__ = "products"

    id = Column(Integer, primary_key=True, index=True)
    external_id = Column(String(512), nullable=False)
    store = Column(String(64), nullable=False)
    name = Column(String(512), nullable=False)
    url = Column(Text, nullable=False)
    image_url = Column(Text, nullable=True)
    category = Column(String(128), nullable=True)
    current_price = Column(Float, nullable=True)
    available = Column(Boolean, default=True)
    coupon_code = Column(String(64), nullable=True)
    # SHA-256 fingerprint for deduplication (normalised title ± store)
    fingerprint = Column(String(64), nullable=True, index=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    price_history = relationship(
        "PriceHistory", back_populates="product", cascade="all, delete-orphan"
    )
    offers = relationship(
        "Offer", back_populates="product", cascade="all, delete-orphan"
    )

    __table_args__ = (
        UniqueConstraint("external_id", "store", name="uq_product_external_store"),
        Index("ix_product_store", "store"),
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Product id={self.id} store={self.store} name={self.name!r}>"


class PriceHistory(Base):
    """One price observation for a product at a specific point in time."""

    __tablename__ = "price_history"

    id = Column(BigInteger, primary_key=True, index=True)
    product_id = Column(
        Integer, ForeignKey("products.id", ondelete="CASCADE"), nullable=False
    )
    price = Column(Float, nullable=False)
    available = Column(Boolean, default=True)
    recorded_at = Column(DateTime, server_default=func.now(), index=True)

    product = relationship("Product", back_populates="price_history")

    __table_args__ = (Index("ix_price_history_product_recorded", "product_id", "recorded_at"),)

    def __repr__(self) -> str:  # pragma: no cover
        return f"<PriceHistory product_id={self.product_id} price={self.price}>"


class Offer(Base):
    """A detected deal linked to a product."""

    __tablename__ = "offers"

    id = Column(Integer, primary_key=True, index=True)
    product_id = Column(
        Integer, ForeignKey("products.id", ondelete="CASCADE"), nullable=False
    )
    current_price = Column(Float, nullable=False)
    original_price = Column(Float, nullable=False)
    discount_pct = Column(Float, nullable=False)  # e.g. 73.0 for 73 %
    score = Column(Integer, nullable=False)
    offer_type = Column(Enum(OfferType), nullable=False)
    status = Column(Enum(OfferStatus), default=OfferStatus.PENDING, nullable=False)
    rapid_drop = Column(Boolean, default=False)
    # Supplementary scores computed after the main scorer
    viral_score = Column(Integer, default=0, nullable=False)
    resale_score = Column(Integer, default=0, nullable=False)
    detected_at = Column(DateTime, server_default=func.now(), index=True)
    # Offer expires if still PENDING after this deadline
    publication_deadline = Column(DateTime, nullable=True)
    affiliate_url = Column(Text, nullable=True)

    product = relationship("Product", back_populates="offers")
    publication = relationship(
        "Publication", back_populates="offer", uselist=False
    )

    __table_args__ = (Index("ix_offers_status_score", "status", "score"),)

    def __repr__(self) -> str:  # pragma: no cover
        return (
            f"<Offer id={self.id} product_id={self.product_id} "
            f"score={self.score} type={self.offer_type}>"
        )


class Publication(Base):
    """Record of a Telegram message sent for an offer."""

    __tablename__ = "publications"

    id = Column(Integer, primary_key=True, index=True)
    offer_id = Column(
        Integer, ForeignKey("offers.id", ondelete="CASCADE"), unique=True, nullable=False
    )
    telegram_message_id = Column(BigInteger, nullable=True)
    sent_at = Column(DateTime, server_default=func.now())
    success = Column(Boolean, default=True)
    error_message = Column(Text, nullable=True)

    offer = relationship("Offer", back_populates="publication")

    def __repr__(self) -> str:  # pragma: no cover
        return (
            f"<Publication id={self.id} offer_id={self.offer_id} "
            f"success={self.success}>"
        )


class ScraperHealth(Base):
    """Tracks the operational health of each scraper."""

    __tablename__ = "scraper_health"

    id = Column(Integer, primary_key=True, index=True)
    store = Column(String(64), nullable=False, unique=True, index=True)
    consecutive_failures = Column(Integer, default=0, nullable=False)
    last_success_at = Column(DateTime, nullable=True)
    last_products_found = Column(Integer, nullable=True)
    last_error = Column(Text, nullable=True)
    is_healthy = Column(Boolean, default=True, nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    def __repr__(self) -> str:  # pragma: no cover
        return (
            f"<ScraperHealth store={self.store!r} "
            f"healthy={self.is_healthy} failures={self.consecutive_failures}>"
        )


class UserSubscription(Base):
    """
    A user's keyword subscription.

    When an offer is detected whose product name contains *keyword*, the user
    with *chat_id* receives a personal Telegram DM.
    """

    __tablename__ = "user_subscriptions"

    id = Column(Integer, primary_key=True, index=True)
    chat_id = Column(BigInteger, nullable=False, index=True)
    keyword = Column(String(256), nullable=False)
    # Optional upper-price ceiling (MXN).  NULL = no price limit.
    max_price = Column(Float, nullable=True)
    # Optional store filter.  NULL = all stores.
    store_filter = Column(String(64), nullable=True)
    active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, server_default=func.now())

    __table_args__ = (
        UniqueConstraint("chat_id", "keyword", name="uq_subscription_chat_keyword"),
        Index("ix_subscription_active", "active"),
    )

    def __repr__(self) -> str:  # pragma: no cover
        return (
            f"<UserSubscription chat_id={self.chat_id} "
            f"keyword={self.keyword!r} active={self.active}>"
        )


class RevenueRecord(Base):
    """
    Estimated affiliate revenue for one published offer.

    Values are *estimates* based on typical commission rates.  Actual
    earnings depend on real conversions in each affiliate dashboard.
    """

    __tablename__ = "revenue_records"

    id = Column(Integer, primary_key=True, index=True)
    offer_id = Column(
        Integer, ForeignKey("offers.id", ondelete="CASCADE"), unique=True, nullable=False
    )
    store = Column(String(64), nullable=False)
    affiliate_network = Column(String(64), nullable=True)   # "amazon", "admitad", etc.
    product_price = Column(Float, nullable=False)
    commission_rate = Column(Float, nullable=False)          # 0.04 = 4 %
    estimated_commission_mxn = Column(Float, nullable=False)
    short_url = Column(Text, nullable=True)                 # Bitly short link
    created_at = Column(DateTime, server_default=func.now(), index=True)

    offer = relationship("Offer")

    __table_args__ = (Index("ix_revenue_created", "created_at"),)

    def __repr__(self) -> str:  # pragma: no cover
        return (
            f"<RevenueRecord offer_id={self.offer_id} "
            f"store={self.store!r} estimated={self.estimated_commission_mxn:.2f}>"
        )


class OfferClickEvent(Base):
    """
    Recorded each time a user clicks on an offer link.

    Used to calculate engagement metrics, CTR, and to rank future offers.
    """

    __tablename__ = "offer_click_events"

    id = Column(BigInteger, primary_key=True, index=True)
    offer_id = Column(
        Integer, ForeignKey("offers.id", ondelete="CASCADE"), nullable=False
    )
    source = Column(String(64), default="telegram", nullable=False)
    clicked_at = Column(DateTime, server_default=func.now(), index=True)

    offer = relationship("Offer")

    __table_args__ = (Index("ix_click_offer_id", "offer_id"),)

    def __repr__(self) -> str:  # pragma: no cover
        return f"<OfferClickEvent offer_id={self.offer_id} source={self.source!r}>"


class OfferPurchaseEvent(Base):
    """
    Recorded when a confirmed purchase / affiliate conversion is detected.

    ``revenue_mxn`` is the actual or estimated commission earned (MXN).
    """

    __tablename__ = "offer_purchase_events"

    id = Column(BigInteger, primary_key=True, index=True)
    offer_id = Column(
        Integer, ForeignKey("offers.id", ondelete="CASCADE"), nullable=False
    )
    revenue_mxn = Column(Float, default=0.0, nullable=False)
    source = Column(String(64), default="telegram", nullable=False)
    purchased_at = Column(DateTime, server_default=func.now(), index=True)

    offer = relationship("Offer")

    __table_args__ = (Index("ix_purchase_offer_id", "offer_id"),)

    def __repr__(self) -> str:  # pragma: no cover
        return (
            f"<OfferPurchaseEvent offer_id={self.offer_id} "
            f"revenue_mxn={self.revenue_mxn:.2f}>"
        )
