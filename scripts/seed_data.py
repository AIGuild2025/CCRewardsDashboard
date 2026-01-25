"""Reference values for supported banks, networks, and categories.

This script intentionally does not write to the database. It prints the current
supported values for documentation and future API-layer validation.
"""


SUPPORTED_BANKS = [
    {"code": "hdfc", "name": "HDFC Bank"},
    {"code": "icici", "name": "ICICI Bank"},
    {"code": "sbi", "name": "State Bank of India"},
    {"code": "amex", "name": "American Express"},
    {"code": "citi", "name": "Citibank"},
    {"code": "chase", "name": "JPMorgan Chase"},
]

CARD_NETWORKS = ["Visa", "Mastercard", "American Express", "RuPay"]

SPENDING_CATEGORIES = [
    "Food & Dining",
    "Shopping",
    "Travel",
    "Entertainment",
    "Bills & Utilities",
    "Healthcare",
    "Transportation",
    "Groceries",
    "Fuel",
    "Other",
]


def print_reference_data() -> None:
    """Print supported reference values."""
    print("Starting seed data script...")
    
    print("\nSupported banks:")
    for bank in SUPPORTED_BANKS:
        print(f"  - {bank['name']} ({bank['code']})")
    
    print("\nSupported card networks:")
    for network in CARD_NETWORKS:
        print(f"  - {network}")
    
    print("\nDefault spending categories:")
    for category in SPENDING_CATEGORIES:
        print(f"  - {category}")
    
    print("\n✅ Reference data listed successfully!")
    print(f"   Total banks: {len(SUPPORTED_BANKS)}")
    print(f"   Total networks: {len(CARD_NETWORKS)}")
    print(f"   Total categories: {len(SPENDING_CATEGORIES)}")


if __name__ == "__main__":
    print_reference_data()
