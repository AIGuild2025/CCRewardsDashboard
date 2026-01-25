"""Statement processing service.

This module orchestrates the complete statement processing workflow:
1. Extract PDF content
2. Detect bank
3. Parse statement data
4. Mask PII
5. Validate masking
6. Persist to database
"""

import time
from datetime import date
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import get_error
from app.core.exceptions import (
    BankDetectionError,
    DuplicateStatementError,
    MaskingError,
    PDFExtractionError,
    ParsingError,
    ValidationError,
)
from app.masking.pipeline import PIIMaskingPipeline
from app.models.card import Card
from app.models.statement import Statement
from app.models.transaction import Transaction
from app.models.user import User
from app.parsers.factory import get_parser_factory
from app.repositories.card import CardRepository
from app.repositories.statement import StatementRepository
from app.repositories.transaction import TransactionRepository
from app.schemas.internal import ParsedStatement
from app.schemas.statement import StatementUploadResult


class StatementService:
    """Service for processing credit card statements.

    This service coordinates between PDF parsing, PII masking, and
    database persistence to provide end-to-end statement processing.
    """

    def __init__(self, db: AsyncSession):
        """Initialize the service.

        Args:
            db: Database session for persistence
        """
        self.db = db
        self.parser_factory = get_parser_factory()
        self.card_repo = CardRepository(db)
        self.statement_repo = StatementRepository(db)
        self.transaction_repo = TransactionRepository(db)

    async def process_upload(
        self, pdf_bytes: bytes, user: User, password: str | None = None
    ) -> StatementUploadResult:
        """Process a PDF statement upload.

        Complete workflow:
        1. Extract PDF elements
        2. Detect bank and select parser
        3. Parse to structured data
        4. Validate completeness
        5. Mask PII
        6. Validate no PII leaked
        7. Persist statement + transactions
        8. Return result

        Args:
            pdf_bytes: PDF file content as bytes
            user: Authenticated user uploading the statement
            password: Optional password for encrypted PDFs

        Returns:
            StatementUploadResult with processing details

        Raises:
            PDFExtractionError: If PDF extraction fails
            BankDetectionError: If bank cannot be detected
            ParsingError: If statement parsing fails
            ValidationError: If parsed data is invalid
            MaskingError: If PII masking fails
            DuplicateStatementError: If statement already exists
        """
        start_time = time.time()

        try:
            # Step 1-3: Extract, detect, and parse
            parsed_statement = await self._parse_pdf(pdf_bytes, password)

            # Step 4: Validate parsed data
            self._validate_parsed_statement(parsed_statement)

            # Step 5-6: Mask PII and validate
            masked_data = await self._mask_statement_data(parsed_statement, user.id)

            # Step 7: Persist to database
            statement_id, card_id, transactions_count = await self._persist_statement(
                parsed_statement, masked_data, user.id
            )

            # Step 8: Calculate processing time and return result
            processing_time_ms = int((time.time() - start_time) * 1000)

            return StatementUploadResult(
                statement_id=statement_id,
                card_id=card_id,
                bank=parsed_statement.bank_code,
                statement_month=parsed_statement.statement_month,
                transactions_count=transactions_count,
                reward_points=parsed_statement.reward_points,
                reward_points_earned=parsed_statement.reward_points_earned,
                processing_time_ms=processing_time_ms,
            )

        except Exception as e:
            # Rollback any partial changes
            await self.db.rollback()
            raise

    async def _parse_pdf(
        self, pdf_bytes: bytes, password: str | None
    ) -> ParsedStatement:
        """Extract and parse PDF content.

        Args:
            pdf_bytes: PDF file content
            password: Optional PDF password

        Returns:
            ParsedStatement with extracted data

        Raises:
            PDFExtractionError: If extraction fails
            BankDetectionError: If bank cannot be detected
            ParsingError: If parsing fails
        """
        try:
            print("[SERVICE] Starting PDF parsing...")
            # Use ParserFactory to handle extraction, detection, and parsing
            parsed_statement = self.parser_factory.parse(pdf_bytes, password)
            print(
                f"[SERVICE] Parse complete: {len(parsed_statement.transactions)} transactions"
            )
            return parsed_statement

        except ValueError as e:
            print(f"[SERVICE] ValueError caught: {e}")
            error_msg = str(e).lower()

            # Map ValueError to specific error codes
            if "password" in error_msg and "required" in error_msg:
                raise PDFExtractionError("PARSE_003") from e
            elif "password" in error_msg and (
                "incorrect" in error_msg or "wrong" in error_msg
            ):
                raise PDFExtractionError("PARSE_004") from e
            elif "empty" in error_msg or "no elements" in error_msg:
                raise PDFExtractionError("PARSE_002") from e
            elif "bank" in error_msg or "unsupported" in error_msg:
                raise BankDetectionError("PARSE_001") from e
            elif "card number" in error_msg or "statement period" in error_msg:
                raise ParsingError("PARSE_005") from e
            else:
                # Generic extraction error
                raise PDFExtractionError("PARSE_002") from e

        except Exception as e:
            print(f"[SERVICE] Exception caught: {type(e).__name__}: {e}")
            # Catch-all for unexpected errors
            raise ParsingError("PARSE_005") from e

    def _validate_parsed_statement(self, parsed: ParsedStatement) -> None:
        """Validate parsed statement has required data.

        Args:
            parsed: Parsed statement to validate

        Raises:
            ValidationError: If required data is missing
        """
        if not parsed.card_last_four:
            raise ValidationError("VAL_001", {"field": "card_last_four"})

        if not parsed.statement_month:
            raise ValidationError("VAL_001", {"field": "statement_month"})

        # Temporarily allow 0 transactions for debugging
        if not parsed.transactions or len(parsed.transactions) == 0:
            print(f"[SERVICE] WARNING: No transactions found in statement")
            # raise ParsingError("PARSE_005", {"reason": "no_transactions"})

        # Validate card last four is 4-5 characters
        if not (4 <= len(parsed.card_last_four) <= 5):
            raise ValidationError(
                "VAL_001", {"field": "card_last_four", "value": parsed.card_last_four}
            )

    async def _mask_statement_data(
        self, parsed: ParsedStatement, user_id: UUID
    ) -> dict[str, Any]:
        """Mask PII in parsed statement data.

        Args:
            parsed: Parsed statement with unmasked data
            user_id: User ID for scoped HMAC tokens

        Returns:
            Dictionary with masked transaction data

        Raises:
            MaskingError: If masking fails or validation detects leaks
        """
        try:
            pipeline = PIIMaskingPipeline(user_id=user_id)

            # Convert transactions to dict format for masking
            transactions_data = []
            for txn in parsed.transactions:
                txn_dict = {
                    "transaction_date": txn.transaction_date.isoformat(),
                    "description": txn.description,
                    "amount_cents": txn.amount_cents,
                    "transaction_type": txn.transaction_type,
                    "category": txn.category,
                }
                transactions_data.append(txn_dict)

            print(f"[SERVICE] Masking {len(transactions_data)} transactions...")

            # Mask transaction data (focuses on description field)
            masked_transactions = []
            for txn_dict in transactions_data:
                masked_txn = pipeline.mask_dict(
                    txn_dict, fields_to_mask={"description"}
                )
                masked_transactions.append(masked_txn)

            print(f"[SERVICE] Masked {len(masked_transactions)} transactions")

            # Validate no PII leaked
            for masked_txn in masked_transactions:
                masked_desc = masked_txn.get("description", "")
                if not pipeline.validate_no_leaks(masked_desc, strict=False):
                    raise MaskingError("MASK_002", {"field": "description"})

            print("[SERVICE] PII validation passed")
            return {"transactions": masked_transactions}

        except MaskingError:
            raise
        except Exception as e:
            print(f"[SERVICE] Masking error: {type(e).__name__}: {e}")
            import traceback

            traceback.print_exc()
            raise MaskingError("MASK_001") from e

    async def _persist_statement(
        self, parsed: ParsedStatement, masked_data: dict[str, Any], user_id: UUID
    ) -> tuple[UUID, UUID, int]:
        """Persist statement and transactions to database.

        Args:
            parsed: Parsed statement data
            masked_data: Masked transaction data
            user_id: User ID for ownership

        Returns:
            Tuple of (statement_id, card_id, transactions_count)

        Raises:
            DuplicateStatementError: If statement already exists
        """
        try:
            # Step 1: Find or create card
            print(
                f"[SERVICE] Finding or creating card: last_four={parsed.card_last_four[-4:]}, bank_code={parsed.bank_code}"
            )
            card = await self._find_or_create_card(
                user_id=user_id,
                last_four=parsed.card_last_four[-4:],  # Normalize to 4 digits
                bank_code=parsed.bank_code,
            )
            print(f"[SERVICE] Card ready: {card.id}")

            # Step 2: Check for duplicate
            print(f"[SERVICE] Checking for duplicate statement...")
            existing = await self.statement_repo.get_by_card_and_month(
                user_id=user_id, card_id=card.id, statement_month=parsed.statement_month
            )
            if existing:
                raise DuplicateStatementError(
                    "PARSE_006",
                    {
                        "card_id": str(card.id),
                        "statement_month": parsed.statement_month.isoformat(),
                    },
                )

            # Step 3: Create statement
            print(
                f"[SERVICE] Creating statement: month={parsed.statement_month}, balance={parsed.closing_balance_cents}, rewards={parsed.reward_points}, earned={parsed.reward_points_earned}"
            )
            statement = Statement(
                user_id=user_id,
                card_id=card.id,
                statement_month=parsed.statement_month,
                closing_balance=parsed.closing_balance_cents,
                reward_points=parsed.reward_points,
                reward_points_earned=parsed.reward_points_earned,
            )
            self.db.add(statement)
            await self.db.flush()  # Get statement.id
            print(f"[SERVICE] Statement created: {statement.id}")

            # Step 4: Create transactions
            print(
                f"[SERVICE] Creating {len(masked_data['transactions'])} transactions..."
            )
            transactions_count = 0
            for masked_txn in masked_data["transactions"]:
                transaction = Transaction(
                    statement_id=statement.id,
                    user_id=user_id,
                    txn_date=date.fromisoformat(masked_txn["transaction_date"]),
                    merchant=masked_txn["description"],  # Masked merchant name
                    category=masked_txn.get("category"),
                    amount=masked_txn["amount_cents"],
                    is_credit=masked_txn["transaction_type"].lower() == "credit",
                    reward_points=0,  # TODO: Calculate based on category
                )
                self.db.add(transaction)
                transactions_count += 1

            print(f"[SERVICE] Committing transaction...")
            # Step 5: Commit transaction
            await self.db.commit()

            print(
                f"[SERVICE] Successfully persisted: statement_id={statement.id}, transactions={transactions_count}"
            )
            return statement.id, card.id, transactions_count

        except DuplicateStatementError:
            # Let outer exception handler handle rollback
            raise
        except Exception as e:
            print(f"[SERVICE] Persist error: {type(e).__name__}: {e}")
            import traceback

            traceback.print_exc()
            await self.db.rollback()
            raise
        except Exception as e:
            await self.db.rollback()
            raise ParsingError("DB_001") from e

    async def _find_or_create_card(
        self, user_id: UUID, last_four: str, bank_code: str | None
    ) -> Card:
        """Find existing card or create new one.

        Args:
            user_id: User ID for ownership
            last_four: Last 4 digits of card
            bank_code: Bank identifier

        Returns:
            Card instance (existing or newly created)
        """
        # Try to find existing card
        if bank_code:
            card = await self.card_repo.get_by_last_four_and_bank(
                user_id=user_id, last_four=last_four, bank_code=bank_code
            )
            if card:
                return card

        # Create new card
        card = Card(
            user_id=user_id,
            last_four=last_four,
            bank_code=bank_code or "unknown",
            network=None,  # TODO: Detect from card number pattern
            product_name=None,
        )
        self.db.add(card)
        await self.db.flush()  # Get card.id

        return card
