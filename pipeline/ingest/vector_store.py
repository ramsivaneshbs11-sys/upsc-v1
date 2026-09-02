from qdrant_client import QdrantClient
from qdrant_client.models import VectorParams, Distance, PointStruct
from rank_bm25 import BM25Okapi
import uuid
from typing import List, Dict, Any
import logging

logger = logging.getLogger(__name__)

class VectorStore:
    def __init__(self, collection_name: str = "upsc_knowledge", vector_size: int = 384):
        """
        Initializes Qdrant Client (in-memory for simple testing, can be disk-based).
        """
        # For MVP, running in memory. For production, switch to:
        # self.client = QdrantClient("localhost", port=6333) 
        self.client = QdrantClient(":memory:")
        self.collection_name = collection_name
        self.vector_size = vector_size
        
        self.client.recreate_collection(
            collection_name=self.collection_name,
            vectors_config=VectorParams(size=self.vector_size, distance=Distance.COSINE),
        )
        self.bm25_corpus = []
        self.bm25_model = None
        self.documents_metadata = []

    def index_documents(self, documents: List[Dict[str, Any]]):
        """
        Indexes chunks into Qdrant (dense vectors) AND builds the BM25 model (sparse).
        """
        points = []
        tokenized_corpus = []
        
        for doc in documents:
            doc_id = str(uuid.uuid4())
            text = doc["text"]
            metadata = doc["metadata"]
            embedding = doc["embedding"]
            
            # Prepare Dense Vector
            points.append(PointStruct(id=doc_id, vector=embedding, payload={"text": text, **metadata}))
            
            # Prepare Sparse / Keyword index (BM25)
            tokenized_corpus.append(text.lower().split(" "))
            self.documents_metadata.append({"id": doc_id, "text": text, "metadata": metadata})

        logger.info(f"Uploading {len(points)} points to Qdrant collection '{self.collection_name}'...")
        self.client.upsert(
            collection_name=self.collection_name,
            points=points
        )
        
        logger.info("Building BM25 Index...")
        self.bm25_model = BM25Okapi(tokenized_corpus)
        logger.info("Indexing complete.")

    def search_hybrid(self, query: str, query_embedding: List[float], top_k: int = 5) -> List[Dict[str, Any]]:
        """
        Performs vector search + BM25 search. Returns combined results.
        """
        pass # To be implemented in retriever service

if __name__ == "__main__":
    vs = VectorStore()
    print("VectorStore initialized.")
