"""
app/database/classification_models.py
──────────────────────────────────────
SQLAlchemy model for dynamically registered subject classifications.

This is SEPARATE from the existing Document model (models.py).
History and Anthropology are managed by the old hardcoded config;
this table is ONLY for NEW classifications added via the admin API.

Table: classifications
  - name             : "Geography", "Polity", "Economy", etc.
  - collection_name  : "geography_collection" (Qdrant collection auto-derived)
  - anchors          : JSON list of anchor sentences for the query classifier
  - description      : Optional human note about this classification
  - created_at       : Timestamp
"""
from datetime import datetime, timezone
from sqlalchemy import String, DateTime, Text, JSON
from sqlalchemy.orm import Mapped, mapped_column

from app.database.session import Base


class Classification(Base):
    """
    Represents a dynamically registered subject classification.
    Each row corresponds to one Qdrant vector collection.

    Lifecycle:
        registered → active (after Qdrant collection is created)
        active     → deleted (via DELETE /api/v1/classifications/{name})
    """
    __tablename__ = "classifications"

    # ── Primary key ─────────────────────────────────────────────────────────
    name: Mapped[str] = mapped_column(
        String(100),
        primary_key=True,
        comment="Classification display name e.g. 'Geography'"
    )

    # ── Qdrant collection ────────────────────────────────────────────────────
    collection_name: Mapped[str] = mapped_column(
        String(150),
        unique=True,
        nullable=False,
        comment="Qdrant collection name e.g. 'geography_collection'"
    )

    # ── Query Classifier anchors ─────────────────────────────────────────────
    anchors: Mapped[list] = mapped_column(
        JSON,
        nullable=False,
        default=list,
        comment="List of anchor sentences used by the local embedding classifier"
    )

    # ── Optional description ─────────────────────────────────────────────────
    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Optional admin note about this classification"
    )

    # ── Qdrant collection status ─────────────────────────────────────────────
    qdrant_status: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="active",
        comment="'active' if Qdrant collection was created successfully, 'failed' otherwise"
    )

    # ── Timestamps ───────────────────────────────────────────────────────────
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )
