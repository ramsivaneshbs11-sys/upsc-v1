import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

DEFAULT_INPUT_DIR = BASE_DIR / "data" / "extracted"
DEFAULT_OUTPUT_DIR = BASE_DIR / "data" / "preprocessed"

DEFAULT_INPUT_DIR.mkdir(parents=True, exist_ok=True)
DEFAULT_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# Page-Wise Hybrid chunking constants
DEFAULT_MAX_CHUNK_SIZE = 1200   # Hard cap per chunk — keeps BGE safely under 512 tokens
DEFAULT_MIN_PAGE_SIZE  = 300    # Tiny pages below this are merged with the next page

# Kept for backward-compatibility with benchmark.py / main.py CLI flags
DEFAULT_CHUNK_SIZE    = DEFAULT_MAX_CHUNK_SIZE
DEFAULT_CHUNK_OVERLAP = 0
