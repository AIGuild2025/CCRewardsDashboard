import pdfplumber
import fitz
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def extract_text_pdfplumber(pdf_path):
    try:
        text_lines = []
        with pdfplumber.open(pdf_path) as pdf:
            for page in pdf.pages:
                text = page.extract_text()
                if text:
                    text_lines.extend(text.split('\n'))
        logger.info(f"[pdfplumber] Extracted {len(text_lines)} lines from {pdf_path}")
        return text_lines
    except Exception as e:
        logger.error(f"[pdfplumber] Failed to extract text: {e}")
        return None


def extract_text_pymupdf(pdf_path):
    try:
        text_lines = []
        doc = fitz.open(pdf_path)
        for page_num in range(len(doc)):
            page = doc[page_num]
            text = page.get_text()
            if text:
                text_lines.extend(text.split('\n'))
        doc.close()
        logger.info(f"[PyMuPDF] Extracted {len(text_lines)} lines from {pdf_path}")
        return text_lines
    except Exception as e:
        logger.error(f"[PyMuPDF] Failed to extract text: {e}")
        return None


def extract_text(pdf_path):
    logger.info(f"Starting text extraction from: {pdf_path}")

    text_lines = extract_text_pdfplumber(pdf_path)

    if text_lines is None or len(text_lines) == 0:
        logger.warning("pdfplumber failed or returned no text, falling back to PyMuPDF")
        text_lines = extract_text_pymupdf(pdf_path)

    if text_lines is None or len(text_lines) == 0:
        logger.error("Both extractors failed. Cannot process PDF.")
        return []

    text_lines = [line.strip() for line in text_lines if line.strip()]
    logger.info(f"Final extracted lines: {len(text_lines)}")
    return text_lines


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        pdf_path = sys.argv[1]
        lines = extract_text(pdf_path)
        for line in lines[:20]:
            print(line)
