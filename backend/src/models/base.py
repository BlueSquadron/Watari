"""Base model with common columns for all SQLAlchemy models."""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy.sql import func


class Base(DeclarativeBase):
    """Base class for all SQLAlchemy models."""

    pass


#: Canonical tz-aware timestamp type used throughout the schema.
#: All timestamps are stored as ``TIMESTAMPTZ`` so the application can
#: pass timezone-aware ``datetime`` objects without coercion.
TS = DateTime(timezone=True)


class TimestampMixin:
    """Mixin providing created_at and updated_at timestamp columns."""

    created_at: Mapped[datetime] = mapped_column(
        TS,
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        TS,
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )


class BaseModel(TimestampMixin):
    """Mixin providing id (UUID PK) + created_at + updated_at."""

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )
