"""
app/database/classification_repository.py
──────────────────────────────────────────
CRUD functions for the `classifications` table.

Completely separate from repository.py (which handles the Document table).
All functions operate ONLY on the Classification model.
"""
from sqlalchemy.orm import Session
from app.database.classification_models import Classification


def create_classification(
    db: Session,
    name: str,
    collection_name: str,
    anchors: list[str],
    description: str | None = None,
    qdrant_status: str = "active",
) -> Classification:
    """Insert a new classification record into the classifications table."""
    record = Classification(
        name=name,
        collection_name=collection_name,
        anchors=anchors,
        description=description,
        qdrant_status=qdrant_status,
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return record


def get_classification_by_name(db: Session, name: str) -> Classification | None:
    """Return a classification record by name, or None if not found."""
    return db.get(Classification, name)


def list_classifications(db: Session) -> list[Classification]:
    """Return all registered dynamic classifications."""
    return db.query(Classification).order_by(Classification.created_at).all()


def delete_classification(db: Session, name: str) -> bool:
    """
    Permanently delete a classification record.
    Returns True if deleted, False if not found.
    """
    record = db.get(Classification, name)
    if record is None:
        return False
    db.delete(record)
    db.commit()
    return True


def update_qdrant_status(db: Session, name: str, status: str) -> Classification | None:
    """Update the qdrant_status field for a classification (e.g. 'failed')."""
    record = db.get(Classification, name)
    if record is None:
        return None
    record.qdrant_status = status
    db.commit()
    db.refresh(record)
    return record
