import sys
import json
import re
from pathlib import Path
import fitz
import numpy as np
from collections import Counter

# Add project root to sys.path
ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

try:
    from rapidocr_onnxruntime import RapidOCR
    RAPID_OCR_AVAILABLE = True
except ImportError:
    RAPID_OCR_AVAILABLE = False

from gemini_batch_extract import consolidate_extracted_json

def build_dictionary_from_book():
    """Builds a vocabulary of valid words directly from the other successfully parsed pages of the book."""
    dir_path = Path("output/TRIBES INDIA")
    word_counts = Counter()
    
    if not dir_path.exists():
        return set()
        
    for f in dir_path.glob("page_*.json"):
        # Skip the pages we know are blank or newly OCR'd
        page_num = int(f.stem.split("_")[1])
        if page_num in [10, 12, 13, 14, 15, 16, 17, 18, 50, 51, 82, 83, 84, 191, 196, 198, 199, 200, 205, 206, 240, 263, 281, 290]:
            continue
            
        try:
            with open(f, "r", encoding="utf-8") as file:
                data = json.load(file)
                for block in data.get("text_blocks", []):
                    text = block.get("text", "")
                    words = re.findall(r"\b[a-zA-Z]{2,}\b", text.lower())
                    word_counts.update(words)
        except Exception:
            pass
            
    dictionary = set(word_counts.keys())
    
    # Common short words
    dictionary.update([
        "a", "an", "the", "in", "on", "at", "to", "of", "and", "or", "is", "was", "for", "by", "as", 
        "it", "he", "she", "they", "we", "us", "him", "her", "his", "their", "them", "who", "whom", 
        "its", "our", "you", "your"
    ])
    
    # Common UPSC History/Anthropology keywords
    COMMON_UPSC_KEYWORDS = [
        "indus", "harappa", "harappan", "munda", "naga", "nagas", "tribal", "india", "today", "british", "colonial", 
        "ryotwari", "zamindari", "revolt", "struggle", "independence", "anthropology", "anthropologist", "culture", 
        "racial", "origin", "prehistoric", "history", "civilization", "archaeological", "palaeontological", "mohenjodaro", 
        "aryans", "aryan", "rigvedic", "dasas", "dasyus", "asuras", "hinduism", "sanskrit", "brahmin", "caste", "castes", 
        "chandalas", "buddha", "ashoka", "maurya", "gupta", "mughal", "delhi", "sultanate", "gandhi", "nehru", "congress", 
        "national", "movement", "santhal", "oraon", "gond", "bhil", "todas", "khasi", "garo", "jaintia", "kuki", "chenchu", 
        "kadmbari", "panchatantra", "puran", "vedic", "ramayan", "mahabharat", "elwin", "ghurye", "srinivas", "dube", 
        "majumdar", "bose", "guha", "risley"
    ]
    dictionary.update(COMMON_UPSC_KEYWORDS)
    
    return dictionary

def split_run_together_word(s: str, word_set: set) -> str:
    """Dynamic programming dynamic segmenter to split run-together words."""
    if s.lower() in word_set:
        return s
        
    memo = {}
    
    def solve(sub):
        if not sub:
            return []
        if sub in memo:
            return memo[sub]
            
        best = None
        for i in range(1, len(sub) + 1):
            prefix = sub[:i]
            if prefix in word_set or (len(prefix) == 1 and prefix in ["a", "i"]):
                suffix_splits = solve(sub[i:])
                if suffix_splits is not None:
                    cand = [prefix] + suffix_splits
                    if best is None or len(cand) < len(best):
                        best = cand
        memo[sub] = best
        return best

    splits = solve(s.lower())
    if splits:
        return " ".join(splits)
    return s

def clean_sentence_locally(sentence: str, word_set: set) -> str:
    """Tokenizes a sentence and fixes any run-together words locally."""
    tokens = sentence.split()
    cleaned_tokens = []
    for token in tokens:
        clean_match = re.match(r"^([^\w]*)(.*?)([^\w]*)$", token)
        if clean_match:
            prefix, word, suffix = clean_match.groups()
            if len(word) > 7 and not word.lower() in word_set:
                split_word = split_run_together_word(word, word_set)
                cleaned_tokens.append(f"{prefix}{split_word}{suffix}")
            else:
                cleaned_tokens.append(token)
        else:
            cleaned_tokens.append(token)
            
    return " ".join(cleaned_tokens)

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
    
    print("Building dictionary from other book pages...")
    word_set = build_dictionary_from_book()
    print(f"Dictionary ready with {len(word_set)} words.")
    
    print(f"Starting Local Column-Aware RapidOCR extraction with Local Word Segmentation for pages: {missing_pages}")

    ocr_engine = RapidOCR()
    doc = fitz.open(str(pdf_path))
    total_pages = len(doc)

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
                
                if any(pat.search(line_text) for pat in ignore_patterns):
                    continue
                    
                xc = (box[0][0] + box[1][0] + box[2][0] + box[3][0]) / 4.0
                yc = (box[0][1] + box[1][1] + box[2][1] + box[3][1]) / 4.0
                
                if yc < ph * 0.08:
                    headers.append(line_text)
                elif yc > ph * 0.92:
                    footers.append(line_text)
                elif xc < x_mid:
                    col1.append((yc, line_text))
                else:
                    col2.append((yc, line_text))
            
            col1.sort(key=lambda x: x[0])
            col2.sort(key=lambda x: x[0])
            
            # Group text and clean spacing issues locally
            left_para = " ".join([text for yc, text in col1]).strip()
            right_para = " ".join([text for yc, text in col2]).strip()
            
            left_para = clean_sentence_locally(left_para, word_set)
            right_para = clean_sentence_locally(right_para, word_set)
            
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
