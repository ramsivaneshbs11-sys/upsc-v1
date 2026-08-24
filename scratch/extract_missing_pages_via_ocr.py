import sys
import json
import re
import os
import requests
from pathlib import Path
import fitz
import numpy as np

# Add project root to sys.path
ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

try:
    from rapidocr_onnxruntime import RapidOCR
    RAPID_OCR_AVAILABLE = True
except ImportError:
    RAPID_OCR_AVAILABLE = False

from dotenv import load_dotenv
load_dotenv(ROOT_DIR / ".env")

from gemini_batch_extract import consolidate_extracted_json

def call_groq_clean(text: str) -> str:
    """Uses Groq API to fix spacing and split run-together words in the paragraph."""
    if not text:
        return ""
    
    api_key = os.environ.get("GROQ_API_KEY", "")
    if not api_key:
        print("[WARNING] GROQ_API_KEY not found in env, returning raw text.")
        return text
        
    model = os.environ.get("GROQ_MODEL", "llama-3.3-70b-versatile")
    
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    
    prompt = (
        "The following text is extracted from a scanned PDF by OCR. It has run-together words, missing spaces, "
        "or minor spelling issues. Clean and format the text into proper, natural English sentences.\n"
        "RULES:\n"
        "1. Do NOT add any new information, comments, or annotations.\n"
        "2. Do NOT change the meaning or remove any technical/proper nouns.\n"
        "3. Output ONLY the cleaned text, nothing else.\n\n"
        f"Text:\n{text}"
    )
    
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.0
    }
    
    try:
        resp = requests.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers=headers,
            json=payload,
            timeout=15.0
        )
        if resp.status_code == 200:
            result = resp.json()["choices"][0]["message"]["content"].strip()
            if result:
                return result
    except Exception as e:
        print(f"[ERROR] Groq API call failed: {e}")
        
    return text

def extract_missing_pages():
    if not RAPID_OCR_AVAILABLE:
        print("[ERROR] RapidOCR is not installed.")
        return

    pdf_path = Path("TRIBES INDIA.pdf")
    output_dir = Path("output/TRIBES INDIA")
    progress_path = output_dir / "progress.json"

    if not pdf_path.exists():
        print(f"[ERROR] PDF not found: {pdf_path}")
        return

    missing_pages = [10, 12, 13, 14, 15, 16, 17, 18, 50, 51, 82, 83, 84, 191, 196, 198, 199, 200, 205, 206, 240, 263, 281, 290]
    print(f"Starting Local Column-Aware RapidOCR extraction with LLM Cleanup for pages: {missing_pages}")

    ocr_engine = RapidOCR()
    doc = fitz.open(str(pdf_path))
    total_pages = len(doc)

    # Patterns to ignore (watermarks, footers, headers)
    ignore_patterns = [
        re.compile(r"upscpdf", re.IGNORECASE),
        re.compile(r"download all form", re.IGNORECASE),
        re.compile(r"tribal india today", re.IGNORECASE),
        re.compile(r"tribes through the ages", re.IGNORECASE),
        re.compile(r"^\s*\d{1,3}\s*$"), # standalone page numbers
    ]

    for p_num in missing_pages:
        print(f"  Processing page {p_num} ...", end="", flush=True)
        page = doc[p_num - 1]
        
        # Render page at 150 DPI for OCR
        pix = page.get_pixmap(dpi=150)
        img = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, 3)
        
        # Use raw RGB image directly
        img_for_ocr = img

        res, _ = ocr_engine(img_for_ocr)
        
        text_blocks = []
        if res:
            ph, pw = img_for_ocr.shape[0], img_for_ocr.shape[1]
            x_mid = pw / 2.0
            
            headers = []
            footers = []
            col1 = []  # Left Column lines (yc, text)
            col2 = []  # Right Column lines (yc, text)
            
            for item in res:
                box, line_text = item[0], item[1].strip()
                if not line_text:
                    continue
                
                # Check ignore patterns (watermarks / boilerplate headers)
                if any(pat.search(line_text) for pat in ignore_patterns):
                    continue
                    
                # Calculate box center
                xc = (box[0][0] + box[1][0] + box[2][0] + box[3][0]) / 4.0
                yc = (box[0][1] + box[1][1] + box[2][1] + box[3][1]) / 4.0
                
                # Categorize based on coordinate limits
                if yc < ph * 0.08:
                    headers.append(line_text)
                elif yc > ph * 0.92:
                    footers.append(line_text)
                elif xc < x_mid:
                    col1.append((yc, line_text))
                else:
                    col2.append((yc, line_text))
            
            # Sort the column lines vertically (top to bottom)
            col1.sort(key=lambda x: x[0])
            col2.sort(key=lambda x: x[0])
            
            # Group left page and right page text into separate paragraphs
            left_para = " ".join([text for yc, text in col1]).strip()
            right_para = " ".join([text for yc, text in col2]).strip()
            
            # Clean paragraphs using Groq LLM
            print(f" (Cleaning Left... ", end="", flush=True)
            left_para = call_groq_clean(left_para)
            print("Right... ", end="", flush=True)
            right_para = call_groq_clean(right_para)
            print("done) ", end="", flush=True)
            
            # Format as text blocks
            for h in headers:
                text_blocks.append({"type": "heading", "text": h})
            if left_para:
                text_blocks.append({"type": "paragraph", "text": left_para})
            if right_para:
                text_blocks.append({"type": "paragraph", "text": right_para})
            for f in footers:
                text_blocks.append({"type": "paragraph", "text": f})

        # Save single-page JSON
        page_data = {
            "page_num": p_num,
            "text_blocks": text_blocks,
            "tables": [],
            "is_blank": len(text_blocks) == 0
        }
        
        out_file = output_dir / f"page_{p_num:04d}.json"
        with open(out_file, "w", encoding="utf-8") as f:
            json.dump(page_data, f, indent=2, ensure_ascii=False)
            
        print(f" [OK] (Extracted {len(text_blocks)} blocks)")

    doc.close()

    # 5. Update progress.json
    print("\nUpdating progress.json...")
    if progress_path.exists():
        with open(progress_path, "r", encoding="utf-8") as f:
            progress = json.load(f)
    else:
        progress = {"pdf": pdf_path.name, "extracted_pages": [], "status": "in_progress"}

    extracted_pages = set(progress.get("extracted_pages", []))
    for p in missing_pages:
        extracted_pages.add(p)
        
    progress["extracted_pages"] = sorted(list(extracted_pages))
    
    if len(progress["extracted_pages"]) == total_pages:
        progress["status"] = "complete"
        print("Set status to 'complete'")
        
    with open(progress_path, "w", encoding="utf-8") as f:
        json.dump(progress, f, indent=2, ensure_ascii=False)

    # 6. Consolidate everything
    print("Consolidating JSON files...")
    merged_file = consolidate_extracted_json(output_dir, pdf_path.name, total_pages)
    print(f"[SUCCESS] Re-extraction complete! Consolidated file saved to: {merged_file}")

if __name__ == "__main__":
    extract_missing_pages()
