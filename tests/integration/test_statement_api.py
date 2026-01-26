"""Integration tests for statement API endpoints."""

import io
from datetime import date, datetime
from uuid import uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.card import Card
from app.models.statement import Statement
from app.models.transaction import Transaction
from app.models.user import User
from app.repositories.card import CardRepository
from app.repositories.statement import StatementRepository
from app.repositories.transaction import TransactionRepository


class TestStatementUpload:
    """Test statement upload endpoint."""

    @pytest.mark.asyncio
    async def test_upload_invalid_content_type(
        self, client: AsyncClient, auth_headers: dict, test_user: User
    ):
        """Test upload with non-PDF content-type returns API_001 error."""
        response = await client.post(
            "/api/v1/statements/upload",
            content=b"This is not a PDF",
            headers={**auth_headers, "Content-Type": "text/plain"},
        )

        assert response.status_code == 400
        data = response.json()
        assert data["detail"]["error_code"] == "API_001"

    @pytest.mark.asyncio
    async def test_upload_invalid_mime_type(
        self, client: AsyncClient, auth_headers: dict, test_user: User
    ):
        """Test upload with wrong MIME type returns API_001 error."""
        response = await client.post(
            "/api/v1/statements/upload",
            content=b"%PDF-" + b"fake",
            headers=auth_headers,
        )

        assert response.status_code == 400
        data = response.json()
        assert data["detail"]["error_code"] == "API_001"

    @pytest.mark.asyncio
    async def test_upload_file_too_large(
        self, client: AsyncClient, auth_headers: dict, test_user: User
    ):
        """Test upload with file >25MB returns API_002 error."""
        # Create a file larger than 25MB
        large_content = b"%PDF-" + b"x" * (26 * 1024 * 1024)  # 26MB
        response = await client.post(
            "/api/v1/statements/upload",
            content=large_content,
            headers={**auth_headers, "Content-Type": "application/pdf"},
        )

        assert response.status_code == 400
        data = response.json()
        assert data["detail"]["error_code"] == "API_002"

    @pytest.mark.asyncio
    async def test_upload_invalid_pdf_magic_bytes(
        self, client: AsyncClient, auth_headers: dict, test_user: User
    ):
        """Test upload with invalid PDF magic bytes returns API_005 error."""
        # Create a file with .pdf extension and correct MIME but invalid content
        file_content = b"Not a real PDF content"
        response = await client.post(
            "/api/v1/statements/upload",
            content=file_content,
            headers={**auth_headers, "Content-Type": "application/pdf"},
        )

        assert response.status_code == 400
        data = response.json()
        assert data["detail"]["error_code"] == "API_005"
        assert "corrupt" in data["detail"]["user_message"].lower()


class TestStatementList:
    """Test statement list endpoint."""

    @pytest.fixture
    async def setup_statements(
        self, db_session: AsyncSession, test_user: User
    ) -> dict:
        """Create test statements and cards."""
        card_repo = CardRepository(db_session)
        stmt_repo = StatementRepository(db_session)

        # Create cards
        card1 = await card_repo.create(
            Card(
                user_id=test_user.id,
                bank_code="HDFC",
                last_four="1234",
            )
        )
        card2 = await card_repo.create(
            Card(
                user_id=test_user.id,
                bank_code="ICICI",
                last_four="5678",
            )
        )

        # Create statements for different months
        statements = []
        for i in range(5):
            stmt = await stmt_repo.create(
                Statement(
                    user_id=test_user.id,
                    card_id=card1.id if i < 3 else card2.id,
                    statement_month=date(2024, i + 1, 1),
                    statement_period=date(2024, i + 1, 1),
                    closing_balance=1500000,
                )
            )
            statements.append(stmt)

        await db_session.commit()
        return {"card1": card1, "card2": card2, "statements": statements}

    @pytest.mark.asyncio
    async def test_list_statements_default_pagination(
        self, client: AsyncClient, auth_headers: dict, setup_statements: dict
    ):
        """Test listing statements with default pagination."""
        response = await client.get(
            "/api/v1/statements",
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        
        # Check pagination metadata
        assert "pagination" in data
        assert data["pagination"]["page"] == 1
        assert data["pagination"]["limit"] == 20
        assert data["pagination"]["total"] == 5
        assert data["pagination"]["total_pages"] == 1

        # Check statements
        assert "statements" in data
        assert len(data["statements"]) == 5
        
        # Verify sorted by created_at DESC (newest first)
        dates = [s["statement_month"] for s in data["statements"]]
        assert dates == sorted(dates, reverse=True)

    @pytest.mark.asyncio
    async def test_list_statements_with_pagination(
        self, client: AsyncClient, auth_headers: dict, setup_statements: dict
    ):
        """Test pagination with page and limit parameters."""
        response = await client.get(
            "/api/v1/statements?page=1&limit=2",
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["pagination"]["page"] == 1
        assert data["pagination"]["limit"] == 2
        assert data["pagination"]["total"] == 5
        assert data["pagination"]["total_pages"] == 3
        assert len(data["statements"]) == 2

        # Test page 2
        response = await client.get(
            "/api/v1/statements?page=2&limit=2",
            headers=auth_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert data["pagination"]["page"] == 2
        assert len(data["statements"]) == 2

    @pytest.mark.asyncio
    async def test_list_statements_filter_by_card(
        self, client: AsyncClient, auth_headers: dict, setup_statements: dict
    ):
        """Test filtering statements by card_id."""
        card1_id = setup_statements["card1"].id
        
        response = await client.get(
            f"/api/v1/statements?card_id={card1_id}",
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["pagination"]["total"] == 3  # 3 statements for card1
        assert len(data["statements"]) == 3
        
        # Verify all statements belong to card1
        for stmt in data["statements"]:
            assert stmt["card_id"] == str(card1_id)

    @pytest.mark.asyncio
    async def test_list_statements_filter_by_date_range(
        self, client: AsyncClient, auth_headers: dict, setup_statements: dict
    ):
        """Test filtering statements by date range."""
        response = await client.get(
            "/api/v1/statements?from_date=2024-01-01&to_date=2024-03-31",
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["pagination"]["total"] == 3  # Jan, Feb, Mar
        assert len(data["statements"]) == 3

    @pytest.mark.asyncio
    async def test_list_statements_invalid_limit(
        self, client: AsyncClient, auth_headers: dict
    ):
        """Test with invalid limit value returns 400."""
        response = await client.get(
            "/api/v1/statements?limit=500",
            headers=auth_headers,
        )

        assert response.status_code == 400
        data = response.json()
        # Now returns structured error format
        assert data["error_code"] == "VAL_001"
        assert "limit" in data["message"].lower()

    @pytest.mark.asyncio
    async def test_list_statements_empty_results(
        self, client: AsyncClient, auth_headers: dict
    ):
        """Test listing with no statements returns empty array."""
        response = await client.get(
            "/api/v1/statements",
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["statements"] == []
        assert data["pagination"]["total"] == 0


class TestStatementDetail:
    """Test statement detail endpoint."""

    @pytest.fixture
    async def setup_statement_with_transactions(
        self, db_session: AsyncSession, test_user: User
    ) -> dict:
        """Create statement with transactions for testing."""
        card_repo = CardRepository(db_session)
        stmt_repo = StatementRepository(db_session)
        txn_repo = TransactionRepository(db_session)

        # Create card
        card = await card_repo.create(
            Card(
                user_id=test_user.id,
                bank_code="HDFC",
                last_four="1234",
                
            )
        )

        # Create statement
        statement = await stmt_repo.create(
            Statement(
                user_id=test_user.id,
                card_id=card.id,
                statement_month=date(2024, 1, 1),
                statement_period=date(2024, 1, 1),
                closing_balance=1500000,
            )
        )

        # Create transactions
        transactions = [
            Transaction(
                user_id=test_user.id,
                statement_id=statement.id,
                txn_date=date(2024, 1, 5),
                merchant="Starbucks",
                amount=45000,
                category="dining",
                is_credit=False,
                reward_points=45,
            ),
            Transaction(
                user_id=test_user.id,
                statement_id=statement.id,
                txn_date=date(2024, 1, 10),
                merchant="Amazon",
                amount=250000,
                category="shopping",
                is_credit=False,
                reward_points=250,
            ),
            Transaction(
                user_id=test_user.id,
                statement_id=statement.id,
                txn_date=date(2024, 1, 12),
                merchant="Shell",
                amount=150000,
                category="fuel",
                is_credit=False,
                reward_points=150,
            ),
            Transaction(
                user_id=test_user.id,
                statement_id=statement.id,
                txn_date=date(2024, 1, 15),
                merchant="Payment",
                amount=500000,
                category="payment",
                is_credit=True,
                reward_points=0,
            ),
        ]

        for txn in transactions:
            await txn_repo.create(txn)

        await db_session.commit()
        return {"statement": statement, "transactions": transactions}

    @pytest.mark.asyncio
    async def test_get_statement_detail_success(
        self, client: AsyncClient, auth_headers: dict, setup_statement_with_transactions: dict
    ):
        """Test getting statement detail with spending summary."""
        statement = setup_statement_with_transactions["statement"]
        
        response = await client.get(
            f"/api/v1/statements/{statement.id}",
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        
        # Check statement metadata
        assert data["id"] == str(statement.id)
        assert data["statement_month"] == "2024-01-01"
        
        # Check spending summary exists
        assert "spending_summary" in data
        summary = data["spending_summary"]
        
        # Check totals (amounts are stored/returned in cents)
        assert summary["total_debit"] == 445000  # 45000 + 250000 + 150000
        assert summary["total_credit"] == 500000
        assert summary["net_spending"] == -55000  # 445000 - 500000
        
        # Check category breakdown
        assert "by_category" in summary
        categories = {cat["category"]: cat for cat in summary["by_category"]}
        assert "shopping" in categories
        assert categories["shopping"]["amount"] == 250000
        assert categories["shopping"]["count"] == 1
        assert categories["shopping"]["reward_points"] == 250
        
        # Check top merchants
        assert "top_merchants" in summary
        assert len(summary["top_merchants"]) == 3  # debit-only
        # Verify sorted by amount DESC
        amounts = [m["amount"] for m in summary["top_merchants"]]
        assert amounts == sorted(amounts, reverse=True)
        
        merch_map = {m["merchant"]: m for m in summary["top_merchants"]}
        assert merch_map["Starbucks"]["category"] == "dining"
        assert merch_map["Amazon"]["category"] == "shopping"
        assert merch_map["Shell"]["category"] == "fuel"

    @pytest.mark.asyncio
    async def test_get_statement_not_found(
        self, client: AsyncClient, auth_headers: dict
    ):
        """Test getting non-existent statement returns API_003 error."""
        fake_id = uuid4()
        response = await client.get(
            f"/api/v1/statements/{fake_id}",
            headers=auth_headers,
        )

        assert response.status_code == 404
        data = response.json()
        assert data["detail"]["error_code"] == "API_003"

    @pytest.mark.asyncio
    async def test_get_statement_wrong_user(
        self, client: AsyncClient, db_session: AsyncSession, test_user: User
    ):
        """Test accessing another user's statement returns API_004 error."""
        # Create another user
        from app.core.security import hash_password
        from app.repositories.user import UserRepository
        user_repo = UserRepository(db_session)
        other_user = await user_repo.create(
            User(
                email="other@example.com",
                password_hash=hash_password("Password123!"),
                full_name="Other User"
            )
        )
        
        # Create statement for other user
        card_repo = CardRepository(db_session)
        stmt_repo = StatementRepository(db_session)
        
        card = await card_repo.create(
            Card(
                user_id=other_user.id,
                bank_code="HDFC",
                last_four="9999",
                
            )
        )
        statement = await stmt_repo.create(
            Statement(
                user_id=other_user.id,
                card_id=card.id,
                statement_month=date(2024, 1, 1),
                statement_period=date(2024, 1, 1),
                closing_balance=1500000,
            )
        )
        await db_session.commit()
        
        # Try to access with test_user's token
        from app.core.security import create_access_token
        token = create_access_token(user_id=test_user.id)
        headers = {"Authorization": f"Bearer {token}"}
        
        response = await client.get(
            f"/api/v1/statements/{statement.id}",
            headers=headers,
        )

        assert response.status_code == 403
        data = response.json()
        assert data["detail"]["error_code"] == "API_004"


class TestStatementTransactions:
    """Test statement transactions endpoint."""

    @pytest.fixture
    async def setup_statement_with_many_transactions(
        self, db_session: AsyncSession, test_user: User
    ) -> dict:
        """Create statement with many transactions for pagination testing."""
        card_repo = CardRepository(db_session)
        stmt_repo = StatementRepository(db_session)
        txn_repo = TransactionRepository(db_session)

        card = await card_repo.create(
            Card(
                user_id=test_user.id,
                bank_code="HDFC",
                last_four="1234",
                
            )
        )

        statement = await stmt_repo.create(
            Statement(
                user_id=test_user.id,
                card_id=card.id,
                statement_month=date(2024, 1, 1),
                statement_period=date(2024, 1, 1),
                closing_balance=2000000,
            )
        )

        # Create 60 transactions for pagination testing
        transactions = []
        categories = ["dining", "shopping", "fuel", "entertainment", "utilities"]
        merchants = ["Merchant A", "Merchant B", "Merchant C", "Starbucks", "Amazon"]
        
        for i in range(60):
            txn = await txn_repo.create(
                Transaction(
                    user_id=test_user.id,
                    statement_id=statement.id,
                    txn_date=date(2024, 1, (i % 28) + 1),
                    merchant=merchants[i % len(merchants)],
                    amount=(i + 1) * 100,
                    category=categories[i % len(categories)],
                    is_credit=False,
                    reward_points=(i + 1) * 10,
                )
            )
            transactions.append(txn)

        await db_session.commit()
        return {"statement": statement, "transactions": transactions}

    @pytest.mark.asyncio
    async def test_list_transactions_default(
        self, client: AsyncClient, auth_headers: dict, setup_statement_with_many_transactions: dict
    ):
        """Test listing transactions with default pagination."""
        statement = setup_statement_with_many_transactions["statement"]
        
        response = await client.get(
            f"/api/v1/statements/{statement.id}/transactions",
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        
        assert data["pagination"]["page"] == 1
        assert data["pagination"]["limit"] == 50  # Default for transactions
        assert data["pagination"]["total"] == 60
        assert data["pagination"]["total_pages"] == 2
        assert len(data["transactions"]) == 50

    @pytest.mark.asyncio
    async def test_list_transactions_pagination(
        self, client: AsyncClient, auth_headers: dict, setup_statement_with_many_transactions: dict
    ):
        """Test transaction pagination."""
        statement = setup_statement_with_many_transactions["statement"]
        
        # Page 2
        response = await client.get(
            f"/api/v1/statements/{statement.id}/transactions?page=2&limit=50",
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["pagination"]["page"] == 2
        assert len(data["transactions"]) == 10  # Remaining transactions

    @pytest.mark.asyncio
    async def test_list_transactions_filter_by_category(
        self, client: AsyncClient, auth_headers: dict, setup_statement_with_many_transactions: dict
    ):
        """Test filtering transactions by category."""
        statement = setup_statement_with_many_transactions["statement"]
        
        response = await client.get(
            f"/api/v1/statements/{statement.id}/transactions?category=dining",
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        
        # Verify all transactions are dining
        for txn in data["transactions"]:
            assert txn["category"] == "dining"

    @pytest.mark.asyncio
    async def test_list_transactions_search_merchant(
        self, client: AsyncClient, auth_headers: dict, setup_statement_with_many_transactions: dict
    ):
        """Test searching transactions by merchant name."""
        statement = setup_statement_with_many_transactions["statement"]
        
        response = await client.get(
            f"/api/v1/statements/{statement.id}/transactions?search=Starbucks",
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        
        # Verify all transactions match search
        for txn in data["transactions"]:
            assert "Starbucks" in txn["merchant"]

    @pytest.mark.asyncio
    async def test_list_transactions_sort_by_amount(
        self, client: AsyncClient, auth_headers: dict, setup_statement_with_many_transactions: dict
    ):
        """Test sorting transactions by amount."""
        statement = setup_statement_with_many_transactions["statement"]
        
        # Sort ascending
        response = await client.get(
            f"/api/v1/statements/{statement.id}/transactions?sort=amount",
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        amounts = [txn["amount"] for txn in data["transactions"]]
        assert amounts == sorted(amounts)

        # Sort descending
        response = await client.get(
            f"/api/v1/statements/{statement.id}/transactions?sort=-amount",
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        amounts = [txn["amount"] for txn in data["transactions"]]
        assert amounts == sorted(amounts, reverse=True)

    @pytest.mark.asyncio
    async def test_list_transactions_date_range(
        self, client: AsyncClient, auth_headers: dict, setup_statement_with_many_transactions: dict
    ):
        """Test filtering transactions by date range."""
        statement = setup_statement_with_many_transactions["statement"]
        
        response = await client.get(
            f"/api/v1/statements/{statement.id}/transactions?from_date=2024-01-10&to_date=2024-01-15",
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        
        # Verify all transactions are in date range
        for txn in data["transactions"]:
            txn_date = date.fromisoformat(txn["txn_date"])
            assert date(2024, 1, 10) <= txn_date <= date(2024, 1, 15)


class TestStatementDelete:
    """Test statement delete endpoint."""

    @pytest.fixture
    async def setup_statement_for_delete(
        self, db_session: AsyncSession, test_user: User
    ) -> dict:
        """Create statement with transactions for delete testing."""
        card_repo = CardRepository(db_session)
        stmt_repo = StatementRepository(db_session)
        txn_repo = TransactionRepository(db_session)

        card = await card_repo.create(
            Card(
                user_id=test_user.id,
                bank_code="HDFC",
                last_four="1234",
                
            )
        )

        statement = await stmt_repo.create(
            Statement(
                user_id=test_user.id,
                card_id=card.id,
                statement_month=date(2024, 1, 1),
                statement_period=date(2024, 1, 1),
                closing_balance=1500000,
            )
        )

        # Create transactions
        transactions = []
        for i in range(3):
            txn = await txn_repo.create(
                Transaction(
                    user_id=test_user.id,
                    statement_id=statement.id,
                    txn_date=date(2024, 1, i + 1),
                    merchant=f"Merchant {i}",
                    amount=100000,
                    category="shopping",
                    is_credit=False,
                    reward_points=100,
                )
            )
            transactions.append(txn)

        await db_session.commit()
        return {"statement": statement, "transactions": transactions}

    @pytest.mark.asyncio
    async def test_delete_statement_success(
        self, client: AsyncClient, auth_headers: dict, setup_statement_for_delete: dict, db_session: AsyncSession
    ):
        """Test permanently deleting a statement (and cascading transactions)."""
        statement = setup_statement_for_delete["statement"]
        transactions = setup_statement_for_delete["transactions"]
        
        response = await client.delete(
            f"/api/v1/statements/{statement.id}",
            headers=auth_headers,
        )

        assert response.status_code == 204

        # Verify statement is deleted
        stmt_repo = StatementRepository(db_session)
        deleted_stmt = await stmt_repo.get_by_id(statement.id)
        assert deleted_stmt is None

        # Verify transactions are also deleted
        txn_repo = TransactionRepository(db_session)
        for txn in transactions:
            deleted_txn = await txn_repo.get_by_id(txn.id)
            assert deleted_txn is None

    @pytest.mark.asyncio
    async def test_delete_statement_not_found(
        self, client: AsyncClient, auth_headers: dict
    ):
        """Test deleting non-existent statement returns API_003 error."""
        fake_id = uuid4()
        response = await client.delete(
            f"/api/v1/statements/{fake_id}",
            headers=auth_headers,
        )

        assert response.status_code == 404
        data = response.json()
        assert data["detail"]["error_code"] == "API_003"

    @pytest.mark.asyncio
    async def test_delete_statement_wrong_user(
        self, client: AsyncClient, db_session: AsyncSession, test_user: User
    ):
        """Test deleting another user's statement returns API_004 error."""
        # Create another user
        from app.core.security import hash_password
        from app.repositories.user import UserRepository
        user_repo = UserRepository(db_session)
        other_user = await user_repo.create(
            User(
                email="other2@example.com",
                password_hash=hash_password("Password123!"),
                full_name="Other User"
            )
        )
        
        # Create statement for other user
        card_repo = CardRepository(db_session)
        stmt_repo = StatementRepository(db_session)
        
        card = await card_repo.create(
            Card(
                user_id=other_user.id,
                bank_code="HDFC",
                last_four="9999",
                
            )
        )
        statement = await stmt_repo.create(
            Statement(
                user_id=other_user.id,
                card_id=card.id,
                statement_month=date(2024, 1, 1),
                statement_period=date(2024, 1, 1),
                closing_balance=1500000,
            )
        )
        await db_session.commit()
        
        # Try to delete with test_user's token
        from app.core.security import create_access_token
        token = create_access_token(user_id=test_user.id)
        headers = {"Authorization": f"Bearer {token}"}
        
        response = await client.delete(
            f"/api/v1/statements/{statement.id}",
            headers=headers,
        )

        assert response.status_code == 403
        data = response.json()
        assert data["detail"]["error_code"] == "API_004"

    @pytest.mark.asyncio
    async def test_list_excludes_deleted_statements(
        self, client: AsyncClient, auth_headers: dict, setup_statement_for_delete: dict
    ):
        """Test that deleted statements are excluded from list endpoint."""
        statement = setup_statement_for_delete["statement"]
        
        # Delete statement
        await client.delete(
            f"/api/v1/statements/{statement.id}",
            headers=auth_headers,
        )

        # List statements - should not include deleted one
        response = await client.get(
            "/api/v1/statements",
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["pagination"]["total"] == 0
        assert len(data["statements"]) == 0
