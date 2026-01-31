"""
LLM-based semantic extraction (fallback layer).

Used ONLY when rule-based (<70%) and heuristic (<50%) extractions fail.
Keeps costs low by using LLM as a resilience layer, not primary extraction.
"""

import logging
import json
from typing import Dict, Any, Optional
import os

logger = logging.getLogger(__name__)

# Try importing available LLM clients
try:
    from openai import OpenAI
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False

try:
    from anthropic import Anthropic
    ANTHROPIC_AVAILABLE = True
except ImportError:
    ANTHROPIC_AVAILABLE = False


class LLMExtractor:
    """
    Use LLM to extract structured data from unstructured content.
    
    This is a fallback when rule-based and heuristic extraction fail.
    It's expensive but highly reliable for edge cases.
    """
    
    CARD_SCHEMA = """{
    "card_name": "string",
    "bank_name": "string",
    "annual_fee": number or null,
    "earning_rate": {
        "category": "string (e.g. '3x on travel')",
        "type": "string (points|cash|miles)"
    },
    "benefits": ["string"],
    "eligibility": "string",
    "credit_score_required": "string or null"
    }"""
    
    def __init__(self, model: Optional[str] = None, temperature: float = 0.0):
        """
        Initialize LLM extractor.
        
        Args:
            model: Model name (defaults to env var or 'gpt-4-turbo-preview')
            temperature: Sampling temperature (0.0 = deterministic)
        """
        self.model = model or os.getenv("LLM_MODEL", "gpt-4-turbo-preview")
        self.temperature = temperature
        self.client = self._init_client()
    
    def _init_client(self):
        """Initialize appropriate LLM client."""
        if "gpt" in self.model.lower() and OPENAI_AVAILABLE:
            return OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        elif "claude" in self.model.lower() and ANTHROPIC_AVAILABLE:
            return Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
        else:
            logger.warning(f"No valid LLM client available for model {self.model}")
            return None
    
    def extract(self, text: str, url: str) -> Dict[str, Any]:
        """
        Extract credit card data using LLM.
        
        Args:
            text: Plain text content from page
            url: Page URL (for context)
        
        Returns:
            Extracted data as dictionary
        """
        if not self.client:
            logger.error("No LLM client available")
            return {}
        
        # Truncate text to fit token limits (keep recent tokens which often have important info)
        text_sample = text[-8000:] if len(text) > 8000 else text
        
        prompt = f"""Extract structured credit card information from the text below.
Return ONLY valid JSON matching this schema:

{self.CARD_SCHEMA}

Important:
- Extract ONLY information explicitly stated in the text
- Leave fields as null if not found
- For annual_fee, extract just the number (e.g., 95, not "$95")
- For benefits, list actual benefits (e.g., "3x points on travel")
- Be strict: only include information you can clearly identify

TEXT:
{text_sample}

RESPONSE (JSON only, no other text):"""
        
        try:
            logger.info(f"Calling LLM for extraction from {url}")
            
            if "gpt" in self.model.lower():
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {"role": "system", "content": "You are a financial data extraction expert. Extract credit card details with high precision."},
                        {"role": "user", "content": prompt}
                    ],
                    temperature=self.temperature,
                    timeout=30
                )
                result_text = response.choices[0].message.content
            
            elif "claude" in self.model.lower():
                response = self.client.messages.create(
                    model=self.model,
                    max_tokens=1000,
                    messages=[
                        {"role": "user", "content": prompt}
                    ],
                    temperature=self.temperature
                )
                result_text = response.content[0].text
            
            else:
                logger.error(f"Unknown model: {self.model}")
                return {}
            
            # Parse JSON response
            result_text = result_text.strip()
            if result_text.startswith("```json"):
                result_text = result_text[7:-3]  # Remove markdown
            elif result_text.startswith("```"):
                result_text = result_text[3:-3]
            
            data = json.loads(result_text)
            logger.info(f"LLM extraction successful")
            
            return data
        
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse LLM response as JSON: {e}")
            return {}
        except Exception as e:
            logger.error(f"LLM extraction failed: {e}")
            return {}


def extract_with_llm(
    page_content,
    model: Optional[str] = None
) -> Dict[str, Any]:
    """
    Convenience function for LLM extraction.
    
    Args:
        page_content: PageContent object from fetcher
        model: Optional model override
    
    Returns:
        Extracted data dictionary
    """
    extractor = LLMExtractor(model=model)
    return extractor.extract(page_content.text, page_content.url)


def validate_extraction_json(data: Dict[str, Any]) -> bool:
    """
    Validate that extracted data matches expected schema.
    
    Args:
        data: Extracted data
    
    Returns:
        True if valid
    """
    required_fields = ["card_name", "annual_fee", "benefits"]
    return any(field in data for field in required_fields)
