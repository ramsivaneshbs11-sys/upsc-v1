import sys
import os
import uuid
import json
import shutil
import logging
import argparse
import tempfile
from pathlib import Path
from datetime import datetime

# ── Path setup ────────────────────────────────────────────────────────────────
ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))
os.environ["HF_HUB_DISABLE_SYMLINKS"] = "1"

# ── Logging ───────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)
logger = logging.getLogger("ide_pre_extract")

DIVIDER = "=" * 65

def run_pre_extraction(pdf_path: Path, classification: str):
    """
    Executes the pre-extraction steps:
      1. Generate UUID
      2. Save PDF to uploads/<classification>/<uuid>.pdf
      3. Register in PostgreSQL (status=registered)
      4. Render all pages to JPEG images for vision inspection
      5. Create manifest.json
    """
    import fitz  # PyMuPDF
    from app.services.storage_service import save_uploaded_pdf
    from app.database.session import SessionLocal
    from app.database import repository

    print(f"\n{DIVIDER}")
    print(f"  IDE PRE-EXTRACTION SETUP — {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print(f"  PDF            : {pdf_path.name}")
    print(f"  Classification : {classification}")
    print(DIVIDER)

    # ── Step 1: Generate UUID ────────────────────────────────────────────────
    print("\n  -- Step 1: Generate UUID")
    file_id = str(uuid.uuid4())
    print(f"  [OK]   file_id = {file_id}")

    # ── Step 2: Save PDF locally ─────────────────────────────────────────────
    print("\n  -- Step 2: Save PDF locally")
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
            shutil.copy2(pdf_path, tmp.name)
            tmp_path = Path(tmp.name)
        saved_path = save_uploaded_pdf(file_id, classification, tmp_path)
        print(f"  [OK]   Saved -> {saved_path}")
    except Exception as e:
        print(f"  [FAIL] Failed to save PDF: {e}")
        sys.exit(1)

    # ── Step 3: Register in PostgreSQL ──────────────────────────────────────
    print("\n  -- Step 3: Register in PostgreSQL")
    db = SessionLocal()
    try:
        doc = repository.create_document(
            db=db,
            file_id=file_id,
            original_filename=pdf_path.name,
            classification=classification,
            file_path=str(saved_path),
        )
        print(f"  [OK]   Registered -> document_id={doc.id}, status=registered")
    except Exception as e:
        db.close()
        print(f"  [FAIL] PostgreSQL registration failed: {e}")
        sys.exit(1)
    finally:
        db.close()

    # ── Step 4: Render all PDF pages to JPEG ─────────────────────────────────
    print("\n  -- Step 4: Render PDF pages to JPEGs")
    temp_extract_dir = ROOT_DIR / "data" / "temp_extraction" / file_id
    temp_extract_dir.mkdir(parents=True, exist_ok=True)

    try:
        doc = fitz.open(str(pdf_path))
        total_pages = len(doc)
        print(f"  Rendering {total_pages} pages ...")

        for idx in range(total_pages):
            page_num = idx + 1
            page = doc[idx]
            # 150 DPI rendering
            mat = fitz.Matrix(150 / 72, 150 / 72)
            pix = page.get_pixmap(matrix=mat, colorspace=fitz.csRGB)
            jpeg_bytes = pix.tobytes(output="jpeg", jpg_quality=85)
            
            jpeg_path = temp_extract_dir / f"page_{page_num}.jpg"
            with open(jpeg_path, "wb") as f:
                f.write(jpeg_bytes)
            
            if page_num % 10 == 0 or page_num == total_pages:
                print(f"    Rendered page {page_num}/{total_pages}")
        
        doc.close()
        print(f"  [OK]   All pages saved in -> {temp_extract_dir}")
    except Exception as e:
        print(f"  [FAIL] Failed to render PDF pages: {e}")
        sys.exit(1)

    # ── Step 5: Create manifest.json ─────────────────────────────────────────
    print("\n  -- Step 5: Create manifest.json")
    manifest = {
        "file_id": file_id,
        "original_filename": pdf_path.name,
        "classification": classification,
        "total_pages": total_pages,
        "extracted_pages": [],
        "status": "registered",
        "created_at": datetime.now().isoformat()
    }
    
    manifest_path = temp_extract_dir / "manifest.json"
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)
    
    print(f"  [OK]   Manifest created -> {manifest_path}")

    print(f"\n{DIVIDER}")
    print(f"  PRE-EXTRACTION COMPLETE")
    print(f"  Use the following document UUID to run batch extraction in chat:")
    print(f"  UUID: {file_id}")
    print(f"  Pages folder: data/temp_extraction/{file_id}")
    print(DIVIDER)


def main():
    parser = argparse.ArgumentParser(
        description="Pre-extraction helper script"
    )
    parser.add_argument(
        "pdf_path",
        type=str,
        help="Path to the PDF file.",
    )
    parser.add_argument(
        "--classification",
        type=str,
        required=True,
        choices=["History", "Anthropology"],
        help="Document classification: 'History' or 'Anthropology'",
    )

    args = parser.parse_args()
    pdf_path = Path(args.pdf_path)

    if not pdf_path.exists():
        logger.error(f"PDF file not found: {pdf_path}")
        sys.exit(1)

    run_pre_extraction(pdf_path, args.classification)


if __name__ == "__main__":
    main()
