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
import logging
from datetime import date
from typing import Any
from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.errors import get_error
from app.core.exceptions import (
    BankDetectionError,
    MaskingError,
    PDFExtractionError,
    ParsingError,
    ValidationError,
)
from app.masking.pipeline import PIIMaskingPipeline
from app.models.card import Card
from app.models.merchant_category_override import MerchantCategoryOverride
from app.models.statement import Statement
from app.models.transaction import Transaction
from app.models.user import User
from app.categorization.rules import categorize, normalize_merchant
from app.parsers.factory import get_parser_factory
from app.repositories.card import CardRepository
from app.repositories.statement import StatementRepository
from app.repositories.transaction import TransactionRepository
from app.schemas.internal import ParsedStatement
from app.schemas.statement import StatementUploadResult


logger = logging.getLogger(__name__)


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
            logger.info("Starting PDF parsing")
            # Use ParserFactory to handle extraction, detection, and parsing
            parsed_statement = self.parser_factory.parse(pdf_bytes, password)
            logger.info("Parse complete", extra={"transactions_count": len(parsed_statement.transactions)})
            return parsed_statement

        except ValueError as e:
            logger.warning("PDF parse error (ValueError)", extra={"error_type": type(e).__name__})
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
            if settings.debug:
                logger.exception(
                    "Unexpected PDF parse error", extra={"error_type": type(e).__name__}
                )
            else:
                logger.error(
                    "Unexpected PDF parse error", extra={"error_type": type(e).__name__}
                )
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

        if not parsed.transactions or len(parsed.transactions) == 0:
            raise ParsingError("PARSE_005", {"reason": "no_transactions"})

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
                raw_cat = (txn.category or "").strip().lower()
                txn_dict = {
                    "transaction_date": txn.transaction_date.isoformat(),
                    "description": txn.description,
                    "amount_cents": txn.amount_cents,
                    "transaction_type": txn.transaction_type,
                    # Many banks do not provide a category/MCC. Infer if missing.
                    "category": raw_cat
                    or categorize(txn.description, transaction_type=txn.transaction_type),
                }
                transactions_data.append(txn_dict)

            logger.info("Masking transactions", extra={"transactions_count": len(transactions_data)})

            # Mask transaction data (focuses on description field)
            masked_transactions = []
            for txn_dict in transactions_data:
                masked_txn = pipeline.mask_dict(
                    txn_dict, fields_to_mask={"description"}
                )
                masked_transactions.append(masked_txn)

            # Apply user overrides (debit-only) after masking so merchant_key is derived
            # from the persisted merchant string (masked) and cannot contain raw PII.
            debit_keys: set[str] = set()
            for t in masked_transactions:
                if (t.get("transaction_type") or "").strip().lower() == "credit":
                    continue
                key = normalize_merchant(t.get("description"))
                if key:
                    debit_keys.add(key)

            override_map: dict[str, str] = {}
            if debit_keys:
                result = await self.db.execute(
                    select(MerchantCategoryOverride).where(
                        MerchantCategoryOverride.user_id == user_id,
                        MerchantCategoryOverride.deleted_at.is_(None),
                        MerchantCategoryOverride.merchant_key.in_(sorted(debit_keys)),
                    )
                )
                overrides = result.scalars().all()
                override_map = {o.merchant_key: o.category for o in overrides}

            if override_map:
                for t in masked_transactions:
                    if (t.get("transaction_type") or "").strip().lower() == "credit":
                        continue
                    key = normalize_merchant(t.get("description"))
                    if key and key in override_map:
                        t["category"] = override_map[key]

            logger.info("Masked transactions", extra={"transactions_count": len(masked_transactions)})

            # Validate no PII leaked
            for masked_txn in masked_transactions:
                masked_desc = masked_txn.get("description", "")
                is_clean, detected = pipeline.validate_no_leaks(
                    masked_desc, strict=True
                )
                if not is_clean:
                    raise MaskingError(
                        "MASK_002",
                        {"field": "description", "detected": detected},
                    )

            logger.info("PII validation passed")
            return {"transactions": masked_transactions}

        except MaskingError:
            raise
        except Exception as e:
            if settings.debug:
                logger.exception(
                    "Masking pipeline failed", extra={"error_type": type(e).__name__}
                )
            else:
                logger.error(
                    "Masking pipeline failed", extra={"error_type": type(e).__name__}
                )
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

        Notes:
            This method is idempotent for the (user_id, card_id, statement_month) key.
            If a statement already exists, it is updated in place and its transactions
            are replaced.
        """
        try:
            # Step 1: Find or create card
            logger.info("Finding or creating card", extra={"bank_code": parsed.bank_code})
            card = await self._find_or_create_card(
                user_id=user_id,
                last_four=parsed.card_last_four[-4:],  # Normalize to 4 digits
                bank_code=parsed.bank_code,
            )
            logger.info("Card ready", extra={"card_id": str(card.id)})

            # Step 2: Upsert statement (idempotent upload)
            logger.info("Checking for existing statement (upsert)")
            existing = await self.statement_repo.get_by_card_and_month(
                user_id=user_id, card_id=card.id, statement_month=parsed.statement_month
            )
            if existing and existing.deleted_at is not None:
                # Legacy cleanup: if a statement was previously "soft deleted",
                # remove it fully so the user can upload a new copy.
                #
                # Use a SQL DELETE (not ORM instance delete) to rely on DB-level
                # ON DELETE CASCADE and avoid SQLAlchemy trying to NULL child FKs.
                await self.db.execute(delete(Statement).where(Statement.id == existing.id))
                await self.db.flush()
                existing = None

            def build_masked_content() -> dict[str, Any]:
                # Authoritative masked payload stored on the statement record.
                return {
                    "bank_code": parsed.bank_code,
                    "card_last_four": parsed.card_last_four[-4:],
                    "statement_month": parsed.statement_month.isoformat(),
                    "statement_period": parsed.statement_month.isoformat(),
                    "closing_balance_cents": parsed.closing_balance_cents,
                    "reward_points": parsed.reward_points,
                    "reward_points_earned": parsed.reward_points_earned,
                    "metadata": {
                        "statement_date": parsed.statement_date.isoformat()
                        if parsed.statement_date
                        else None,
                        "due_date": parsed.due_date.isoformat() if parsed.due_date else None,
                        "minimum_due_cents": parsed.minimum_due_cents,
                    },
                    "transactions": masked_data["transactions"],
                }

            if existing:
                # Update statement in place (UPSERT).
                existing.document_type = "credit_card_statement"
                existing.source_bank = parsed.bank_code or "unknown"
                existing.statement_period = parsed.statement_month
                existing.ingestion_status = "SUCCESS"
                existing.masked_content = build_masked_content()

                existing.closing_balance = parsed.closing_balance_cents
                existing.reward_points = parsed.reward_points
                existing.reward_points_earned = parsed.reward_points_earned

                # Replace transactions (hard delete then insert).
                await self.db.execute(
                    delete(Transaction).where(Transaction.statement_id == existing.id)
                )
                transactions_count = 0
                for masked_txn in masked_data["transactions"]:
                    transaction = Transaction(
                        statement_id=existing.id,
                        user_id=user_id,
                        txn_date=date.fromisoformat(masked_txn["transaction_date"]),
                        merchant=masked_txn["description"],
                        merchant_key=normalize_merchant(masked_txn.get("description")),
                        category=masked_txn.get("category"),
                        amount=masked_txn["amount_cents"],
                        is_credit=masked_txn["transaction_type"].lower() == "credit",
                        reward_points=0,
                    )
                    self.db.add(transaction)
                    transactions_count += 1

                await self.db.commit()
                logger.info(
                    "Upserted statement and replaced transactions",
                    extra={
                        "statement_id": str(existing.id),
                        "transactions_count": transactions_count,
                    },
                )
                return existing.id, card.id, transactions_count

            # Step 3: Create statement
            logger.info(
                "Creating statement",
                extra={
                    "statement_month": parsed.statement_month.isoformat(),
                    "bank_code": parsed.bank_code,
                },
            )
            statement = Statement(
                user_id=user_id,
                card_id=card.id,
                document_type="credit_card_statement",
                source_bank=parsed.bank_code or "unknown",
                statement_period=parsed.statement_month,
                ingestion_status="SUCCESS",
                masked_content=build_masked_content(),
                statement_month=parsed.statement_month,
                closing_balance=parsed.closing_balance_cents,
                reward_points=parsed.reward_points,
                reward_points_earned=parsed.reward_points_earned,
            )
            self.db.add(statement)
            await self.db.flush()  # Get statement.id
            logger.info("Statement created", extra={"statement_id": str(statement.id)})

            # Step 4: Create transactions
            logger.info(
                "Creating transactions",
                extra={"transactions_count": len(masked_data["transactions"])},
            )
            transactions_count = 0
            for masked_txn in masked_data["transactions"]:
                transaction = Transaction(
                    statement_id=statement.id,
                    user_id=user_id,
                    txn_date=date.fromisoformat(masked_txn["transaction_date"]),
                    merchant=masked_txn["description"],  # Masked merchant name
                    merchant_key=normalize_merchant(masked_txn.get("description")),
                    category=masked_txn.get("category"),
                    amount=masked_txn["amount_cents"],
                    is_credit=masked_txn["transaction_type"].lower() == "credit",
                    reward_points=0,  # TODO: Calculate based on category
                )
                self.db.add(transaction)
                transactions_count += 1

            # Step 5: Commit transaction
            await self.db.commit()

            logger.info(
                "Persisted statement and transactions",
                extra={
                    "statement_id": str(statement.id),
                    "transactions_count": transactions_count,
                },
            )
            return statement.id, card.id, transactions_count

        except Exception as e:
            if settings.debug:
                logger.exception(
                    "Database persistence failed", extra={"error_type": type(e).__name__}
                )
            else:
                logger.error(
                    "Database persistence failed", extra={"error_type": type(e).__name__}
                )
            await self.db.rollback()
            raise

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
