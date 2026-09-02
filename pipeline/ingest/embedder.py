from sentence_transformers import SentenceTransformer
from typing import List, Dict, Any
import logging

logger = logging.getLogger(__name__)

class Embedder:
    def __init__(self, model_name: str = "all-MiniLM-L6-v2"):
        """
        Initializes the sentence transformer model.
        For production, this can be swapped with Qwen3-Embedding-8B via Together.ai.
        """
        logger.info(f"Loading embedding model: {model_name}")
        self.model = SentenceTransformer(model_name)

    def embed_documents(self, documents: List[Dict[str, Any]], batch_size: int = 32) -> List[Dict[str, Any]]:
        """
        Embeds the chunked documents.
        Adds 'embedding' key to each document.
        """
        texts = [doc["text"] for doc in documents]
        
        logger.info(f"Embedding {len(texts)} chunks...")
        embeddings = self.model.encode(texts, batch_size=batch_size, show_progress_bar=True)
        
        for doc, emb in zip(documents, embeddings):
            doc["embedding"] = emb.tolist()
            
        logger.info("Embedding complete.")
        return documents

if __name__ == "__main__":
    embedder = Embedder()
    print("Embedder initialized.")
