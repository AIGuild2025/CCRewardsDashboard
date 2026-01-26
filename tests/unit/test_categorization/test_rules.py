from app.categorization.rules import categorize


def test_categorize_payment_received_credit() -> None:
    assert categorize("PAYMENT RECEIVED 000DP...", transaction_type="credit") == "payment"


def test_categorize_fuel_surcharge_waiver() -> None:
    assert categorize("FUEL SURCHARGE WAIVER EXCL TAX", transaction_type="credit") == "fees"


def test_categorize_health_pharmacy() -> None:
    assert categorize("APOLLO PHARMACIES LIMI IN", transaction_type="debit") == "health"


def test_categorize_apple_services() -> None:
    assert categorize("UPI-Apple Services", transaction_type="debit") == "entertainment"

def test_categorize_cleartrip_travel() -> None:
    assert categorize("CleartripPrivateLimited", transaction_type="debit") == "travel"

def test_categorize_reliance_retail_shopping() -> None:
    assert categorize("Reliance Retail Ltd", transaction_type="debit") == "shopping"

def test_categorize_fuels_to_fuel() -> None:
    assert categorize("UPI-B2 FUELS", transaction_type="debit") == "fuel"

def test_categorize_reliance_bp_mobility_to_fuel() -> None:
    assert categorize("UPI-RELIANCE BP MOBILITMITED", transaction_type="debit") == "fuel"

def test_categorize_service_stn_to_fuel() -> None:
    assert categorize("UPI-Satyanam Service Stn", transaction_type="debit") == "fuel"

def test_categorize_bakery_to_food() -> None:
    assert categorize("UPI-KALKATIA BAKERY", transaction_type="debit") == "food"

def test_categorize_udemy_to_education() -> None:
    assert categorize("UPI-Udemy India LLP", transaction_type="debit") == "education"

def test_categorize_personal_care_salon() -> None:
    assert (
        categorize(
            "UPI-T2 UNISEX SALON 24 Nov 25 UPI-RELIANCE BP MOBILITMITED",
            transaction_type="debit",
        )
        == "personal_care"
    )


def test_categorize_empty() -> None:
    assert categorize("", transaction_type=None) == "other"
