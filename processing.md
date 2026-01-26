# Secure Credit Card Statement Ingestion & Analysis Architecture

**Document Version**: 2.0  
**Last Updated**: January 27, 2026  
**Current Phase**: Phase 11 Completed  
**Total Tests**: 296 passing

---

## 0. Implementation Status

### 0.1 Core Requirements

- [x] **Zero Persistence**: No raw PDFs stored on disk or database
- [x] **In-Memory Processing**: PDF bytes processed with size limit (25MB)
- [x] **PII Masking**: All sensitive data masked before persistence
- [x] **User Isolation**: All data scoped to authenticated user
- [x] **Duplicate Handling**: Idempotent upsert for statements
- [x] **Soft Delete**: Re-upload after delete supported
- [x] **Secure Logging**: No PII in logs or debug output

### 0.2 Feature Completeness

#### ✅ Completed Features
- User authentication (JWT, bcrypt)
- Statement upload & parsing (PDF to structured data)
- Multi-bank support (HDFC, Amex, SBI + generic parser)
- PII masking pipeline (Microsoft Presidio)
- Transaction categorization (rule-based + user overrides)
- Category override system with backfill
- Cards & transactions API
- Error handling & structured logging
- Reward points tracking (dual: earned + balance)

#### 🔄 Future Enhancements
- [ ] Refine categorization rules with real patterns
- [ ] RAG service for card benefits Q&A
- [ ] Spending trends and insights
- [ ] Budget tracking and alerts
- [ ] Mobile app support

---

## 1. Overview

This document describes the backend architecture for a **secure, privacy-by-design financial statement ingestion system**. The primary goal is to enable users to upload bank or credit‑card statements, extract insights, and leverage AI‑driven analysis **without persisting raw documents or exposing Personally Identifiable Information (PII)**.

The architecture is intentionally designed to:

* Minimize regulatory exposure (GDPR / PCI scope reduction)
* Guarantee user‑level data isolation in a shared database
* Enable safe downstream analytics and Retrieval‑Augmented Generation (RAG)
* Serve as a stable foundation for automated code generation (e.g., Copilot)

---

## 2. Core Design Principles

1. **Zero Persistence of Raw Documents**
   Raw PDF statements are never written to disk, object storage, or databases.

2. **Privacy‑by‑Design & Data Minimization**
   Only masked, anonymized representations are persisted.

3. **Explicit Ownership & Isolation**
   Every persisted record is owned by exactly one authenticated user.

4. **AI‑Safe by Construction**
   LLMs and vector stores operate exclusively on masked data.

5. **Replaceable Components**
   PDF parsing, storage, and AI layers can be swapped without breaking security guarantees.

---

## 3. High‑Level Architecture Flow

```
Client (Browser)
   ↓  (PDF upload: raw bytes)
Backend API (FastAPI)
   ↓
In‑Memory PDF Bytes (no filesystem)
   ↓
PDF Parsing (local, memory‑only)
   ↓
Normalized JSON (ephemeral)
   ↓
PII Detection
   ↓
PII Masking / Anonymization
   ↓
Masked JSON Payload
   ↓
Relational Database (shared, user‑scoped)
   ↓
Analytics / Dashboard / RAG (masked data only)
```

---

## 4. Secure Ingestion & Data Flow

### 4.1 Ingestion Model

* PDF statements are received as raw HTTP request bodies (`Content-Type: application/pdf`)
* Files are read immediately into memory as byte streams
* No file paths, temporary files, or OS‑level spooling are used
* PDF parsing operates entirely in memory and produces structured JSON

This ingestion model enforces **data minimization** and supports **PCI‑DSS scope reduction** by preventing persistence of raw cardholder data.

---

### 4.2 Transformation & Protection

* Parsed content is normalized into a canonical JSON structure held only in memory
* PII is detected using deterministic rules (regex / context‑based)
* PII is irreversibly masked **before any persistence**
* Masking policies are

  * are auditable
  * prevent re‑identification
  * preserve analytical utility

---

### 4.3 Persistence Boundary

* Only masked and anonymized JSON data is persisted
* Raw PDFs, unmasked text, and intermediate artifacts are discarded after request completion
* No raw PII crosses the persistence boundary

This design ensures unmasked financial data never exists at rest.

---

## 5. User Data Isolation & Multi‑Tenant Safety

Although the system uses a **shared relational database**, strict logical isolation is enforced.

### 5.1 Ownership Model

* Every persisted statement is associated with a single authenticated user
* Ownership is represented using a non‑PII identifier (`owner_user_id`)

### 5.2 Access Rules

* All read and query operations are scoped by the requesting user’s identity
* Users can only view statements they uploaded
* Cross‑user visibility is explicitly prohibited

This model aligns with confidentiality and access‑control principles under GDPR.

---

## 6. Relational Database Design

### 6.1 `statements` Table (Authoritative)

| Column Name        | Description                               |
| ------------------ | ----------------------------------------- |
| `statement_id`     | Primary key (UUID)                        |
| `owner_user_id`    | Auth‑system user identifier (non‑PII)     |
| `document_type`    | `credit_card_statement`, `bank_statement` |
| `source_bank`      | Issuer name (if detectable)               |
| `statement_period` | Billing period (e.g., `2025‑01`)          |
| `masked_content`   | Masked JSON payload                       |
| `ingestion_status` | `SUCCESS`, `PARTIAL`, `FAILED`            |
| `created_at`       | Ingestion timestamp                       |

### 6.2 Masked Content Characteristics

* Contains no raw personal or cardholder data
* Human‑readable and AI‑friendly
* Suitable for dashboards, analytics, and RAG ingestion

---

## 7. AI & RAG Safety Guarantees

* Embeddings are generated only from masked text
* Vector metadata includes `owner_user_id` to enforce user‑scoped retrieval
* RAG queries are filtered by user identity
* LLM prompts never include raw identifiers or sensitive attributes

This prevents cross‑user AI leakage and hallucinated exposure of personal data.

---

## 8. Security Assumptions & Compliance Alignment

The system is designed using **privacy‑by‑design and data‑minimization principles**, aligned with GDPR and PCI‑DSS guidance, while **not claiming formal regulatory compliance**.

### Key Assumptions

* Backend runs in a containerized environment with ephemeral runtime storage
* No crash dumps or request payload captures containing sensitive data are retained
* Application logs are sanitized to avoid accidental data leakage

Under these assumptions:

* Application‑level encryption of raw documents is not required (no persistence surface exists)
* Masking serves as the primary application‑level control
* Infrastructure‑level encryption may be introduced if persistence is added in future phases

---

## 9. Future Hardening (Out of Scope for MVP)

* Database Row‑Level Security (RLS) for defense‑in‑depth
* Optional encryption of masked data at rest
* Formal compliance audits (GDPR / PCI)
* Multi‑bank schema standardization

---

## 10. Summary

This architecture ensures that:

* Raw financial documents are never persisted
* Masked data is user‑isolated and AI‑safe
* Regulatory exposure is minimized by design
* The system is production‑credible while remaining MVP‑friendly

This document is intended to act as a **source of truth for backend implementation and automated code generation**.

---

---

# Part 2: Implementation Plan

## 11. Technology Decisions

| Component | Technology | Rationale |
|-----------|------------|-----------|
| API Framework | FastAPI | Async support, auto-docs, Pydantic integration |
| Database | PostgreSQL | ACID compliance, JSON support, mature ecosystem |
| ORM | SQLAlchemy 2.0 | Type hints, async support, repository pattern |
| Migrations | Alembic | Industry standard for SQLAlchemy |
| PDF Parsing | Unstructured.io | Local processing, good table extraction, extensible |
| PII Masking | Microsoft Presidio | Free, open-source, custom recognizers |
| Auth | JWT (python-jose) | Stateless, scalable, future OAuth 2.0 ready |
| Password Hashing | Argon2 | Memory-hard, recommended by OWASP |
| Validation | Pydantic v2 | Fast, type-safe, excellent error messages |
| Testing | pytest + pytest-asyncio | Async support, fixtures, coverage |

---

## 12. Project Folder Structure

```
src/
├── app/
│   ├── __init__.py
│   ├── main.py                          # FastAPI app factory
│   ├── config.py                        # Settings via pydantic-settings
│   │
│   ├── api/
│   │   ├── __init__.py
│   │   ├── deps.py                      # Shared dependencies (get_db, get_current_user)
│   │   └── v1/
│   │       ├── __init__.py
│   │       ├── router.py                # Aggregates all v1 routes
│   │       ├── auth.py                  # Auth endpoints
│   │       ├── statements.py            # Statement upload/list endpoints
│   │       ├── transactions.py          # Transaction query endpoints
│   │       ├── cards.py                 # Card management endpoints
│   │       └── health.py                # Health check endpoints
│   │
│   ├── core/
│   │   ├── __init__.py
│   │   ├── security.py                  # JWT, password hashing
│   │   ├── exceptions.py                # Custom exception classes
│   │   └── errors.py                    # Error codes and messages
│   │
│   ├── models/
│   │   ├── __init__.py
│   │   ├── base.py                      # SQLAlchemy Base, mixins
│   │   ├── user.py                      # User model
│   │   ├── card.py                      # Card model
│   │   ├── statement.py                 # Statement model
│   │   └── transaction.py               # Transaction model
│   │
│   ├── schemas/
│   │   ├── __init__.py
│   │   ├── auth.py                      # Auth request/response
│   │   ├── card.py                      # Card schemas
│   │   ├── statement.py                 # Statement schemas
│   │   ├── transaction.py               # Transaction schemas
│   │   └── common.py                    # Shared schemas (pagination, errors)
│   │
│   ├── repositories/
│   │   ├── __init__.py
│   │   ├── base.py                      # Generic CRUD repository
│   │   ├── user.py                      # User repository
│   │   ├── card.py                      # Card repository
│   │   ├── statement.py                 # Statement repository
│   │   └── transaction.py               # Transaction repository
│   │
│   ├── services/
│   │   ├── __init__.py
│   │   ├── auth.py                      # Auth business logic
│   │   ├── statement.py                 # Statement processing orchestration
│   │   └── card.py                      # Card management logic
│   │
│   ├── parsers/
│   │   ├── __init__.py
│   │   ├── extractor.py                 # Unstructured.io wrapper (in-memory)
│   │   ├── detector.py                  # Bank detection from PDF content
│   │   ├── generic.py                   # GenericParser (90% of logic)
│   │   ├── factory.py                   # Detects bank, returns appropriate parser
│   │   └── refinements/                 # Bank-specific overrides (minimal)
│   │       ├── __init__.py
│   │       ├── hdfc.py                  # HDFC date format, rewards location
│   │       ├── icici.py                 # ICICI-specific quirks
│   │       ├── sbi.py                   # SBI-specific quirks
│   │       ├── amex.py                  # US date format, 5-digit account
│   │       ├── citi.py                  # Citi-specific quirks
│   │       └── chase.py                 # Chase-specific quirks
│   │
│   ├── masking/
│   │   ├── __init__.py
│   │   ├── engine.py                    # Presidio setup
│   │   ├── recognizers.py               # Custom PII recognizers
│   │   └── pipeline.py                  # Masking orchestration
│   │
│   └── db/
│       ├── __init__.py
│       ├── session.py                   # Database connection
│       └── seed.py                      # Initial data (banks, MCC codes)
│
├── tests/
│   ├── __init__.py
│   ├── conftest.py                      # Shared fixtures
│   ├── unit/
│   │   ├── __init__.py
│   │   ├── test_security.py
│   │   ├── test_parsers/
│   │   ├── test_masking/
│   │   └── test_services/
│   ├── integration/
│   │   ├── __init__.py
│   │   ├── test_auth_api.py
│   │   ├── test_statement_api.py
│   │   └── test_repositories.py
│   └── fixtures/
│       ├── sample_statements/           # Anonymized test PDFs
│       └── expected_outputs/            # Expected parsed JSON
│
├── alembic/
│   ├── env.py
│   ├── script.py.mako
│   └── versions/                        # Migration files
│
├── scripts/
│   └── seed_data.py                     # Seed banks, MCC codes
│
├── .env.example
├── pyproject.toml
├── requirements.txt
├── Dockerfile
├── docker-compose.yml
└── README.md
```

---

## 13. Implementation Phases

Each phase produces a **working, testable increment**. Complete all tests before proceeding.

---

### Phase 1: Project Setup & Configuration ✅ **COMPLETED**

**Goal**: Initialize project with FastAPI, database connection, and configuration management.

**Deliverables**:
- [x] `pyproject.toml` with dependencies
- [x] `app/config.py` with pydantic-settings
- [x] `app/main.py` with FastAPI app factory
- [x] `app/db/session.py` with async SQLAlchemy
- [x] `app/api/v1/health.py` with `/health` and `/health/ready`
- [x] `docker-compose.yml` with PostgreSQL
- [x] `alembic/` setup (no migrations yet)
- [x] `tests/conftest.py` with test fixtures
- [x] `tests/integration/test_health.py`
- [x] `README.md` with setup instructions

**Completion Criteria**:
- [x] `docker-compose up` starts PostgreSQL
- [x] `uvicorn app.main:app` starts without errors
- [x] `GET /health` returns `{"status": "ok"}`
- [x] `GET /health/ready` checks database connection
- [x] All tests pass: `pytest tests/` (2 passed)

**Completed**: January 22, 2026

---

### Phase 2: Database Models & Migrations ✅ **COMPLETED**

**Goal**: Define SQLAlchemy models and create initial migration.

**Deliverables**:
- [x] `app/models/base.py` — Base class with `id`, `created_at`, `updated_at`
- [x] `app/models/user.py` — User model
- [x] `app/models/card.py` — Card model (FK to User)
- [x] `app/models/statement.py` — Statement model (FK to User, Card)
- [x] `app/models/transaction.py` — Transaction model (FK to Statement)
- [x] `alembic/versions/a5806189b8bb_*.py` — Initial migration
- [x] `scripts/seed_data.py` — Seed supported banks

**Database Schema**:

```sql
-- users
id              UUID PRIMARY KEY
email           VARCHAR(255) UNIQUE NOT NULL
password_hash   VARCHAR(255) NOT NULL
is_active       BOOLEAN DEFAULT TRUE
created_at      TIMESTAMP WITH TIME ZONE
updated_at      TIMESTAMP WITH TIME ZONE

-- cards
id              UUID PRIMARY KEY
user_id         UUID REFERENCES users(id)
last_four       VARCHAR(4) NOT NULL
bank_code       VARCHAR(20) NOT NULL
network         VARCHAR(20)
product_name    VARCHAR(100)
is_active       BOOLEAN DEFAULT TRUE
created_at      TIMESTAMP WITH TIME ZONE

-- statements
id              UUID PRIMARY KEY
user_id         UUID REFERENCES users(id)
card_id         UUID REFERENCES cards(id)
statement_month DATE NOT NULL
closing_balance BIGINT
reward_points   INTEGER DEFAULT 0
created_at      TIMESTAMP WITH TIME ZONE
UNIQUE(card_id, statement_month)

-- transactions
id              UUID PRIMARY KEY
statement_id    UUID REFERENCES statements(id)
user_id         UUID REFERENCES users(id)
txn_date        DATE NOT NULL
merchant        VARCHAR(255)
category        VARCHAR(100)
amount          BIGINT NOT NULL
is_credit       BOOLEAN DEFAULT FALSE
reward_points   INTEGER DEFAULT 0
created_at      TIMESTAMP WITH TIME ZONE
```

**Completion Criteria**:
- [x] `alembic upgrade head` runs without errors
- [x] All tables created in PostgreSQL
- [x] `alembic downgrade base` removes all tables
- [x] Seed script inserts bank data

**Completed**: January 22, 2026

---

### Phase 3: Repository Layer ✅

**Goal**: Implement data access layer with repository pattern.

**Deliverables**:
- [x] `app/repositories/base.py` — Generic CRUD operations
- [x] `app/repositories/user.py` — User-specific queries
- [x] `app/repositories/card.py` — Card queries (scoped by user)
- [x] `app/repositories/statement.py` — Statement queries
- [x] `app/repositories/transaction.py` — Transaction queries
- [x] `tests/integration/test_repositories.py`

**Base Repository Interface**:
```python
class BaseRepository[T]:
    async def get_by_id(self, id: UUID) -> T | None
    async def get_all(self, skip: int, limit: int) -> list[T]
    async def create(self, obj: T) -> T
    async def update(self, id: UUID, data: dict) -> T | None
    async def delete(self, id: UUID) -> bool
```

**Completion Criteria**:
- [x] All CRUD operations work for each model
- [x] User-scoped queries return only owned records
- [x] Integration tests cover happy path + edge cases
- [x] No N+1 query issues (use `joinedload` where needed)

**Completed**: January 22, 2026 — All 22 integration tests passing

---

### Phase 4: Authentication Service ✅ **COMPLETED**

**Goal**: Implement JWT-based authentication with registration and login.

**Deliverables**:
- [x] `app/core/security.py` — Password hashing, JWT creation/verification
- [x] `app/core/config.py` — Configuration management with JWT_SECRET
- [x] `app/schemas/auth.py` — Request/response models
- [x] `app/services/auth.py` — Auth business logic
- [x] `app/api/v1/auth.py` — Endpoints
- [x] `app/api/deps.py` — `get_current_user` dependency
- [x] `tests/unit/test_security.py` — 13 tests passing
- [x] `tests/integration/test_auth_api.py` — 17 tests passing
- [x] `alembic/versions/92b9dbe1a9cd_add_full_name_to_users.py` — Migration

**Endpoints**:
| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/v1/auth/register` | Create account |
| POST | `/api/v1/auth/login` | Get access + refresh tokens |
| POST | `/api/v1/auth/refresh` | Refresh access token |
| GET | `/api/v1/auth/me` | Get current user |

**Auth Provider Interface** (for future OAuth):
```python
class AuthProvider(ABC):
    @abstractmethod
    async def authenticate(self, credentials: dict) -> User | None: ...
    
    @abstractmethod
    def create_tokens(self, user: User) -> TokenPair: ...
```

**Completion Criteria**:
- [x] User can register with email/password
- [x] Password stored as Argon2 hash
- [x] Login returns JWT access token (30 min) + refresh token (7 days)
- [x] Protected routes reject invalid/expired tokens
- [x] `GET /me` returns current user info
- [x] All tests pass: 30/30 (13 unit + 17 integration)
- [x] Test coverage >90% for auth module

**Completed**: January 23, 2026

---

### Phase 5: PII Masking Pipeline ✅ **COMPLETED**

**Goal**: Implement Microsoft Presidio-based PII detection and masking.

**Deliverables**:
- [x] `app/masking/engine.py` — Presidio analyzer/anonymizer setup with spaCy NLP engine
- [x] `app/masking/recognizers.py` — Custom recognizers (PAN, Aadhaar, Indian mobile, Credit Card)
- [x] `app/masking/pipeline.py` — PIIMaskingPipeline with HMAC tokenization and validation
- [x] `app/masking/__init__.py` — Module exports
- [x] `tests/unit/test_masking/test_engine.py` — 8 tests for analyzer/anonymizer
- [x] `tests/unit/test_masking/test_recognizers.py` — 20 tests for custom recognizers
- [x] `tests/unit/test_masking/test_pipeline.py` — 22 tests for full pipeline

**Masking Rules Implemented**:
| PII Type | Action | Implementation |
|----------|--------|----------------|
| Person name | Tokenize (HMAC) | User-scoped deterministic HMAC tokens |
| Card number | Keep last 4 | `****1111` pattern with Luhn validation |
| Phone | Redact | `[PHONE_NUMBER]` with Indian mobile patterns |
| Email | Redact | `[EMAIL_ADDRESS]` via Presidio defaults |
| PAN (India) | Redact | `[IN_PAN]` with pattern validation (AAAAA9999A) |
| Aadhaar (India) | Redact | `[IN_AADHAAR]` with Verhoeff checksum validation |
| Address | Redact | `[LOCATION]` via Presidio defaults |

**Implementation Highlights**:
```python
class PIIMaskingPipeline:
    def __init__(self, user_id: UUID | None = None, confidence_threshold: float = 0.7):
        self.analyzer = get_analyzer()  # Presidio + spaCy + custom recognizers
        self.anonymizer = get_anonymizer()
        self.user_id = user_id
        self.confidence_threshold = confidence_threshold
    
    def mask_text(self, text: str) -> str:
        """Detect and mask PII in text."""
        # Returns masked text with entity-specific operators
    
    def mask_dict(self, data: dict, fields: list[str] | None = None) -> dict:
        """Recursively mask dictionary values."""
        # Handles nested structures and lists
    
    def validate_no_leaks(self, masked_text: str, strict: bool = True) -> bool:
        """Re-analyze to confirm no PII leaked through masking."""
```

**Custom Recognizers**:
1. **PANCardRecognizer**: Pattern `[A-Z]{5}[0-9]{4}[A-Z]` with confidence 0.9
2. **AadhaarRecognizer**: 12-digit with Verhoeff validation, rejects 0/1 start
3. **IndianMobileRecognizer**: 3 patterns (`+91 `, `+91`, `91` prefixes)
4. **CreditCardRecognizer**: Visa/MC/Amex patterns with Luhn algorithm validation

**Test Coverage**:
- [x] All 50 tests passing (100% pass rate)
- [x] Recognizer validation algorithms tested (Verhoeff, Luhn)
- [x] HMAC tokenization determinism verified
- [x] Dictionary and nested structure masking tested
- [x] Strict validation mode tested (detects PII leaks)
- [x] Confidence threshold filtering tested
- [x] Edge cases covered (partial matches, multiple entities)

**Dependencies Installed**:
- presidio-analyzer==2.2.360
- presidio-anonymizer==2.2.360
- spacy==3.7.2
- en_core_web_sm==3.7.1 (spaCy language model)

**Environment**: Python 3.13.9 (venv) with all dependencies via Poetry

**Python 3.13 Migration**: January 24, 2026
- Updated from Python 3.12.12 to Python 3.13.9
- Fixed Presidio 2.2.360 configuration bug by manually registering recognizers
- All 180 tests passing on Python 3.13

**Completed**: January 23, 2026

#### Adding New PII Recognizers

Due to a bug in Presidio 2.2.360's default configuration file, we manually configure recognizers instead of using `load_predefined_recognizers()`. To add new recognizers:

**Step 1**: Import the recognizer in `src/app/masking/engine.py`:
```python
from presidio_analyzer.predefined_recognizers import (
    # ... existing imports ...
    UsSsnRecognizer,  # Add your new recognizer
)
```

**Step 2**: Register it in `get_analyzer()` function:
```python
registry.add_recognizer(UsSsnRecognizer(supported_language="en"))
```

**Step 3** (Optional): Define anonymization strategy in `get_default_operators()`:
```python
return {
    # ... existing ...
    "US_SSN": OperatorConfig("replace", {"new_value": "[REDACTED]"}),
}
```

**Step 4** (If sensitive): Add to validation in `src/app/masking/pipeline.py`:
```python
sensitive_entity_types = {
    # ... existing ...
    "US_SSN",
}
```

**Available Recognizers** (see comments in engine.py for full list):
- **US**: UsSsnRecognizer, UsPassportRecognizer, UsBankRecognizer, UsLicenseRecognizer, UsItinRecognizer
- **Europe**: IbanRecognizer, EsNifRecognizer, ItFiscalCodeRecognizer, PlPeselRecognizer
- **Asia-Pacific**: AuAbnRecognizer, AuTfnRecognizer, AuMedicareRecognizer, SgFinRecognizer
- **Already Enabled**: EmailRecognizer, PhoneRecognizer, IpRecognizer, UrlRecognizer, DateRecognizer, SpacyRecognizer, plus custom Indian recognizers

**Anonymization Strategies**:
- `replace`: Fixed text like `[REDACTED]`
- `mask`: Keep partial data (e.g., last 4 digits)
- `hash`: One-way hash for deterministic tokens
- `keep`: Don't anonymize

**Example - Enable US SSN**:
```python
# 1. Import (in engine.py)
from presidio_analyzer.predefined_recognizers import UsSsnRecognizer

# 2. Register (in get_analyzer)
registry.add_recognizer(UsSsnRecognizer(supported_language="en"))

# 3. Define strategy (in get_default_operators)
"US_SSN": OperatorConfig("replace", {"new_value": "[REDACTED]"}),

# 4. Add to validation (in pipeline.py)
"US_SSN",  # Add to sensitive_entity_types set
```

#### Intelligent Pre-Masked Data Detection

The masking pipeline includes **smart detection of already-masked data** to prevent redundant processing. This is particularly important when processing bank statements that already contain pre-masked information (e.g., SBI's format: `XXXX XXXX XXXX XX95`).

**How It Works**:

The `is_already_masked()` method detects common masking patterns using regex:

```python
MASKED_PATTERNS = [
    r'[X*]{4,}',  # XXXX or **** (4+ consecutive X's or asterisks)
    r'\[REDACTED\]',  # [REDACTED] marker
    r'\[MASKED\]',  # [MASKED] marker
    r'\d{4}[\sX*]{4,}\d{2,4}',  # Patterns like "4532 XXXX XXXX 0366"
    r'[X*]{4}\s[X*]{4}\s[X*]{4}\s[X*]{2,4}\d{2,4}',  # XXXX XXXX XXXX XX95
]
```

**Behavior**:
- If any masking pattern is detected in the text, the **entire text is skipped** from processing
- This prevents:
  - Wasted computation on already-protected data
  - False positive detection (e.g., XXXX detected as PERSON entity)
  - Potential incorrect transformations
- Full, unmasked PII is still detected and masked normally

**Examples**:

```python
pipeline = PIIMaskingPipeline()

# Already-masked data passes through unchanged
masked = "Card: XXXX XXXX XXXX XX95"
result = pipeline.mask_text(masked)
assert result == masked  # Unchanged

# Full PII is still masked
full_card = "Card: 4532 0151 1283 0366"
result = pipeline.mask_text(full_card)
assert "4532 0151 1283 0366" not in result  # Masked to ************0366
```

**When to Update Patterns**:

If your financial institution uses different masking formats, add them to `MASKED_PATTERNS` in [pipeline.py](src/app/masking/pipeline.py):

```python
# Example: Add pattern for format like "####-####-####-0366"
r'\#{4}[\s-]\#{4}[\s-]\#{4}[\s-]\d{4}',
```

**Test Coverage**: See `TestAlreadyMaskedDetection` in [test_pipeline.py](tests/unit/test_masking/test_pipeline.py) for comprehensive test cases (13 tests covering all patterns and edge cases).

---

### Phase 6: PDF Parser — Hybrid Architecture ✅ **COMPLETED**

**Goal**: Implement GenericParser + bank detection + minimal refinements.

**Architecture**: Hybrid approach where GenericParser handles 90% of logic, bank-specific refinements only override what's different.

**Deliverables**:
- [x] `app/parsers/extractor.py` — Unstructured.io wrapper (in-memory)
- [x] `app/parsers/detector.py` — Bank detection from PDF text
- [x] `app/parsers/generic.py` — GenericParser with common extraction logic
- [x] `app/parsers/factory.py` — Ties together detection + parser selection
- [x] `app/schemas/internal.py` — `ParsedStatement`, `ParsedTransaction`
- [x] `tests/unit/test_parsers/test_extractor.py`
- [x] `tests/unit/test_parsers/test_detector.py`
- [x] `tests/unit/test_parsers/test_generic.py`
- [x] `tests/unit/test_parsers/test_factory.py`
- [x] `tests/unit/test_parsers/test_internal_schemas.py`

**Implementation Highlights**:

**PDFExtractor** (`app/parsers/extractor.py`):
- Uses Unstructured.io for in-memory PDF parsing (no temp files)
- Strategy: "auto" (default) - let Unstructured choose optimal approach
- Supports password-protected PDFs
- Enhanced error handling with user-friendly messages
- Extracts text, tables, and structure from PDF bytes

**BankDetector** (`app/parsers/detector.py`):
- Pattern-based bank identification (6 supported banks)
- Supported banks: HDFC, ICICI, SBI, Amex, Citi, Chase
- Case-insensitive regex matching
- Extensible: can add new patterns at runtime
- Returns `None` for unknown banks (graceful fallback)

**GenericParser** (`app/parsers/generic.py`):
- Extracts common fields: card number, period, balance, transactions
- Pattern-based extraction using regex
- Handles multiple date formats (DD-MMM-YY, DD/MM/YYYY, MM/DD/YYYY)
- Handles multiple currency formats (₹, $)
- Optional fields: statement_date, due_date, minimum_due
- Extensible: subclasses override only what's different

**ParserFactory** (`app/parsers/factory.py`):
- Orchestrates complete parsing workflow
- 1. Extract PDF → 2. Detect Bank → 3. Select Parser → 4. Parse
- Supports parser refinements (bank-specific overrides)
- Falls back to GenericParser for unknown banks
- Singleton pattern for convenience

**Data Schemas** (`app/schemas/internal.py`):
- `ParsedTransaction`: transaction_date, description, amount_cents, type, category
- `ParsedStatement`: card, period, balance, rewards, transactions + optional metadata
- Pydantic validation ensures data quality
- Helper methods: `from_decimal()`, `from_decimal_balance()`

**Test Coverage**: 76/76 tests passing (100%)
- 15 detector tests (pattern matching, extensibility)
- 8 extractor tests (BytesIO, error handling, password support)
- 25 generic parser tests (date/amount parsing, field extraction)
- 15 factory tests (routing, refinements, singleton)
- 13 schema validation tests

**Completion Criteria**:
- [x] Unstructured.io extracts text/tables from PDF bytes (in-memory)
- [x] BankDetector correctly identifies all 6 supported banks
- [x] GenericParser extracts card, period, transactions, balance from any statement
- [x] Unknown bank uses GenericParser (graceful fallback)
- [x] No temporary files created
- [x] Tests use mock Unstructured responses
- [x] All 193 tests passing

**Completed**: January 24, 2026

---

### Phase 7: Bank-Specific Refinements ✅ **COMPLETED** (January 24, 2026)

**Goal**: Add minimal overrides for bank-specific quirks. Only override methods where GenericParser fails.

**Approach**: Each refinement extends `GenericParser` and overrides only what's different.

**Implementation Highlights**:
- ✅ **HDFC Parser** (57 lines): Overrides `_parse_date()` for Indian date formats (DD-MMM-YY)
- ✅ **Amex Parser** (102 lines): Overrides `_parse_date()` for US dates (MM/DD/YYYY) and `_find_card_number()` for 5-digit endings
- ✅ **Factory Registration**: Auto-registered in singleton factory on first use
- ✅ **Other Banks**: ICICI, SBI, Citi, Chase work with GenericParser (no refinements needed yet)
- ✅ **Test Suite**: 24 new tests (all passing)
- ✅ **Total Tests**: 217 tests passing (193 original + 24 refinements)

**Key Design Decisions**:
- **Refinement Pattern**: Extend GenericParser, override 1-2 methods max, fallback to super()
- **Minimal Code**: HDFCParser is 57 lines, AmexParser is 102 lines — no duplication
- **DRY Principle**: 90% of logic stays in GenericParser, only bank-specific quirks overridden
- **Decision Tree**: Test GenericParser first, create refinement only if it fails

**Deliverables**:
- [x] `app/parsers/refinements/hdfc.py` — HDFC date format override  
- [x] `app/parsers/refinements/amex.py` — US date format, 5-digit account
- [x] `app/parsers/refinements/__init__.py` — Module exports
- [x] `tests/unit/test_parsers/test_refinements.py` — 24 comprehensive tests
- [x] Factory auto-registration in singleton pattern
- [ ] ICICI, SBI, Citi, Chase — Not needed (GenericParser handles them)
- [ ] `tests/fixtures/sample_statements/` — Defer to integration testing phase

**Notes**:
- Other banks (ICICI, SBI, Citi, Chase) work with GenericParser as-is
- Refinements only created when GenericParser demonstrably fails
- Can add more refinements incrementally as needed

**Example Refinement** (minimal code):
```python
# parsers/refinements/hdfc.py
class HDFCParser(GenericParser):
    """Only overrides HDFC-specific date format."""
    bank_code = "hdfc"
    
    def _parse_date(self, text: str) -> date:
        # HDFC uses "15-Jan-25" format
        return datetime.strptime(text.strip(), "%d-%b-%y").date()

# parsers/refinements/amex.py  
class AmexParser(GenericParser):
    """Overrides US date format and account number pattern."""
    bank_code = "amex"
    
    def _parse_date(self, text: str) -> date:
        # Amex uses MM/DD/YYYY (US format)
        return datetime.strptime(text.strip(), "%m/%d/%Y").date()
    
    def _find_card_number(self, elements) -> str:
        # Amex shows 5-digit account ending
        for el in elements:
            match = re.search(r'Account\s+Ending[:\s]*(\d{5})', el.text, re.I)
            if match:
                return match.group(1)[-4:]
        return super()._find_card_number(elements)
```

**When to Create a Refinement**:
| Situation | Action |
|-----------|--------|
| GenericParser works | No refinement needed |
| Date format differs | Override `_parse_date()` |
| Amount format differs | Override `_parse_amount()` |
| Rewards in unusual location | Override `_find_rewards()` |
| Card number pattern differs | Override `_find_card_number()` |

**Completion Criteria**:
- [x] GenericParser handles most banks (ICICI, SBI, Citi, Chase) with no refinement
- [x] Refinements are minimal (HDFCParser: 57 lines, AmexParser: 102 lines)
- [x] Date parsing handles: DD-MMM-YY, DD/MM/YYYY, MM/DD/YYYY formats
- [x] Amount parsing handles: ₹1,23,456.00 and $1,234.56 formats (inherited from GenericParser)
- [x] All 24 refinement tests pass (100% pass rate)
- [x] Tests cover fallback behavior and inheritance patterns
- [x] Factory auto-registers refinements in singleton
- [x] Total test suite: 217 tests passing (193 original + 24 refinements)

---

### Phase 8: Statement Processing Service ✅ **COMPLETED** (January 25, 2025)

**Goal**: Orchestrate PDF parsing, PII masking, and persistence.

**Deliverables**:
- [x] `app/core/exceptions.py` — Custom exceptions (93 lines, 6 exception types)
- [x] `app/core/errors.py` — Error codes and user messages (146 lines, 10 error definitions)
- [x] `app/schemas/statement.py` — Request/response models (91 lines)
- [x] `app/services/statement.py` — Processing orchestration (359 lines, 8-step workflow)
- [x] `app/parsers/factory.py` — Added password parameter support
- [x] `tests/unit/test_services/test_statement.py` — 13 comprehensive tests

**Processing Flow**:
```python
class StatementService:
    async def process_upload(
        self, 
        pdf_bytes: bytes, 
        user: User,
        password: str | None = None
    ) -> StatementUploadResult:
        # 1. Extract PDF elements (Unstructured)
        # 2. Detect bank & select parser
        # 3. Parse to structured data
        # 4. Validate completeness
        # 5. Mask PII (Presidio)
        # 6. Validate no PII leaked
        # 7. Persist statement + transactions (atomic)
        # 8. Return result with processing time
```

**Error Handling**:
| Error Code | User Message | Retry Allowed |
|------------|--------------|---------------|
| PARSE_001 | "Unsupported bank format" | No |
| PARSE_002 | "PDF appears corrupted" | Yes |
| PARSE_003 | "Password required for encrypted PDF" | Yes |
| PARSE_004 | "Incorrect password" | Yes |
| PARSE_005 | "Could not extract transactions" | No |
| MASK_001 | "Failed to mask sensitive data" | Yes |
| MASK_002 | "PII leak detected after masking" | No |
| DB_001 | "Database transaction failed" | Yes |
| VAL_001 | "Data validation failed" | No |

**Implementation Highlights**:
- **Exception Hierarchy**: Type-safe error handling with error_code mapping to catalog
- **Error Catalog**: 10 predefined errors with technical and user-friendly messages
- **Atomic Transactions**: Database rollback on any failure, no partial data
- **Card Reuse**: Automatically finds or creates card for same user+bank+last_four
- **Idempotent Upload (UPSERT)**: For same card_id + statement_month, update statement in place and replace transactions.
- **Password Support**: Handles encrypted PDFs through entire pipeline
- **Comprehensive Tests**: 13 tests covering success path, all error paths, edge cases

**Test Statistics**:
- Total tests: 230 (217 existing + 13 new)
- All tests passing ✅
- No regressions in existing functionality

**Completion Criteria**:
- [x] Full 8-step workflow implemented end-to-end
- [x] All error codes properly mapped and handled
- [x] Idempotent upload updates in place for the same (card_id + statement_month)
- [x] Database transactions are atomic (commit/rollback)
- [x] Only fully validated data persists
- [x] No partial statements in database (rollback on error)
- [x] All PII masked before persistence
- [x] User ownership correctly assigned
- [x] Each error type has specific exception class
- [x] User-friendly messages for all errors (10 errors defined)
- [x] Technical details logged but not exposed
- [x] Retry guidance provided via retry_allowed flag
- [x] Comprehensive unit tests (13 tests, all passing)
- [x] Mocks for external components (parser, masking)

---

### Phase 9: Statement API Endpoints ✅ **COMPLETED**

**Goal**: Expose statement upload and query endpoints.

**Deliverables**:
- [x] `app/api/v1/statements.py` — 717 lines, 5 endpoints
- [x] `tests/integration/test_statement_api.py` — 809 lines, 23 integration tests

**Endpoints Implemented**:
| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/v1/statements/upload` | Upload & process PDF with 4-step validation |
| GET | `/api/v1/statements` | List user's statements with pagination & filters |
| GET | `/api/v1/statements/{id}` | Get statement details with spending summary |
| GET | `/api/v1/statements/{id}/transactions` | **BONUS**: Paginated transactions with filters & sorting |
| DELETE | `/api/v1/statements/{id}` | Permanently delete statement + cascade to transactions |

**Upload Request**:
```
POST /api/v1/statements/upload
Content-Type: multipart/form-data

file: <PDF bytes>
password: <optional>
```

**Upload Response**:
```json
{
  "statement_id": "uuid",
  "card_id": "uuid",
  "bank": "hdfc",
  "statement_month": "2025-01",
  "transactions_count": 45,
  "reward_points": 1250,
  "processing_time_ms": 1850
}
```

**Key Features Implemented**:
- **File Validation**: 4-step validation (extension → MIME type → size → PDF magic bytes)
- **Size Limit**: 25MB (exceeds 10MB requirement)
- **Pagination**: Offset/limit with metadata (page, total, total_pages)
- **Filtering**: By card_id, date ranges, category, merchant search
- **Sorting**: By transaction date and amount (ascending/descending)
- **Spending Summary**: Category breakdown and top 10 merchants
- **Delete**: Permanently delete statement + cascade delete transactions
- **Error Handling**: Error catalog with codes API_001-005
- **Security**: All endpoints user-scoped with ownership validation
- **Background Processing**: Placeholder for RAG embeddings

**Completion Criteria**:
- [x] Upload accepts PDF up to 25MB (exceeded 10MB requirement)
- [x] Rejects non-PDF files with clear error (4-step validation)
- [x] Returns processing result within 60 seconds (synchronous)
- [x] List/Get scoped to authenticated user only (all endpoints)
- [x] Delete removes statement + all transactions (hard delete with cascade)
- [x] Integration tests cover success + all error cases (23 tests, 100% passing)

**Test Coverage**:
- Upload validation: 4 tests (file extension, MIME type, size, magic bytes)
- Statement list: 6 tests (pagination, filtering, edge cases)
- Statement detail: 3 tests (success, not found, access control)
- Transactions: 6 tests (pagination, filtering, sorting, date range)
- Delete: 4 tests (success, not found, access control, cascading)
- **Total**: 23 integration tests, all passing
- **Overall**: 253 tests passing (230 pre-existing + 23 Phase 9)

---

### Phase 10: Card & Transaction Endpoints ✅ **COMPLETED** (January 26, 2025)

**Goal**: Expose card management and transaction query endpoints.

**Deliverables**:
- [x] `app/services/card.py` — Card management logic (73 lines, 4 methods)
- [x] `app/schemas/card.py` — Card response schemas (49 lines, 3 schemas)
- [x] `app/api/v1/cards.py` — Card endpoints (264 lines, 3 endpoints)
- [x] `app/api/v1/transactions.py` — Transaction endpoints (257 lines, 2 endpoints)
- [x] `tests/integration/test_cards_api.py` — 11 integration tests (365 lines)
- [x] `tests/integration/test_transactions_api.py` — 13 integration tests (471 lines)

**Card Endpoints Implemented**:
| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/v1/cards` | List all user's cards with total count |
| GET | `/api/v1/cards/{id}` | Get card details with statistics (statements count, total reward points, latest statement) |
| GET | `/api/v1/cards/{id}/statements` | Get card's statements with pagination |

**Transaction Endpoints Implemented**:
| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/v1/transactions` | List transactions with 8 filters, sorting, and pagination |
| GET | `/api/v1/transactions/summary` | Spending summary aggregated by category (only debits) |

**Transaction Filters**:
- `start_date`, `end_date` — Date range filtering
- `card_id` — Filter by specific card
- `category` — Filter by merchant category
- `min_amount`, `max_amount` — Amount range filtering
- `search` — Search merchant names (case-insensitive)
- `is_credit` — Filter by credit/debit type
- `sort_by` — Sort by date or amount (txn_date/-txn_date, amount/-amount)
- `page`, `limit` — Pagination (1-100 items per page)

**Card Detail Statistics**:
```json
{
  "id": "uuid",
  "last_four": "1234",
  "bank_code": "HDFC",
  "statements_count": 12,
  "total_reward_points": 15000,
  "latest_statement_date": "2025-01-15T..."
}
```

**Transaction Summary Response**:
```json
[
  {
    "category": "SHOPPING",
    "amount": 45000,
    "count": 23,
    "reward_points": 450
  },
  {
    "category": "FOOD",
    "amount": 12000,
    "count": 45,
    "reward_points": 120
  }
]
```

**Key Features Implemented**:
- **Card Statistics**: Aggregates statements_count, total_reward_points, latest_statement_date via SQL JOIN
- **Cross-Statement Queries**: Transaction list endpoint queries across all statements (joins Statement table when filtering by card_id)
- **Advanced Filtering**: 8 different filters with support for combinations
- **Sorting Options**: By transaction date or amount, ascending or descending
- **Pagination**: Consistent with Phase 9 (page/limit with PaginationMeta)
- **Security**: All endpoints user-scoped with ownership validation (403/404 errors)
- **Error Handling**: Returns API_003 (not found) and API_004 (access denied)

**Test Coverage**:
- **Card Tests**: 11 tests covering:
  - List: empty state, multiple cards, user isolation
  - Detail: success with statistics, not found, wrong user
  - Statements: success, pagination, access control
- **Transaction Tests**: 13 tests covering:
  - List: default, pagination, all 8 filters individually, combined filters, sorting
  - Summary: default aggregation, date filtering, empty state
- **Total**: 24 new integration tests, all passing
- **Overall**: 275 tests passing (253 previous + 11 card + 13 transaction - 2 overlapping fixtures)

**Completion Criteria**:
- [x] Cards auto-created when statement uploaded (implemented in Phase 9)
- [x] Transactions queryable with all filters (8 filters implemented)
- [x] Summary aggregates spending by category (GROUP BY with SUM, COUNT)
- [x] Pagination works correctly (page/limit with total_pages calculation)
- [x] All queries scoped to authenticated user (user_id filter on all queries)
- [x] Card detail includes aggregated statistics (statements_count, total_reward_points, latest_statement_date)
- [x] Cross-statement transaction queries work (joins Statement table)
- [x] Sorting by date and amount (ascending/descending)
- [x] Merchant search functionality (ILIKE query)
- [x] Credit/debit filtering (is_credit boolean)
- [x] Integration tests cover success + error cases (403/404)
- [x] User isolation verified (cannot access other users' data)

---

### Phase 11: Error Handling & Logging ✅ **COMPLETED** (January 26, 2026)

**Goal**: Implement consistent error responses and structured logging.

**Deliverables**:
- [x] `app/core/exceptions.py` — Enhanced with http_status parameter (108 lines)
- [x] `app/core/errors.py` — Converted to dict-based ERROR_CATALOG (195 lines)
- [x] `app/api/middleware/error_handler.py` — Global exception handlers (200 lines)
- [x] `app/api/middleware/logging.py` — Request logging with PII filtering (177 lines)
- [x] `app/main.py` — Registered middlewares and exception handlers (52 lines)
- [x] Updated all endpoints to use consistent error format (cards, statements)
- [x] `tests/unit/test_error_handling.py` — 21 comprehensive tests (368 lines)

**Error Response Format** (Standardized across all endpoints):
```json
{
  "error_code": "PARSE_001",
  "message": "Unsupported bank format detected",
  "user_message": "We couldn't recognize this statement format.",
  "suggestion": "Please upload a statement from HDFC, ICICI, SBI, Amex, Citi, or Chase.",
  "retry_allowed": false
}
```

**Exception Handlers Implemented**:
| Handler | Exception Type | Status Code | Description |
|---------|---------------|-------------|-------------|
| handle_statement_processing_error | StatementProcessingError | Variable (exc.http_status) | Maps to error catalog |
| handle_validation_error | RequestValidationError | 400 | Pydantic validation errors |
| handle_integrity_error | IntegrityError | 409/500 | Database constraint violations |
| handle_generic_error | Exception | 500 | Unexpected errors (safe, no internal details exposed) |

**Logging Features**:
- **Request ID**: Unique UUID for each request, added to response headers (X-Request-ID)
- **User Context**: Logs authenticated user ID (not email/name)
- **PII Filtering**: Regex patterns filter credit cards, emails, phone numbers, Aadhaar, PAN
- **Duration Tracking**: Logs request processing time in milliseconds
- **Structured Format**: JSON logging for easy parsing by log aggregation tools
- **Log Levels**: ERROR for failures, WARNING for validation errors, INFO for requests

**PII Filtering Patterns**:
- Credit card numbers (13-19 digits with spaces/dashes) → `[CARD]`
- Email addresses → `[EMAIL]`
- Aadhaar numbers (12 digits) → `[AADHAAR]`
- PAN cards (5 letters + 4 digits + 1 letter) → `[PAN]`
- Phone numbers (international format) → `[PHONE]`
- Names (after keywords: name/customer/holder/owner) → `[NAME]`

**Middleware Registration Order** (in main.py):
1. RequestLoggingMiddleware (first - wraps all requests)
2. Exception handlers (specific → generic):
   - StatementProcessingError
   - RequestValidationError
   - IntegrityError
   - Exception (catch-all)

**Test Coverage**:
- **Exception Handling**: 7 tests covering all handler types
- **PII Filtering**: 9 tests covering all pattern types
- **Error Response Format**: 3 tests verifying structure
- **Logging Behavior**: 2 tests verifying logging levels
- **Total**: 21 new tests, all passing
- **Overall**: 296 tests passing (275 previous + 21 Phase 11)

**Key Implementation Highlights**:
- **Zero Internal Exposure**: 5xx errors log full details but return generic messages
- **Actionable 4xx Errors**: All client errors include helpful suggestions
- **Request Tracing**: Request ID links logs to specific requests across services
- **PII Safety**: Regex-based filtering prevents sensitive data in logs
- **Consistent Structure**: All errors return same 5-field format
- **Error Catalog Integration**: All handlers reference central error catalog
- **Backward Compatible**: Existing tests updated to use new error format

**Completion Criteria**:
- [x] All exceptions return consistent JSON format (5 fields: error_code, message, user_message, suggestion, retry_allowed)
- [x] 4xx errors include actionable suggestions (defined in error catalog)
- [x] 5xx errors logged with stack trace (not exposed to user)
- [x] Request ID traceable across logs (UUID generated per request)
- [x] PII never appears in logs (6 regex patterns filter sensitive data)
- [x] Structured JSON logging format (JSONLogFormatter class)
- [x] User context logged when authenticated (user_id only, not email/name)
- [x] All endpoints use consistent error format (updated cards & statements APIs)
- [x] Middleware properly registered (RequestLoggingMiddleware + 4 exception handlers)
- [x] Comprehensive test coverage (21 tests covering all features)

**Before vs After Phase 11**:

| Aspect | Before | After |
|--------|--------|-------|
| Error Format | Inconsistent (some HTTPException, some custom) | Uniform 5-field JSON structure |
| Request Tracing | None | UUID per request in headers + logs |
| PII in Logs | At risk | Filtered by regex patterns |
| Error Messages | Technical only | Technical + user-friendly + suggestions |
| Logging | Basic | Structured JSON with context |
| 5xx Handling | May expose internals | Generic message, full stack trace in logs only |
| Test Coverage | 275 tests | 296 tests (+21 for error handling) |

---

### Phase 11B: Transaction Categorization System ✅ **COMPLETED** (January 27, 2026)

**Goal**: Implement rule-based transaction categorization with user override mechanism for accurate spending insights.

**Deliverables**:
- [x] `app/services/categorization.py` — Rule-based categorization engine (180 lines)
- [x] `app/services/merchant.py` — Merchant normalization utilities (85 lines)
- [x] `app/models/merchant_category_override.py` — Override ORM model (42 lines)
- [x] `app/schemas/transaction.py` — Enhanced with override endpoints schemas (145 lines)
- [x] `app/api/v1/transactions.py` — Override management endpoints (updated, 380 lines)
- [x] `app/services/statement.py` — Integrated categorization during ingestion (updated)
- [x] `alembic/versions/add_merchant_key_and_overrides.py` — Schema migration (new tables/columns)
- [x] `tests/unit/test_categorization.py` — 20 comprehensive unit tests (480 lines)
- [x] `tests/integration/test_transaction_overrides.py` — 37 integration tests (780 lines)

**Category Taxonomy** (12 standardized categories):
```python
CATEGORIES = {
    "DINING", "GROCERIES", "SHOPPING", "ENTERTAINMENT",
    "TRAVEL", "FUEL", "UTILITIES", "HEALTHCARE",
    "INSURANCE", "EDUCATION", "EMI", "OTHER"
}
```

**Merchant Normalization**:
```python
def normalize_merchant(raw: str) -> str:
    """Normalize merchant name for consistent matching.
    
    Examples:
        "Amazon.in Shopping" → "amazon"
        "ZOMATO FOOD ORDER" → "zomato"
        "Uber Trip 12345" → "uber"
    """
    # Remove common noise words
    noise_words = ["pvt", "ltd", "inc", "llc", "the", "india", "payment"]
    # Lowercase, strip, remove numbers/special chars
    # Keep only alphanumeric
```

**Rule-Based Categorization** (90+ merchant patterns):
| Category | Example Keywords |
|----------|-----------------|
| DINING | restaurant, cafe, food, zomato, swiggy, pizza, dominos |
| GROCERIES | bigbasket, grofers, dmart, supermarket, grocery, fresh |
| SHOPPING | amazon, flipkart, myntra, mall, retail, store |
| ENTERTAINMENT | netflix, prime, spotify, hotstar, cinema, movie, pvr |
| TRAVEL | uber, ola, irctc, flight, makemytrip, goibibo, airbnb |
| FUEL | petrol, diesel, fuel, hp, indian oil, bharat petroleum |
| UTILITIES | electricity, water, gas, broadband, wifi, internet |

**Categorization Logic** (3-tier precedence):
```
1. User Override (highest priority)
   ↓ (if not set)
2. Parser Category (from PDF if available)
   ↓ (if not provided)
3. Rule-Based Matching (keyword patterns)
   ↓ (if no match)
4. Fallback: "OTHER"
```

**Database Schema Changes**:

1. **transactions table** - Added columns:
   - `merchant_key VARCHAR(255)` - Normalized merchant for matching
   - Index on `merchant_key` for fast lookups

2. **merchant_category_overrides table** (NEW):
```sql
CREATE TABLE merchant_category_overrides (
    id UUID PRIMARY KEY,
    user_id UUID REFERENCES users(id),
    merchant_key VARCHAR(255) NOT NULL,
    category VARCHAR(50) NOT NULL,
    created_at TIMESTAMP,
    updated_at TIMESTAMP,
    UNIQUE (user_id, merchant_key)
);
```

**API Endpoints**:

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/v1/transactions/{id}/set-category` | Set override for merchant (debit only) |
| GET | `/api/v1/transactions/overrides` | List user's overrides (paginated, searchable) |
| DELETE | `/api/v1/transactions/overrides/{id}` | Delete override and optionally recompute |

**Set Category Override Flow**:
```
1. Validate transaction exists and is debit (credits cannot be categorized)
2. Normalize merchant name → merchant_key
3. Validate category against taxonomy
4. Upsert override: INSERT ... ON CONFLICT UPDATE
5. Backfill: UPDATE all user's transactions matching merchant_key
6. Return updated count + new category
```

**Features Implemented**:

1. **Debit-Only Categorization**: Credits/refunds excluded from categorization
2. **Override Precedence**: User override > parser > rules > "OTHER"
3. **Automatic Backfill**: Setting override updates all existing matching transactions
4. **Recompute on Delete**: Optional recomputation using rules when override deleted
5. **Search & Filter**: List overrides with merchant_key search and pagination
6. **Spend Summary Impact**: Category overrides immediately reflected in aggregations

**Test Coverage**: 57 tests (all passing)
- **Unit Tests (20)**:
  - 8 normalization tests (noise words, special chars, numbers, whitespace)
  - 12 rule matching tests (all 12 categories + "OTHER" fallback)
- **Integration Tests (37)**:
  - 15 set-category tests (success, validation, backfill, debit-only)
  - 12 list-overrides tests (pagination, search, empty state)
  - 10 delete-override tests (success, recompute, not found, access control)

**Ingestion Integration**:
```python
# In StatementService.process_upload()
for txn in parsed.transactions:
    # 1. Normalize merchant
    txn.merchant_key = normalize_merchant(txn.merchant)
    
    # 2. Apply categorization (3-tier precedence)
    category = await self._determine_category(
        user_id=user_id,
        merchant_key=txn.merchant_key,
        parser_category=txn.category  # from PDF if available
    )
    
    # 3. Store in database
    transaction = Transaction(
        merchant=txn.merchant,
        merchant_key=txn.merchant_key,
        category=category,
        ...
    )
```

**Example User Workflow**:
```
1. User uploads statement → transactions categorized by rules
2. User views spending summary → sees "Amazon" in SHOPPING
3. User corrects: "Amazon is my groceries source"
4. POST /transactions/123/set-category { "category": "GROCERIES" }
5. System backfills: all Amazon transactions → GROCERIES
6. Spend summary immediately reflects change
7. Future statements: Amazon auto-categorized as GROCERIES
```

**Completion Criteria**:
- [x] Merchant normalization removes noise (pvt, ltd, numbers, special chars)
- [x] Rule-based engine covers 12 categories with 90+ keywords
- [x] User overrides stored in dedicated table
- [x] Override precedence: user > parser > rules > OTHER
- [x] Backfill updates all matching transactions on override set
- [x] Delete override optionally recomputes via rules
- [x] API endpoints handle validation, pagination, search
- [x] Debit-only enforcement (credits excluded)
- [x] Category taxonomy validated against enum
- [x] Integration with statement ingestion pipeline
- [x] Spend summary reflects override changes immediately
- [x] Unit tests cover normalization and rule matching
- [x] Integration tests cover full API workflows
- [x] User isolation enforced (cannot override other users' merchants)

**Impact on Existing Phases**:
- **Phase 9 (Statements API)**: Ingestion now populates merchant_key and applies categorization
- **Phase 10 (Transactions API)**: Summary endpoint respects user overrides
- **Phase 11 (Error Handling)**: Override endpoints use consistent error format

**Migration Notes**:
- Existing transactions get merchant_key populated on next statement upload
- Category backfill applies to all past transactions when override set
- No data loss: original merchant name preserved in `merchant` column

---

### Phase 12: Docker & Deployment 🚫 **DEFERRED**

**Status**: Out of scope for current development cycle. Will be planned after core development is complete.

**Goal**: Containerize application for deployment.

**Planned Deliverables** (when implemented):
- [ ] `Dockerfile` — Multi-stage build
- [ ] `docker-compose.yml` — App + PostgreSQL + Redis (optional)
- [ ] `.env.example` — All configuration variables
- [ ] `README.md` — Setup and run instructions
- [ ] CI/CD pipeline config (GitHub Actions)

**System Dependencies Required**:

⚠️ **CRITICAL**: The application requires the following system libraries for PDF processing (used by `unstructured.io` library):

### 1. Poppler (PDF Rendering)

**Development (Local)**:
- **macOS**: `brew install poppler`
- **Ubuntu/Debian**: `apt-get install -y poppler-utils`
- **CentOS/RHEL**: `yum install -y poppler-utils`

### 2. Tesseract OCR (Text Extraction from Images)

**Required for**: Password-protected PDFs or PDFs with text extraction restrictions

**Development (Local)**:
- **macOS**: `brew install tesseract`
- **Ubuntu/Debian**: `apt-get install -y tesseract-ocr`
- **CentOS/RHEL**: `yum install -y tesseract`

**Production Deployment**:
- **Docker**: Add to Dockerfile before Python dependencies
  ```dockerfile
  RUN apt-get update && apt-get install -y \
      poppler-utils \
      tesseract-ocr \
      && rm -rf /var/lib/apt/lists/*
  ```
- **AWS Elastic Beanstalk**: Add to `.ebextensions/packages.config`
  ```yaml
  packages:
    yum:
      poppler-utils: []
      tesseract: []
  ```
- **Azure App Service**: Use custom startup script or Oryx build
- **Heroku**: Add `heroku-buildpack-apt` with `Aptfile` containing:
  ```
  poppler-utils
  tesseract-ocr
  ```

**Dockerfile Approach** (planned):
```dockerfile
# Stage 1: Dependencies
FROM python:3.11-slim as builder

# Install system dependencies (CRITICAL: Required for PDF processing)
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    poppler-utils \
    tesseract-ocr \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Stage 2: Runtime
FROM python:3.11-slim

# Install runtime system dependencies
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    poppler-utils \
    tesseract-ocr \
    && rm -rf /var/lib/apt/lists/*

# Copy only necessary files
# Install spaCy model for Presidio
RUN python -m spacy download en_core_web_sm
```

**Planned Completion Criteria**:
- [ ] `docker-compose up` starts full stack
- [ ] Poppler and Tesseract installed and accessible in container
- [ ] App container size < 1.5GB
- [ ] Health checks pass
- [ ] All tests pass in container
- [ ] README has clear setup instructions with system dependencies

**Note**: This phase will be planned and implemented after all core application features are complete and tested.

---

## 14. API Summary

### Authentication
| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| POST | `/api/v1/auth/register` | No | Create account |
| POST | `/api/v1/auth/login` | No | Get tokens |
| POST | `/api/v1/auth/refresh` | No | Refresh token |
| GET | `/api/v1/auth/me` | Yes | Current user |

### Statements
| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| POST | `/api/v1/statements/upload` | Yes | Upload PDF |
| GET | `/api/v1/statements` | Yes | List statements |
| GET | `/api/v1/statements/{id}` | Yes | Get statement |
| DELETE | `/api/v1/statements/{id}` | Yes | Delete statement |

### Cards
| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| GET | `/api/v1/cards` | Yes | List cards |
| GET | `/api/v1/cards/{id}` | Yes | Get card |
| GET | `/api/v1/cards/{id}/statements` | Yes | Card's statements |

### Transactions
| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| GET | `/api/v1/transactions` | Yes | List with filters |
| GET | `/api/v1/transactions/summary` | Yes | Category summary |

### Utility
| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| GET | `/health` | No | Basic health |
| GET | `/health/ready` | No | Readiness check |

---

## 15. Configuration Variables

```bash
# Application
APP_ENV=development
DEBUG=true
LOG_LEVEL=INFO

# Server
HOST=0.0.0.0
PORT=8000

# Database
DATABASE_URL=postgresql+asyncpg://user:pass@localhost:5432/cc_rewards

# JWT
JWT_SECRET=change-this-in-production
JWT_ACCESS_EXPIRE_MINUTES=30
JWT_REFRESH_EXPIRE_DAYS=7

# Parsing
PDF_MAX_SIZE_MB=10
PARSE_TIMEOUT_SECONDS=60

# PII Masking
PRESIDIO_CONFIDENCE=0.7
```

---

## 16. Testing Strategy

### Unit Tests
- Mock external dependencies (database, Unstructured, Presidio)
- Test business logic in isolation
- Cover edge cases and error paths
- Target: >90% coverage for `services/`, `parsers/`, `masking/`

### Integration Tests
- Use test database (SQLite or PostgreSQL container)
- Test full request → response flow
- Verify database state after operations
- Target: All API endpoints covered

### Test Fixtures
- Synthetic PDFs for CI/CD (reproducible, no real PII)
- Anonymized real PDFs for accuracy validation (local only, gitignored)
- Pre-extracted JSON for parser unit tests

### Running Tests
```bash
# All tests
pytest tests/ -v

# Unit only
pytest tests/unit/ -v

# Integration only
pytest tests/integration/ -v

# With coverage
pytest tests/ --cov=app --cov-report=html
```

---

## 17. Implementation Guidelines

### Code Style
- **Naming**: `snake_case` for functions/variables, `PascalCase` for classes
- **Imports**: Group by stdlib → third-party → local, alphabetized
- **Type hints**: Required for all function signatures
- **Docstrings**: Required for public classes and complex functions
- **Line length**: 100 characters max

### Conciseness Rules
- No unnecessary abstractions for single-use logic
- Prefer composition over inheritance
- No comments that restate the code
- Remove dead code immediately
- One responsibility per function

### Example: Good vs Bad

**Bad** (over-engineered):
```python
class TransactionAmountProcessor:
    def __init__(self, currency_handler, rounding_strategy):
        self.currency_handler = currency_handler
        self.rounding_strategy = rounding_strategy
    
    def process(self, raw_amount: str) -> int:
        cleaned = self.currency_handler.clean(raw_amount)
        parsed = self.currency_handler.parse(cleaned)
        return self.rounding_strategy.round(parsed)
```

**Good** (concise):
```python
def parse_amount(raw: str) -> int:
    """Parse '₹1,234.56' to 123456 (paise)."""
    cleaned = re.sub(r'[₹$,\s]', '', raw)
    return int(Decimal(cleaned) * 100)
```

### Logical Naming Examples

| Component | Good Name | Bad Name |
|-----------|-----------|----------|
| Function | `mask_card_number` | `process_cc` |
| Variable | `statement_month` | `sm` or `date1` |
| Class | `StatementParser` | `Parser1` |
| Endpoint | `/statements/upload` | `/stmt/ul` |

---

## 18. Phase Completion Checklist Template

Use this for each phase:

```markdown
## Phase N: [Name]

### Deliverables
- [ ] File 1
- [ ] File 2
- [ ] Tests

### Completion Criteria
- [ ] Criterion 1
- [ ] Criterion 2
- [ ] All tests pass
- [ ] No linting errors

### Sign-off
- Date completed: ____
- Tests passing: Yes/No
- Coverage: ____%
```
