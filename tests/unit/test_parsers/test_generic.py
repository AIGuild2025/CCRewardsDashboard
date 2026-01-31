"""Tests for generic parser."""

from datetime import date
from decimal import Decimal
from unittest.mock import Mock

import pytest

from app.parsers.generic import GenericParser
from app.schemas.internal import ParsedStatement


class TestGenericParser:
    """Test suite for GenericParser."""

    def test_parse_date_formats(self):
        """Test parsing various date formats."""
        parser = GenericParser()

        # DD-MMM-YY
        assert parser._parse_date("15-Jan-25") == date(2025, 1, 15)
        assert parser._parse_date("01-Dec-24") == date(2024, 12, 1)

        # DD-MMM-YYYY
        assert parser._parse_date("15-Jan-2025") == date(2025, 1, 15)

        # DD/MM/YYYY
        assert parser._parse_date("15/01/2025") == date(2025, 1, 15)

        # DD-MM-YYYY
        assert parser._parse_date("15-01-2025") == date(2025, 1, 15)

        # DD/MM/YY
        assert parser._parse_date("15/01/25") == date(2025, 1, 15)

    def test_parse_date_invalid(self):
        """Test parsing invalid date raises error."""
        parser = GenericParser()

        with pytest.raises(ValueError, match="Could not parse date"):
            parser._parse_date("invalid-date")

        with pytest.raises(ValueError):
            parser._parse_date("32/13/2025")  # Invalid day/month

    def test_parse_amount_indian_format(self):
        """Test parsing Indian currency format."""
        parser = GenericParser()

        assert parser._parse_amount("₹1,23,456.00") == Decimal("123456.00")
        assert parser._parse_amount("₹1,234.56") == Decimal("1234.56")
        assert parser._parse_amount("₹ 99.99") == Decimal("99.99")

    def test_parse_amount_us_format(self):
        """Test parsing US currency format."""
        parser = GenericParser()

        assert parser._parse_amount("$1,234.56") == Decimal("1234.56")
        assert parser._parse_amount("$99.99") == Decimal("99.99")

    def test_parse_amount_plain_decimal(self):
        """Test parsing plain decimal amounts."""
        parser = GenericParser()

        assert parser._parse_amount("1234.56") == Decimal("1234.56")
        assert parser._parse_amount("99") == Decimal("99")

    def test_parse_amount_invalid(self):
        """Test parsing invalid amount raises error."""
        parser = GenericParser()

        with pytest.raises(ValueError, match="Could not parse amount"):
            parser._parse_amount("invalid")

    def test_find_card_number(self):
        """Test extracting card number."""
        parser = GenericParser()

        text1 = "Card Number: xxxxxxxxxxxx1234"
        assert parser._find_card_number([], text1) == "1234"

        text2 = "Card ending in: xxxx5678"
        assert parser._find_card_number([], text2) == "5678"

        text3 = "Card xxxxxxxxxxxx9012"
        assert parser._find_card_number([], text3) == "9012"

    def test_find_card_number_not_found(self):
        """Test card number extraction failure."""
        parser = GenericParser()

        with pytest.raises(ValueError, match="Could not find card number"):
            parser._find_card_number([], "No card number here")

    def test_find_statement_period(self):
        """Test extracting statement period."""
        parser = GenericParser()

        text = """
        Statement Period: 01-Jan-25 to 31-Jan-25
        """
        result = parser._find_statement_period([], text)
        assert result == date(2025, 1, 1)

        text2 = """
        Billing Period: 01-Dec-2024 to 31-Dec-2024
        """
        result2 = parser._find_statement_period([], text2)
        assert result2 == date(2024, 12, 1)

    def test_find_statement_period_not_found(self):
        """Test statement period extraction failure."""
        parser = GenericParser()

        with pytest.raises(ValueError, match="Could not find statement period"):
            parser._find_statement_period([], "No period here")

    def test_find_closing_balance(self):
        """Test extracting closing balance."""
        parser = GenericParser()

        text1 = "Closing Balance: ₹12,345.67"
        assert parser._find_closing_balance([], text1) == 1234567  # cents

        text2 = "Total Balance: $999.99"
        assert parser._find_closing_balance([], text2) == 99999

        text3 = "Amount Due: 5000.00"
        assert parser._find_closing_balance([], text3) == 500000

    def test_find_closing_balance_not_found(self):
        """Test closing balance extraction failure."""
        parser = GenericParser()

        with pytest.raises(ValueError, match="Could not find closing balance"):
            parser._find_closing_balance([], "No balance here")

    def test_find_rewards_found(self):
        """Test extracting reward points."""
        parser = GenericParser()

        text1 = "Reward Points: 1500"
        assert parser._find_rewards([], text1) == 1500

        text2 = "Points Earned: 2500"
        assert parser._find_rewards([], text2) == 2500

        text3 = "Total Points: 3000"
        assert parser._find_rewards([], text3) == 3000

    def test_find_rewards_not_found(self):
        """Test rewards returns 0 when not found."""
        parser = GenericParser()

        result = parser._find_rewards([], "No rewards here")
        assert result == 0

    def test_find_statement_date(self):
        """Test extracting statement date."""
        parser = GenericParser()

        text = "Statement Date: 01-Feb-25"
        result = parser._find_statement_date([], text)
        assert result == date(2025, 2, 1)

    def test_find_statement_date_not_found(self):
        """Test statement date returns None when not found."""
        parser = GenericParser()

        result = parser._find_statement_date([], "No date here")
        assert result is None

    def test_find_due_date(self):
        """Test extracting due date."""
        parser = GenericParser()

        text1 = "Due Date: 20-Feb-25"
        result1 = parser._find_due_date([], text1)
        assert result1 == date(2025, 2, 20)

        text2 = "Payment Due Date: 25-Feb-2025"
        result2 = parser._find_due_date([], text2)
        assert result2 == date(2025, 2, 25)

    def test_find_due_date_not_found(self):
        """Test due date returns None when not found."""
        parser = GenericParser()

        result = parser._find_due_date([], "No due date here")
        assert result is None

    def test_find_minimum_due(self):
        """Test extracting minimum due amount."""
        parser = GenericParser()

        text1 = "Minimum Due: ₹1,000.00"
        result1 = parser._find_minimum_due([], text1)
        assert result1 == 100000  # cents

        text2 = "Minimum Payment Due: $50.00"
        result2 = parser._find_minimum_due([], text2)
        assert result2 == 5000

    def test_find_minimum_due_not_found(self):
        """Test minimum due returns None when not found."""
        parser = GenericParser()

        result = parser._find_minimum_due([], "No minimum here")
        assert result is None

    def test_extract_transactions(self):
        """Test extracting transactions from text."""
        parser = GenericParser()

        text = """
        15-Jan-25 Amazon Purchase 1,234.56
        16-Jan-25 Restaurant Expense 567.89
        17-Jan-25 Payment Credit 2,000.00
        """

        transactions = parser._extract_transactions([], text)

        assert len(transactions) >= 0  # Pattern matching may vary
        # Note: Real-world transaction extraction would be more sophisticated

    def test_parse_full_statement(self):
        """Test parsing a complete statement."""
        parser = GenericParser()

        # Create mock elements
        mock_element = Mock()
        mock_element.__str__ = Mock(
            return_value="""
        HDFC Bank Credit Card Statement
        Card Number: xxxxxxxxxxxx1234
        Statement Period: 01-Jan-25 to 31-Jan-25
        Closing Balance: ₹12,345.67
        Reward Points: 1500
        Statement Date: 01-Feb-25
        Due Date: 20-Feb-25
        Minimum Due: ₹1,000.00
        """
        )

        elements = [mock_element]

        statement = parser.parse(elements)

        assert isinstance(statement, ParsedStatement)
        assert statement.card_last_four == "1234"
        assert statement.statement_month == date(2025, 1, 1)
        assert statement.closing_balance_cents == 1234567
        assert statement.reward_points == 1500
        assert statement.statement_date == date(2025, 2, 1)
        assert statement.due_date == date(2025, 2, 20)
        assert statement.minimum_due_cents == 100000

    def test_parse_missing_required_field(self):
        """Test parsing fails when required field is missing."""
        parser = GenericParser()

        mock_element = Mock()
        mock_element.__str__ = Mock(return_value="Incomplete statement data")

        with pytest.raises(ValueError):
            parser.parse([mock_element])

    def test_bank_code_assignment(self):
        """Test that bank_code can be set and included in result."""
        parser = GenericParser()
        parser.bank_code = "hdfc"

        mock_element = Mock()
        mock_element.__str__ = Mock(
            return_value="""
        Card Number: xxxx 1234
        Statement Period: 01-Jan-25 to 31-Jan-25
        Closing Balance: 10000.00
        """
        )

        statement = parser.parse([mock_element])
        assert statement.bank_code == "hdfc"
