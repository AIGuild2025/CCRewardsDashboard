"""Integration tests for transaction API endpoints."""

from datetime import date
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.card import Card
from app.models.statement import Statement
from app.models.transaction import Transaction
from app.models.user import User
from app.repositories.card import CardRepository
from app.repositories.statement import StatementRepository
from app.repositories.transaction import TransactionRepository
from app.categorization.rules import normalize_merchant


@pytest.fixture
async def setup_transactions(
    test_user: User, db_session: AsyncSession
) -> dict:
    """Setup test data with card, statement, and transactions."""
    # Create card
    card_repo = CardRepository(db_session)
    card = await card_repo.create(
        Card(
            user_id=test_user.id,
            bank_code="HDFC",
            last_four="1234",
        )
    )

    # Create statement
    stmt_repo = StatementRepository(db_session)
    statement = await stmt_repo.create(
        Statement(
            user_id=test_user.id,
            card_id=card.id,
            statement_month=date(2024, 1, 1),
            statement_period=date(2024, 1, 1),
            closing_balance=1500000,
            reward_points=500,
        )
    )

    # Create transactions
    txn_repo = TransactionRepository(db_session)
    
    txn1 = await txn_repo.create(
        Transaction(
            user_id=test_user.id,
            statement_id=statement.id,
            txn_date=date(2024, 1, 5),
            merchant="Starbucks",
            merchant_key=normalize_merchant("Starbucks"),
            category="FOOD",
            amount=45000,
            is_credit=False,
            reward_points=5,
        )
    )

    txn2 = await txn_repo.create(
        Transaction(
            user_id=test_user.id,
            statement_id=statement.id,
            txn_date=date(2024, 1, 10),
            merchant="Amazon",
            merchant_key=normalize_merchant("Amazon"),
            category="SHOPPING",
            amount=250000,
            is_credit=False,
            reward_points=25,
        )
    )

    txn3 = await txn_repo.create(
        Transaction(
            user_id=test_user.id,
            statement_id=statement.id,
            txn_date=date(2024, 1, 15),
            merchant="Shell",
            merchant_key=normalize_merchant("Shell"),
            category="FUEL",
            amount=150000,
            is_credit=False,
            reward_points=15,
        )
    )

    txn4 = await txn_repo.create(
        Transaction(
            user_id=test_user.id,
            statement_id=statement.id,
            txn_date=date(2024, 1, 20),
            merchant="Payment",
            merchant_key=normalize_merchant("Payment"),
            category="PAYMENT",
            amount=500000,
            is_credit=True,
            reward_points=0,
        )
    )

    await db_session.commit()

    return {
        "card": card,
        "statement": statement,
        "transactions": [txn1, txn2, txn3, txn4],
    }


class TestTransactionList:
    """Test transaction listing endpoint."""

    @pytest.mark.asyncio
    async def test_list_transactions_default(
        self,
        client: AsyncClient,
        auth_headers: dict,
        test_user: User,
        setup_transactions: dict,
    ):
        """Test listing transactions with default pagination."""
        response = await client.get(
            "/api/v1/transactions",
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["pagination"]["total"] == 4
        assert len(data["transactions"]) == 4

        # Verify sorted by date descending (newest first)
        assert data["transactions"][0]["txn_date"] == "2024-01-20"
        assert data["transactions"][-1]["txn_date"] == "2024-01-05"

    @pytest.mark.asyncio
    async def test_list_transactions_pagination(
        self,
        client: AsyncClient,
        auth_headers: dict,
        test_user: User,
        setup_transactions: dict,
    ):
        """Test transaction pagination."""
        response = await client.get(
            "/api/v1/transactions?page=1&limit=2",
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["pagination"]["page"] == 1
        assert data["pagination"]["limit"] == 2
        assert data["pagination"]["total"] == 4
        assert data["pagination"]["total_pages"] == 2
        assert len(data["transactions"]) == 2

    @pytest.mark.asyncio
    async def test_list_transactions_filter_by_category(
        self,
        client: AsyncClient,
        auth_headers: dict,
        test_user: User,
        setup_transactions: dict,
    ):
        """Test filtering transactions by category."""
        response = await client.get(
            "/api/v1/transactions?category=FOOD",
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["pagination"]["total"] == 1
        assert data["transactions"][0]["category"] == "FOOD"
        assert data["transactions"][0]["merchant"] == "Starbucks"

    @pytest.mark.asyncio
    async def test_list_transactions_filter_by_date_range(
        self,
        client: AsyncClient,
        auth_headers: dict,
        test_user: User,
        setup_transactions: dict,
    ):
        """Test filtering transactions by date range."""
        response = await client.get(
            "/api/v1/transactions?start_date=2024-01-08&end_date=2024-01-15",
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["pagination"]["total"] == 2  # Amazon and Shell
        txn_dates = [t["txn_date"] for t in data["transactions"]]
        assert "2024-01-10" in txn_dates
        assert "2024-01-15" in txn_dates

    @pytest.mark.asyncio
    async def test_list_transactions_filter_by_amount_range(
        self,
        client: AsyncClient,
        auth_headers: dict,
        test_user: User,
        setup_transactions: dict,
    ):
        """Test filtering transactions by amount range."""
        response = await client.get(
            "/api/v1/transactions?min_amount=100000&max_amount=300000",
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["pagination"]["total"] == 2  # Amazon (250000) and Shell (150000)
        amounts = [t["amount"] for t in data["transactions"]]
        assert 250000 in amounts
        assert 150000 in amounts

    @pytest.mark.asyncio
    async def test_list_transactions_search_merchant(
        self,
        client: AsyncClient,
        auth_headers: dict,
        test_user: User,
        setup_transactions: dict,
    ):
        """Test searching transactions by merchant name."""
        response = await client.get(
            "/api/v1/transactions?search=star",
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["pagination"]["total"] == 1
        assert "Starbucks" in data["transactions"][0]["merchant"]

    @pytest.mark.asyncio
    async def test_list_transactions_filter_by_credit_type(
        self,
        client: AsyncClient,
        auth_headers: dict,
        test_user: User,
        setup_transactions: dict,
    ):
        """Test filtering by credit/debit type."""
        # Get only credits
        response = await client.get(
            "/api/v1/transactions?is_credit=true",
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["pagination"]["total"] == 1
        assert data["transactions"][0]["is_credit"] is True
        assert data["transactions"][0]["merchant"] == "Payment"

        # Get only debits
        response = await client.get(
            "/api/v1/transactions?is_credit=false",
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["pagination"]["total"] == 3  # All except payment

    @pytest.mark.asyncio
    async def test_list_transactions_sort_by_amount(
        self,
        client: AsyncClient,
        auth_headers: dict,
        test_user: User,
        setup_transactions: dict,
    ):
        """Test sorting transactions by amount."""
        # Sort ascending
        response = await client.get(
            "/api/v1/transactions?sort_by=amount",
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        amounts = [t["amount"] for t in data["transactions"]]
        assert amounts == sorted(amounts)  # Verify ascending order

        # Sort descending
        response = await client.get(
            "/api/v1/transactions?sort_by=-amount",
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        amounts = [t["amount"] for t in data["transactions"]]
        assert amounts == sorted(amounts, reverse=True)

    @pytest.mark.asyncio
    async def test_list_transactions_filter_by_card(
        self,
        client: AsyncClient,
        auth_headers: dict,
        test_user: User,
        setup_transactions: dict,
        db_session: AsyncSession,
    ):
        """Test filtering transactions by card ID."""
        card = setup_transactions["card"]

        # Create another card with statement and transaction
        card_repo = CardRepository(db_session)
        card2 = await card_repo.create(
            Card(
                user_id=test_user.id,
                bank_code="ICICI",
                last_four="5678",
            )
        )

        stmt_repo = StatementRepository(db_session)
        statement2 = await stmt_repo.create(
            Statement(
                user_id=test_user.id,
                card_id=card2.id,
                statement_month=date(2024, 2, 1),
                statement_period=date(2024, 2, 1),
                closing_balance=1000000,
            )
        )

        txn_repo = TransactionRepository(db_session)
        await txn_repo.create(
            Transaction(
                user_id=test_user.id,
                statement_id=statement2.id,
                txn_date=date(2024, 2, 5),
                merchant="Walmart",
                category="SHOPPING",
                amount=300000,
                is_credit=False,
            )
        )
        await db_session.commit()

        # Filter by first card - should get 4 transactions
        response = await client.get(
            f"/api/v1/transactions?card_id={card.id}",
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["pagination"]["total"] == 4

        # Filter by second card - should get 1 transaction
        response = await client.get(
            f"/api/v1/transactions?card_id={card2.id}",
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["pagination"]["total"] == 1
        assert data["transactions"][0]["merchant"] == "Walmart"

    @pytest.mark.asyncio
    async def test_list_transactions_combined_filters(
        self,
        client: AsyncClient,
        auth_headers: dict,
        test_user: User,
        setup_transactions: dict,
    ):
        """Test combining multiple filters."""
        response = await client.get(
            "/api/v1/transactions?category=SHOPPING&min_amount=200000&sort_by=-amount",
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["pagination"]["total"] == 1
        assert data["transactions"][0]["category"] == "SHOPPING"
        assert data["transactions"][0]["amount"] >= 200000


class TestTransactionSummary:
    """Test transaction spending summary endpoint."""

    @pytest.mark.asyncio
    async def test_get_spending_summary(
        self,
        client: AsyncClient,
        auth_headers: dict,
        test_user: User,
        setup_transactions: dict,
    ):
        """Test getting spending summary grouped by category."""
        response = await client.get(
            "/api/v1/transactions/summary",
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        
        # Should have 3 categories (FOOD, SHOPPING, FUEL) - PAYMENT excluded as credit
        assert len(data) == 3

        # Find SHOPPING category (highest amount)
        shopping = next(c for c in data if c["category"] == "SHOPPING")
        assert shopping["amount"] == 250000
        assert shopping["count"] == 1
        assert shopping["reward_points"] == 25

        # Verify sorted by amount (descending)
        amounts = [c["amount"] for c in data]
        assert amounts == sorted(amounts, reverse=True)

    @pytest.mark.asyncio
    async def test_get_spending_summary_with_date_filter(
        self,
        client: AsyncClient,
        auth_headers: dict,
        test_user: User,
        setup_transactions: dict,
    ):
        """Test spending summary with date range filter."""
        response = await client.get(
            "/api/v1/transactions/summary?start_date=2024-01-01&end_date=2024-01-10",
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        
        # Should only include FOOD (Jan 5) and SHOPPING (Jan 10)
        assert len(data) == 2
        categories = [c["category"] for c in data]
        assert "FOOD" in categories
        assert "SHOPPING" in categories
        assert "FUEL" not in categories

    @pytest.mark.asyncio
    async def test_get_spending_summary_empty(
        self,
        client: AsyncClient,
        auth_headers: dict,
        test_user: User,
    ):
        """Test spending summary when no transactions exist."""
        response = await client.get(
            "/api/v1/transactions/summary",
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 0


class TestTransactionCategoryOverride:
    @pytest.mark.asyncio
    async def test_override_debit_transaction_backfills(
        self,
        client: AsyncClient,
        auth_headers: dict,
        db_session: AsyncSession,
        setup_transactions: dict,
    ):
        txn = setup_transactions["transactions"][1]  # Amazon (debit)

        resp = await client.put(
            f"/api/v1/transactions/{txn.id}/category",
            headers=auth_headers,
            json={"category": "utilities"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["transaction_id"] == str(txn.id)
        assert body["merchant"] == "Amazon"
        assert body["merchant_key"] == normalize_merchant("Amazon")
        assert body["category"] == "utilities"
        assert body["updated_transactions_count"] >= 1

        updated = (
            await db_session.execute(select(Transaction).where(Transaction.id == txn.id))
        ).scalar_one()
        assert updated.category == "utilities"

        from app.models.merchant_category_override import MerchantCategoryOverride

        ov = (
            await db_session.execute(
                select(MerchantCategoryOverride).where(
                    MerchantCategoryOverride.user_id == txn.user_id,
                    MerchantCategoryOverride.merchant_key
                    == normalize_merchant("Amazon"),
                    MerchantCategoryOverride.deleted_at.is_(None),
                )
            )
        ).scalar_one()
        assert ov.category == "utilities"

    @pytest.mark.asyncio
    async def test_override_rejects_credit_transaction(
        self,
        client: AsyncClient,
        auth_headers: dict,
        setup_transactions: dict,
    ):
        txn = setup_transactions["transactions"][3]  # Payment (credit)
        resp = await client.put(
            f"/api/v1/transactions/{txn.id}/category",
            headers=auth_headers,
            json={"category": "shopping"},
        )
        assert resp.status_code == 400
        assert resp.json()["detail"]["error_code"] == "API_008"


class TestMerchantCategoryOverrideReadDelete:
    @pytest.mark.asyncio
    async def test_list_and_delete_override_with_recompute(
        self,
        client: AsyncClient,
        auth_headers: dict,
        db_session: AsyncSession,
        setup_transactions: dict,
    ):
        txn = setup_transactions["transactions"][1]  # Amazon (debit)

        # Create override
        resp = await client.put(
            f"/api/v1/transactions/{txn.id}/category",
            headers=auth_headers,
            json={"category": "utilities"},
        )
        assert resp.status_code == 200

        # List overrides
        list_resp = await client.get(
            "/api/v1/transactions/category-overrides",
            headers=auth_headers,
        )
        assert list_resp.status_code == 200
        data = list_resp.json()
        assert data["pagination"]["total"] == 1
        assert len(data["overrides"]) == 1
        ov = data["overrides"][0]
        assert ov["merchant_key"] == normalize_merchant("Amazon")
        assert ov["category"] == "utilities"

        # Delete with recompute back to rules fallback.
        del_resp = await client.delete(
            f"/api/v1/transactions/category-overrides/{ov['id']}?recompute=true",
            headers=auth_headers,
        )
        assert del_resp.status_code == 200
        del_body = del_resp.json()
        assert del_body["merchant_key"] == normalize_merchant("Amazon")
        assert del_body["recomputed_transactions_count"] >= 1

        # Override removed.
        list_resp2 = await client.get(
            "/api/v1/transactions/category-overrides",
            headers=auth_headers,
        )
        assert list_resp2.status_code == 200
        assert list_resp2.json()["pagination"]["total"] == 0

        # Transaction category recomputed (rules fallback).
        updated = (
            await db_session.execute(select(Transaction).where(Transaction.id == txn.id))
        ).scalar_one()
        assert updated.category == "shopping"
