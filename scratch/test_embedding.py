import sys
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

try:
    print("Importing sentence_transformers...")
    from sentence_transformers import SentenceTransformer
    print("SentenceTransformers imported successfully!")
    
    model_name = "BAAI/bge-base-en-v1.5"
    print(f"Loading model: {model_name}...")
    model = SentenceTransformer(model_name)
    print("Model loaded successfully!")
    
    print("Encoding a test sentence...")
    vecs = model.encode(["Hello World!"], normalize_embeddings=True)
    print(f"Encoded successfully! Vector shape: {vecs.shape}")
except Exception as e:
    logger.exception("Failed to run embedding:")
    sys.exit(1)
