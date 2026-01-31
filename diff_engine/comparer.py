"""
Diff engine for tracking changes in card data.

Compares new data with previous versions to understand what changed.
Enables:
- Change notifications
- Trend analysis
- Audit trails
- No blind overwrites
"""

import logging
from typing import Dict, Any, Optional, List
from datetime import datetime
from dataclasses import dataclass, asdict
import json

logger = logging.getLogger(__name__)


@dataclass
class FieldDiff:
    """Represents change in a single field."""
    field_name: str
    old_value: Any
    new_value: Any
    change_type: str  # 'added', 'removed', 'modified'
    severity: str     # 'critical', 'warning', 'info'


@dataclass
class CardDiff:
    """Represents changes in entire card data."""
    card_name: str
    bank: str
    changes: List[FieldDiff]
    timestamp: datetime
    has_critical_changes: bool = False
    summary: str = ""


class ChangeComparator:
    """
    Compare old and new card data to identify changes.
    """
    
    # Field severity levels
    CRITICAL_FIELDS = {"annual_fee", "base_earning_rate"}
    WARNING_FIELDS = {"category_bonuses", "bonus_offer"}
    INFO_FIELDS = {"benefits", "meta"}
    
    @staticmethod
    def compare(
        old_data: Optional[Dict[str, Any]],
        new_data: Dict[str, Any]
    ) -> CardDiff:
        """
        Compare old and new card data.
        
        Args:
            old_data: Previous card data (None if first time)
            new_data: Current card data
        
        Returns:
            CardDiff with list of changes
        """
        changes: List[FieldDiff] = []
        
        if not old_data:
            # First time seeing this card
            logger.info(f"New card detected: {new_data.get('card_name')}")
            return CardDiff(
                card_name=new_data.get("card_name", "Unknown"),
                bank=new_data.get("bank_name", "Unknown"),
                changes=[
                    FieldDiff(
                        field_name="*all*",
                        old_value=None,
                        new_value=new_data,
                        change_type="added",
                        severity="info"
                    )
                ],
                timestamp=datetime.utcnow(),
                summary="New card"
            )
        
        # Compare field by field
        all_keys = set(old_data.keys()) | set(new_data.keys())
        
        for key in all_keys:
            if key in ("meta", "timestamp"):
                continue  # Skip metadata
            
            old_val = old_data.get(key)
            new_val = new_data.get(key)
            
            if old_val != new_val:
                change = FieldDiff(
                    field_name=key,
                    old_value=old_val,
                    new_value=new_val,
                    change_type=ChangeComparator._determine_change_type(old_val, new_val),
                    severity=ChangeComparator._determine_severity(key)
                )
                changes.append(change)
                
                logger.info(f"Change detected in {key}: {old_val} → {new_val}")
        
        # Create summary
        has_critical = any(c.severity == "critical" for c in changes)
        
        summary_parts = []
        if changes:
            for severity in ["critical", "warning", "info"]:
                matching = [c for c in changes if c.severity == severity]
                if matching:
                    summary_parts.append(f"{len(matching)} {severity} change(s)")
        
        summary = " | ".join(summary_parts) if summary_parts else "No changes"
        
        return CardDiff(
            card_name=new_data.get("card_name", "Unknown"),
            bank=new_data.get("bank_name", "Unknown"),
            changes=changes,
            timestamp=datetime.utcnow(),
            has_critical_changes=has_critical,
            summary=summary
        )
    
    @staticmethod
    def _determine_change_type(old_val: Any, new_val: Any) -> str:
        """Determine type of change."""
        if old_val is None:
            return "added"
        elif new_val is None:
            return "removed"
        else:
            return "modified"
    
    @staticmethod
    def _determine_severity(field_name: str) -> str:
        """Determine severity of field change."""
        if field_name in ChangeComparator.CRITICAL_FIELDS:
            return "critical"
        elif field_name in ChangeComparator.WARNING_FIELDS:
            return "warning"
        else:
            return "info"


def diff_and_log(
    old_data: Optional[Dict[str, Any]],
    new_data: Dict[str, Any]
) -> CardDiff:
    """
    Compare data and log changes.
    
    Args:
        old_data: Previous data
        new_data: Current data
    
    Returns:
        CardDiff result
    """
    diff = ChangeComparator.compare(old_data, new_data)
    
    # Log changes
    if diff.changes:
        logger.warning(f"Changes detected for {diff.card_name}: {diff.summary}")
        for change in diff.changes:
            if change.severity == "critical":
                logger.critical(f"  CRITICAL: {change.field_name} = {change.new_value}")
            elif change.severity == "warning":
                logger.warning(f"  {change.field_name} = {change.new_value}")
            else:
                logger.info(f"  {change.field_name} changed")
    else:
        logger.info(f"No changes for {diff.card_name}")
    
    return diff


def get_field_history(
    historical_data: List[Dict[str, Any]],
    field_name: str
) -> List[Dict[str, Any]]:
    """
    Get historical values for a single field.
    
    Args:
        historical_data: List of past records
        field_name: Field to track
    
    Returns:
        List of (timestamp, value) tuples showing evolution
    """
    history = []
    
    for record in historical_data:
        if field_name in record:
            history.append({
                "timestamp": record.get("meta", {}).get("timestamp"),
                "value": record.get(field_name)
            })
    
    return history


def has_important_change(diff: CardDiff) -> bool:
    """
    Check if diff contains important changes (not just benefits/meta).
    
    Args:
        diff: CardDiff object
    
    Returns:
        True if has critical or warning changes
    """
    return any(c.severity in ("critical", "warning") for c in diff.changes)
