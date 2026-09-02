from typing import List, Dict, Any
from langchain.text_splitter import RecursiveCharacterTextSplitter
import logging

logger = logging.getLogger(__name__)

class Chunker:
    def __init__(self, chunk_size: int = 1000, chunk_overlap: int = 200):
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            length_function=len,
            is_separator_regex=False,
            separators=["\n\n", "\n", " ", ""]
        )

    def chunk_documents(self, documents: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Chunks the input documents while preserving metadata.
        Documents should be a list of dicts with 'text' and 'metadata' keys.
        """
        chunked_data = []
        for doc in documents:
            text = doc.get("text", "")
            metadata = doc.get("metadata", {})
            
            if not text.strip():
                continue
                
            chunks = self.text_splitter.split_text(text)
            for i, chunk in enumerate(chunks):
                chunk_metadata = metadata.copy()
                chunk_metadata["chunk_index"] = i
                
                chunked_data.append({
                    "text": chunk,
                    "metadata": chunk_metadata
                })
        
        logger.info(f"Created {len(chunked_data)} chunks from {len(documents)} documents.")
        return chunked_data

if __name__ == "__main__":
    chunker = Chunker()
    print("Chunker initialized.")
