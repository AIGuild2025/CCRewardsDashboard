"""
Alert handling (Slack, email, etc.)
"""

import logging
import os
from typing import Dict, Any, Optional
import json

logger = logging.getLogger(__name__)


class AlertHandler:
    """
    Handle alerts via various channels.
    """
    
    def __init__(self):
        self.slack_webhook = os.getenv("SLACK_WEBHOOK_URL")
        self.email_recipient = os.getenv("ALERT_EMAIL")
    
    def send_alert(
        self,
        title: str,
        message: str,
        severity: str = "info",
        details: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Send alert via configured channels.
        
        Args:
            title: Alert title
            message: Alert message
            severity: 'critical', 'warning', 'info'
            details: Additional details
        """
        logger.log(
            logging.CRITICAL if severity == "critical" else logging.WARNING,
            f"[{severity.upper()}] {title}: {message}"
        )
        
        if severity == "critical":
            if self.slack_webhook:
                self._send_slack_alert(title, message, severity, details)
            if self.email_recipient:
                self._send_email_alert(title, message, severity, details)
    
    def _send_slack_alert(
        self,
        title: str,
        message: str,
        severity: str,
        details: Optional[Dict]
    ) -> None:
        """Send alert to Slack."""
        try:
            import requests
            
            color_map = {
                "critical": "#FF0000",
                "warning": "#FFA500",
                "info": "#0000FF"
            }
            
            payload = {
                "attachments": [
                    {
                        "color": color_map.get(severity, "#808080"),
                        "title": title,
                        "text": message,
                        "fields": [
                            {"title": "Severity", "value": severity, "short": True}
                        ]
                    }
                ]
            }
            
            if details:
                for key, value in details.items():
                    payload["attachments"][0]["fields"].append({
                        "title": key,
                        "value": str(value),
                        "short": True
                    })
            
            requests.post(self.slack_webhook, json=payload, timeout=5)
            logger.debug("Slack alert sent")
        
        except Exception as e:
            logger.error(f"Failed to send Slack alert: {e}")
    
    def _send_email_alert(
        self,
        title: str,
        message: str,
        severity: str,
        details: Optional[Dict]
    ) -> None:
        """Send alert via email."""
        try:
            import smtplib
            from email.mime.text import MIMEText
            from email.mime.multipart import MIMEMultipart
            
            # Note: This is a placeholder. In production, use proper email config
            logger.info(f"Email alert would be sent to {self.email_recipient}")
        
        except Exception as e:
            logger.error(f"Failed to send email alert: {e}")


# Global alert handler
_alert_handler = None


def get_alert_handler() -> AlertHandler:
    """Get or create global alert handler."""
    global _alert_handler
    if _alert_handler is None:
        _alert_handler = AlertHandler()
    return _alert_handler
