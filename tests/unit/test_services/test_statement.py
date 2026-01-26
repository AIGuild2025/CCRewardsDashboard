"""Unit tests for StatementService."""

from datetime import date, datetime
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, Mock, patch
from uuid import UUID, uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import (
    BankDetectionError,
    MaskingError,
    PDFExtractionError,
    ParsingError,
    ValidationError,
)
from app.models.card import Card
from app.models.statement import Statement
from app.models.transaction import Transaction
from app.models.user import User
from app.schemas.internal import ParsedStatement, ParsedTransaction
from app.services.statement import StatementService


@pytest.fixture
def mock_db():
    """Create a mock database session."""
    db = AsyncMock(spec=AsyncSession)
    db.add = Mock()
    db.delete = AsyncMock()
    db.flush = AsyncMock()
    # Default DB execute() result used for override lookup during masking.
    # SQLAlchemy's Result.scalars().all() is synchronous; mimic that shape.
    execute_result = MagicMock()
    scalars_result = MagicMock()
    scalars_result.all.return_value = []
    execute_result.scalars.return_value = scalars_result
    db.execute = AsyncMock(return_value=execute_result)
    db.commit = AsyncMock()
    db.rollback = AsyncMock()
    return db


@pytest.fixture
def test_user():
    """Create a test user."""
    return User(
        id=uuid4(),
        email="test@example.com",
        password_hash="hashed",
        is_active=True
    )


@pytest.fixture
def sample_parsed_statement():
    """Create a sample parsed statement."""
    return ParsedStatement(
        card_last_four="1234",
        statement_month=date(2025, 1, 1),
        closing_balance_cents=100000,
        reward_points=500,
        transactions=[
            ParsedTransaction(
                transaction_date=date(2025, 1, 15),
                description="Amazon Purchase",
                amount_cents=5000,
                transaction_type="debit",
                category="Shopping"
            ),
            ParsedTransaction(
                transaction_date=date(2025, 1, 20),
                description="Salary Credit",
                amount_cents=50000,
                transaction_type="credit",
                category=None
            )
        ],
        bank_code="hdfc"
    )


@pytest.fixture
def mock_parser_factory():
    """Create a mock parser factory."""
    with patch("app.services.statement.get_parser_factory") as mock:
        yield mock


@pytest.fixture
def mock_masking_pipeline():
    """Create a mock masking pipeline."""
    with patch('app.services.statement.PIIMaskingPipeline') as mock:
        yield mock


class TestStatementService:
    """Test suite for StatementService."""

    def test_initialization(self, mock_db):
        """Test service initializes with database session."""
        service = StatementService(mock_db)
        
        assert service.db == mock_db
        assert service.parser_factory is not None
        assert service.card_repo is not None
        assert service.statement_repo is not None
        assert service.transaction_repo is not None

    @pytest.mark.asyncio
    async def test_process_upload_success(
        self,
        mock_db,
        test_user,
        sample_parsed_statement,
        mock_parser_factory,
        mock_masking_pipeline
    ):
        """Test successful statement processing."""
        # Setup mocks
        factory_instance = mock_parser_factory.return_value
        factory_instance.parse.return_value = sample_parsed_statement
        
        pipeline_instance = mock_masking_pipeline.return_value
        pipeline_instance.mask_dict.side_effect = lambda d, fields_to_mask=None: {
            **d,
            "description": f"MASKED_{d['description']}"
        }
        pipeline_instance.validate_no_leaks.return_value = (True, [])
        
        # Mock repositories
        service = StatementService(mock_db)
        
        # Mock card creation with ID
        test_card_id = uuid4()
        test_card = Card(
            id=test_card_id,
            user_id=test_user.id,
            last_four="1234",
            bank_code="hdfc"
        )
        
        # Mock db.add to set IDs when objects are added
        statement_id = uuid4()
        def mock_add(obj):
            if isinstance(obj, Card):
                obj.id = test_card_id
            elif isinstance(obj, Statement):
                obj.id = statement_id
            elif isinstance(obj, Transaction):
                obj.id = uuid4()
        
        mock_db.add.side_effect = mock_add
        service.card_repo.get_by_last_four_and_bank = AsyncMock(return_value=None)
        
        # Mock statement duplicate check
        service.statement_repo.get_by_card_and_month = AsyncMock(return_value=None)
        
        # Execute
        pdf_bytes = b"fake pdf content"
        result = await service.process_upload(pdf_bytes, test_user)
        
        # Verify
        assert result.statement_id is not None
        assert result.card_id is not None
        assert result.bank == "hdfc"
        assert result.statement_month == date(2025, 1, 1)
        assert result.transactions_count == 2
        assert result.reward_points == 500
        assert result.processing_time_ms >= 0  # Processing can be very fast in tests
        
        # Verify database operations
        assert mock_db.add.call_count >= 3  # Card + Statement + 2 Transactions
        mock_db.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_process_upload_pdf_extraction_error(
        self,
        mock_db,
        test_user,
        mock_parser_factory
    ):
        """Test handling of PDF extraction errors."""
        # Setup mock to raise ValueError
        factory_instance = mock_parser_factory.return_value
        factory_instance.parse.side_effect = ValueError("Could not extract PDF")
        
        service = StatementService(mock_db)
        pdf_bytes = b"corrupted pdf"
        
        # Execute and verify exception
        with pytest.raises(PDFExtractionError) as exc_info:
            await service.process_upload(pdf_bytes, test_user)
        
        assert exc_info.value.error_code == "PARSE_002"
        mock_db.rollback.assert_called_once()

    @pytest.mark.asyncio
    async def test_process_upload_password_required(
        self,
        mock_db,
        test_user,
        mock_parser_factory
    ):
        """Test handling of password-protected PDFs."""
        factory_instance = mock_parser_factory.return_value
        factory_instance.parse.side_effect = ValueError("Password required for encrypted PDF")
        
        service = StatementService(mock_db)
        pdf_bytes = b"encrypted pdf"
        
        with pytest.raises(PDFExtractionError) as exc_info:
            await service.process_upload(pdf_bytes, test_user)
        
        assert exc_info.value.error_code == "PARSE_003"

    @pytest.mark.asyncio
    async def test_process_upload_incorrect_password(
        self,
        mock_db,
        test_user,
        mock_parser_factory
    ):
        """Test handling of incorrect PDF password."""
        factory_instance = mock_parser_factory.return_value
        factory_instance.parse.side_effect = ValueError("Incorrect password provided")
        
        service = StatementService(mock_db)
        pdf_bytes = b"encrypted pdf"
        
        with pytest.raises(PDFExtractionError) as exc_info:
            await service.process_upload(pdf_bytes, test_user, password="wrong")
        
        assert exc_info.value.error_code == "PARSE_004"

    @pytest.mark.asyncio
    async def test_process_upload_unsupported_bank(
        self,
        mock_db,
        test_user,
        mock_parser_factory
    ):
        """Test handling of unsupported bank format."""
        factory_instance = mock_parser_factory.return_value
        factory_instance.parse.side_effect = ValueError("Unsupported bank detected")
        
        service = StatementService(mock_db)
        pdf_bytes = b"unknown bank pdf"
        
        with pytest.raises(BankDetectionError) as exc_info:
            await service.process_upload(pdf_bytes, test_user)
        
        assert exc_info.value.error_code == "PARSE_001"

    @pytest.mark.asyncio
    async def test_process_upload_missing_required_field(
        self,
        mock_db,
        test_user,
        mock_parser_factory
    ):
        """Test validation of missing required fields."""
        # Mock parser to return statement with missing transactions
        # (We can't create ParsedStatement with empty card_last_four due to validator)
        invalid_statement = ParsedStatement(
            card_last_four="1234",
            statement_month=date(2025, 1, 1),
            closing_balance_cents=100000,
            reward_points=500,
            transactions=[]  # Empty transactions list
        )
        
        factory_instance = mock_parser_factory.return_value
        factory_instance.parse.return_value = invalid_statement
        
        service = StatementService(mock_db)
        pdf_bytes = b"pdf content"
        
        with pytest.raises(ParsingError) as exc_info:
            await service.process_upload(pdf_bytes, test_user)
        
        assert exc_info.value.error_code == "PARSE_005"

    @pytest.mark.asyncio
    async def test_process_upload_no_transactions(
        self,
        mock_db,
        test_user,
        mock_parser_factory
    ):
        """Test handling of statement with no transactions."""
        empty_statement = ParsedStatement(
            card_last_four="1234",
            statement_month=date(2025, 1, 1),
            closing_balance_cents=100000,
            reward_points=500,
            transactions=[]  # Empty
        )
        
        factory_instance = mock_parser_factory.return_value
        factory_instance.parse.return_value = empty_statement
        
        service = StatementService(mock_db)
        pdf_bytes = b"pdf content"
        
        with pytest.raises(ParsingError) as exc_info:
            await service.process_upload(pdf_bytes, test_user)
        
        assert exc_info.value.error_code == "PARSE_005"

    @pytest.mark.asyncio
    async def test_process_upload_duplicate_statement_upserts(
        self,
        mock_db,
        test_user,
        sample_parsed_statement,
        mock_parser_factory,
        mock_masking_pipeline
    ):
        """Test idempotent upload updates in place and returns same statement_id."""
        factory_instance = mock_parser_factory.return_value
        factory_instance.parse.return_value = sample_parsed_statement
        
        pipeline_instance = mock_masking_pipeline.return_value
        pipeline_instance.mask_dict.side_effect = lambda d, fields_to_mask=None: d
        pipeline_instance.validate_no_leaks.return_value = (True, [])
        
        service = StatementService(mock_db)
        
        # Mock existing card
        test_card = Card(
            id=uuid4(),
            user_id=test_user.id,
            last_four="1234",
            bank_code="hdfc"
        )
        service.card_repo.get_by_last_four_and_bank = AsyncMock(return_value=test_card)
        
        # Mock existing statement
        existing_statement_id = uuid4()
        existing_statement = Statement(
            user_id=test_user.id,
            card_id=test_card.id,
            statement_month=sample_parsed_statement.statement_month,
            closing_balance=123,  # will be updated
            reward_points=1,
            reward_points_earned=2,
        )
        existing_statement.id = existing_statement_id
        existing_statement.deleted_at = None
        service.statement_repo.get_by_card_and_month = AsyncMock(return_value=existing_statement)
        
        pdf_bytes = b"pdf content"
        result = await service.process_upload(pdf_bytes, test_user)

        assert result.statement_id == existing_statement_id
        assert result.card_id == test_card.id
        assert result.transactions_count == len(sample_parsed_statement.transactions)
        mock_db.commit.assert_called_once()

        # Statement fields updated and undeleted.
        assert existing_statement.deleted_at is None
        assert existing_statement.closing_balance == sample_parsed_statement.closing_balance_cents
        assert existing_statement.reward_points == sample_parsed_statement.reward_points
        assert existing_statement.reward_points_earned == sample_parsed_statement.reward_points_earned

    @pytest.mark.asyncio
    async def test_process_upload_soft_deleted_existing_statement_creates_new(
        self,
        mock_db,
        test_user,
        sample_parsed_statement,
        mock_parser_factory,
        mock_masking_pipeline,
    ):
        """If a legacy soft-deleted statement exists, uploading should create a new statement."""
        factory_instance = mock_parser_factory.return_value
        factory_instance.parse.return_value = sample_parsed_statement

        pipeline_instance = mock_masking_pipeline.return_value
        pipeline_instance.mask_dict.side_effect = lambda d, fields_to_mask=None: d
        pipeline_instance.validate_no_leaks.return_value = (True, [])

        service = StatementService(mock_db)

        test_card = Card(
            id=uuid4(),
            user_id=test_user.id,
            last_four="1234",
            bank_code="hdfc",
        )
        service.card_repo.get_by_last_four_and_bank = AsyncMock(return_value=test_card)

        legacy = Statement(
            user_id=test_user.id,
            card_id=test_card.id,
            statement_month=sample_parsed_statement.statement_month,
            closing_balance=123,
            reward_points=1,
            reward_points_earned=2,
        )
        legacy.id = uuid4()
        legacy.deleted_at = datetime.now()
        service.statement_repo.get_by_card_and_month = AsyncMock(return_value=legacy)

        # Assign IDs when new Statement/Transaction objects are added.
        new_statement_id = uuid4()

        def mock_add(obj):
            if isinstance(obj, Statement) and obj.id is None:
                obj.id = new_statement_id

        mock_db.add.side_effect = mock_add

        pdf_bytes = b"pdf content"
        result = await service.process_upload(pdf_bytes, test_user)

        assert result.statement_id != legacy.id
        mock_db.execute.assert_called()

    @pytest.mark.asyncio
    async def test_process_upload_masking_failure(
        self,
        mock_db,
        test_user,
        sample_parsed_statement,
        mock_parser_factory,
        mock_masking_pipeline
    ):
        """Test handling of masking pipeline failure."""
        factory_instance = mock_parser_factory.return_value
        factory_instance.parse.return_value = sample_parsed_statement
        
        pipeline_instance = mock_masking_pipeline.return_value
        pipeline_instance.mask_dict.side_effect = Exception("Masking failed")
        
        service = StatementService(mock_db)
        pdf_bytes = b"pdf content"
        
        with pytest.raises(MaskingError) as exc_info:
            await service.process_upload(pdf_bytes, test_user)
        
        assert exc_info.value.error_code == "MASK_001"

    @pytest.mark.asyncio
    async def test_process_upload_pii_leak_detected(
        self,
        mock_db,
        test_user,
        sample_parsed_statement,
        mock_parser_factory,
        mock_masking_pipeline
    ):
        """Test handling of PII leak detection."""
        factory_instance = mock_parser_factory.return_value
        factory_instance.parse.return_value = sample_parsed_statement
        
        pipeline_instance = mock_masking_pipeline.return_value
        pipeline_instance.mask_dict.side_effect = lambda d, fields_to_mask=None: d
        pipeline_instance.validate_no_leaks.return_value = (False, ["EMAIL_ADDRESS"])  # PII detected
        
        service = StatementService(mock_db)
        pdf_bytes = b"pdf content"
        
        with pytest.raises(MaskingError) as exc_info:
            await service.process_upload(pdf_bytes, test_user)
        
        assert exc_info.value.error_code == "MASK_002"

    @pytest.mark.asyncio
    async def test_process_upload_uses_existing_card(
        self,
        mock_db,
        test_user,
        sample_parsed_statement,
        mock_parser_factory,
        mock_masking_pipeline
    ):
        """Test reusing existing card for same user and bank."""
        factory_instance = mock_parser_factory.return_value
        factory_instance.parse.return_value = sample_parsed_statement
        
        pipeline_instance = mock_masking_pipeline.return_value
        pipeline_instance.mask_dict.side_effect = lambda d, fields_to_mask=None: d
        pipeline_instance.validate_no_leaks.return_value = (True, [])
        
        service = StatementService(mock_db)
        
        # Mock existing card with ID
        existing_card_id = uuid4()
        existing_card = Card(
            id=existing_card_id,
            user_id=test_user.id,
            last_four="1234",
            bank_code="hdfc"
        )
        
        # Mock db.add to set IDs when objects are added
        statement_id = uuid4()
        def mock_add(obj):
            if isinstance(obj, Statement):
                obj.id = statement_id
            elif isinstance(obj, Transaction):
                obj.id = uuid4()
        
        mock_db.add.side_effect = mock_add
        service.card_repo.get_by_last_four_and_bank = AsyncMock(return_value=existing_card)
        service.statement_repo.get_by_card_and_month = AsyncMock(return_value=None)
        
        pdf_bytes = b"pdf content"
        result = await service.process_upload(pdf_bytes, test_user)
        
        # Verify existing card was used
        assert result.card_id == existing_card_id
        
        # Verify card was not created (only statement + transactions added)
        assert mock_db.add.call_count >= 3  # Statement + 2 Transactions (no Card)

    def test_validate_parsed_statement_invalid_card_last_four(self, mock_db):
        """Test that ParsedStatement model validates card last four."""
        # Model validation happens at creation time
        with pytest.raises(ValueError) as exc_info:
            ParsedStatement(
                card_last_four="12",  # Too short
                statement_month=date(2025, 1, 1),
                closing_balance_cents=100000,
                reward_points=500,
                transactions=[ParsedTransaction(
                    transaction_date=date(2025, 1, 15),
                    description="Test",
                    amount_cents=5000,
                    transaction_type="debit"
                )]
            )
        
        assert "4-5 characters" in str(exc_info.value)
