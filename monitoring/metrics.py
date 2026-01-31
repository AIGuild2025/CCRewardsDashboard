"""
Metrics collection and monitoring.
"""

import logging
from typing import Dict, Any, Optional
from datetime import datetime, timedelta
from collections import defaultdict

logger = logging.getLogger(__name__)


class MetricsCollector:
    """
    Collects and tracks metrics for monitoring.
    """
    
    def __init__(self):
        self.metrics = defaultdict(list)
        self.alerts = []
    
    def log_extraction(
        self,
        bank: str,
        card_name: str,
        success: bool,
        confidence: float = 0.0,
        extraction_method: str = "unknown",
        load_time_ms: float = 0.0
    ) -> None:
        """
        Log extraction result.
        
        Args:
            bank: Bank name
            card_name: Card name
            success: Whether extraction succeeded
            confidence: Confidence score
            extraction_method: Method used
            load_time_ms: Page load time
        """
        metric = {
            "timestamp": datetime.utcnow(),
            "bank": bank,
            "card_name": card_name,
            "success": success,
            "confidence": confidence,
            "extraction_method": extraction_method,
            "load_time_ms": load_time_ms
        }
        
        self.metrics[f"{bank}:extraction"].append(metric)
        
        logger.debug(f"Logged extraction: {bank}/{card_name} - {'✓' if success else '✗'}")
    
    def get_success_rate(self, bank: Optional[str] = None, hours: int = 24) -> float:
        """
        Get extraction success rate.
        
        Args:
            bank: Optional bank filter
            hours: Time window
        
        Returns:
            Success rate (0-1)
        """
        cutoff = datetime.utcnow() - timedelta(hours=hours)
        
        extractions = []
        for key, values in self.metrics.items():
            if "extraction" not in key:
                continue
            if bank and bank not in key:
                continue
            
            extractions.extend([v for v in values if v["timestamp"] >= cutoff])
        
        if not extractions:
            return 1.0
        
        successes = sum(1 for e in extractions if e["success"])
        return successes / len(extractions)
    
    def get_avg_confidence(self, bank: Optional[str] = None) -> float:
        """
        Get average extraction confidence.
        
        Args:
            bank: Optional bank filter
        
        Returns:
            Average confidence (0-1)
        """
        extractions = []
        for key, values in self.metrics.items():
            if "extraction" not in key:
                continue
            if bank and bank not in key:
                continue
            
            extractions.extend(values)
        
        if not extractions:
            return 0.0
        
        total_confidence = sum(e.get("confidence", 0) for e in extractions)
        return total_confidence / len(extractions)
    
    def check_success_rate(
        self,
        bank: str,
        threshold: float = 0.9,
        hours: int = 24
    ) -> Optional[Dict[str, Any]]:
        """
        Check if success rate is below threshold.
        
        Args:
            bank: Bank to check
            threshold: Alert threshold (default 90%)
            hours: Time window
        
        Returns:
            Alert dict if below threshold, None otherwise
        """
        rate = self.get_success_rate(bank, hours)
        
        if rate < threshold:
            alert = {
                "type": "extraction_failure_rate",
                "severity": "critical",
                "bank": bank,
                "success_rate": rate,
                "threshold": threshold,
                "message": f"{bank} success rate {rate:.1%} below threshold {threshold:.1%}"
            }
            self.alerts.append(alert)
            logger.critical(alert["message"])
            return alert
        
        return None
    
    def check_null_spike(
        self,
        field_name: str,
        null_count: int,
        total_count: int,
        threshold: float = 0.2
    ) -> Optional[Dict[str, Any]]:
        """
        Alert if null values spike in a field.
        
        Args:
            field_name: Field to check
            null_count: Count of null values
            total_count: Total count
            threshold: Alert if null ratio > threshold
        
        Returns:
            Alert dict if threshold exceeded
        """
        if total_count == 0:
            return None
        
        null_ratio = null_count / total_count
        
        if null_ratio > threshold:
            alert = {
                "type": "null_spike",
                "severity": "warning",
                "field": field_name,
                "null_ratio": null_ratio,
                "threshold": threshold,
                "message": f"Field {field_name} has {null_ratio:.1%} nulls (threshold: {threshold:.1%})"
            }
            self.alerts.append(alert)
            logger.warning(alert["message"])
            return alert
        
        return None
    
    def get_metrics_summary(self) -> Dict[str, Any]:
        """Get summary of all metrics."""
        return {
            "total_extractions": sum(len(v) for v in self.metrics.values()),
            "success_rate": self.get_success_rate(),
            "avg_confidence": self.get_avg_confidence(),
            "active_alerts": len(self.alerts)
        }


# Global metrics instance
_global_metrics = None


def get_metrics_collector() -> MetricsCollector:
    """Get or create global metrics collector."""
    global _global_metrics
    if _global_metrics is None:
        _global_metrics = MetricsCollector()
    return _global_metrics
