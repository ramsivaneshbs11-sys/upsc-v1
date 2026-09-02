import fitz  # PyMuPDF
import os
import re
from typing import List, Dict, Any
import logging

logger = logging.getLogger(__name__)

class PDFExtractor:
    def __init__(self, data_dir: str):
        self.data_dir = data_dir
        
    def extract_text_with_metadata(self, pdf_path: str) -> List[Dict[str, Any]]:
        """
        Extracts text from a PDF page by page, attaching metadata like source and page number.
        Returns a list of dictionaries, one for each page.
        """
        if not os.path.exists(pdf_path):
            logger.error(f"File not found: {pdf_path}")
            return []
            
        filename = os.path.basename(pdf_path)
        subject_dir = os.path.basename(os.path.dirname(pdf_path))
        
        pages_data = []
        try:
            doc = fitz.open(pdf_path)
            for page_num in range(len(doc)):
                page = doc.load_page(page_num)
                text = page.get_text("text")
                
                # Clean text: remove excessive newlines and weird spaces
                text = re.sub(r'\n+', '\n', text)
                text = re.sub(r' +', ' ', text).strip()
                
                if len(text) > 50:  # Skip mostly empty pages
                    pages_data.append({
                        "text": text,
                        "metadata": {
                            "source": filename,
                            "subject": subject_dir,
                            "page": page_num + 1,
                            "type": "textbook"
                        }
                    })
            doc.close()
            logger.info(f"Extracted {len(pages_data)} pages from {filename}")
        except Exception as e:
            logger.error(f"Error processing {pdf_path}: {str(e)}")
            
        return pages_data

if __name__ == "__main__":
    # Test execution
    extractor = PDFExtractor(data_dir="../../data")
    print("PDFExtractor initialized.")
