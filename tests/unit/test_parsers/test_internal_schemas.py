"""Unit tests for internal schemas."""

from datetime import date
from decimal import Decimal

import pytest

from app.schemas.internal import ParsedStatement, ParsedTransaction


class TestParsedTransaction:
    """Test suite for ParsedTransaction model."""

    def test_create_transaction_basic(self):
        """Test creating a basic transaction."""
        txn = ParsedTransaction(
            transaction_date=date(2025, 1, 15),
            description="Amazon Purchase",
            amount_cents=123456,
            transaction_type="debit",
        )

        assert txn.transaction_date == date(2025, 1, 15)
        assert txn.description == "Amazon Purchase"
        assert txn.amount_cents == 123456
        assert txn.transaction_type == "debit"
        assert txn.category is None

    def test_create_transaction_with_category(self):
        """Test creating transaction with category."""
        txn = ParsedTransaction(
            transaction_date=date(2025, 1, 15),
            description="Restaurant",
            amount_cents=5000,
            transaction_type="debit",
            category="dining",
        )

        assert txn.category == "dining"

    def test_create_transaction_default_type(self):
        """Test transaction defaults to debit type."""
        txn = ParsedTransaction(
            transaction_date=date(2025, 1, 15),
            description="Purchase",
            amount_cents=1000,
        )

        assert txn.transaction_type == "debit"

    def test_from_decimal_basic(self):
        """Test creating transaction from decimal amount."""
        txn = ParsedTransaction.from_decimal(
            transaction_date=date(2025, 1, 15),
            description="Amazon",
            amount_decimal=Decimal("1234.56"),
        )

        assert txn.amount_cents == 123456
        assert txn.description == "Amazon"

    def test_from_decimal_with_all_params(self):
        """Test from_decimal with all parameters."""
        txn = ParsedTransaction.from_decimal(
            transaction_date=date(2025, 1, 15),
            description="Restaurant",
            amount_decimal=Decimal("567.89"),
            transaction_type="credit",
            category="dining",
        )

        assert txn.amount_cents == 56789
        assert txn.transaction_type == "credit"
        assert txn.category == "dining"

    def test_from_decimal_integer_amount(self):
        """Test from_decimal with integer amount."""
        txn = ParsedTransaction.from_decimal(
            transaction_date=date(2025, 1, 15),
            description="Payment",
            amount_decimal=Decimal("1000"),
        )

        assert txn.amount_cents == 100000


class TestParsedStatement:
    """Test suite for ParsedStatement model."""

    def test_create_statement_basic(self):
        """Test creating a basic statement."""
        stmt = ParsedStatement(
            card_last_four="1234",
            statement_month=date(2025, 1, 1),
            closing_balance_cents=123456,
            reward_points=1500,
        )

        assert stmt.card_last_four == "1234"
        assert stmt.statement_month == date(2025, 1, 1)
        assert stmt.closing_balance_cents == 123456
        assert stmt.reward_points == 1500
        assert stmt.transactions == []

    def test_create_statement_with_transactions(self):
        """Test creating statement with transactions."""
        txn1 = ParsedTransaction(
            transaction_date=date(2025, 1, 15),
            description="Purchase 1",
            amount_cents=1000,
        )
        txn2 = ParsedTransaction(
            transaction_date=date(2025, 1, 16),
            description="Purchase 2",
            amount_cents=2000,
        )

        stmt = ParsedStatement(
            card_last_four="1234",
            statement_month=date(2025, 1, 1),
            closing_balance_cents=123456,
            transactions=[txn1, txn2],
        )

        assert len(stmt.transactions) == 2
        assert stmt.transactions[0].description == "Purchase 1"
        assert stmt.transactions[1].description == "Purchase 2"

    def test_create_statement_default_rewards(self):
        """Test statement defaults to 0 reward points."""
        stmt = ParsedStatement(
            card_last_four="1234",
            statement_month=date(2025, 1, 1),
            closing_balance_cents=100000,
        )

        assert stmt.reward_points == 0

    def test_create_statement_with_optional_fields(self):
        """Test creating statement with optional metadata."""
        stmt = ParsedStatement(
            card_last_four="1234",
            statement_month=date(2025, 1, 1),
            closing_balance_cents=100000,
            bank_code="hdfc",
            statement_date=date(2025, 2, 1),
            due_date=date(2025, 2, 20),
            minimum_due_cents=10000,
        )

        assert stmt.bank_code == "hdfc"
        assert stmt.statement_date == date(2025, 2, 1)
        assert stmt.due_date == date(2025, 2, 20)
        assert stmt.minimum_due_cents == 10000

    def test_from_decimal_balance_basic(self):
        """Test creating statement from decimal balance."""
        stmt = ParsedStatement.from_decimal_balance(
            card_last_four="1234",
            statement_month=date(2025, 1, 1),
            closing_balance_decimal=Decimal("12345.67"),
        )

        assert stmt.closing_balance_cents == 1234567
        assert stmt.reward_points == 0
        assert stmt.transactions == []

    def test_from_decimal_balance_with_transactions(self):
        """Test from_decimal_balance with transactions."""
        txn = ParsedTransaction(
            transaction_date=date(2025, 1, 15),
            description="Purchase",
            amount_cents=1000,
        )

        stmt = ParsedStatement.from_decimal_balance(
            card_last_four="1234",
            statement_month=date(2025, 1, 1),
            closing_balance_decimal=Decimal("999.99"),
            reward_points=500,
            transactions=[txn],
        )

        assert stmt.closing_balance_cents == 99999
        assert stmt.reward_points == 500
        assert len(stmt.transactions) == 1

    def test_from_decimal_balance_with_kwargs(self):
        """Test from_decimal_balance with optional kwargs."""
        stmt = ParsedStatement.from_decimal_balance(
            card_last_four="1234",
            statement_month=date(2025, 1, 1),
            closing_balance_decimal=Decimal("10000.00"),
            bank_code="hdfc",
            statement_date=date(2025, 2, 1),
            due_date=date(2025, 2, 20),
        )

        assert stmt.bank_code == "hdfc"
        assert stmt.statement_date == date(2025, 2, 1)
        assert stmt.due_date == date(2025, 2, 20)

    def test_statement_month_validation(self):
        """Test statement_month should be first day of month."""
        # Note: Pydantic doesn't enforce this by default
        # This is a documentation/convention test
        stmt = ParsedStatement(
            card_last_four="1234",
            statement_month=date(2025, 1, 1),
            closing_balance_cents=100000,
        )

        assert stmt.statement_month.day == 1
