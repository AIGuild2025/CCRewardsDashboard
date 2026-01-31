"""Integration tests for card API endpoints."""

from datetime import date

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import create_access_token, hash_password
from app.models.card import Card
from app.models.statement import Statement
from app.models.user import User
from app.repositories.card import CardRepository
from app.repositories.statement import StatementRepository
from app.repositories.user import UserRepository


class TestCardList:
    """Test card listing endpoint."""

    @pytest.mark.asyncio
    async def test_list_cards_empty(
        self, client: AsyncClient, auth_headers: dict, test_user: User
    ):
        """Test listing cards when user has none."""
        response = await client.get(
            "/api/v1/cards",
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 0
        assert len(data["cards"]) == 0

    @pytest.mark.asyncio
    async def test_list_cards_success(
        self,
        client: AsyncClient,
        auth_headers: dict,
        test_user: User,
        db_session: AsyncSession,
    ):
        """Test listing cards returns all user cards."""
        # Create cards
        card_repo = CardRepository(db_session)
        card1 = await card_repo.create(
            Card(
                user_id=test_user.id,
                bank_code="HDFC",
                last_four="1234",
                network="Visa",
                product_name="Regalia",
            )
        )
        card2 = await card_repo.create(
            Card(
                user_id=test_user.id,
                bank_code="ICICI",
                last_four="5678",
                network="Mastercard",
            )
        )
        await db_session.commit()

        response = await client.get(
            "/api/v1/cards",
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 2
        assert len(data["cards"]) == 2

        # Verify card data
        card_ids = [c["id"] for c in data["cards"]]
        assert str(card1.id) in card_ids
        assert str(card2.id) in card_ids

    @pytest.mark.asyncio
    async def test_list_cards_only_user_cards(
        self,
        client: AsyncClient,
        auth_headers: dict,
        test_user: User,
        db_session: AsyncSession,
    ):
        """Test that only authenticated user's cards are returned."""
        # Create another user with a card
        user_repo = UserRepository(db_session)
        other_user = await user_repo.create(
            User(
                email="other@example.com",
                password_hash=hash_password("Password123!"),
                full_name="Other User",
            )
        )

        card_repo = CardRepository(db_session)
        
        # Create card for test user
        my_card = await card_repo.create(
            Card(
                user_id=test_user.id,
                bank_code="HDFC",
                last_four="1234",
            )
        )
        
        # Create card for other user
        await card_repo.create(
            Card(
                user_id=other_user.id,
                bank_code="ICICI",
                last_four="9999",
            )
        )
        await db_session.commit()

        response = await client.get(
            "/api/v1/cards",
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1  # Only test user's card
        assert data["cards"][0]["id"] == str(my_card.id)
        assert data["cards"][0]["last_four"] == "1234"


class TestCardDetail:
    """Test card detail endpoint."""

    @pytest.mark.asyncio
    async def test_get_card_detail_success(
        self,
        client: AsyncClient,
        auth_headers: dict,
        test_user: User,
        db_session: AsyncSession,
    ):
        """Test getting card details with statistics."""
        # Create card
        card_repo = CardRepository(db_session)
        card = await card_repo.create(
            Card(
                user_id=test_user.id,
                bank_code="HDFC",
                last_four="1234",
                network="Visa",
                product_name="Regalia",
            )
        )

        # Create statements
        stmt_repo = StatementRepository(db_session)
        await stmt_repo.create(
            Statement(
                user_id=test_user.id,
                card_id=card.id,
                statement_month=date(2024, 1, 1),
                statement_period=date(2024, 1, 1),
                closing_balance=1500000,
                reward_points=500,
            )
        )
        await stmt_repo.create(
            Statement(
                user_id=test_user.id,
                card_id=card.id,
                statement_month=date(2024, 2, 1),
                statement_period=date(2024, 2, 1),
                closing_balance=2000000,
                reward_points=750,
            )
        )
        await db_session.commit()

        response = await client.get(
            f"/api/v1/cards/{card.id}",
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == str(card.id)
        assert data["last_four"] == "1234"
        assert data["bank_code"] == "HDFC"
        assert data["network"] == "Visa"
        assert data["product_name"] == "Regalia"
        assert data["statements_count"] == 2
        assert data["total_reward_points"] == 1250  # 500 + 750

    @pytest.mark.asyncio
    async def test_get_card_not_found(
        self, client: AsyncClient, auth_headers: dict, test_user: User
    ):
        """Test getting non-existent card returns 404."""
        from uuid import uuid4

        fake_id = uuid4()
        response = await client.get(
            f"/api/v1/cards/{fake_id}",
            headers=auth_headers,
        )

        assert response.status_code == 404
        data = response.json()
        assert data["detail"]["error_code"] == "API_003"

    @pytest.mark.asyncio
    async def test_get_card_wrong_user(
        self,
        client: AsyncClient,
        test_user: User,
        db_session: AsyncSession,
    ):
        """Test accessing another user's card returns 403."""
        # Create another user with a card
        user_repo = UserRepository(db_session)
        other_user = await user_repo.create(
            User(
                email="other2@example.com",
                password_hash=hash_password("Password123!"),
                full_name="Other User",
            )
        )

        card_repo = CardRepository(db_session)
        other_card = await card_repo.create(
            Card(
                user_id=other_user.id,
                bank_code="HDFC",
                last_four="9999",
            )
        )
        await db_session.commit()

        # Try to access with test_user's token
        token = create_access_token(user_id=test_user.id)
        headers = {"Authorization": f"Bearer {token}"}

        response = await client.get(
            f"/api/v1/cards/{other_card.id}",
            headers=headers,
        )

        assert response.status_code == 403
        data = response.json()
        assert data["detail"]["error_code"] == "API_004"


class TestCardStatements:
    """Test card statements endpoint."""

    @pytest.mark.asyncio
    async def test_get_card_statements_success(
        self,
        client: AsyncClient,
        auth_headers: dict,
        test_user: User,
        db_session: AsyncSession,
    ):
        """Test getting statements for a card."""
        # Create card and statements
        card_repo = CardRepository(db_session)
        card = await card_repo.create(
            Card(
                user_id=test_user.id,
                bank_code="HDFC",
                last_four="1234",
            )
        )

        stmt_repo = StatementRepository(db_session)
        stmt1 = await stmt_repo.create(
            Statement(
                user_id=test_user.id,
                card_id=card.id,
                statement_month=date(2024, 1, 1),
                statement_period=date(2024, 1, 1),
                closing_balance=1500000,
                reward_points=500,
            )
        )
        stmt2 = await stmt_repo.create(
            Statement(
                user_id=test_user.id,
                card_id=card.id,
                statement_month=date(2024, 2, 1),
                statement_period=date(2024, 2, 1),
                closing_balance=2000000,
                reward_points=750,
            )
        )
        await db_session.commit()

        response = await client.get(
            f"/api/v1/cards/{card.id}/statements",
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["pagination"]["total"] == 2
        assert len(data["statements"]) == 2

        # Verify sorted by statement_month descending (newest first)
        assert data["statements"][0]["statement_month"] == "2024-02-01"
        assert data["statements"][1]["statement_month"] == "2024-01-01"

    @pytest.mark.asyncio
    async def test_get_card_statements_pagination(
        self,
        client: AsyncClient,
        auth_headers: dict,
        test_user: User,
        db_session: AsyncSession,
    ):
        """Test pagination for card statements."""
        # Create card with multiple statements
        card_repo = CardRepository(db_session)
        card = await card_repo.create(
            Card(
                user_id=test_user.id,
                bank_code="HDFC",
                last_four="1234",
            )
        )

        stmt_repo = StatementRepository(db_session)
        for month in range(1, 6):  # Create 5 statements
            await stmt_repo.create(
                Statement(
                    user_id=test_user.id,
                    card_id=card.id,
                    statement_month=date(2024, month, 1),
                    statement_period=date(2024, month, 1),
                    closing_balance=1500000,
                )
            )
        await db_session.commit()

        # Get first page
        response = await client.get(
            f"/api/v1/cards/{card.id}/statements?page=1&limit=2",
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["pagination"]["page"] == 1
        assert data["pagination"]["limit"] == 2
        assert data["pagination"]["total"] == 5
        assert data["pagination"]["total_pages"] == 3
        assert len(data["statements"]) == 2

    @pytest.mark.asyncio
    async def test_get_card_statements_wrong_card(
        self,
        client: AsyncClient,
        test_user: User,
        db_session: AsyncSession,
    ):
        """Test accessing statements for another user's card returns 403."""
        # Create another user with card
        user_repo = UserRepository(db_session)
        other_user = await user_repo.create(
            User(
                email="other3@example.com",
                password_hash=hash_password("Password123!"),
                full_name="Other User",
            )
        )

        card_repo = CardRepository(db_session)
        other_card = await card_repo.create(
            Card(
                user_id=other_user.id,
                bank_code="HDFC",
                last_four="9999",
            )
        )
        await db_session.commit()

        # Try with test_user's token
        token = create_access_token(user_id=test_user.id)
        headers = {"Authorization": f"Bearer {token}"}

        response = await client.get(
            f"/api/v1/cards/{other_card.id}/statements",
            headers=headers,
        )

        assert response.status_code == 403
        data = response.json()
        assert data["detail"]["error_code"] == "API_004"
