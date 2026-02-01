"""PDF text extraction wrapper using Unstructured.io.

This module provides a clean abstraction over the Unstructured library,
making it easy to swap PDF parsing libraries in the future without
affecting the rest of the codebase.
"""

import io
from typing import Any


class PDFExtractionError(Exception):
    """Raised when PDF extraction fails."""

    pass


def partition_pdf(*args, **kwargs):
    """Lazily import and call Unstructured's PDF partitioner.

    Kept as a module-level symbol so tests can patch `app.parsers.extractor.partition_pdf`
    without importing heavy dependencies at process start.
    """
    from unstructured.partition.pdf import partition_pdf as _partition_pdf

    return _partition_pdf(*args, **kwargs)


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

        normalized_password = password.strip() if isinstance(password, str) else None
        if normalized_password == "":
            normalized_password = None

        try:
            # If encrypted, validate/decrypt up-front using pypdf.
            # This avoids relying on downstream libraries to handle all encryption variants,
            # and ensures we return correct error codes (required vs incorrect password).
            bytes_to_parse = pdf_bytes
            password_for_unstructured = normalized_password
            if pdf_bytes.startswith(b"%PDF"):
                try:
                    from pypdf import PdfReader, PdfWriter
                except ImportError:
                    PdfReader = None  # type: ignore[assignment]
                    PdfWriter = None  # type: ignore[assignment]

                if PdfReader is not None and PdfWriter is not None:
                    try:
                        reader = PdfReader(io.BytesIO(pdf_bytes))
                    except Exception:
                        reader = None

                    if reader is not None and getattr(reader, "is_encrypted", False):
                        password_to_try = normalized_password
                        if not password_to_try:
                            # Some PDFs are encrypted but use an empty user password.
                            password_to_try = ""

                        ok = reader.decrypt(password_to_try)
                        if not ok:
                            if not normalized_password:
                                raise ValueError("PDF password required")
                            raise ValueError("Incorrect PDF password")

                        # Decrypt to plain PDF bytes for downstream parsing.
                        try:
                            writer = PdfWriter()
                            for page in reader.pages:
                                writer.add_page(page)
                            out = io.BytesIO()
                            writer.write(out)
                        except Exception:
                            # If pypdf can't re-write this decrypted PDF, fall back to Unstructured.
                            bytes_to_parse = pdf_bytes
                            password_for_unstructured = normalized_password
                        else:
                            bytes_to_parse = out.getvalue()
                            password_for_unstructured = None

            # Use BytesIO to avoid temp files
            pdf_file = io.BytesIO(bytes_to_parse)

            try:
                elements = partition_pdf(
                    file=pdf_file,
                    strategy=self.strategy,
                    include_page_breaks=True,      # Helps with multi-page statements
                    infer_table_structure=True,    # Extract transaction tables
                    extract_images_in_pdf=False,   # Skip images for security/speed
                    password=password_for_unstructured,  # Handle encrypted PDFs (if still encrypted)
                )
            except Exception:
                # Unstructured may fail due to optional OCR dependencies (tesseract),
                # font cache/temp issues, or model downloads. Fall back to deterministic
                # pypdf text extraction so downstream parsers can still run.
                if bytes_to_parse.startswith(b"%PDF"):
                    try:
                        from pypdf import PdfReader

                        reader = PdfReader(io.BytesIO(bytes_to_parse))
                        if getattr(reader, "is_encrypted", False):
                            ok = reader.decrypt(password_for_unstructured or "")
                            if not ok:
                                if not password_for_unstructured:
                                    raise ValueError("PDF password required")
                                raise ValueError("Incorrect PDF password")

                        texts = [(page.extract_text() or "") for page in reader.pages]
                        texts = [t for t in texts if t.strip()]
                        if texts:
                            class _TextElement:
                                __slots__ = ("text", "category")

                                def __init__(self, text: str):
                                    self.text = text
                                    self.category = "NarrativeText"

                                def __str__(self) -> str:
                                    return self.text

                            return [_TextElement(t) for t in texts]
                    except Exception:
                        pass
                raise
            
            if not elements:
                raise ValueError("PDF extraction returned no elements (empty or corrupted)")

            return elements

        except Exception as e:
            # Provide user-friendly error messages
            error_msg = str(e).lower()
            
            if "password" in error_msg or "encrypted" in error_msg:
                # Unstructured throws different exceptions depending on PDF backend.
                # When no password is provided, prompt for one; otherwise treat as incorrect.
                if not normalized_password:
                    raise ValueError("PDF password required") from e
                raise ValueError("Incorrect PDF password") from e
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
