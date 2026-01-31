"""
Main package initialization.
"""

__version__ = "1.0.0"
__author__ = "Credit Card Intel Team"
__description__ = "AI-augmented, change-resilient credit card intelligence platform"

# Import key modules for easy access
from fetcher import load_page, PageContent
from validator import is_page_changed
from extractor import extract_rule_based, extract_heuristic, extract_with_llm
from normalizer import normalize, CardNormalized
from diff_engine import diff_and_log, has_important_change
from storage import DatabaseManager, CardRepository
from monitoring import get_metrics_collector, get_alert_handler
from scheduler import run

__all__ = [
    "load_page",
    "PageContent",
    "is_page_changed",
    "extract_rule_based",
    "extract_heuristic",
    "extract_with_llm",
    "normalize",
    "CardNormalized",
    "diff_and_log",
    "has_important_change",
    "DatabaseManager",
    "CardRepository",
    "get_metrics_collector",
    "get_alert_handler",
    "run"
]
