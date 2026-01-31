"""
Main pipeline orchestrator - the entry point for scraping runs.

This is what you call via cron, Airflow, or manual trigger.
"""

import logging
import sys
import time
from typing import Optional, Dict, Any
import argparse
import yaml
import os
from datetime import datetime

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Import modules
from fetcher import load_page, PageContent
from validator import is_page_changed
from extractor import extract_rule_based, extract_heuristic, extract_with_llm
from normalizer import normalize
from diff_engine import diff_and_log, has_important_change
from storage import DatabaseManager, CardRepository, ExtractionLogRepository
from monitoring import get_metrics_collector, get_alert_handler


def load_config(config_file: str = "config/banks.yaml") -> Dict[str, Any]:
    """Load configuration from YAML."""
    with open(config_file, 'r') as f:
        return yaml.safe_load(f)


def load_selectors(selector_file: str = "config/selectors.yaml") -> Dict[str, Any]:
    """Load selectors from YAML."""
    with open(selector_file, 'r') as f:
        config = yaml.safe_load(f)
    return config.get("selectors", {})


def run(
    bank: str,
    card_key: Optional[str] = None,
    url: Optional[str] = None,
    force: bool = False
) -> bool:
    """
    Run scraping pipeline for a bank/card.
    
    Args:
        bank: Bank name (must exist in config)
        card_key: Optional card key (if None, scrape all cards from bank)
        url: Optional URL override
        force: Force extraction even if page didn't change
    
    Returns:
        True if successful
    """
    start_time = time.time()
    metrics = get_metrics_collector()
    alerts = get_alert_handler()
    db = DatabaseManager()
    card_repo = CardRepository(db)
    log_repo = ExtractionLogRepository(db)
    
    try:
        # Load config
        config = load_config()
        selectors = load_selectors()
        
        if bank not in config["banks"]:
            logger.error(f"Bank {bank} not found in config")
            return False
        
        bank_config = config["banks"][bank]
        card_urls = bank_config["card_urls"] if not url else {card_key: {"url": url}}
        
        # Process each card
        success_count = 0
        for card_key, card_config in card_urls.items():
            card_url = card_config["url"]
            
            try:
                logger.info(f"Scraping {bank}/{card_key} from {card_url}")
                
                # 1. Load page
                page_load_start = time.time()
                page = load_page(card_url, timeout_ms=bank_config.get("base_timeout", 60000))
                load_time_ms = (time.time() - page_load_start) * 1000
                
                # 2. Check if page changed
                if not force and not is_page_changed(page):
                    logger.info(f"Page unchanged for {card_key}. Skipping extraction.")
                    continue
                
                # 3. Extract with fallback strategy
                extraction_start = time.time()
                extraction_method = None
                raw_data = {}
                confidence = 0.0
                
                # Try rule-based
                bank_selectors = selectors.get(bank, {}).get(card_key, {})
                if bank_selectors:
                    raw_data, confidence = extract_rule_based(page, bank, bank_selectors)
                    extraction_method = "rule_based"
                    logger.info(f"Rule-based extraction confidence: {confidence:.2f}")
                
                # Fallback to heuristic
                if confidence < 0.70:
                    logger.info("Rule-based confidence too low. Trying heuristic...")
                    raw_data, confidence = extract_heuristic(page)
                    extraction_method = "heuristic"
                    logger.info(f"Heuristic extraction confidence: {confidence:.2f}")
                
                # Fallback to LLM
                if confidence < 0.50:
                    logger.info("Heuristic confidence too low. Using LLM...")
                    raw_data = extract_with_llm(page)
                    extraction_method = "llm"
                    confidence = 0.90  # Semantic extraction is usually high confidence
                    logger.info(f"LLM extraction confidence: {confidence:.2f}")
                
                extraction_time_ms = (time.time() - extraction_start) * 1000
                
                if not raw_data:
                    raise Exception("All extraction methods failed")
                
                # 4. Normalize
                normalized_data = normalize(
                    raw_data,
                    bank=bank,
                    url=card_url,
                    confidence=confidence
                )
                
                # 5. Compare with previous version
                card_id = f"{bank}/{card_key}".lower().replace(" ", "_")
                old_version = card_repo.get_latest_version(card_id)
                
                if old_version:
                    diff = diff_and_log(old_version.data, normalized_data.dict())
                    
                    if has_important_change(diff):
                        logger.warning(f"Important changes detected: {diff.summary}")
                        alerts.send_alert(
                            title=f"Card Update: {bank}/{card_key}",
                            message=diff.summary,
                            severity="warning"
                        )
                
                # 6. Save
                card_repo.save_card_with_version(
                    normalized_data.dict(),
                    extraction_method=extraction_method,
                    confidence=confidence,
                    old_version=old_version
                )
                
                # 7. Log metrics
                metrics.log_extraction(
                    bank=bank,
                    card_name=card_key,
                    success=True,
                    confidence=confidence,
                    extraction_method=extraction_method,
                    load_time_ms=load_time_ms
                )
                
                log_repo.log_extraction(
                    bank_name=bank,
                    url=card_url,
                    success=True,
                    extraction_method=extraction_method,
                    confidence=confidence,
                    load_time_ms=load_time_ms,
                    extraction_time_ms=extraction_time_ms,
                    card_id=card_id
                )
                
                logger.info(f"✓ Successfully scraped {bank}/{card_key}")
                success_count += 1
            
            except Exception as e:
                logger.error(f"✗ Failed to scrape {bank}/{card_key}: {e}", exc_info=True)
                
                metrics.log_extraction(
                    bank=bank,
                    card_name=card_key,
                    success=False,
                    extraction_method="error"
                )
                
                log_repo.log_extraction(
                    bank_name=bank,
                    url=card_url,
                    success=False,
                    extraction_method="error",
                    error_message=str(e),
                    card_id=f"{bank}/{card_key}"
                )
                
                alerts.send_alert(
                    title=f"Scraping Error: {bank}/{card_key}",
                    message=str(e),
                    severity="critical"
                )
        
        # Check health
        total_time = time.time() - start_time
        logger.info(f"Pipeline complete. Scraped {success_count} cards in {total_time:.1f}s")
        
        # Check thresholds
        success_rate = metrics.get_success_rate(bank)
        if success_rate < 0.90:
            metrics.check_success_rate(bank, threshold=0.90)
        
        return success_count > 0
    
    except Exception as e:
        logger.error(f"Pipeline failed: {e}", exc_info=True)
        return False


def main():
    """CLI entry point."""
    parser = argparse.ArgumentParser(description="Credit Card Intelligence Scraper")
    parser.add_argument("--bank", required=True, help="Bank name (e.g., 'Chase')")
    parser.add_argument("--card", help="Specific card key (if not provided, scrape all)")
    parser.add_argument("--url", help="Override URL")
    parser.add_argument("--force", action="store_true", help="Force extraction even if page unchanged")
    
    args = parser.parse_args()
    
    success = run(args.bank, args.card, args.url, args.force)
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
