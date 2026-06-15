import csv
import logging
from typing import List, Dict, Any
from pathlib import Path

logger = logging.getLogger(__name__)

class CSVLoader:
    """Loader for CSV documents."""

    @staticmethod
    def load(file_path: str) -> List[Dict[str, Any]]:
        """
        Convert rows into structured text.
        
        Args:
            file_path: Path to the CSV file.
            
        Returns:
            List of dictionaries containing row text and metadata.
        """
        logger.info(f"Loading CSV file: {file_path}")
        pages = []
        try:
            filename = Path(file_path).name
            with open(file_path, "r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                
                # Each row becomes a "page" or structured block of text
                row_idx = 1
                for row in reader:
                    # Convert row to a readable text representation
                    row_text = "\n".join(f"{k}: {v}" for k, v in row.items() if v)
                    
                    pages.append({
                        "text": row_text,
                        "metadata": {
                            "source_file": filename,
                            "page_number": row_idx,
                            "document_type": "csv"
                        }
                    })
                    row_idx += 1
                    
            logger.info(f"Successfully loaded {len(pages)} rows from {filename}")
        except Exception as e:
            logger.error(f"Error loading CSV {file_path}: {str(e)}")
            raise
            
        return pages
