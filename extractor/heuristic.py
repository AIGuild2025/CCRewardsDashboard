"""
Heuristic extraction using document structure and section awareness.

When rule-based extraction fails (confidence < 70%), use this.
Analyzes page structure, headings, and section boundaries.
"""

import logging
import re
from typing import Dict, Any, List, Tuple, Optional

logger = logging.getLogger(__name__)


class HeuristicExtractor:
    """
    Extract data by understanding page structure and sections.
    """
    
    def __init__(self):
        self.confidence = 0.0
    
    def extract(self, text: str, url: str) -> Tuple[Dict[str, Any], float]:
        """
        Extract using heuristic parsing of text structure.
        
        Args:
            text: Plain text content from page
            url: Page URL
        
        Returns:
            Tuple of (extracted_data, confidence)
        """
        data = {}
        self.confidence = 0.0
        
        try:
            # Split into sections by common headers
            sections = self._split_by_sections(text)
            logger.debug(f"Identified {len(sections)} sections")
            
            # Extract from each section
            data["card_name"] = self._extract_card_name(text)
            data["fees"] = self._extract_fees(sections, text)
            data["earning_rate"] = self._extract_earning_rates(sections, text)
            data["benefits"] = self._extract_benefits(sections, text)
            data["eligibility"] = self._extract_eligibility(sections, text)
            
            # Calculate confidence based on how much we found
            filled_fields = sum(1 for v in data.values() if v)
            self.confidence = min(0.85, 0.4 + (filled_fields / 5) * 0.45)
            
            logger.info(f"Heuristic extraction complete. Confidence: {self.confidence:.2f}")
            
        except Exception as e:
            logger.error(f"Heuristic extraction failed: {e}")
            self.confidence = 0.0
        
        return data, self.confidence
    
    def _split_by_sections(self, text: str) -> List[Dict[str, str]]:
        """
        Split text into sections by common headers.
        
        Returns:
            List of sections with header and content
        """
        sections = []
        current_section = {"header": "", "content": ""}
        
        lines = text.split('\n')
        for line in lines:
            # Heuristic: headers are short, all caps or title case, isolated
            if line.strip() and len(line.strip()) < 100 and \
               (line.isupper() or line[0].isupper()) and \
               not any(c.isdigit() for c in line[:10]):
                
                if current_section["content"]:
                    sections.append(current_section)
                
                current_section = {"header": line.strip(), "content": ""}
            else:
                current_section["content"] += line + "\n"
        
        if current_section["content"]:
            sections.append(current_section)
        
        return sections
    
    def _extract_card_name(self, text: str) -> Optional[str]:
        """
        Extract card name (usually early in page).
        """
        lines = text.split('\n')
        for line in lines[:20]:  # Check first 20 lines
            if 15 < len(line) < 100 and line[0].isupper():
                return line.strip()
        return None
    
    def _extract_fees(self, sections: List[Dict], text: str) -> Optional[Dict]:
        """
        Extract fee information from sections.
        """
        fees = {}
        
        fee_keywords = ["annual fee", "annual charge", "yearly fee", "membership"]
        
        for section in sections:
            section_text = (section["header"] + " " + section["content"]).lower()
            
            for keyword in fee_keywords:
                if keyword in section_text:
                    # Look for dollar amounts
                    amounts = re.findall(r'\$(\d+(?:,\d{3})*(?:\.\d{2})?)', section["content"])
                    if amounts:
                        fees["annual"] = amounts[0].replace(',', '')
                        logger.debug(f"Found annual fee: ${amounts[0]}")
        
        return fees if fees else None
    
    def _extract_earning_rates(self, sections: List[Dict], text: str) -> Optional[str]:
        """
        Extract earning rates (points, cash back, miles).
        """
        earning_keywords = ["earn", "points", "cash back", "miles", "rewards", "bonus"]
        
        for section in sections:
            section_text = section["content"].lower()
            if any(kw in section_text for kw in earning_keywords):
                # Take first 200 chars of section
                return section["content"][:200].strip()
        
        return None
    
    def _extract_benefits(self, sections: List[Dict], text: str) -> Optional[List[str]]:
        """
        Extract benefit list.
        """
        benefit_keywords = ["benefit", "perk", "feature"]
        
        benefits = []
        for section in sections:
            if any(kw in section["header"].lower() for kw in benefit_keywords):
                # Extract bullet points or list items
                lines = section["content"].split('\n')
                benefits = [line.strip() for line in lines if line.strip() and len(line.strip()) > 5]
        
        return benefits if benefits else None
    
    def _extract_eligibility(self, sections: List[Dict], text: str) -> Optional[str]:
        """
        Extract eligibility information.
        """
        eligibility_keywords = ["eligible", "eligibility", "requirement", "income", "credit"]
        
        for section in sections:
            if any(kw in section["header"].lower() for kw in eligibility_keywords):
                return section["content"][:300].strip()
        
        return None


def extract_heuristic(page_content) -> Tuple[Dict[str, Any], float]:
    """
    Convenience function for heuristic extraction.
    
    Args:
        page_content: PageContent object from fetcher
    
    Returns:
        Tuple of (extracted_data, confidence)
    """
    extractor = HeuristicExtractor()
    return extractor.extract(page_content.text, page_content.url)
