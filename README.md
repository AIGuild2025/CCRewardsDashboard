# Credit Card Statement Parser API

REST API for parsing credit card statements and extracting categorized transactions with LLM-powered classification.

## Features

- 📄 **PDF Parsing**: Extracts transactions from password-protected credit card statements
- 🤖 **AI Classification**: Categorizes transactions using Groq LLM (llama-3.3-70b-versatile)
- 🔐 **Security**: Encrypted password storage using AES-256
- ✅ **Validation**: Optional dual-model validation for accuracy verification
- 📊 **Category Analytics**: Spending breakdown by category with rewards calculation

## Quick Start

### 1. Install Dependencies

```bash
cd poc_pdfparser
pip install -r requirements.txt
```

### 2. Configure Environment

Create `.env` file:
```env
GROQ_API_KEY=your_groq_api_key_here
GROQ_MODEL=llama-3.3-70b-versatile
LLM_TEMPERATURE=0.1
```

### 3. Set Up PDF Passwords (Optional)

If PDFs are password-protected:
```bash
python -m src.password_manager save
```
Follow prompts to add PDF filename patterns and passwords.

### 4. Start API Server

```bash
python -m uvicorn api:app --host 0.0.0.0 --port 8000
```

Server runs at: `http://localhost:8000`

API Docs: `http://localhost:8000/docs`

## API Endpoints

### Authentication
All endpoints (except `/health`) require Bearer token authentication:
```
Authorization: Bearer cc_user1_token_2026
```

### Available Endpoints

| Method | Endpoint | Description | Speed |
|--------|----------|-------------|-------|
| GET | `/health` | Health check (no auth) | Instant |
| POST | `/api/v1/parse-pdf` | Upload & parse PDF | ~3s |
| POST | `/api/v1/parse-pdf?validate=true` | Parse with validation | ~6s |
| GET | `/api/v1/transactions` | Get full transaction details | Instant |
| GET | `/api/v1/categories` | Get category summary (lightweight) | Instant |
| GET | `/api/v1/categories/{name}` | Get specific category details | Instant |

## Usage Workflow

### Step 1: Parse PDF

**Request:**
```bash
POST /api/v1/parse-pdf
Content-Type: multipart/form-data
Authorization: Bearer cc_user1_token_2026

file: statement.pdf
```

**Response:**
```json
{
  "username": "CCUser1",
  "parsed_at": "2026-01-31T19:00:00",
  "model_info": {
    "primary_model": "llama-3.3-70b-versatile",
    "validation_enabled": false
  },
  "summary": {
    "total_categories": 5,
    "total_transactions": 26,
    "total_spending": 17724.8,
    "total_rewards": 161
  },
  "categories": {
    "Dining": {
      "money_spent": 4795.0,
      "rewards_earned": 42,
      "transaction_count": 12,
      "transactions": [...]
    }
  }
}
```

### Step 2: View Results

**Get Full Details:**
```bash
GET /api/v1/transactions
Authorization: Bearer cc_user1_token_2026
```

**Get Summary Only:**
```bash
GET /api/v1/categories
Authorization: Bearer cc_user1_token_2026
```

**Get Specific Category:**
```bash
GET /api/v1/categories/Dining
Authorization: Bearer cc_user1_token_2026
```

## Postman Collection

Import `CCRewardsDashboard_API.postman_collection.json` for pre-configured requests.

**Collection Variables:**
- `base_url`: http://localhost:8000
- `auth_token`: cc_user1_token_2026

## Transaction Categories

- Groceries
- Dining
- Fuel
- Shopping
- Entertainment
- Travel
- Utilities
- Healthcare
- Education
- Other

## Security

### API Authentication
- **Token**: `cc_user1_token_2026` for user `CCUser1`
- **Type**: Bearer token (static)
- Add more users in `api.py` → `VALID_TOKENS` dict

### PDF Password Storage
- **Encryption**: Fernet AES-256
- **Key File**: `.encryption_key` (NEVER commit)
- **Encrypted Store**: `secrets.yaml.enc` (optional commit)

### Git Security
Never commit:
- `.env` - API keys
- `.encryption_key` - Master encryption key
- `sample_pdfs/*.pdf` - Actual statements
- `output/*.json` - Parsed results

## Project Structure

```
poc_pdfparser/
├── api.py                           # FastAPI server
├── requirements.txt                 # Dependencies
├── .env                            # Configuration (not in git)
├── .encryption_key                 # Master key (not in git)
├── secrets.yaml.enc                # Encrypted passwords
├── CCRewardsDashboard_API.postman_collection.json
├── sample_pdfs/                    # PDF statements
├── output/                         # Generated JSON (auto-created)
└── src/
    ├── config.py                   # Environment config
    ├── models.py                   # Pydantic models
    ├── parser_service.py           # PDF parsing orchestrator
    ├── transaction_extractor.py    # LLM classification
    └── password_manager.py         # Encrypted password vault
```

## Validation Mode

Enable dual-model validation for accuracy checks:

```bash
POST /api/v1/parse-pdf?validate=true
```

**Benefits:**
- Cross-validates classifications with second LLM
- Returns accuracy metrics
- Identifies mismatches

**Trade-offs:**
- 2x API calls (more cost)
- 2x processing time (~6s vs ~3s)

**Recommended Use:**
- Testing phase: Enable validation
- Production: Disable validation (faster, cheaper)

## Troubleshooting

**Server won't start:**
- Check if port 8000 is available
- Verify `.env` file exists with `GROQ_API_KEY`

**PDF parsing fails:**
- Check if PDF password is in `secrets.yaml.enc`
- Verify `.encryption_key` file exists

**Authentication error:**
- Ensure Bearer token is `cc_user1_token_2026`
- Check Authorization header format

**No transactions extracted:**
- PDF format may not be supported
- Check server logs for parsing errors

## Performance

- **PDF Parsing**: ~3 seconds (single model)
- **With Validation**: ~6 seconds (dual model)
- **Cached Retrieval**: <100ms
- **Concurrent Requests**: Supported (FastAPI async)

## Technology Stack

- **PDF Processing**: PDFPlumber 0.10.3
- **LLM**: Groq API (llama-3.3-70b-versatile)
- **API Framework**: FastAPI 0.115.0
- **Server**: Uvicorn ASGI
- **Validation**: Pydantic 2.5.3
- **Encryption**: Cryptography 42.0.0

## Support

For issues or questions, check:
- API docs: http://localhost:8000/docs
- Server logs in terminal
- Postman collection for examples
