# CC Rewards Dashboard

A secure, AI-powered credit card statement processing and rewards analysis platform. This system intelligently parses credit card statements from multiple banks, extracts transaction and reward data, and provides structured APIs for financial insights.

## ✨ Key Features

- 🏦 **Multi-Bank Support**: Parse statements from HDFC, American Express, and State Bank of India with extensible architecture
- 💳 **Dual Reward Tracking**: Track both monthly earned points and total reward balance
- 🔒 **Security First**: JWT authentication, PII masking, soft deletes, encrypted connections
- 🚀 **Quick Start Scripts**: One-command setup with `./start.sh` to launch database + API
- 📊 **Rich API**: RESTful endpoints with auto-generated Swagger UI documentation
- 🧪 **Test Suite**: Comprehensive unit and integration tests with separate test database
- 📦 **Postman Collection**: Pre-configured API requests for rapid testing

## 🏗️ Architecture Overview

### System Components

**API Layer (FastAPI)**
- RESTful API endpoints for statement upload, transaction retrieval, and rewards tracking
- JWT-based authentication with user management
- Comprehensive error handling with custom error codes
- Health check endpoints with database connectivity validation
- Auto-generated API documentation (Swagger UI, ReDoc)

**Parser Service**
- Multi-bank PDF statement parser supporting HDFC, Amex, SBI, and extensible to other banks
- Intelligent text extraction using `unstructured` library with OCR fallback
- Bank-specific refinement layers for accurate data extraction
- PII masking for secure data handling
- Dual reward points tracking (monthly earned vs. total balance)

**Data Layer**
- PostgreSQL database with SQLAlchemy ORM
- UUID-based entities with soft delete support
- Comprehensive schema:
  - **Users**: Authentication and profile management
  - **Cards**: Credit card metadata (bank, network, product, last 4 digits)
  - **Statements**: Monthly statement records with reward points tracking
  - **Transactions**: Detailed transaction history with categorization
- Alembic-managed migrations for schema evolution
- Separate development and test databases with in-memory tmpfs for fast testing

**Security & Compliance**
- Secure password hashing with bcrypt
- PII masking during statement processing
- Environment-based configuration management
- Encrypted database connections
- Audit trails with timestamp tracking

### Data Flow

```
PDF Statement Upload
        ↓
PDF Parsing (unstructured.io)
        ↓
Bank Detection (pattern matching)
        ↓
Bank-Specific Refinement Parser
        ↓
Data Extraction & Validation
        ↓
PII Masking Layer
        ↓
Structured Data Storage
        ↓
API Response (JSON)
```

### Supported Banks

- **HDFC Bank**: Transaction parsing, reward points, statement period detection
- **American Express**: Transaction categorization, spend analysis
- **State Bank of India (SBI)**: Reward points breakdown (earned/balance), transaction extraction
- **Extensible**: Template-based architecture for adding new banks

## 🚀 Quick Start

### Prerequisites

- **Python 3.13+** (3.11+ minimum)
- **Docker & Docker Compose** (for PostgreSQL databases)
- **Git** (for version control)

### Installation & Setup

1. **Clone the repository**
```bash
git clone <repository-url>
cd CCRewardsDashboard
```

2. **Create Python virtual environment**
```bash
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. **Install dependencies**
```bash
pip install -r requirements.txt
```

4. **Configure environment variables**
```bash
cp .env.example .env
```

Edit `.env` and set required values:
```env
# Generate a secure JWT secret
JWT_SECRET=<run: openssl rand -hex 32>

# Database URLs (default values work with Docker Compose)
DATABASE_URL=postgresql+asyncpg://cc_user:cc_password@localhost:5432/cc_rewards
TEST_DATABASE_URL=postgresql+asyncpg://cc_user:cc_password@localhost:5433/cc_rewards_test
```

5. **Start PostgreSQL databases**
```bash
# Start both development and test databases
docker compose up -d postgres postgres_test

# Verify containers are running
docker ps | grep cc_rewards
```

6. **Apply database migrations**
```bash
alembic upgrade head
```

7. **Start the API server**
```bash
cd src
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

The server will be available at:
- **API**: http://localhost:8000
- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

### Using Postman Collection

A complete Postman collection is included for easy API testing:

```bash
# Import collection and environment into Postman
postman/CCRewardsDashboard.postman_collection.json
postman/CCRewardsDashboard.local.postman_environment.json
```

The collection includes pre-configured requests for:
- User registration and authentication
- Statement upload with file attachment
- Statement listing and details
- Card management
- Transaction queries

### First API Request

Create a user and upload a statement:

```bash
# 1. Register a user
curl -X POST http://localhost:8000/api/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{
    "email": "user@example.com",
    "password": "securepassword",
    "full_name": "John Doe"
  }'

# 2. Login to get JWT token
curl -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{
    "email": "user@example.com",
    "password": "securepassword"
  }'

# 3. Upload statement (use token from step 2)
# Visit http://localhost:8000/docs for interactive upload via Swagger UI
```

## 📁 Project Structure

```
CCRewardsDashboard/
├── src/
│   └── app/
│       ├── api/
│       │   └── v1/
│       │       ├── auth.py          # Authentication endpoints (register, login)
│       │       ├── statements.py    # Statement upload, list, detail, delete
│       │       └── cards.py         # Card management endpoints
│       ├── parsers/
│       │   ├── detector.py         # Bank detection logic
│       │   ├── extractor.py        # PDF text/table extraction
│       │   ├── factory.py          # Parser factory & orchestration
│       │   ├── generic.py          # Generic PDF parser (fallback)
│       │   └── refinements/
│       │       ├── hdfc.py         # HDFC Bank-specific parser
│       │       ├── amex.py         # American Express parser
│       │       └── sbi.py          # SBI-specific parser with dual rewards
│       ├── services/
│       │   ├── auth.py             # Authentication business logic
│       │   └── statement.py        # Statement processing service
│       ├── models/
│       │   ├── user.py             # User ORM model
│       │   ├── card.py             # Card ORM model
│       │   ├── statement.py        # Statement ORM model
│       │   └── transaction.py      # Transaction ORM model
│       ├── schemas/
│       │   ├── auth.py             # Auth request/response schemas
│       │   ├── statement.py        # Statement schemas
│       │   ├── card.py             # Card schemas
│       │   └── internal.py         # Internal data structures
│       ├── db/
│       │   └── session.py          # Database session management
│       ├── config.py               # Configuration (env vars, settings)
│       ├── exceptions.py           # Custom exception classes
│       └── main.py                 # FastAPI application entry point
├── tests/
│   ├── unit/                       # Unit tests (parsers, services)
│   │   ├── test_parsers/          # Parser unit tests
│   │   │   ├── test_detector.py   # Bank detection tests
│   │   │   ├── test_extractor.py  # PDF extraction tests
│   │   │   ├── test_factory.py    # Parser factory tests
│   │   │   └── test_refinements.py # Bank-specific parser tests
│   │   └── test_services/         # Service layer tests
│   ├── integration/                # Integration tests (API endpoints)
│   │   └── test_api/              # API endpoint tests
│   └── conftest.py                 # Pytest fixtures and test configuration
├── alembic/
│   ├── versions/                   # Database migration files
│   └── env.py                      # Alembic configuration
├── postman/
│   ├── CCRewardsDashboard.postman_collection.json  # Postman API collection
│   └── CCRewardsDashboard.local.postman_environment.json  # Local environment
├── scripts/                        # Utility scripts
├── docker-compose.yml              # PostgreSQL database containers
├── requirements.txt                # Python dependencies
├── start.sh                        # Start all services (database + API)
├── stop.sh                         # Stop all services
├── .env.example                    # Environment variable template
├── .gitignore                      # Git ignore rules
├── Architecture.md                 # Detailed system architecture
├── processing.md                   # Development progress notes
└── README.md                       # This file
```

## 🗄️ Database Schema

### Users
- `id` (UUID, PK)
- `email` (unique, indexed)
- `password_hash`
- `full_name`
- `is_active`
- Timestamps: `created_at`, `updated_at`, `deleted_at`

### Cards
- `id` (UUID, PK)
- `user_id` (FK → users)
- `last_four` (last 4 digits)
- `bank_code` (e.g., 'hdfc', 'amex', 'sbi')
- `network` (e.g., 'visa', 'mastercard', 'amex')
- `product_name`
- `is_active`
- Timestamps: `created_at`, `updated_at`, `deleted_at`

### Statements
- `id` (UUID, PK)
- `user_id` (FK → users)
- `card_id` (FK → cards)
- `statement_month` (first day of month, unique per card)
- `closing_balance` (in cents)
- `reward_points` (total balance)
- `reward_points_earned` (monthly earned)
- Timestamps: `created_at`, `updated_at`, `deleted_at`

### Transactions
- `id` (UUID, PK)
- `statement_id` (FK → statements)
- `user_id` (FK → users)
- `txn_date`
- `merchant`
- `category`
- `amount` (in cents)
- `is_credit` (boolean)
- `reward_points`
- Timestamps: `created_at`, `updated_at`, `deleted_at`

## 🧪 Testing

### Run All Tests

```bash
# Run entire test suite
pytest tests/ -v

# Run with coverage report
pytest tests/ --cov=app --cov-report=html

# Run specific test modules
pytest tests/unit/test_parsers/ -v
pytest tests/integration/test_api/test_statements.py -v
```

### Test Database

Tests use a separate PostgreSQL instance (`cc_rewards_test` on port 5433) with `tmpfs` for in-memory performance. The test database is automatically cleaned between test runs.

```bash
# Start test database only
docker compose up -d postgres_test

# Check test database status
docker logs cc_rewards_test_db
```

## 🔧 Development Workflow

### Convenience Scripts

The project includes shell scripts for streamlined development:

**`./start.sh`** - Start all services
- Activates virtual environment automatically
- Starts PostgreSQL with Docker Compose
- Waits for database to be ready
- Applies pending migrations
- Starts FastAPI server with hot reload on port 8000

**`./stop.sh`** - Stop all services
- Stops FastAPI server gracefully
- Stops PostgreSQL containers

**Quick Commands**
```bash
# Full restart (after code changes or config updates)
./stop.sh && ./start.sh

# Check service status
docker ps                    # View running containers
ps aux | grep uvicorn       # Check API server process
```

### Database Management

**Start/Stop Databases**
```bash
# Start development database only
docker compose up -d postgres

# Start both databases
docker compose up -d

# Stop databases
docker compose stop

# View logs
docker compose logs -f postgres
```

**Create New Migration**
```bash
alembic revision --autogenerate -m "description of changes"
```

**Apply Migrations**
```bash
# Apply all pending migrations
alembic upgrade head

The parser architecture uses a factory pattern with bank-specific refinements:

1. **Create new refinement parser** in `src/app/parsers/refinements/<bank>.py`
```python
from app.parsers.generic import GenericParser

class NewBankParser(GenericParser):
    """Parser refinement for <Bank Name>.
    
    Bank-specific behaviors:
    - Card number format: <describe format>
    - Date format: <describe format>
    - Reward points: <describe if special handling needed>
    """
    
    def _extract_card_number(self, elements, full_text):
        """Override if bank has unique card number format."""
        # Bank-specific regex patterns
        patterns = [r"pattern1", r"pattern2"]
        # ... implementation
    
    def _extract_statement_period(self, elements, full_text):
        """Override if bank has unique date format."""
        # ... implementation
    
    def _extract_rewards(self, elements, full_text):
        """Override if bank shows reward points differently."""
        # ... implementation
```

2. **Register parser** in `src/app/parsers/factory.py`
```python
from app.parsers.refinements import NewBankParser

# In ParserFactory.__init__():
self.register_refinement("newbank", NewBankParser)
```

3. **Add bank detection** patterns in `src/app/parsers/detector.py`
```python
self.bank_patterns = {
    "newbank": [
        r"New Bank Name",
        r"NEWBANK CREDIT CARD",
    ],
    # ... existing patterns
}
```

4. **Add test cases** in `tests/unit/test_parsers/test_refinements.py`
```python
def test_newbank_parser():
    parser = NewBankParser()
    # Test with sample PDF or text
    assert parser.parse(elements)
```

5. **Test with real statement** via API:
```bash
# Upload test statement
curl -X POST http://localhost:8000/api/v1/statements/upload \
  -H "Authorization: Bearer <token>" \
  -F "file=@newbank_statement.pdf"
```

The `GenericParser` provides fallback implementations for all methods, so you only need to override methods where the bank has unique formats.
1. Create new refinement parser in `src/app/parsers/refinements/<bank>.py`
2. Inherit from `CreditCardParser`
3. Implement bank-specific extraction methods
4. Register bank in parser factory
5. Add test cases in `tests/unit/test_parsers/test_refinements.py`

Example:
```python
class NewBankParser(CreditCardParser):
    def _extract_card_number(self, elements, full_text):
        # Bank-specific logic
        pass
    
    def _extract_statement_period(self, elements, full_text):
        # Bank-specific logic
        pass
```

## 🔐 Security Features

- **Authentication**: JWT-based token authentication with configurable expiry
- **Password Security**: Bcrypt hashing with salt
- **PII Masking**: Automatic masking of sensitive data during parsing
- **Soft Deletes**: Data retention with logical deletion (deleted_at timestamp)
- **Environment Isolation**: Separate development and test databases
- **Input Validation**: Pydantic schema validation on all API inputs

## 📊 API Endpoints

### Authentication
- `POST /api/v1/auth/register` - Create new user account
- `POST /api/v1/auth/login` - Login and receive JWT token

### Statements
- `POST /api/v1/statements/upload` - Upload credit card statement (PDF)
- `GET /api/v1/statements` - List all statements for authenticated user
- `GET /api/v1/statements/{id}` - Get statement details with transactions
- `GET /api/v1/statements/summary` - Get aggregated summary across all cards
- `DELETE /api/v1/statements/{id}` - Soft delete a statement

### Cards
- `GET /api/v1/cards` - List all cards for authenticated user

### Health Checks
- `GET /health` - Basic health check
- `GET /health/ready` - Readiness check with database connectivity (returns 503 if DB unavailable)

## 🛠️ Technology Stack

| Componserver logs for parser output (`[PARSER]`, `[HDFC PARSER]`, `[SBI PARSER]`, etc.)
- Verify bank is supported (HDFC, Amex, SBI currently implemented)
- For unsupported banks, the system falls back to `GenericParser` which may have lower accuracy

**Server won't start**
```bash
# Check if port 8000 is already in use
lsof -i :8000

# Kill existing process
kill -9 <PID>

# Or use the stop script
./stop.sh
```
| **API Framework** | FastAPI | High-performance async Python web framework |
| **Database** | PostgreSQL 16 | Relational database with ACID compliance |
| **ORM** | SQLAlchemy 2.0 | Async database operations with type hints |
| **Migrations** | Alembic | Database schema version control |
| **PDF Processing** | unstructured.io | Advanced PDF parsing with layout detection |
| **Authentication** | JWT + bcrypt | Secure token-based auth with password hashing |
| **Validation** | Pydantic V2 | Request/response validation with type safety |
| **Testing** | pytest + pytest-asyncio | Comprehensive test framework |
| **Containerization** | Docker Compose | Database orchestration |

## 📝 Configuration

Key environment variables in `.env`:

| Variable | Description | Default |
|----------|-------------|---------|
| `DATABASE_URL` | PostgreSQL connection string (dev) | `postgresql+asyncpg://...5432/cc_rewards` |
| `TEST_DATABASE_URL` | PostgreSQL connection string (test) | `postgresql+asyncpg://...5433/cc_rewards_test` |
| `JWT_SECRET` | Secret key for JWT token generation | *(required, generate with openssl)* |
| `JWT_ALGORITHM` | JWT signing algorithm | `HS256` |
| `JWT_EXPIRATION_MINUTES` | Token expiry time | `60` |

## 🐛 Troubleshooting

**Database connection errors**
```bash
# Check if containers are running
docker ps | grep postgres

# Restart databases
docker compose restart postgres postgres_test
```

**Migration conflicts**
```bash
# Check current revision
alembic current

# View migration history
alembic history

# Reset to specific revision
alembic downgrade <revision_id>
```

**PDF parsing issues**
- Ensure PDF is not password-protected (or provide password in API request)
- Check server logs for parser output (`[PARSER]`, `[HDFC PARSER]`, `[SBI PARSER]`, etc.)
- Verify bank is supported (HDFC, Amex, SBI currently implemented)
- For unsupported banks, the system falls back to `GenericParser` which may have lower accuracy

**Server won't start**
```bash
# Check if port 8000 is already in use
lsof -i :8000

# Kill existing process
kill -9 <PID>

# Or use the stop script and restart
./stop.sh
./start.sh
```

**Quick restart** (when making code changes)
```bash
./stop.sh && ./start.sh
```

## 📚 Additional Documentation

- **[Architecture.md](Architecture.md)**: Detailed system architecture, design decisions, and future roadmap
- **[processing.md](processing.md)**: Development progress tracking and implementation notes

## 🤝 Contributing

1. Create a feature branch from `main`
2. Implement changes with tests
3. Ensure all tests pass: `pytest tests/ -v`
4. Submit pull request with clear description

## 📄 License

[Add your license here]
