"""Tests for PDF extractor wrapper."""

import io
from unittest.mock import Mock, patch

import pytest
from pypdf import PdfWriter

from app.parsers.extractor import PDFExtractionError, PDFExtractor


class TestPDFExtractor:
    """Test suite for PDFExtractor."""

    def test_initialization(self):
        """Test extractor can be initialized with different strategies."""
        extractor = PDFExtractor()
        assert extractor.strategy == "auto"

        extractor_hirez = PDFExtractor(strategy="hi_res")
        assert extractor_hirez.strategy == "hi_res"

    @patch("app.parsers.extractor.partition_pdf")
    def test_extract_success(self, mock_partition):
        """Test successful PDF extraction."""
        # Setup mock
        mock_element1 = Mock()
        mock_element1.__str__ = Mock(return_value="Line 1")
        mock_element2 = Mock()
        mock_element2.__str__ = Mock(return_value="Line 2")
        mock_partition.return_value = [mock_element1, mock_element2]

        # Test
        extractor = PDFExtractor()
        pdf_bytes = b"fake pdf content"
        elements = extractor.extract(pdf_bytes)

        # Verify
        assert len(elements) == 2
        mock_partition.assert_called_once()
        call_kwargs = mock_partition.call_args.kwargs
        assert call_kwargs["strategy"] == "auto"
        assert call_kwargs["include_page_breaks"] is True
        assert call_kwargs["infer_table_structure"] is True
        assert call_kwargs["extract_images_in_pdf"] is False
        assert call_kwargs["password"] is None

    @patch("app.parsers.extractor.partition_pdf")
    def test_extract_uses_bytesio(self, mock_partition):
        """Test that extract uses BytesIO (no temp files)."""
        # Mock with elements to avoid empty validation error
        mock_element = Mock()
        mock_partition.return_value = [mock_element]

        extractor = PDFExtractor()
        pdf_bytes = b"fake pdf"
        extractor.extract(pdf_bytes)

        # Verify BytesIO was used
        call_kwargs = mock_partition.call_args.kwargs
        assert isinstance(call_kwargs["file"], io.BytesIO)

    @patch("app.parsers.extractor.partition_pdf")
    def test_extract_failure(self, mock_partition):
        """Test extraction error handling."""
        mock_partition.side_effect = Exception("PDF is corrupted")

        extractor = PDFExtractor()
        with pytest.raises(ValueError) as exc_info:
            extractor.extract(b"bad pdf")

        assert "corrupted" in str(exc_info.value).lower()

    @patch("app.parsers.extractor.partition_pdf")
    def test_extract_encrypted_requires_password(self, mock_partition):
        """Encrypted PDFs should prompt for password before calling Unstructured."""
        w = PdfWriter()
        w.add_blank_page(width=200, height=200)
        w.encrypt("secret")
        buf = io.BytesIO()
        w.write(buf)
        encrypted = buf.getvalue()

        extractor = PDFExtractor()
        with pytest.raises(ValueError, match="password required"):
            extractor.extract(encrypted, password=None)

        mock_partition.assert_not_called()

    @patch("app.parsers.extractor.partition_pdf")
    def test_extract_encrypted_incorrect_password(self, mock_partition):
        """Encrypted PDFs with wrong password should raise incorrect password."""
        w = PdfWriter()
        w.add_blank_page(width=200, height=200)
        w.encrypt("secret")
        buf = io.BytesIO()
        w.write(buf)
        encrypted = buf.getvalue()

        extractor = PDFExtractor()
        with pytest.raises(ValueError, match="(?i)incorrect pdf password"):
            extractor.extract(encrypted, password="wrong")

        mock_partition.assert_not_called()

    @patch("app.parsers.extractor.partition_pdf")
    def test_extract_encrypted_correct_password_decrypts(self, mock_partition):
        """Encrypted PDFs should be decrypted before passing to Unstructured."""
        w = PdfWriter()
        w.add_blank_page(width=200, height=200)
        w.encrypt("secret")
        buf = io.BytesIO()
        w.write(buf)
        encrypted = buf.getvalue()

        mock_element = Mock()
        mock_partition.return_value = [mock_element]

        extractor = PDFExtractor()
        elements = extractor.extract(encrypted, password="secret")
        assert elements == [mock_element]

        call_kwargs = mock_partition.call_args.kwargs
        assert isinstance(call_kwargs["file"], io.BytesIO)
        # Should not pass password downstream after decrypt.
        assert call_kwargs["password"] is None

    def test_get_full_text(self):
        """Test concatenating element text."""
        mock_element1 = Mock()
        mock_element1.__str__ = Mock(return_value="HDFC Bank")
        mock_element2 = Mock()
        mock_element2.__str__ = Mock(return_value="Statement Period")

        extractor = PDFExtractor()
        full_text = extractor.get_full_text([mock_element1, mock_element2])

        assert full_text == "HDFC Bank\nStatement Period"

    def test_get_full_text_empty(self):
        """Test get_full_text with empty elements."""
        extractor = PDFExtractor()
        full_text = extractor.get_full_text([])
        assert full_text == ""

    def test_get_text_by_type(self):
        """Test filtering elements by type."""
        mock_table = Mock()
        mock_table.category = "Table"
        mock_table.__str__ = Mock(return_value="Table content")

        mock_text = Mock()
        mock_text.category = "NarrativeText"
        mock_text.__str__ = Mock(return_value="Narrative content")

        extractor = PDFExtractor()
        tables = extractor.get_text_by_type([mock_table, mock_text], "Table")

        assert len(tables) == 1
        assert tables[0] == "Table content"

    def test_extract_tables(self):
        """Test extracting only table elements."""
        mock_table1 = Mock()
        mock_table1.category = "Table"
        mock_table1.__str__ = Mock(return_value="Transaction table")

        mock_table2 = Mock()
        mock_table2.category = "Table"
        mock_table2.__str__ = Mock(return_value="Summary table")

        mock_text = Mock()
        mock_text.category = "NarrativeText"
        mock_text.__str__ = Mock(return_value="Other text")

        extractor = PDFExtractor()
        tables = extractor.extract_tables([mock_table1, mock_table2, mock_text])

        assert len(tables) == 2
        assert "Transaction table" in tables
        assert "Summary table" in tables
