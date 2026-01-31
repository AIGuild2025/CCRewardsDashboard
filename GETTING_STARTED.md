# Getting Started

## 1. Install Dependencies

```bash
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

pip install -r requirements.txt
playwright install  # Install browsers
```

## 2. Configure Environment

```bash
cp .env.example .env
# Edit .env with your settings:
# - DATABASE_URL (optional, defaults to SQLite)
# - OPENAI_API_KEY or ANTHROPIC_API_KEY (for LLM fallback)
# - SLACK_WEBHOOK_URL (for alerts)
```

## 3. Verify Setup

```bash
# Test Playwright
python -c "from fetcher import load_page; print('✓ Playwright ready')"

# Test config loading
python -c "from scheduler import load_config; print('✓ Config loaded:', load_config())"
```

## 4. Run First Scrape

```bash
# Scrape all Chase cards
python scheduler/run_pipeline.py --bank Chase

# Or scrape one card
python scheduler/run_pipeline.py --bank Chase --card sapphire_preferred
```

You should see:
```
2024-01-30 10:15:23 - __main__ - INFO - Scraping Chase/sapphire_preferred from https://...
2024-01-30 10:15:25 - fetcher - INFO - Page loaded successfully in 2000ms
2024-01-30 10:15:26 - extractor - INFO - Rule-based extraction confidence: 0.92
2024-01-30 10:15:26 - __main__ - INFO - ✓ Successfully scraped Chase/sapphire_preferred
```

## 5. Check Database

```bash
# SQLite (default)
sqlite3 credit_card_intel.db "SELECT * FROM cards;"

# Or PostgreSQL
psql credit_card_intel -c "SELECT * FROM cards;"
```

## 6. Run Tests

```bash
pytest tests/ -v
```

---

## Troubleshooting

### Playwright not found
```bash
playwright install
```

### Database connection error
Check `DATABASE_URL` in `.env` or use default SQLite

### LLM not responding
- Add `OPENAI_API_KEY` or `ANTHROPIC_API_KEY`
- Or remove config to use rule-based only

---

## Next: Production Deployment

See [ARCHITECTURE.md](ARCHITECTURE.md#next-steps) for scaling & monitoring setup.
