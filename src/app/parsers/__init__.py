"""PDF parsing module for credit card statements.

This module provides functionality to extract structured data from
credit card statement PDFs using a hybrid architecture:
- GenericParser handles common patterns across all banks
- Bank-specific refinements override only what's different
"""

from app.parsers.detector import BankDetector
from app.parsers.extractor import PDFExtractor
from app.parsers.factory import ParserFactory
from app.parsers.generic import GenericParser

__all__ = [
    "PDFExtractor",
    "BankDetector",
    "GenericParser",
    "ParserFactory",
]
