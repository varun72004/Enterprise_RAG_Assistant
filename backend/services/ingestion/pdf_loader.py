import fitz  # PyMuPDF
import logging
from typing import List, Dict, Any
from pathlib import Path

logger = logging.getLogger(__name__)

class PDFLoader:
    """Loader for PDF documents using PyMuPDF (fitz)."""

    @staticmethod
    def load(file_path: str) -> List[Dict[str, Any]]:
        """
        Extract text from a PDF file and preserve page metadata.
        
        Args:
            file_path: Path to the PDF file.
            
        Returns:
            List of dictionaries containing page text and metadata.
        """
        logger.info(f"Loading PDF file: {file_path}")
        pages = []
        try:
            doc = fitz.open(file_path)
            filename = Path(file_path).name
            
            for page_num in range(len(doc)):
                page = doc[page_num]
                text = page.get_text("text").strip()
                
                if text:
                    pages.append({
                        "text": text,
                        "metadata": {
                            "source_file": filename,
                            "page_number": page_num + 1,
                            "document_type": "pdf"
                        }
                    })
            doc.close()
            logger.info(f"Successfully loaded {len(pages)} pages from {filename}")
        except Exception as e:
            logger.error(f"Error loading PDF {file_path}: {str(e)}")
            raise
            
        return pages
