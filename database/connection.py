"""
SQLAlchemy database engine and session factory.
"""
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase

from config.settings import DATABASE_URL


engine = create_engine(DATABASE_URL, pool_pre_ping=True, future=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


class Base(DeclarativeBase):
    """Shared declarative base for all ORM models."""


def get_db():
    """Yield a database session and close it when done."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    """Create all tables if they do not exist yet."""
    # Import models so that Base.metadata is populated before create_all.
    from database import models  # noqa: F401  pylint: disable=import-outside-toplevel

    Base.metadata.create_all(bind=engine)
