"""PDF text extraction service using PyMuPDF with optional OCR fallback."""

import logging
from pathlib import Path

import fitz  # PyMuPDF

logger = logging.getLogger(__name__)

# Check if Tesseract is available
_TESSERACT_AVAILABLE = False
try:
    import pytesseract
    from PIL import Image
    import io
    # Quick check if tesseract binary exists
    pytesseract.get_tesseract_version()
    _TESSERACT_AVAILABLE = True
    logger.info("Tesseract OCR is available for fallback text extraction.")
except Exception:
    logger.info("Tesseract OCR not available. OCR fallback will be disabled.")


def _ocr_page(page: fitz.Page) -> str:
    """Extract text from a page using OCR.
    
    Converts the PDF page to an image and runs Tesseract OCR.
    
    Args:
        page: A PyMuPDF page object.
        
    Returns:
        Extracted text string, or empty string on failure.
    """
    if not _TESSERACT_AVAILABLE:
        return ""
    
    try:
        # Render page to image at 300 DPI for good OCR quality
        mat = fitz.Matrix(300 / 72, 300 / 72)
        pixmap = page.get_pixmap(matrix=mat)
        img_data = pixmap.tobytes("png")
        image = Image.open(io.BytesIO(img_data))
        
        text = pytesseract.image_to_string(image)
        return text.strip()
    except Exception as e:
        logger.warning(f"OCR failed for page {page.number + 1}: {e}")
        return ""


def extract_text(filepath: Path) -> list[dict]:
    """Extract text from a PDF file page by page.
    
    Uses PyMuPDF for direct text extraction. Falls back to OCR
    (if Tesseract is available) when a page yields no text.
    
    Args:
        filepath: Path to the PDF file.
        
    Returns:
        List of dicts with 'page' (1-indexed) and 'text' keys.
        Empty pages are skipped.
        
    Raises:
        ValueError: If the file cannot be opened as a PDF.
        FileNotFoundError: If the file does not exist.
    """
    if not filepath.exists():
        raise FileNotFoundError(f"PDF file not found: {filepath}")
    
    pages_data: list[dict] = []
    
    try:
        doc = fitz.open(str(filepath))
    except Exception as e:
        raise ValueError(f"Failed to open PDF '{filepath.name}': {e}") from e
    
    try:
        total_pages = len(doc)
        logger.info(f"Processing '{filepath.name}': {total_pages} pages")
        
        for page_num in range(total_pages):
            page = doc[page_num]
            
            # Try direct text extraction first
            text = page.get_text("text").strip()
            
            # Fall back to OCR if no text found
            if not text:
                logger.debug(f"Page {page_num + 1}: No text found, attempting OCR...")
                text = _ocr_page(page)
            
            # Skip truly empty pages
            if not text:
                logger.debug(f"Page {page_num + 1}: Skipped (empty)")
                continue
            
            pages_data.append({
                "page": page_num + 1,  # 1-indexed
                "text": text,
            })
        
        logger.info(
            f"Extracted text from {len(pages_data)}/{total_pages} pages "
            f"of '{filepath.name}'"
        )
    finally:
        doc.close()
    
    return pages_data


def get_pdf_page_count(filepath: Path) -> int:
    """Get the total number of pages in a PDF.
    
    Args:
        filepath: Path to the PDF file.
        
    Returns:
        Number of pages in the PDF.
    """
    try:
        doc = fitz.open(str(filepath))
        count = len(doc)
        doc.close()
        return count
    except Exception:
        return 0
