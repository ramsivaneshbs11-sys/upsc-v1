"""
scratch/heal_incomplete_ingest.py
───────────────────────────────────
1. Fixes outdated file paths in PostgreSQL.
2. If Qdrant points == 0: Re-embeds and upserts.
3. If Qdrant points > 0 but status != 'ingested':
   - If points == chunks: Marks status as 'ingested' in PostgreSQL.
   - If points < chunks: Re-embeds and upserts to complete the points.
"""
import os
import sys
import json
import logging
from pathlib import Path

# Add workspace root to python path
ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    stream=sys.stdout
)
logger = logging.getLogger("heal_incomplete_ingest")

from app.database.session import SessionLocal
from app.database.models import Document
from app.database import repository
from app.services.embedding_service import run_embedding
from app.services.qdrant_service import run_qdrant_upsert, get_qdrant_client
from app.core.config import QDRANT_COLLECTION_MAP
from qdrant_client.http import models

def resolve_and_fix_path(db, doc, attr_name):
    path_str = getattr(doc, attr_name)
    if not path_str:
        return None
    
    p = Path(path_str)
    if p.exists():
        return p

    path_str_fixed = path_str.replace("upsc-pdf-extraction-pipeline-main/upsc-pdf-extraction-pipeline-main", "RAG-main/RAG-main")
    path_str_fixed = path_str_fixed.replace("upsc-pdf-extraction-pipeline-main\\upsc-pdf-extraction-pipeline-main", "RAG-main\\RAG-main")
    p_fixed = Path(path_str_fixed)
    if p_fixed.exists():
        setattr(doc, attr_name, str(p_fixed))
        db.commit()
        return p_fixed

    for marker in ["uploads", "data"]:
        if marker in p.parts:
            idx = p.parts.index(marker)
            rel_parts = p.parts[idx:]
            fallback = ROOT_DIR.joinpath(*rel_parts)
            if fallback.exists():
                setattr(doc, attr_name, str(fallback))
                db.commit()
                return fallback
                
    return None

def heal_all():
    db = SessionLocal()
    client = get_qdrant_client()
    
    try:
        docs = db.query(Document).all()
        if not docs:
            logger.info("No documents found in the database.")
            return

        logger.info(f"Scanning {len(docs)} documents for path fixes and vector ingestion check...")
        
        healed_count = 0
        status_corrected_count = 0
        failed_count = 0
        healthy_count = 0
        path_fixes_count = 0

        for doc in docs:
            # 1. Correct paths in the database if they are broken
            path_changed = False
            for attr in ["file_path", "extracted_json_path", "preprocessed_json_path"]:
                old_val = getattr(doc, attr)
                resolved = resolve_and_fix_path(db, doc, attr)
                if resolved and str(resolved) != old_val:
                    path_changed = True
            
            if path_changed:
                path_fixes_count += 1
                logger.info(f"Fixed paths for document: {doc.original_filename}")

            # 2. Get collection name
            collection_name = QDRANT_COLLECTION_MAP.get(doc.classification)
            if not collection_name:
                logger.warning(f"Document {doc.original_filename} has unmapped classification: {doc.classification}")
                continue

            # 3. Check Qdrant points count
            qdrant_points = 0
            try:
                res = client.scroll(
                    collection_name=collection_name,
                    scroll_filter=models.Filter(
                        must=[
                            models.FieldCondition(
                                key="file_id",
                                match=models.MatchValue(value=str(doc.id))
                            )
                        ]
                    ),
                    limit=1000 # Increase limit to scroll all points if possible
                )
                qdrant_points = len(res[0])
            except Exception as e:
                pass

            # Count preprocessed chunks
            total_chunks = 0
            if doc.preprocessed_json_path:
                prep_path = Path(doc.preprocessed_json_path)
                if prep_path.exists():
                    try:
                        with open(prep_path, "r", encoding="utf-8") as f:
                            prep_data = json.load(f)
                        total_chunks = len(prep_data.get("chunks", []))
                    except Exception:
                        pass

            # 4. Check status
            if qdrant_points > 0:
                if doc.status == "ingested":
                    healthy_count += 1
                    continue
                else:
                    # Qdrant has points but PostgreSQL status is not 'ingested'
                    if total_chunks > 0 and qdrant_points >= total_chunks:
                        logger.info(f"Correcting PostgreSQL status to 'ingested' for: {doc.original_filename} (Qdrant points: {qdrant_points}, chunks: {total_chunks})")
                        doc.status = "ingested"
                        db.commit()
                        status_corrected_count += 1
                        continue
                    else:
                        logger.warning(f"Document {doc.original_filename} has incomplete points in Qdrant ({qdrant_points}/{total_chunks}). Will re-ingest.")
            
            # 5. Ingest missing or incomplete vectors
            logger.info(f"Healing document: {doc.original_filename} (ID: {doc.id}, Class: {doc.classification})")
            
            if not doc.preprocessed_json_path:
                logger.error(f"  -> Cannot heal: preprocessed_json_path is not defined in DB record.")
                failed_count += 1
                continue

            prep_path = Path(doc.preprocessed_json_path)
            if not prep_path.exists():
                logger.error(f"  -> Cannot heal: Preprocessed JSON file does not exist on disk: {prep_path}")
                failed_count += 1
                continue

            # Step 1: Run embedding
            logger.info("  -> Step 1/2: Generating embeddings (BGE)...")
            emb_success, embedded_chunks, emb_error = run_embedding(prep_path)
            if not emb_success:
                logger.error(f"  -> [FAIL] Embedding failed: {emb_error}")
                failed_count += 1
                continue
            
            logger.info(f"  -> Generated {len(embedded_chunks)} vector embeddings.")

            # Step 2: Run Qdrant upsert
            logger.info("  -> Step 2/2: Upserting to Qdrant...")
            qdrant_success, qdrant_error = run_qdrant_upsert(
                file_id=doc.id,
                classification=doc.classification,
                embedded_chunks=embedded_chunks
            )
            
            if not qdrant_success:
                logger.error(f"  -> [FAIL] Qdrant upsert failed: {qdrant_error}")
                failed_count += 1
                continue

            # Update DB status
            doc.status = "ingested"
            db.commit()
            logger.info(f"  -> [SUCCESS] Document '{doc.original_filename}' successfully healed and status set to 'ingested'!")
            healed_count += 1

        logger.info("\n" + "="*50)
        logger.info("HEALING SUMMARY")
        logger.info(f"  Path records fixed in DB  : {path_fixes_count}")
        logger.info(f"  Already healthy in Qdrant : {healthy_count}")
        logger.info(f"  DB Statuses corrected     : {status_corrected_count}")
        logger.info(f"  Healed (re-ingested)      : {healed_count}")
        logger.info(f"  Failed to heal            : {failed_count}")
        logger.info("="*50)

    except Exception as e:
        logger.exception(f"Healing failed due to exception: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    heal_all()
