import os
import argparse
import logging
from .pdf_extractor import PDFExtractor
from .chunker import Chunker
from .embedder import Embedder
from .vector_store import VectorStore

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def main():
    parser = argparse.ArgumentParser(description="Run the UPSC Ingestion Pipeline")
    parser.add_argument("--data_dir", type=str, default="data/HISTORY", help="Directory containing PDFs")
    args = parser.parse_args()

    # 1. Initialize components
    extractor = PDFExtractor(data_dir=args.data_dir)
    chunker = Chunker()
    embedder = Embedder()
    vector_store = VectorStore(collection_name="upsc_knowledge")

    all_pages = []

    # 2. Extract
    logger.info(f"Starting extraction from {args.data_dir}...")
    for root, _, files in os.walk(args.data_dir):
        for file in files:
            if file.lower().endswith('.pdf'):
                pdf_path = os.path.join(root, file)
                logger.info(f"Processing {pdf_path}")
                pages = extractor.extract_text_with_metadata(pdf_path)
                all_pages.extend(pages)

    if not all_pages:
        logger.warning("No pages extracted. Exiting.")
        return

    # 3. Chunk
    logger.info("Starting chunking...")
    chunks = chunker.chunk_documents(all_pages)

    # 4. Embed
    logger.info("Starting embedding...")
    embedded_chunks = embedder.embed_documents(chunks)

    # 5. Index
    logger.info("Starting indexing to Vector DB...")
    vector_store.index_documents(embedded_chunks)
    
    logger.info(f"Pipeline complete! Successfully ingested {len(embedded_chunks)} chunks.")

if __name__ == "__main__":
    main()
