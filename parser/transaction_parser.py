import re
from datetime import datetime
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


DATE_PATTERN = r'\b(\d{2}/\d{2}/\d{4})\b'

AMOUNT_PATTERNS = [
    r'(?:INR\s*)?(\d{1,3}(?:,\d{3})*(?:\.\d{2}))',
    r'(?:INR\s*)?(\d+\.\d{2})',
]

SKIP_KEYWORDS = [
    'statement period',
    'cardholder',
    'card type',
    'card number',
    'network',
    'date',
    'description',
    'amount',
    'transaction details',
    'transactions',
    'membership rewards',
    'reward points',
    'total',
    'points earned',
    'american express',
    'hdfc bank',
    'credit card statement',
    'usd',
]


def normalize_date(date_str):
    try:
        dt = datetime.strptime(date_str, "%d/%m/%Y")
        return dt.strftime("%Y-%m-%d")
    except Exception as e:
        logger.error(f"Failed to normalize date: {date_str} - {e}")
        return None


def normalize_amount(amount_str):
    try:
        cleaned = amount_str.replace(',', '').replace('INR', '').strip()
        return float(cleaned)
    except Exception as e:
        logger.error(f"Failed to normalize amount: {amount_str} - {e}")
        return None


def should_skip_line(line):
    line_lower = line.lower()
    for keyword in SKIP_KEYWORDS:
        if keyword in line_lower:
            return True
    return False


def extract_transaction_from_line(line):
    if should_skip_line(line):
        return None

    date_match = re.search(DATE_PATTERN, line)
    if not date_match:
        return None

    date_str = date_match.group(1)
    normalized_date = normalize_date(date_str)
    if not normalized_date:
        return None

    amount_str = None
    for pattern in AMOUNT_PATTERNS:
        amount_match = re.search(pattern, line)
        if amount_match:
            amount_str = amount_match.group(1)
            break

    if not amount_str:
        return None

    normalized_amount = normalize_amount(amount_str)
    if normalized_amount is None or normalized_amount <= 0:
        return None

    date_end = date_match.end()
    amount_start = line.find(amount_str)

    if amount_start > date_end:
        description = line[date_end:amount_start].strip()
    else:
        description = line[date_end:].replace(amount_str, '').strip()

    description = re.sub(r'\s+', ' ', description).strip()

    if not description or len(description) < 2:
        logger.warning(f"Skipping row with empty/invalid description: {line}")
        return None

    return {
        "date": normalized_date,
        "description": description,
        "amount": normalized_amount
    }


def parse_transactions(text_lines):
    transactions = []
    total_rows = 0
    parsed_rows = 0
    skipped_rows = 0

    for line in text_lines:
        if not line.strip():
            continue

        total_rows += 1
        transaction = extract_transaction_from_line(line)

        if transaction:
            transactions.append(transaction)
            parsed_rows += 1
        else:
            if re.search(DATE_PATTERN, line) and not should_skip_line(line):
                skipped_rows += 1
                logger.debug(f"Skipped row: {line}")

    logger.info(f"Total rows detected: {total_rows}")
    logger.info(f"Rows successfully parsed: {parsed_rows}")
    logger.info(f"Rows skipped: {skipped_rows}")

    return transactions


if __name__ == "__main__":
    sample_lines = [
        "05/01/2025 AMAZON.IN 2499.00",
        "10/01/2025 SWIGGY 450.50",
        "15/01/2025 INDIGO 5,250.00",
        "20/01/2025 INR 3,999.00",
        "Statement Period: 01/01/2025 - 31/01/2025",
        "Date Description Amount",
        "25/01/2025 FLIPKART INR 1,899.00"
    ]

    transactions = parse_transactions(sample_lines)
    for t in transactions:
        print(t)
