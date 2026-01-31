"""Verification tests aligned with processing.md Section F.

These tests focus on the persistence boundary guarantees and idempotency semantics:
- No unmasked PII should cross into persistence (DB rows store masked data only).
- Upload should be idempotent (UPSERT) for same user+card+bank+month.
- Delete + re-upload should work (hard delete semantics).

We patch the PDF parsing + masking components to keep these tests deterministic and
independent of external PDF parsing / NLP model availability.
"""

from __future__ import annotations

import json
import re
from datetime import date

import pytest
from httpx import AsyncClient
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.card import Card
from app.models.merchant_category_override import MerchantCategoryOverride
from app.models.statement import Statement
from app.models.transaction import Transaction
from app.schemas.internal import ParsedStatement, ParsedTransaction
from app.services.statement import StatementService
from app.categorization.rules import normalize_merchant


class _FakeMaskingPipeline:
    """Minimal masking pipeline for tests.

    We only need deterministic behavior here to validate the persistence boundary.
    """

    _email = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")
    _card = re.compile(r"\b(?:\d[ -]*?){13,19}\b")

    def __init__(self, user_id=None, **kwargs):
        self.user_id = user_id

    def mask_dict(self, data: dict, fields_to_mask=None) -> dict:
        masked = dict(data)
        if fields_to_mask is None:
            fields_to_mask = set(k for k, v in data.items() if isinstance(v, str))
        if "description" in fields_to_mask and isinstance(data.get("description"), str):
            desc = data["description"]
            desc = self._email.sub("[REDACTED]", desc)
            desc = self._card.sub("[CARD]", desc)
            masked["description"] = desc
        return masked

    def validate_no_leaks(self, text: str, strict: bool = True):
        # Simple "sensitive" leak detection: email or long digit sequences.
        detected = []
        if self._email.search(text):
            detected.append("EMAIL_ADDRESS")
        if self._card.search(text):
            detected.append("CREDIT_CARD")
        return (len(detected) == 0, detected)


def _pdf_bytes() -> bytes:
    # Upload endpoint requires PDF magic bytes; the content isn't parsed in these tests.
    return b"%PDF-1.4\n%fake\n"


@pytest.mark.asyncio
async def test_upload_persists_masked_content_and_no_pii(
    client: AsyncClient,
    auth_headers: dict,
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
):
    pii_desc = "AMAZON 4111 1111 1111 1111 john.doe@example.com"
    parsed = ParsedStatement(
        card_last_four="1234",
        statement_month=date(2025, 1, 1),
        closing_balance_cents=123456,
        reward_points=42,
        reward_points_earned=7,
        bank_code="sbi",
        transactions=[
            ParsedTransaction(
                transaction_date=date(2025, 1, 5),
                description=pii_desc,
                amount_cents=1000,
                transaction_type="debit",
                category=None,
            )
        ],
    )

    async def _fake_parse_pdf(self, pdf_bytes: bytes, password: str | None):
        return parsed

    monkeypatch.setattr(StatementService, "_parse_pdf", _fake_parse_pdf)
    monkeypatch.setattr("app.services.statement.PIIMaskingPipeline", _FakeMaskingPipeline)

    resp = await client.post(
        "/api/v1/statements/upload",
        headers={**auth_headers, "Content-Type": "application/pdf"},
        content=_pdf_bytes(),
    )
    assert resp.status_code == 201
    body = resp.json()
    statement_id = body["statement_id"]

    stmt = (await db_session.execute(select(Statement).where(Statement.id == statement_id))).scalar_one()
    txns = (
        await db_session.execute(
            select(Transaction).where(Transaction.statement_id == statement_id).order_by(Transaction.txn_date.asc())
        )
    ).scalars().all()

    assert stmt.masked_content is not None
    assert len(txns) == 1

    # Ensure no raw PDF bytes are persisted in masked_content.
    assert "%PDF-" not in json.dumps(stmt.masked_content)

    # Ensure PII was masked before crossing the persistence boundary.
    persisted_merchant = txns[0].merchant
    assert "@" not in persisted_merchant
    assert "4111" not in persisted_merchant
    assert "[REDACTED]" in persisted_merchant
    assert "[CARD]" in persisted_merchant
    assert txns[0].merchant_key == normalize_merchant(persisted_merchant)


@pytest.mark.asyncio
async def test_upload_applies_existing_override_for_debit(
    client: AsyncClient,
    auth_headers: dict,
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
):
    # This description would normally match "shopping" due to AMAZON, but we override it.
    raw_desc = "AMAZON 4111 1111 1111 1111 john.doe@example.com"
    parsed = ParsedStatement(
        card_last_four="1234",
        statement_month=date(2025, 1, 1),
        closing_balance_cents=123456,
        bank_code="sbi",
        transactions=[
            ParsedTransaction(
                transaction_date=date(2025, 1, 5),
                description=raw_desc,
                amount_cents=1000,
                transaction_type="debit",
                category=None,
            )
        ],
    )

    async def _fake_parse_pdf(self, pdf_bytes: bytes, password: str | None):
        return parsed

    monkeypatch.setattr(StatementService, "_parse_pdf", _fake_parse_pdf)
    monkeypatch.setattr("app.services.statement.PIIMaskingPipeline", _FakeMaskingPipeline)

    # Pre-create an override using the merchant_key derived from the masked merchant.
    masked_desc = _FakeMaskingPipeline().mask_dict({"description": raw_desc}, fields_to_mask={"description"})[
        "description"
    ]
    from app.models.user import User

    user_id = (await db_session.execute(select(User.id))).scalar_one()
    override = MerchantCategoryOverride(
        user_id=user_id,
        merchant_key=normalize_merchant(masked_desc),
        category="utilities",
    )
    db_session.add(override)
    await db_session.commit()

    resp = await client.post(
        "/api/v1/statements/upload",
        headers={**auth_headers, "Content-Type": "application/pdf"},
        content=_pdf_bytes(),
    )
    assert resp.status_code == 201
    statement_id = resp.json()["statement_id"]

    txn = (
        await db_session.execute(
            select(Transaction).where(Transaction.statement_id == statement_id)
        )
    ).scalars().one()
    assert txn.is_credit is False
    assert txn.category == "utilities"


@pytest.mark.asyncio
async def test_override_endpoint_backfills_and_affects_statement_summary(
    client: AsyncClient,
    auth_headers: dict,
    db_session: AsyncSession,
    test_user,
):
    # Create a statement + transactions directly in this test.
    from app.repositories.card import CardRepository
    from app.repositories.statement import StatementRepository
    from app.repositories.transaction import TransactionRepository
    from app.models.card import Card
    from app.models.statement import Statement
    from app.models.transaction import Transaction

    card_repo = CardRepository(db_session)
    stmt_repo = StatementRepository(db_session)
    txn_repo = TransactionRepository(db_session)

    card = await card_repo.create(
        Card(user_id=test_user.id, bank_code="HDFC", last_four="1234")
    )
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

    amazon_txn = await txn_repo.create(
        Transaction(
            user_id=test_user.id,
            statement_id=statement.id,
            txn_date=date(2024, 1, 10),
            merchant="Amazon",
            merchant_key=normalize_merchant("Amazon"),
            category="shopping",
            amount=250000,
            is_credit=False,
            reward_points=25,
        )
    )
    await txn_repo.create(
        Transaction(
            user_id=test_user.id,
            statement_id=statement.id,
            txn_date=date(2024, 1, 5),
            merchant="Starbucks",
            merchant_key=normalize_merchant("Starbucks"),
            category="dining",
            amount=45000,
            is_credit=False,
            reward_points=5,
        )
    )
    await txn_repo.create(
        Transaction(
            user_id=test_user.id,
            statement_id=statement.id,
            txn_date=date(2024, 1, 15),
            merchant="Shell",
            merchant_key=normalize_merchant("Shell"),
            category="fuel",
            amount=150000,
            is_credit=False,
            reward_points=15,
        )
    )
    await txn_repo.create(
        Transaction(
            user_id=test_user.id,
            statement_id=statement.id,
            txn_date=date(2024, 1, 20),
            merchant="Payment",
            merchant_key=normalize_merchant("Payment"),
            category="payment",
            amount=500000,
            is_credit=True,
            reward_points=0,
        )
    )
    await db_session.commit()

    # Baseline: statement summary should include shopping category and Amazon merchant.
    resp1 = await client.get(
        f"/api/v1/statements/{statement.id}",
        headers=auth_headers,
    )
    assert resp1.status_code == 200
    summary1 = resp1.json()["spending_summary"]
    cats1 = {c["category"]: c for c in summary1["by_category"]}
    assert cats1["shopping"]["amount"] == 250000
    merch1 = {m["merchant"]: m for m in summary1["top_merchants"]}
    assert merch1["Amazon"]["category"] == "shopping"

    # Apply override to recategorize Amazon as utilities and backfill.
    resp2 = await client.put(
        f"/api/v1/transactions/{amazon_txn.id}/category",
        headers=auth_headers,
        json={"category": "utilities"},
    )
    assert resp2.status_code == 200

    # Summary should reflect the override immediately (grouping is based on transactions table).
    resp3 = await client.get(
        f"/api/v1/statements/{statement.id}",
        headers=auth_headers,
    )
    assert resp3.status_code == 200
    summary3 = resp3.json()["spending_summary"]
    cats3 = {c["category"]: c for c in summary3["by_category"]}
    assert "shopping" not in cats3
    assert cats3["utilities"]["amount"] == 250000

    merch3 = {m["merchant"]: m for m in summary3["top_merchants"]}
    assert merch3["Amazon"]["category"] == "utilities"


@pytest.mark.asyncio
async def test_upload_blocks_persistence_when_pii_leak_detected(
    client: AsyncClient,
    auth_headers: dict,
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
):
    parsed = ParsedStatement(
        card_last_four="1234",
        statement_month=date(2025, 1, 1),
        closing_balance_cents=123456,
        bank_code="sbi",
        transactions=[
            ParsedTransaction(
                transaction_date=date(2025, 1, 5),
                description="john.doe@example.com",
                amount_cents=1000,
                transaction_type="debit",
            )
        ],
    )

    class _LeakPipeline(_FakeMaskingPipeline):
        def mask_dict(self, data: dict, fields_to_mask=None) -> dict:
            # Do not mask (simulate broken masking), then force validation to fail.
            return dict(data)

        def validate_no_leaks(self, text: str, strict: bool = True):
            return (False, ["EMAIL_ADDRESS"])

    async def _fake_parse_pdf(self, pdf_bytes: bytes, password: str | None):
        return parsed

    monkeypatch.setattr(StatementService, "_parse_pdf", _fake_parse_pdf)
    monkeypatch.setattr("app.services.statement.PIIMaskingPipeline", _LeakPipeline)

    resp = await client.post(
        "/api/v1/statements/upload",
        headers={**auth_headers, "Content-Type": "application/pdf"},
        content=_pdf_bytes(),
    )
    assert resp.status_code == 400
    assert resp.json()["detail"]["error_code"] == "MASK_002"

    # No DB writes should have occurred (masking happens before persistence).
    assert (await db_session.execute(select(func.count()).select_from(Card))).scalar_one() == 0
    assert (await db_session.execute(select(func.count()).select_from(Statement))).scalar_one() == 0
    assert (await db_session.execute(select(func.count()).select_from(Transaction))).scalar_one() == 0


@pytest.mark.asyncio
async def test_upload_upsert_replaces_transactions_and_returns_same_statement_id(
    client: AsyncClient,
    auth_headers: dict,
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
):
    parsed1 = ParsedStatement(
        card_last_four="1234",
        statement_month=date(2025, 1, 1),
        closing_balance_cents=111,
        reward_points=10,
        reward_points_earned=1,
        bank_code="sbi",
        transactions=[
            ParsedTransaction(
                transaction_date=date(2025, 1, 5),
                description="Merchant A 4111 1111 1111 1111",
                amount_cents=1000,
                transaction_type="debit",
                category=None,
            ),
            ParsedTransaction(
                transaction_date=date(2025, 1, 6),
                description="Merchant B john@example.com",
                amount_cents=2000,
                transaction_type="debit",
                category=None,
            ),
        ],
    )
    parsed2 = ParsedStatement(
        card_last_four="1234",
        statement_month=date(2025, 1, 1),
        closing_balance_cents=222,
        reward_points=20,
        reward_points_earned=2,
        bank_code="sbi",
        transactions=[
            ParsedTransaction(
                transaction_date=date(2025, 1, 7),
                description="Merchant C 4111 1111 1111 1111",
                amount_cents=3000,
                transaction_type="debit",
                category=None,
            )
        ],
    )

    calls = {"n": 0}

    async def _fake_parse_pdf(self, pdf_bytes: bytes, password: str | None):
        calls["n"] += 1
        return parsed1 if calls["n"] == 1 else parsed2

    monkeypatch.setattr(StatementService, "_parse_pdf", _fake_parse_pdf)
    monkeypatch.setattr("app.services.statement.PIIMaskingPipeline", _FakeMaskingPipeline)

    resp1 = await client.post(
        "/api/v1/statements/upload",
        headers={**auth_headers, "Content-Type": "application/pdf"},
        content=_pdf_bytes(),
    )
    assert resp1.status_code == 201
    stmt_id_1 = resp1.json()["statement_id"]

    resp2 = await client.post(
        "/api/v1/statements/upload",
        headers={**auth_headers, "Content-Type": "application/pdf"},
        content=_pdf_bytes(),
    )
    assert resp2.status_code == 201
    stmt_id_2 = resp2.json()["statement_id"]

    assert stmt_id_2 == stmt_id_1  # idempotent upsert

    stmt = (await db_session.execute(select(Statement).where(Statement.id == stmt_id_1))).scalar_one()
    txns = (
        await db_session.execute(select(Transaction).where(Transaction.statement_id == stmt_id_1))
    ).scalars().all()

    # Transactions replaced to match latest upload.
    assert len(txns) == 1
    assert stmt.closing_balance == 222
    assert stmt.reward_points == 20
    assert stmt.reward_points_earned == 2


@pytest.mark.asyncio
async def test_delete_then_reupload_works(
    client: AsyncClient,
    auth_headers: dict,
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
):
    parsed = ParsedStatement(
        card_last_four="1234",
        statement_month=date(2025, 1, 1),
        closing_balance_cents=123,
        reward_points=1,
        reward_points_earned=1,
        bank_code="sbi",
        transactions=[
            ParsedTransaction(
                transaction_date=date(2025, 1, 5),
                description="Merchant A 4111 1111 1111 1111",
                amount_cents=1000,
                transaction_type="debit",
            )
        ],
    )

    async def _fake_parse_pdf(self, pdf_bytes: bytes, password: str | None):
        return parsed

    monkeypatch.setattr(StatementService, "_parse_pdf", _fake_parse_pdf)
    monkeypatch.setattr("app.services.statement.PIIMaskingPipeline", _FakeMaskingPipeline)

    resp1 = await client.post(
        "/api/v1/statements/upload",
        headers={**auth_headers, "Content-Type": "application/pdf"},
        content=_pdf_bytes(),
    )
    assert resp1.status_code == 201
    stmt_id_1 = resp1.json()["statement_id"]
    card_id_1 = resp1.json()["card_id"]

    del_resp = await client.delete(
        f"/api/v1/statements/{stmt_id_1}",
        headers=auth_headers,
    )
    assert del_resp.status_code == 204

    resp2 = await client.post(
        "/api/v1/statements/upload",
        headers={**auth_headers, "Content-Type": "application/pdf"},
        content=_pdf_bytes(),
    )
    assert resp2.status_code == 201
    stmt_id_2 = resp2.json()["statement_id"]
    card_id_2 = resp2.json()["card_id"]

    assert stmt_id_2 != stmt_id_1  # hard delete -> new statement record
    assert card_id_2 == card_id_1  # card should be reused

    assert (await db_session.execute(select(func.count()).select_from(Statement))).scalar_one() == 1
    assert (await db_session.execute(select(func.count()).select_from(Transaction))).scalar_one() == 1
