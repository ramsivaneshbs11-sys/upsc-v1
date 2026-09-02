"""
ingest_to_qdrant.py
────────────────────
Batch ingestion script: embeds all preprocessed JSONs and upserts to Qdrant.

This script is for the case where extraction + preprocessing is already done
(i.e., all data/preprocessed/*.json files exist), and we only need to:
  1. Embed each chunk → 768-dim BGE vector
  2. Upsert vectors to Qdrant collection

Usage:
    python ingest_to_qdrant.py
    python ingest_to_qdrant.py --folder p01           # only P-01
    python ingest_to_qdrant.py --folder sem5          # only Semester-V
    python ingest_to_qdrant.py --dry-run              # count chunks, skip upsert
    python ingest_to_qdrant.py --reset-collections    # drop + recreate collections first

Classification Mapping (auto-detected from folder + PDF name):
  P-01          → History
  Semester-V    → History (BHIC-111, BHIC-112, BHIE-141 are History subjects)
"""

import sys
import os
import json
import uuid
import logging
import argparse
import time
from pathlib import Path
from datetime import datetime

# Add workspace root to path
# Script lives at workspace root, so __file__.parent IS the workspace root
ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))
os.environ["HF_HUB_DISABLE_SYMLINKS"] = "1"

from app.core.config import EMBEDDING_DIMENSION as EMBEDDING_DIM

# ── Logging ───────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)
logger = logging.getLogger("ingest_to_qdrant")

DIVIDER = "=" * 70

# ── Classification mapping ────────────────────────────────────────────────────
# All P-01 and Semester-V folders are History subject material
CLASSIFICATION = "History"
QDRANT_COLLECTION = "history_collection"


# ── Step 1: Qdrant client ────────────────────────────────────────────────────

def get_qdrant_client():
    from qdrant_client import QdrantClient
    from app.core.config import QDRANT_HOST, QDRANT_PORT
    logger.info(f"Connecting to Qdrant at {QDRANT_HOST}:{QDRANT_PORT} ...")
    client = QdrantClient(host=QDRANT_HOST, port=QDRANT_PORT)
    logger.info("Qdrant client connected ✓")
    return client


def ensure_collection(client, collection_name: str, reset: bool = False):
    from qdrant_client.models import Distance, VectorParams
    existing = {col.name for col in client.get_collections().collections}
    if reset and collection_name in existing:
        logger.info(f"Dropping collection '{collection_name}' (--reset-collections) ...")
        client.delete_collection(collection_name)
        existing.discard(collection_name)

    if collection_name not in existing:
        logger.info(f"Creating Qdrant collection '{collection_name}' (dim={EMBEDDING_DIM}, Cosine) ...")
        client.create_collection(
            collection_name=collection_name,
            vectors_config=VectorParams(size=EMBEDDING_DIM, distance=Distance.COSINE),
        )
        logger.info(f"Collection '{collection_name}' created ✓")
    else:
        info = client.get_collection(collection_name)
        logger.info(f"Collection '{collection_name}' exists — {info.points_count} points already stored ✓")


# ── Step 2: Embedding model ───────────────────────────────────────────────────

_model = None

def get_model():
    global _model
    if _model is None:
        from sentence_transformers import SentenceTransformer
        from app.core.config import EMBEDDING_MODEL_NAME
        logger.info(f"Loading embedding model: {EMBEDDING_MODEL_NAME} ...")
        _model = SentenceTransformer(EMBEDDING_MODEL_NAME)
        logger.info("Embedding model loaded ✓")
    return _model


# ── Step 3: Build PDF → preprocessed file mapping ────────────────────────────

def collect_preprocessed_files(folder_filter: str) -> list[dict]:
    """
    Returns list of dicts: {pdf_name, stem, json_path, source_folder}
    Source folders: P-01, Semester-V
    """
    inputs_dir = ROOT_DIR / "inputs"
    preprocess_dir = ROOT_DIR / "data" / "preprocessed"

    results = []

    # P-01 PDFs
    if folder_filter in ("p01", "all"):
        p01_dir = inputs_dir / "P-01"
        for pdf in sorted(p01_dir.rglob("*.pdf")):
            stem = pdf.stem.strip()
            json_path = preprocess_dir / f"{stem}_extracted_preprocessed.json"
            if json_path.exists():
                results.append({
                    "pdf_name": pdf.name,
                    "stem": stem,
                    "json_path": json_path,
                    "source_folder": "P-01",
                    "classification": "History",
                })
            else:
                logger.warning(f"[P-01] Preprocessed JSON not found for: {pdf.name}")

    # Semester-V PDFs
    if folder_filter in ("sem5", "all"):
        sem5_dir = inputs_dir / "Semester-V"
        for pdf in sorted(sem5_dir.rglob("*.pdf")):
            stem = pdf.stem.strip()
            json_path = preprocess_dir / f"{stem}_extracted_preprocessed.json"
            if json_path.exists():
                results.append({
                    "pdf_name": pdf.name,
                    "stem": stem,
                    "json_path": json_path,
                    "source_folder": "Semester-V",
                    "classification": "History",
                })
            else:
                logger.warning(f"[Semester-V] Preprocessed JSON not found for: {pdf.name}")

    return results


# ── Step 4: Ingest single file ────────────────────────────────────────────────

def ingest_one(
    entry: dict,
    client,
    dry_run: bool = False,
) -> dict:
    """
    Embed + upsert one preprocessed JSON file.
    Returns stats dict.
    """
    pdf_name = entry["pdf_name"]
    stem = entry["stem"]
    json_path = entry["json_path"]
    classification = entry["classification"]
    source_folder = entry["source_folder"]

    t0 = time.time()
    stats = {
        "pdf_name": pdf_name,
        "source_folder": source_folder,
        "chunks": 0,
        "vectors_upserted": 0,
        "status": "ok",
        "error": None,
    }

    # Load preprocessed JSON
    try:
        with open(json_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception as e:
        stats["status"] = "error"
        stats["error"] = f"Failed to load JSON: {e}"
        return stats

    chunks = data.get("chunks", [])
    if not chunks:
        stats["status"] = "error"
        stats["error"] = "No chunks in preprocessed JSON"
        return stats

    stats["chunks"] = len(chunks)

    if dry_run:
        logger.info(f"  [DRY-RUN] [{source_folder}] {pdf_name}: {len(chunks)} chunks (skipping embed+upsert)")
        stats["status"] = "dry_run"
        return stats

    # Embed all chunks
    try:
        model = get_model()
        texts = [c["text"] for c in chunks]
        vectors = model.encode(texts, normalize_embeddings=True, show_progress_bar=False)
    except Exception as e:
        stats["status"] = "error"
        stats["error"] = f"Embedding failed: {e}"
        return stats

    # Build Qdrant points
    from qdrant_client.models import PointStruct
    # Use stem + source_folder as file_id for deterministic IDs.
    # IMPORTANT: Include source_folder so that identically-named files across
    # different Semester-V subject subfolders (e.g. Unit-11 in BHIC-111 vs BHIC-112)
    # get distinct Qdrant point IDs and do NOT overwrite each other.
    file_id = f"{source_folder}::{stem}"
    collection_name = QDRANT_COLLECTION

    points = []
    for chunk, vector in zip(chunks, vectors):
        point_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, f"{file_id}:{chunk['chunk_id']}"))
        payload = {
            "file_id": file_id,
            "pdf_name": pdf_name,
            "source_folder": source_folder,
            "classification": classification,
            "chunk_id": chunk["chunk_id"],
            "text": chunk["text"],
            "metadata": chunk.get("metadata", {}),
        }
        points.append(PointStruct(id=point_id, vector=vector.tolist(), payload=payload))

    # Upsert to Qdrant
    try:
        result = client.upsert(collection_name=collection_name, points=points, wait=True)
        stats["vectors_upserted"] = len(points)
        elapsed = time.time() - t0
        logger.info(
            f"  [OK] [{source_folder}] {pdf_name}: "
            f"{len(chunks)} chunks -> {len(points)} vectors upserted "
            f"({elapsed:.1f}s, status={result.status})"
        )
    except Exception as e:
        stats["status"] = "error"
        stats["error"] = f"Qdrant upsert failed: {e}"
        return stats

    return stats


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Batch embed + upsert all preprocessed JSONs to Qdrant"
    )
    parser.add_argument(
        "--folder",
        choices=["p01", "sem5", "all"],
        default="all",
        help="Which folder to process: p01, sem5, or all (default: all)"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Count chunks only, skip embedding and Qdrant upsert"
    )
    parser.add_argument(
        "--reset-collections",
        action="store_true",
        help="Drop and recreate Qdrant collections before ingesting"
    )
    args = parser.parse_args()

    print(f"\n{DIVIDER}")
    print(f"  QDRANT BATCH INGEST — {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"  Folder filter : {args.folder.upper()}")
    print(f"  Dry run       : {args.dry_run}")
    print(f"  Reset colls   : {args.reset_collections}")
    print(DIVIDER)

    # Collect files
    entries = collect_preprocessed_files(folder_filter=args.folder)
    total_chunks = sum(
        len(json.loads(e["json_path"].read_text(encoding="utf-8")).get("chunks", []))
        for e in entries
    )

    print(f"\n  Files to ingest : {len(entries)}")
    print(f"  Total chunks    : {total_chunks}")

    if not entries:
        logger.error("No preprocessed JSON files found. Run run_batch_inputs.py first.")
        sys.exit(1)

    if args.dry_run:
        print("\n  [DRY-RUN MODE] No embedding or upsert will be performed.")
        for e in entries:
            data = json.loads(e["json_path"].read_text(encoding="utf-8"))
            chunks = data.get("chunks", [])
            print(f"    [{e['source_folder']}] {e['pdf_name']}: {len(chunks)} chunks")
        print(f"\n  Total: {total_chunks} chunks across {len(entries)} files")
        return

    # Connect to Qdrant
    try:
        client = get_qdrant_client()
    except Exception as e:
        logger.error(f"Cannot connect to Qdrant: {e}")
        logger.error("Make sure Qdrant is running:")
        logger.error("  docker compose up -d qdrant")
        sys.exit(1)

    # Ensure collection
    try:
        ensure_collection(client, QDRANT_COLLECTION, reset=args.reset_collections)
    except Exception as e:
        logger.error(f"Cannot create Qdrant collection: {e}")
        sys.exit(1)

    # Run ingestion
    print(f"\n{DIVIDER}")
    print(f"  Starting ingestion of {len(entries)} files ...")
    print(DIVIDER)

    grand_start = time.time()
    all_stats = []
    failed = []

    for idx, entry in enumerate(entries, start=1):
        print(f"\n  [{idx:>3}/{len(entries)}] {entry['source_folder']} / {entry['pdf_name']}")
        stats = ingest_one(entry, client, dry_run=args.dry_run)
        all_stats.append(stats)
        if stats["status"] == "error":
            failed.append(stats)
            logger.error(f"  [FAIL] {entry['pdf_name']}: {stats['error']}")

    # Final summary
    total_elapsed = time.time() - grand_start
    total_upserted = sum(s["vectors_upserted"] for s in all_stats)

    print(f"\n{DIVIDER}")
    print(f"  INGESTION COMPLETE — {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"  Runtime         : {total_elapsed/60:.1f} min")
    print(f"  Files processed : {len(entries)}")
    print(f"  Vectors upserted: {total_upserted}")
    print(f"  Failures        : {len(failed)}")
    print(DIVIDER)

    # Collection info
    try:
        info = client.get_collection(QDRANT_COLLECTION)
        print(f"\n  Qdrant collection '{QDRANT_COLLECTION}':")
        print(f"    Total points stored : {info.points_count}")
    except Exception:
        pass

    if failed:
        print("\n  FAILED FILES:")
        for s in failed:
            print(f"    [{s['source_folder']}] {s['pdf_name']}: {s['error']}")
        sys.exit(1)

    print("\n  All files ingested to Qdrant successfully!\n")


if __name__ == "__main__":
    main()
