"""
models.py
──────────
Pydantic data models for preprocessing & chunking stage.
"""

from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional


class ChunkMetadata(BaseModel):
    file_name: str
    page_numbers: List[int]
    source_block_ids: List[str]
    mermaid_codes: Optional[List[str]] = None
    sub_chunk_index: Optional[int] = None   # e.g. 1, 2 — set when a dense page is split
    total_sub_chunks: Optional[int] = None  # e.g. 2 — total splits for this page


class ChunkItem(BaseModel):
    chunk_id: str
    text: str
    character_count: int
    metadata: ChunkMetadata


class PreprocessedOutput(BaseModel):
    metadata: Dict[str, Any]
    chunk_count: int
    chunks: List[ChunkItem]
