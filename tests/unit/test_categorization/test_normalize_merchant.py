from app.categorization.rules import normalize_merchant


def test_normalize_merchant_uppercase_trim_and_collapse_spaces():
    assert normalize_merchant("  UPI-Apple   Services  ") == "UPI-APPLE SERVICES"


def test_normalize_merchant_empty_string():
    assert normalize_merchant("") == ""
    assert normalize_merchant(None) == ""

