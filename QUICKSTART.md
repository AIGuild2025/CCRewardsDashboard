# Quick Start Guide

Get up and running with Phase-1 PDF Parsing in 3 simple steps.

## Step 1: Install Dependencies

```bash
pip install -r requirements.txt
```

If you encounter environment issues, use:
```bash
pip install --user -r requirements.txt
```

## Step 2: Generate PDFs

Generate all 15 dummy credit card statement PDFs:

```bash
python3 generate_all.py
```

Expected output:
```
============================================================
Generating Credit Card Statement PDFs
============================================================

[1/3] Generating AMEX Statements (5 PDFs)...
[2/3] Generating HDFC VISA Statements (5 PDFs)...
[3/3] Generating HDFC MASTERCARD Statements (5 PDFs)...

Total PDFs Generated: 15
============================================================
```

## Step 3: Parse PDFs

Parse any generated PDF:

```bash
python3 main.py data/generated_pdfs/amex_statement_1.pdf
```

Expected output:
```json
{
  "card_name": "Amex Gold",
  "statement_period": "01/01/2025 - 31/01/2025",
  "transactions": [
    {
      "date": "2025-01-10",
      "description": "SWIGGY",
      "amount": 631.0
    },
    ...
  ]
}
```

## Test All PDFs

Run the test suite to verify all 15 PDFs parse successfully:

```bash
python3 test_all.py
```

This will parse all 15 PDFs and show a summary:
```
Total PDFs: 15
Successful: 15
Failed: 0
Total Transactions Parsed: 186
```

## Save Output to File

```bash
python3 main.py data/generated_pdfs/amex_statement_1.pdf > output.json
```

## Common Commands

```bash
# Generate PDFs
python3 generate_all.py

# Parse AMEX statement
python3 main.py data/generated_pdfs/amex_statement_1.pdf

# Parse HDFC VISA statement
python3 main.py data/generated_pdfs/hdfc_visa_statement_3.pdf

# Parse HDFC MASTERCARD statement
python3 main.py data/generated_pdfs/hdfc_mastercard_statement_2.pdf

# Test all PDFs
python3 test_all.py

# Save output
python3 main.py data/generated_pdfs/amex_statement_1.pdf > output.json
```

## Troubleshooting

**Issue:** `ModuleNotFoundError: No module named 'reportlab'`
**Solution:** Install dependencies with `pip install -r requirements.txt`

**Issue:** PDFs not found
**Solution:** Run `python3 generate_all.py` first to generate PDFs

**Issue:** Permission denied
**Solution:** Ensure you have write permissions in the `data/generated_pdfs/` directory

## What's Next?

- Explore the generated PDFs in `data/generated_pdfs/`
- Examine the parser logs to understand what's being extracted
- Try parsing different PDFs to see how the system handles variations
- Check the README.md for detailed documentation
