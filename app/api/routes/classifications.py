"""
app/api/routes/classifications.py
──────────────────────────────────
Admin endpoints for dynamically registering new subject classifications.

This file is 100% NEW — no existing endpoints or logic is modified.

Endpoints:
    POST   /api/v1/classifications              → Register a new classification
    GET    /api/v1/classifications              → List all dynamic classifications
    DELETE /api/v1/classifications/{name}       → Remove a classification + drop Qdrant collection

What POST /api/v1/classifications does automatically:
    1. Validates name (alphanumeric + spaces only, no duplicates)
    2. Derives Qdrant collection name → "{name.lower()}_collection"
    3. Creates the Qdrant vector collection with the correct dimension
    4. Creates the upload directory for this classification
    5. Saves the record (name, collection_name, anchors) to PostgreSQL
    6. Returns a full report

NOTE: History and Anthropology are still managed by the OLD hardcoded config.
      This endpoint is for FUTURE classifications ONLY (e.g. Geography, Polity).
"""
import logging
import re
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field, field_validator
from sqlalchemy.orm import Session

from app.core.config import (
    QDRANT_HOST,
    QDRANT_PORT,
    EMBEDDING_DIMENSION,
    UPLOAD_DIR,
)
from app.database.session import get_db

# New imports — classification-specific modules only
from app.database.classification_models import Classification  # noqa: F401 — needed so Base sees the table
from app.database import classification_repository as cls_repo

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1", tags=["Classification Management"])


# ── Pydantic request / response models ────────────────────────────────────────

class RegisterClassificationRequest(BaseModel):
    """
    Request body for POST /api/v1/classifications.

    - **name**: Display name for the classification (e.g. "Geography").
                Must be alphanumeric with optional spaces. Will be stored as-is.
    - **anchors**: List of representative sentences describing this subject.
                   These are used by the local embedding classifier to route queries.
                   Provide at least 3 and ideally 8–12 rich anchor sentences.
    - **description**: Optional human-readable note about this classification.
    """
    name: str = Field(
        ...,
        min_length=2,
        max_length=100,
        description="Classification display name, e.g. 'Geography'",
        examples=["Geography"],
    )
    anchors: list[str] = Field(
        ...,
        min_length=3,
        description=(
            "List of anchor sentences for the query classifier. "
            "Provide at least 3 rich, representative sentences "
            "describing this subject's UPSC syllabus content."
        ),
        examples=[[
            "Geography physical human economic geography maps atlas topography",
            "Indian geography rivers mountains soil climate rainfall wind zones",
            "World geography continents oceans latitude longitude meridians",
        ]],
    )
    description: str | None = Field(
        default=None,
        max_length=500,
        description="Optional admin note about this classification",
        examples=["UPSC Geography optional paper and GS-1 physical geography topics"],
    )

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        """Only allow alphanumeric characters and single spaces."""
        v = v.strip()
        if not re.match(r"^[A-Za-z][A-Za-z0-9 ]*$", v):
            raise ValueError(
                "Classification name must start with a letter and contain only "
                "letters, digits, and spaces (no special characters)."
            )
        return v

    @field_validator("anchors")
    @classmethod
    def validate_anchors(cls, v: list[str]) -> list[str]:
        """Strip blank anchor strings and ensure minimum count."""
        cleaned = [a.strip() for a in v if a.strip()]
        if len(cleaned) < 3:
            raise ValueError("At least 3 non-empty anchor sentences are required.")
        return cleaned


class ClassificationResponse(BaseModel):
    """Response schema for a single classification record."""
    name: str
    collection_name: str
    anchors: list[str]
    description: str | None
    qdrant_status: str
    created_at: str

    model_config = {"from_attributes": True}


# ── Helper: create Qdrant collection ──────────────────────────────────────────

def _create_qdrant_collection(collection_name: str) -> tuple[bool, str | None]:
    """
    Create a new Qdrant collection for a dynamic classification.

    Returns:
        (success: bool, error_message: str | None)
    """
    try:
        from qdrant_client import QdrantClient
        from qdrant_client.models import Distance, VectorParams

        client = QdrantClient(host=QDRANT_HOST, port=QDRANT_PORT)
        existing = {col.name for col in client.get_collections().collections}

        if collection_name in existing:
            logger.info(
                f"Qdrant collection '{collection_name}' already exists — skipping creation."
            )
            return True, None

        client.create_collection(
            collection_name=collection_name,
            vectors_config=VectorParams(
                size=EMBEDDING_DIMENSION,
                distance=Distance.COSINE,
            ),
        )
        logger.info(f"Qdrant collection '{collection_name}' created successfully ✓")
        return True, None

    except Exception as exc:
        error_msg = f"Failed to create Qdrant collection '{collection_name}': {exc}"
        logger.exception(error_msg)
        return False, error_msg


def _drop_qdrant_collection(collection_name: str) -> tuple[bool, str | None]:
    """
    Drop a Qdrant collection when a classification is deleted.

    Returns:
        (success: bool, error_message: str | None)
    """
    try:
        from qdrant_client import QdrantClient

        client = QdrantClient(host=QDRANT_HOST, port=QDRANT_PORT)
        existing = {col.name for col in client.get_collections().collections}

        if collection_name not in existing:
            logger.warning(
                f"Qdrant collection '{collection_name}' does not exist — skipping drop."
            )
            return True, None

        client.delete_collection(collection_name=collection_name)
        logger.info(f"Qdrant collection '{collection_name}' dropped successfully ✓")
        return True, None

    except Exception as exc:
        error_msg = f"Failed to drop Qdrant collection '{collection_name}': {exc}"
        logger.exception(error_msg)
        return False, error_msg


# ── Endpoints ──────────────────────────────────────────────────────────────────

@router.post(
    "/classifications",
    status_code=status.HTTP_201_CREATED,
    summary="Register a new subject classification",
    response_model=dict,
)
def register_classification(
    body: RegisterClassificationRequest,
    db: Session = Depends(get_db),
):
    """
    Register a new UPSC subject classification.

    Automatically:
    1. Validates the name (no duplicates, alphanumeric only)
    2. Derives the Qdrant collection name as `{name_lowercase}_collection`
    3. Creates the Qdrant vector collection (768-dim cosine)
    4. Creates a dedicated upload folder on disk for this classification
    5. Saves the record in PostgreSQL (name, collection, anchors, description)

    Use this endpoint when the UPSC syllabus adds a **new optional paper**
    (e.g. *Geography*, *Polity*, *Economy*) that needs its own vector store.

    > **Note:** History and Anthropology are managed by the existing hardcoded
    > config and are not affected by this endpoint.
    """
    # ── Guard: Reject if name is a built-in classification ──────────────────
    BUILTIN_CLASSIFICATIONS = {"history", "anthropology"}
    if body.name.lower() in BUILTIN_CLASSIFICATIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"'{body.name}' is a built-in classification managed by the core config. "
                "Use the existing ingestion endpoints for History and Anthropology."
            ),
        )

    # ── Guard: Check for duplicate ───────────────────────────────────────────
    existing = cls_repo.get_classification_by_name(db, body.name)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"Classification '{body.name}' is already registered "
                f"(Qdrant collection: '{existing.collection_name}')."
            ),
        )

    # ── Derive collection name ───────────────────────────────────────────────
    # e.g. "Indian Geography" → "indian_geography_collection"
    collection_name = body.name.lower().replace(" ", "_") + "_collection"

    # ── Step 1: Create Qdrant collection ────────────────────────────────────
    qdrant_ok, qdrant_err = _create_qdrant_collection(collection_name)
    qdrant_status = "active" if qdrant_ok else "failed"

    warnings = []
    if not qdrant_ok:
        warnings.append(f"Qdrant collection creation failed: {qdrant_err}")
        logger.warning(f"[REGISTER] {warnings[-1]}")

    # ── Step 2: Create upload directory on disk ──────────────────────────────
    upload_subdir = UPLOAD_DIR / body.name.lower().replace(" ", "_")
    try:
        upload_subdir.mkdir(parents=True, exist_ok=True)
        logger.info(f"[REGISTER] Upload directory created: {upload_subdir}")
    except Exception as exc:
        warn_msg = f"Could not create upload directory '{upload_subdir}': {exc}"
        warnings.append(warn_msg)
        logger.warning(f"[REGISTER] {warn_msg}")

    # ── Step 3: Persist to PostgreSQL ───────────────────────────────────────
    record = cls_repo.create_classification(
        db=db,
        name=body.name,
        collection_name=collection_name,
        anchors=body.anchors,
        description=body.description,
        qdrant_status=qdrant_status,
    )

    logger.info(
        f"[REGISTER] New classification '{body.name}' registered "
        f"(collection='{collection_name}', anchors={len(body.anchors)}, "
        f"qdrant_status='{qdrant_status}')"
    )

    return {
        "message": f"Classification '{body.name}' registered successfully.",
        "name": record.name,
        "collection_name": record.collection_name,
        "anchors_count": len(record.anchors),
        "upload_directory": str(upload_subdir),
        "qdrant_status": record.qdrant_status,
        "created_at": record.created_at.isoformat(),
        "warnings": warnings,
        "next_steps": [
            f"Upload PDFs for '{body.name}' using POST /api/v1/documents "
            f"with classification='{body.name}' (after re-adding it to ClassificationEnum).",
            "The query classifier will automatically use the new anchors "
            "when routing queries to this classification.",
        ],
    }


@router.get(
    "/classifications",
    status_code=status.HTTP_200_OK,
    summary="List all dynamically registered classifications",
    response_model=dict,
)
def list_classifications(db: Session = Depends(get_db)):
    """
    List all dynamically registered subject classifications.

    > **Note:** Built-in classifications (History, Anthropology) are managed by
    > the core config and will NOT appear in this list. Only classifications
    > added via `POST /api/v1/classifications` are listed here.
    """
    records = cls_repo.list_classifications(db)

    return {
        "total": len(records),
        "builtin_classifications": ["History", "Anthropology"],
        "dynamic_classifications": [
            {
                "name": r.name,
                "collection_name": r.collection_name,
                "anchors_count": len(r.anchors),
                "anchors": r.anchors,
                "description": r.description,
                "qdrant_status": r.qdrant_status,
                "created_at": r.created_at.isoformat(),
            }
            for r in records
        ],
    }


@router.get(
    "/classifications/{name}",
    status_code=status.HTTP_200_OK,
    summary="Get details of a single dynamic classification",
    response_model=dict,
)
def get_classification(name: str, db: Session = Depends(get_db)):
    """
    Get the full details of a dynamically registered classification by name.
    """
    record = cls_repo.get_classification_by_name(db, name)
    if record is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Dynamic classification '{name}' not found.",
        )

    return {
        "name": record.name,
        "collection_name": record.collection_name,
        "anchors": record.anchors,
        "anchors_count": len(record.anchors),
        "description": record.description,
        "qdrant_status": record.qdrant_status,
        "created_at": record.created_at.isoformat(),
    }


@router.delete(
    "/classifications/{name}",
    status_code=status.HTTP_200_OK,
    summary="Delete a dynamic classification and drop its Qdrant collection",
)
def delete_classification(name: str, db: Session = Depends(get_db)):
    """
    Permanently delete a dynamically registered classification.

    This will:
    1. Drop the Qdrant collection (and ALL vectors inside it)
    2. Delete the PostgreSQL record from the `classifications` table

    > **Warning:** This is irreversible! All vectors stored in the
    > Qdrant collection will be permanently lost.

    > **Note:** Built-in classifications (History, Anthropology) cannot
    > be deleted via this endpoint.
    """
    # Guard: Reject deletion of built-in classifications
    BUILTIN_CLASSIFICATIONS = {"history", "anthropology"}
    if name.lower() in BUILTIN_CLASSIFICATIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"'{name}' is a built-in classification and cannot be deleted "
                "via this endpoint. It is managed by the core configuration."
            ),
        )

    # Look up the record
    record = cls_repo.get_classification_by_name(db, name)
    if record is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Dynamic classification '{name}' not found in the database.",
        )

    warnings = []
    collection_name = record.collection_name

    # ── Step 1: Drop Qdrant collection ──────────────────────────────────────
    qdrant_ok, qdrant_err = _drop_qdrant_collection(collection_name)
    if not qdrant_ok:
        warnings.append(f"Qdrant collection drop failed: {qdrant_err}")
        logger.warning(f"[DELETE-CLASSIFICATION] {warnings[-1]}")

    # ── Step 2: Delete PostgreSQL record ────────────────────────────────────
    deleted = cls_repo.delete_classification(db, name)

    logger.info(
        f"[DELETE-CLASSIFICATION] '{name}' removed "
        f"(collection='{collection_name}', db_deleted={deleted})"
    )

    return {
        "message": f"Classification '{name}' has been permanently deleted.",
        "name": name,
        "collection_name": collection_name,
        "qdrant_collection_dropped": qdrant_ok,
        "postgres_record_deleted": deleted,
        "warnings": warnings,
    }
