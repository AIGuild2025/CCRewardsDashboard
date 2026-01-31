"""
Configuration management for PDF Parser Service
"""
import os
from typing import Optional
from pydantic_settings import BaseSettings
from dotenv import load_dotenv

load_dotenv()


class ParserConfig(BaseSettings):
    """Configuration for PDF Parser Service"""
    
    # AWS Textract Configuration
    aws_access_key_id: Optional[str] = os.getenv("AWS_ACCESS_KEY_ID")
    aws_secret_access_key: Optional[str] = os.getenv("AWS_SECRET_ACCESS_KEY")
    aws_region: str = os.getenv("AWS_REGION", "us-east-1")
    aws_s3_bucket: Optional[str] = os.getenv("AWS_S3_BUCKET")
    
    # Groq Configuration for LLM Classification
    groq_api_key: Optional[str] = os.getenv("GROQ_API_KEY")
    groq_model: str = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
    llm_temperature: float = float(os.getenv("LLM_TEMPERATURE", "0.1"))
    
    # Parser Settings
    textract_enabled: bool = os.getenv("TEXTRACT_ENABLED", "true").lower() == "true"
    unstructured_fallback: bool = os.getenv("UNSTRUCTURED_FALLBACK", "true").lower() == "true"
    pii_masking_enabled: bool = os.getenv("PII_MASKING_ENABLED", "true").lower() == "true"
    
    # Accuracy Targets
    target_extraction_accuracy: float = 0.95
    target_reward_accuracy: float = 0.90
    
    # Processing Settings
    max_file_size_mb: int = 50
    supported_formats: list = ["pdf"]
    
    class Config:
        env_file = ".env"
        case_sensitive = False


config = ParserConfig()
