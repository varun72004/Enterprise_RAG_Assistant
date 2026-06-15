import logging
from bs4 import BeautifulSoup
from typing import List, Dict, Any
from pathlib import Path

logger = logging.getLogger(__name__)

class HTMLLoader:
    """Loader for HTML documents using BeautifulSoup."""

    @staticmethod
    def load(file_path: str) -> List[Dict[str, Any]]:
        """
        Extract clean text from an HTML file.
        
        Args:
            file_path: Path to the HTML file.
            
        Returns:
            List with a single dictionary containing the full text and metadata.
        """
        logger.info(f"Loading HTML file: {file_path}")
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                html_content = f.read()
                
            soup = BeautifulSoup(html_content, "html.parser")
            
            # Remove script and style elements
            for script_or_style in soup(["script", "style", "noscript", "meta", "link"]):
                script_or_style.decompose()
                
            # Get text and clean it up
            text = soup.get_text(separator="\n")
            lines = (line.strip() for line in text.splitlines())
            chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
            clean_text = "\n".join(chunk for chunk in chunks if chunk)
            
            filename = Path(file_path).name
            
            return [{
                "text": clean_text,
                "metadata": {
                    "source_file": filename,
                    "page_number": 1,
                    "document_type": "html"
                }
            }]
        except Exception as e:
            logger.error(f"Error loading HTML {file_path}: {str(e)}")
            raise
