"""
Repository pattern for data persistence.
"""

import logging
from typing import Optional, List, Dict, Any
from datetime import datetime
from storage.models import CardRecord, CardVersion, ExtractionLog, DatabaseManager

logger = logging.getLogger(__name__)


class CardRepository:
    """
    Repository for card operations.
    Abstracts database details from business logic.
    """
    
    def __init__(self, db_manager: DatabaseManager):
        self.db = db_manager
    
    def save_card_with_version(
        self,
        card_data: Dict[str, Any],
        extraction_method: str,
        confidence: float,
        old_version: Optional[CardVersion] = None,
        change_summary: str = ""
    ) -> CardVersion:
        """
        Save card data with version tracking.
        
        Args:
            card_data: Normalized card data
            extraction_method: How data was extracted
            confidence: Confidence score
            old_version: Previous version (for diffs)
            change_summary: Human-readable change summary
        
        Returns:
            New CardVersion
        """
        session = self.db.get_session()
        try:
            # Get or create card record
            card_id = f"{card_data['bank_name']}/{card_data['card_name']}".lower().replace(" ", "_")
            
            card = session.query(CardRecord).filter(CardRecord.id == card_id).first()
            if not card:
                card = CardRecord(
                    id=card_id,
                    bank_name=card_data["bank_name"],
                    card_name=card_data["card_name"],
                    source_url=card_data.get("meta", {}).get("source_url", ""),
                    latest_updated=datetime.utcnow()
                )
                session.add(card)
                logger.info(f"Created new card record: {card_id}")
            
            # Update latest values
            card.latest_annual_fee = card_data.get("annual_fee")
            card.latest_base_earning_rate = card_data.get("base_earning_rate")
            card.latest_updated = datetime.utcnow()
            
            # Create version
            version = CardVersion(
                card_id=card_id,
                data=card_data,
                annual_fee=card_data.get("annual_fee"),
                base_earning_rate=card_data.get("base_earning_rate"),
                category_bonuses=card_data.get("category_bonuses"),
                benefits=card_data.get("benefits"),
                extraction_confidence=confidence,
                extraction_method=extraction_method,
                scraper_version=card_data.get("meta", {}).get("scraper_version", "v1.0"),
                change_summary=change_summary
            )
            
            session.add(version)
            session.commit()
            
            logger.info(f"Saved card version for {card_id}")
            return version
        
        finally:
            session.close()
    
    def get_card_history(self, card_id: str, limit: int = 10) -> List[CardVersion]:
        """
        Get version history for a card.
        
        Args:
            card_id: Card identifier
            limit: Max versions to return
        
        Returns:
            List of CardVersion objects
        """
        session = self.db.get_session()
        try:
            versions = session.query(CardVersion).filter(
                CardVersion.card_id == card_id
            ).order_by(CardVersion.created_at.desc()).limit(limit).all()
            
            return versions
        finally:
            session.close()
    
    def get_latest_version(self, card_id: str) -> Optional[CardVersion]:
        """Get latest version of a card."""
        session = self.db.get_session()
        try:
            return session.query(CardVersion).filter(
                CardVersion.card_id == card_id
            ).order_by(CardVersion.created_at.desc()).first()
        finally:
            session.close()


class ExtractionLogRepository:
    """
    Repository for extraction logs.
    """
    
    def __init__(self, db_manager: DatabaseManager):
        self.db = db_manager
    
    def log_extraction(
        self,
        bank_name: str,
        url: str,
        success: bool,
        extraction_method: str,
        confidence: float = 0.0,
        load_time_ms: float = 0.0,
        extraction_time_ms: float = 0.0,
        error_message: str = "",
        card_id: Optional[str] = None
    ) -> None:
        """
        Log an extraction attempt.
        
        Args:
            bank_name: Bank name
            url: Scraped URL
            success: Whether extraction succeeded
            extraction_method: Method used ('rule_based', 'heuristic', 'llm')
            confidence: Confidence score
            load_time_ms: Page load time
            extraction_time_ms: Extraction time
            error_message: Error message if failed
            card_id: Associated card ID
        """
        session = self.db.get_session()
        try:
            log = ExtractionLog(
                bank_name=bank_name,
                card_id=card_id,
                url=url,
                success=1 if success else 0,
                extraction_method=extraction_method,
                confidence=confidence if success else None,
                load_time_ms=load_time_ms,
                extraction_time_ms=extraction_time_ms,
                error_message=error_message if not success else None
            )
            
            session.add(log)
            session.commit()
        
        finally:
            session.close()
    
    def get_success_rate(self, bank_name: str, hours: int = 24) -> float:
        """
        Get recent extraction success rate.
        
        Args:
            bank_name: Filter by bank
            hours: Look back N hours
        
        Returns:
            Success rate (0-1)
        """
        from datetime import timedelta
        
        session = self.db.get_session()
        try:
            cutoff = datetime.utcnow() - timedelta(hours=hours)
            
            total = session.query(ExtractionLog).filter(
                ExtractionLog.bank_name == bank_name,
                ExtractionLog.created_at >= cutoff
            ).count()
            
            if total == 0:
                return 1.0
            
            successes = session.query(ExtractionLog).filter(
                ExtractionLog.bank_name == bank_name,
                ExtractionLog.created_at >= cutoff,
                ExtractionLog.success == 1
            ).count()
            
            return successes / total
        
        finally:
            session.close()
