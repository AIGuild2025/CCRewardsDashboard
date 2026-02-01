import re
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


CARD_PATTERNS = [
    r'(Amex\s+\w+(?:\s+\w+)?)',
    r'(HDFC\s+\w+(?:\s+\w+)?(?:\s+VISA)?(?:\s+Mastercard)?)',
]

PERIOD_PATTERNS = [
    r'Statement Period[:\s]+(\d{2}/\d{2}/\d{4}\s*-\s*\d{2}/\d{2}/\d{4})',
    r'(\d{2}/\d{2}/\d{4}\s*-\s*\d{2}/\d{2}/\d{4})',
]


def extract_card_name(text_lines):
    for line in text_lines:
        for pattern in CARD_PATTERNS:
            match = re.search(pattern, line, re.IGNORECASE)
            if match:
                card_name = match.group(1).strip()
                logger.info(f"Found card name: {card_name}")
                return card_name

    logger.warning("Card name not found, using default")
    return "Unknown Card"


def extract_statement_period(text_lines):
    for line in text_lines:
        for pattern in PERIOD_PATTERNS:
            match = re.search(pattern, line, re.IGNORECASE)
            if match:
                period = match.group(1).strip()
                logger.info(f"Found statement period: {period}")
                return period

    logger.warning("Statement period not found, using default")
    return "Unknown Period"


def extract_metadata(text_lines):
    card_name = extract_card_name(text_lines)
    statement_period = extract_statement_period(text_lines)

    return {
        "card_name": card_name,
        "statement_period": statement_period
    }


if __name__ == "__main__":
    sample_lines = [
        "AMERICAN EXPRESS",
        "Statement Period: 01/01/2025 - 31/01/2025",
        "Card Type: Amex Gold",
        "Cardholder Name: Rahul Mehta"
    ]
    metadata = extract_metadata(sample_lines)
    print(metadata)
