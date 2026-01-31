"""Integration tests for repository layer."""
import sys
from datetime import date, timedelta
from pathlib import Path
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

sys.path.append(str(Path(__file__).parents[2] / "src"))

from app.models.card import Card
from app.models.statement import Statement
from app.models.transaction import Transaction
from app.models.user import User
from app.repositories.card import CardRepository
from app.repositories.statement import StatementRepository
from app.repositories.transaction import TransactionRepository
from app.repositories.user import UserRepository


# Helper fixtures
@pytest.fixture
async def test_user(db_session: AsyncSession) -> User:
    """Create a test user."""
    user = User(
        email="test@example.com",
        password_hash="hashed_password",
        full_name="Test User",
        is_active=True,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest.fixture
async def another_user(db_session: AsyncSession) -> User:
    """Create another test user for security tests."""
    user = User(
        email="another@example.com",
        password_hash="hashed_password",
        full_name="Another User",
        is_active=True,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest.fixture
async def test_card(db_session: AsyncSession, test_user: User) -> Card:
    """Create a test card."""
    card = Card(
        user_id=test_user.id,
        last_four="1234",
        bank_code="hdfc",
        network="Visa",
        product_name="HDFC Regalia",
        is_active=True,
    )
    db_session.add(card)
    await db_session.commit()
    await db_session.refresh(card)
    return card


@pytest.fixture
async def test_statement(
    db_session: AsyncSession, test_user: User, test_card: Card
) -> Statement:
    """Create a test statement."""
    statement = Statement(
        user_id=test_user.id,
        card_id=test_card.id,
        statement_month=date(2026, 1, 1),
        statement_period=date(2026, 1, 1),
        closing_balance=50000,  # Rs. 500.00
        reward_points=250,
    )
    db_session.add(statement)
    await db_session.commit()
    await db_session.refresh(statement)
    return statement


# UserRepository Tests
class TestUserRepository:
    """Test suite for UserRepository."""

    async def test_create_user(self, db_session: AsyncSession):
        """Test creating a new user."""
        repo = UserRepository(db_session)
        user = User(
            email="newuser@example.com",
            password_hash="hashed",
            full_name="New User",
            is_active=True,
        )
        created = await repo.create(user)

        assert created.id is not None
        assert created.email == "newuser@example.com"
        assert created.is_active is True

    async def test_get_by_id(self, db_session: AsyncSession, test_user: User):
        """Test getting user by ID."""
        repo = UserRepository(db_session)
        found = await repo.get_by_id(test_user.id)

        assert found is not None
        assert found.id == test_user.id
        assert found.email == test_user.email

    async def test_get_by_email(self, db_session: AsyncSession, test_user: User):
        """Test finding user by email."""
        repo = UserRepository(db_session)
        found = await repo.get_by_email(test_user.email)

        assert found is not None
        assert found.id == test_user.id

    async def test_email_exists(self, db_session: AsyncSession, test_user: User):
        """Test checking if email exists."""
        repo = UserRepository(db_session)

        assert await repo.email_exists(test_user.email) is True
        assert await repo.email_exists("nonexistent@example.com") is False

    async def test_deactivate_user(self, db_session: AsyncSession, test_user: User):
        """Test soft-deleting a user."""
        repo = UserRepository(db_session)
        deactivated = await repo.deactivate(test_user.id)

        assert deactivated is not None
        assert deactivated.is_active is False

    async def test_get_active_users(self, db_session: AsyncSession, test_user: User):
        """Test getting only active users."""
        repo = UserRepository(db_session)

        # Create inactive user
        inactive = User(
            email="inactive@example.com",
            password_hash="hashed",
            full_name="Inactive User",
            is_active=False,
        )
        await repo.create(inactive)

        active_users = await repo.get_active_users()
        assert len(active_users) >= 1
        assert all(user.is_active for user in active_users)


# CardRepository Tests
class TestCardRepository:
    """Test suite for CardRepository."""

    async def test_create_card(self, db_session: AsyncSession, test_user: User):
        """Test creating a new card."""
        repo = CardRepository(db_session)
        card = Card(
            user_id=test_user.id,
            last_four="5678",
            bank_code="icici",
            network="Mastercard",
            is_active=True,
        )
        created = await repo.create(card)

        assert created.id is not None
        assert created.last_four == "5678"
        assert created.user_id == test_user.id

    async def test_get_by_user(
        self, db_session: AsyncSession, test_user: User, test_card: Card
    ):
        """Test getting card scoped to user."""
        repo = CardRepository(db_session)
        found = await repo.get_by_user(test_user.id, test_card.id)

        assert found is not None
        assert found.id == test_card.id

    async def test_user_cannot_access_other_users_card(
        self,
        db_session: AsyncSession,
        test_user: User,
        another_user: User,
        test_card: Card,
    ):
        """Security test: User cannot access another user's card."""
        repo = CardRepository(db_session)
        not_found = await repo.get_by_user(another_user.id, test_card.id)

        assert not_found is None

    async def test_get_all_by_user(
        self, db_session: AsyncSession, test_user: User, test_card: Card
    ):
        """Test getting all cards for a user."""
        repo = CardRepository(db_session)
        cards = await repo.get_all_by_user(test_user.id)

        assert len(cards) >= 1
        assert all(card.user_id == test_user.id for card in cards)

    async def test_get_by_last_four_and_bank(
        self, db_session: AsyncSession, test_user: User, test_card: Card
    ):
        """Test finding card by last four and bank code."""
        repo = CardRepository(db_session)
        found = await repo.get_by_last_four_and_bank(
            test_user.id, test_card.last_four, test_card.bank_code
        )

        assert found is not None
        assert found.id == test_card.id

    async def test_get_active_cards_only(
        self, db_session: AsyncSession, test_user: User
    ):
        """Test getting only active cards."""
        repo = CardRepository(db_session)

        # Create inactive card
        inactive = Card(
            user_id=test_user.id,
            last_four="0000",
            bank_code="sbi",
            is_active=False,
        )
        await repo.create(inactive)

        active_cards = await repo.get_active_cards_by_user(test_user.id)
        assert all(card.is_active for card in active_cards)


# StatementRepository Tests
class TestStatementRepository:
    """Test suite for StatementRepository."""

    async def test_create_statement(
        self, db_session: AsyncSession, test_user: User, test_card: Card
    ):
        """Test creating a new statement."""
        repo = StatementRepository(db_session)
        statement = Statement(
            user_id=test_user.id,
            card_id=test_card.id,
            statement_month=date(2026, 2, 1),
            statement_period=date(2026, 2, 1),
            closing_balance=75000,
            reward_points=375,
        )
        created = await repo.create(statement)

        assert created.id is not None
        assert created.user_id == test_user.id
        assert created.card_id == test_card.id

    async def test_get_by_user(
        self,
        db_session: AsyncSession,
        test_user: User,
        test_statement: Statement,
    ):
        """Test getting statement scoped to user."""
        repo = StatementRepository(db_session)
        found = await repo.get_by_user(test_user.id, test_statement.id)

        assert found is not None
        assert found.id == test_statement.id
        assert found.card is not None  # Test joinedload

    async def test_user_cannot_access_other_users_statement(
        self,
        db_session: AsyncSession,
        another_user: User,
        test_statement: Statement,
    ):
        """Security test: User cannot access another user's statement."""
        repo = StatementRepository(db_session)
        not_found = await repo.get_by_user(another_user.id, test_statement.id)

        assert not_found is None

    async def test_get_by_card_and_month(
        self,
        db_session: AsyncSession,
        test_user: User,
        test_card: Card,
        test_statement: Statement,
    ):
        """Test checking if statement exists for card and month."""
        repo = StatementRepository(db_session)
        found = await repo.get_by_card_and_month(
            test_user.id, test_card.id, test_statement.statement_month
        )

        assert found is not None
        assert found.id == test_statement.id

    async def test_get_statements_by_card(
        self,
        db_session: AsyncSession,
        test_user: User,
        test_card: Card,
        test_statement: Statement,
    ):
        """Test getting all statements for a card."""
        repo = StatementRepository(db_session)
        statements = await repo.get_statements_by_card(test_user.id, test_card.id)

        assert len(statements) >= 1
        assert all(stmt.card_id == test_card.id for stmt in statements)


# TransactionRepository Tests
class TestTransactionRepository:
    """Test suite for TransactionRepository."""

    async def test_create_transaction(
        self,
        db_session: AsyncSession,
        test_user: User,
        test_statement: Statement,
    ):
        """Test creating a new transaction."""
        repo = TransactionRepository(db_session)
        transaction = Transaction(
            statement_id=test_statement.id,
            user_id=test_user.id,
            txn_date=date.today(),
            merchant="Amazon",
            category="Shopping",
            amount=2500,  # Rs. 25.00
            is_credit=False,
            reward_points=5,
        )
        created = await repo.create(transaction)

        assert created.id is not None
        assert created.merchant == "Amazon"
        assert created.user_id == test_user.id

    async def test_get_by_statement(
        self,
        db_session: AsyncSession,
        test_user: User,
        test_statement: Statement,
    ):
        """Test getting all transactions for a statement."""
        repo = TransactionRepository(db_session)

        # Create test transactions
        txn = Transaction(
            statement_id=test_statement.id,
            user_id=test_user.id,
            txn_date=date.today(),
            merchant="Test Merchant",
            amount=1000,
            is_credit=False,
        )
        await repo.create(txn)

        transactions = await repo.get_by_statement(test_user.id, test_statement.id)
        assert len(transactions) >= 1
        assert all(t.statement_id == test_statement.id for t in transactions)

    async def test_get_by_category(
        self,
        db_session: AsyncSession,
        test_user: User,
        test_statement: Statement,
    ):
        """Test filtering transactions by category."""
        repo = TransactionRepository(db_session)

        # Create transactions with different categories
        for category in ["Food", "Travel", "Food"]:
            txn = Transaction(
                statement_id=test_statement.id,
                user_id=test_user.id,
                txn_date=date.today(),
                merchant=f"{category} Merchant",
                category=category,
                amount=1000,
                is_credit=False,
            )
            await repo.create(txn)

        food_txns = await repo.get_by_category(test_user.id, "Food")
        assert len(food_txns) == 2
        assert all(t.category == "Food" for t in food_txns)

    async def test_get_total_spent_by_category(
        self,
        db_session: AsyncSession,
        test_user: User,
        test_statement: Statement,
    ):
        """Test aggregating spending by category."""
        repo = TransactionRepository(db_session)

        # Create test transactions
        await repo.create(
            Transaction(
                statement_id=test_statement.id,
                user_id=test_user.id,
                txn_date=date.today(),
                category="Food",
                amount=5000,
                is_credit=False,
            )
        )
        await repo.create(
            Transaction(
                statement_id=test_statement.id,
                user_id=test_user.id,
                txn_date=date.today(),
                category="Food",
                amount=3000,
                is_credit=False,
            )
        )

        totals = await repo.get_total_spent_by_category(test_user.id)
        assert "Food" in totals
        assert totals["Food"] == 8000

    async def test_get_debits_and_credits(
        self,
        db_session: AsyncSession,
        test_user: User,
        test_statement: Statement,
    ):
        """Test filtering by debit/credit flag."""
        repo = TransactionRepository(db_session)

        # Create debit and credit transactions
        await repo.create(
            Transaction(
                statement_id=test_statement.id,
                user_id=test_user.id,
                txn_date=date.today(),
                merchant="Purchase",
                amount=1000,
                is_credit=False,
            )
        )
        await repo.create(
            Transaction(
                statement_id=test_statement.id,
                user_id=test_user.id,
                txn_date=date.today(),
                merchant="Payment",
                amount=5000,
                is_credit=True,
            )
        )

        debits = await repo.get_debits_only(test_user.id)
        credits = await repo.get_credits_only(test_user.id)

        assert all(not t.is_credit for t in debits)
        assert all(t.is_credit for t in credits)
