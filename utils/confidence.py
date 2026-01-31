"""
Confidence scoring utilities.
"""

from typing import Dict, Any


def calculate_field_confidence(
    data: Dict[str, Any],
    required_fields: list[str]
) -> float:
    """
    Calculate confidence based on presence of required fields.
    
    Args:
        data: Extracted data
        required_fields: Fields that must be present
    
    Returns:
        Confidence score (0-1)
    """
    present = sum(1 for field in required_fields if field in data and data[field])
    return present / len(required_fields) if required_fields else 0.5


def scale_confidence(
    base_confidence: float,
    method: str,
    has_fallback: bool = False
) -> float:
    """
    Adjust confidence based on extraction method and fallback usage.
    
    Args:
        base_confidence: Base confidence from extractor
        method: Extraction method ('rule_based', 'heuristic', 'llm')
        has_fallback: Whether fallback was used
    
    Returns:
        Adjusted confidence (0-1)
    """
    # LLM-extracted data is inherently more reliable
    if method == "llm":
        return min(0.95, base_confidence + 0.1)
    
    # Using fallback reduces confidence slightly
    if has_fallback:
        return max(0.3, base_confidence * 0.9)
    
    return base_confidence
