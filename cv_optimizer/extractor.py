import pymupdf
import logging

logger = logging.getLogger(__name__)

class PDFExtractor:
    @staticmethod
    def extract_text(pdf_path: str) -> str:
        """Extracts text from a PDF file."""
        try:
            text = ""
            with pymupdf.open(pdf_path) as doc:
                for page in doc:
                    text += page.get_text()
            return text
        except Exception as e:
            logger.error(f"Failed to extract text from {pdf_path}: {e}")
            raise
