import pymupdf
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

class PDFExtractor:
    @staticmethod
    def extract_text(pdf_path: str) -> str:
        """Extracts text from a PDF file.

        Non-PDF files (markdown JDs from discovery, plain-text JDs from the
        browser extension, etc.) are read directly as text. Only actual PDF
        documents go through pymupdf.
        """
        path = Path(pdf_path)
        if path.suffix.lower() != ".pdf":
            return path.read_text(encoding="utf-8", errors="replace")
        try:
            text = ""
            with pymupdf.open(str(path)) as doc:
                for page in doc:
                    text += page.get_text()
            return text
        except Exception as e:
            logger.error(f"Failed to extract text from {pdf_path}: {e}")
            raise
