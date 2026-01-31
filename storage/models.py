"""
Database models and persistence layer.

Using SQLAlchemy for ORM, PostgreSQL for primary storage.
"""

import logging
from typing import Optional, List
from datetime import datetime
from sqlalchemy import create_engine, Column, String, Float, DateTime, JSON, Integer, Text, ForeignKey, Index
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship

logger = logging.getLogger(__name__)

Base = declarative_base()


class CardRecord(Base):
    """
    Represents a credit card in database.
    Version history stored via CardVersion.
    """
    __tablename__ = "cards"
    
    id = Column(String(100), primary_key=True)  # Unique card identifier
    bank_name = Column(String(100), nullable=False, index=True)
    card_name = Column(String(255), nullable=False)
    source_url = Column(String(2048), nullable=False)
    
    # Latest version info (denormalized for quick queries)
    latest_annual_fee = Column(Float, nullable=True)
    latest_base_earning_rate = Column(Float, nullable=True)
    latest_updated = Column(DateTime, nullable=False, index=True)
    
    # Relationships
    versions = relationship("CardVersion", back_populates="card", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<CardRecord {self.bank_name}/{self.card_name}>"


class CardVersion(Base):
    """
    Versioned card data with full history.
    Enables change tracking and audit trails.
    """
    __tablename__ = "card_versions"
    __table_args__ = (Index("idx_card_id_created", "card_id", "created_at"),)
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    card_id = Column(String(100), ForeignKey("cards.id"), nullable=False, index=True)
    
    # Full structured data
    data = Column(JSON, nullable=False)  # Complete card details
    
    # Key fields (denormalized for queries)
    annual_fee = Column(Float, nullable=True)
    base_earning_rate = Column(Float, nullable=True)
    category_bonuses = Column(JSON, nullable=True)
    benefits = Column(JSON, nullable=True)
    
    # Metadata
    extraction_confidence = Column(Float, nullable=False)
    extraction_method = Column(String(50), nullable=False)  # 'rule_based', 'heuristic', 'llm'
    scraper_version = Column(String(20), nullable=False)
    created_at = Column(DateTime, nullable=False, index=True, default=datetime.utcnow)
    
    # Change tracking
    change_summary = Column(Text, nullable=True)  # Human-readable summary
    
    # Relationship
    card = relationship("CardRecord", back_populates="versions")
    
    def __repr__(self):
        return f"<CardVersion {self.card_id} at {self.created_at}>"


class ExtractionLog(Base):
    """
    Log of all extraction attempts for monitoring.
    """
    __tablename__ = "extraction_logs"
    __table_args__ = (Index("idx_bank_timestamp", "bank_name", "created_at"),)
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    
    bank_name = Column(String(100), nullable=False, index=True)
    card_id = Column(String(100), nullable=True, index=True)
    url = Column(String(2048), nullable=False)
    
    # Extraction details
    success = Column(Integer, nullable=False)  # 1=success, 0=failure
    extraction_method = Column(String(50), nullable=False)
    confidence = Column(Float, nullable=True)
    
    # Timing
    load_time_ms = Column(Float, nullable=True)
    extraction_time_ms = Column(Float, nullable=True)
    
    # Error handling
    error_message = Column(Text, nullable=True)
    
    created_at = Column(DateTime, nullable=False, index=True, default=datetime.utcnow)
    
    def __repr__(self):
        status = "✓" if self.success else "✗"
        return f"<ExtractionLog {status} {self.bank_name} at {self.created_at}>"


class DatabaseManager:
    """
    Manages database connections and sessions.
    """
    
    def __init__(self, database_url: Optional[str] = None):
        """
        Initialize database manager.
        
        Args:
            database_url: Connection string (defaults to env var)
        """
        import os
        self.database_url = database_url or os.getenv("DATABASE_URL", "sqlite:///./credit_card_intel.db")
        self.engine = create_engine(self.database_url, echo=False)
        self.SessionLocal = sessionmaker(bind=self.engine)
        
        logger.info(f"Initialized database at {self.database_url}")
    
    def create_all(self) -> None:
        """Create all tables."""
        Base.metadata.create_all(self.engine)
        logger.info("Database tables created")
    
    def get_session(self):
        """Get new database session."""
        return self.SessionLocal()
    
    def save_card(self, session, card: CardRecord) -> None:
        """Save card record."""
        session.add(card)
        session.commit()
        logger.debug(f"Saved card: {card}")
    
    def save_version(self, session, version: CardVersion) -> None:
        """Save card version."""
        session.add(version)
        session.commit()
        logger.debug(f"Saved version for card {version.card_id}")
    
    def get_latest_version(self, session, card_id: str) -> Optional[CardVersion]:
        """Get latest version of a card."""
        return session.query(CardVersion).filter(
            CardVersion.card_id == card_id
        ).order_by(CardVersion.created_at.desc()).first()
    
    def log_extraction(self, session, log: ExtractionLog) -> None:
        """Log an extraction attempt."""
        session.add(log)
        session.commit()
        logger.debug(f"Logged extraction: {log}")
