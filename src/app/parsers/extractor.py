"""PDF text extraction wrapper using Unstructured.io.

This module provides a clean abstraction over the Unstructured library,
making it easy to swap PDF parsing libraries in the future without
affecting the rest of the codebase.
"""

import io
from typing import Any

from unstructured.partition.pdf import partition_pdf


class PDFExtractionError(Exception):
    """Raised when PDF extraction fails."""

    pass


class PDFExtractor:
    """Wrapper around Unstructured.io for PDF text extraction.

    This class provides a simplified interface for extracting structured
    elements from PDF documents. All processing happens in-memory without
    creating temporary files.

    Example:
        >>> extractor = PDFExtractor()
        >>> elements = extractor.extract(pdf_bytes)
        >>> full_text = extractor.get_full_text(elements)
    """

    def __init__(self, strategy: str = "auto"):
        """Initialize the PDF extractor.

        Args:
            strategy: Extraction strategy - "auto", "fast", "hi_res", or "ocr_only".
                     "auto" - Let Unstructured choose based on document (recommended)
                     "fast" - Fast text extraction, no image processing
                     "hi_res" - Better table detection, slower
                     "ocr_only" - Force OCR even on text PDFs
        """
        self.strategy = strategy

    def extract(self, pdf_bytes: bytes, password: str | None = None) -> list[Any]:
        """Extract structured elements from a PDF.

        Args:
            pdf_bytes: PDF file content as bytes
            password: Optional password for encrypted PDFs

        Returns:
            List of Element objects from Unstructured (text, tables, etc.)

        Raises:
            PDFExtractionError: If extraction fails
            ValueError: If PDF is corrupted or password incorrect
        """
        if not pdf_bytes or len(pdf_bytes) == 0:
            raise ValueError("PDF bytes cannot be empty")
        
        try:
            # Use BytesIO to avoid temp files
            pdf_file = io.BytesIO(pdf_bytes)

            elements = partition_pdf(
                file=pdf_file,
                strategy=self.strategy,
                include_page_breaks=True,      # Helps with multi-page statements
                infer_table_structure=True,    # Extract transaction tables
                extract_images_in_pdf=False,   # Skip images for security/speed
                password=password,             # Handle encrypted PDFs
            )
            
            if not elements:
                raise ValueError("PDF extraction returned no elements (empty or corrupted)")

            return elements

        except Exception as e:
            # Provide user-friendly error messages
            error_msg = str(e).lower()
            
            if "password" in error_msg or "encrypted" in error_msg:
                raise ValueError("PDF is password-protected or password is incorrect") from e
            elif "corrupt" in error_msg or "invalid" in error_msg:
                raise ValueError("PDF file appears to be corrupted") from e
            else:
                raise PDFExtractionError(f"Failed to extract PDF content: {e}") from e

    def get_full_text(self, elements: list[Any]) -> str:
        """Concatenate all element text into a single string.

        Args:
            elements: List of Element objects from extract()

        Returns:
            Full text content of the PDF
        """
        return "\n".join(str(element) for element in elements)

    def get_text_by_type(self, elements: list[Any], element_type: str) -> list[str]:
        """Filter elements by type and return their text.

        Args:
            elements: List of Element objects
            element_type: Type to filter by (e.g., "Title", "Table", "NarrativeText")

        Returns:
            List of text strings matching the type
        """
        return [
            str(element) for element in elements if element.category == element_type
        ]

    def extract_tables(self, elements: list[Any]) -> list[str]:
        """Extract only table elements from the PDF.

        Args:
            elements: List of Element objects

        Returns:
            List of table text (often contains transaction data)
        """
        return self.get_text_by_type(elements, "Table")
