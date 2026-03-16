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
    detected_at = Column(DateTime, server_default=func.now(), index=True)
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
