# Phase-1: Credit Card Statement PDF Parsing

A hackathon project focused on programmatically generating realistic dummy credit card statement PDFs with controlled variations and parsing them into structured JSON via a CLI.

## Overview

This system generates 15 realistic credit card statement PDFs across three supported networks and parses them with ~80% accuracy target. Built for a 48-hour hackathon with emphasis on reliability, explainability, and demo safety.

## Supported Card Providers & Networks

1. **American Express (AMEX network)**
   - Rewards: "Membership Rewards"
   - Card variants: Gold, Platinum, SmartEarn, MRCC, Travel Platinum

2. **HDFC Bank - VISA network**
   - Rewards: "Reward Points"
   - Card variants: Regalia, Millennia, MoneyBack, Diners, Freedom

3. **HDFC Bank - MASTERCARD network**
   - Rewards: "Reward Points"
   - Card variants: Regalia, Millennia, MoneyBack, Tata Neu, IndianOil

## Features

- Generates 15 controlled-variation dummy PDFs (5 per network)
- Uses 7 dummy customers randomly distributed across PDFs
- Transaction count: 10-15 per PDF from multiple categories
- Variations include:
  - Different amount formats (2499.00, 2,499.00, INR 2499.00)
  - Statement periods (Jan-May 2025)
  - Long merchant descriptions
  - Edge cases (FX transactions, malformed rows)
- Parser handles format variations and skips invalid rows gracefully

## Project Structure

```
phase1_pdf_parsing/
├── data/
│   └── generated_pdfs/       # Output directory for generated PDFs
├── generators/
│   ├── amex_generator.py     # AMEX statement generator
│   ├── hdfc_visa_generator.py        # HDFC VISA generator
│   └── hdfc_mastercard_generator.py  # HDFC MASTERCARD generator
├── parser/
│   ├── text_extractor.py     # PDF text extraction (pdfplumber + PyMuPDF)
│   ├── metadata_extractor.py # Extract card name and period
│   └── transaction_parser.py # Parse and normalize transactions
├── main.py                   # CLI entry point
├── generate_all.py           # Generate all 15 PDFs
├── requirements.txt          # Python dependencies
└── README.md                 # This file
```

## Installation

1. Install Python 3.8+

2. Install dependencies:
```bash
pip install -r requirements.txt
```

## Usage

### Generate PDFs

Generate all 15 dummy credit card statement PDFs:

```bash
python generate_all.py
```

This creates 15 PDFs in `data/generated_pdfs/`:
- 5 AMEX statements: `amex_statement_1.pdf` to `amex_statement_5.pdf`
- 5 HDFC VISA statements: `hdfc_visa_statement_1.pdf` to `hdfc_visa_statement_5.pdf`
- 5 HDFC MASTERCARD statements: `hdfc_mastercard_statement_1.pdf` to `hdfc_mastercard_statement_5.pdf`

### Parse PDF Statements

Parse a single PDF and output structured JSON:

```bash
python main.py data/generated_pdfs/amex_statement_1.pdf
```

**Output Format:**
```json
{
  "card_name": "Amex Gold",
  "statement_period": "01/01/2025 - 31/01/2025",
  "transactions": [
    {
      "date": "2025-01-05",
      "description": "AMAZON INDIA ONLINE SERVICES PVT LTD BANGALORE",
      "amount": 2499.0
    },
    {
      "date": "2025-01-10",
      "description": "SWIGGY",
      "amount": 450.5
    }
  ]
}
```

## Technical Details

### PDF Generation

- **Library:** ReportLab
- **Currency:** INR
- **Date format in PDFs:** DD/MM/YYYY
- **Card numbers:** Masked with last 4 digits shown
- **Data source:** Fully synthetic dummy data (NO real PII)

**Dummy Customer Pool (7 customers):**
- Rahul Mehta
- Ananya Sharma
- Vikram Iyer
- Neha Kapoor
- Amit Verma
- Priya Nair
- Rohan Malhotra

**Transaction Categories:**
- E-commerce: Amazon, Flipkart
- Food: Swiggy, Zomato
- Travel: IndiGo, IRCTC
- Utilities: Airtel, Jio
- Retail: Reliance Store

### PDF Parsing

- **Primary parser:** pdfplumber
- **Fallback parser:** PyMuPDF (fitz)
- **Date normalization:** DD/MM/YYYY → YYYY-MM-DD
- **Amount normalization:** Removes commas and currency prefixes

**Parsing Logic:**
1. Extract text from PDF (pdfplumber with PyMuPDF fallback)
2. Extract metadata (card name, statement period)
3. Parse transaction rows
4. Skip header rows, summary rows, and malformed entries
5. Normalize dates and amounts
6. Output structured JSON

**Logging:**
- Total rows detected
- Rows successfully parsed
- Rows skipped (with reasons)

## Edge Cases Handled

1. **FX Transactions (AMEX):**
   - Example: "USD 120.00 (Converted INR 9,960.00)"
   - Parser skips FX format rows gracefully

2. **Malformed Rows (HDFC MASTERCARD):**
   - Missing description or amount
   - Parser skips invalid rows

3. **Amount Format Variations:**
   - Handles: `2499.00`, `2,499.00`, `INR 2499.00`
   - Normalizes to: `2499.0`

4. **Long Merchant Descriptions:**
   - Example: "AMAZON INDIA ONLINE SERVICES PVT LTD BANGALORE"
   - Parsed correctly

## Known Limitations

- **NO OCR Support:** Only works with digitally-generated PDFs
- **Synthetic Data Only:** All data is dummy/fake
- **Single-page PDFs:** Multi-page statements not tested
- **Text-based Parsing:** Relies on text extraction, not table detection
- **~80% Accuracy Target:** Designed for hackathon demo, not production

## Development Notes

- Python-only implementation
- Modular architecture for easy extension
- Minimal abstractions for hackathon speed
- Deterministic behavior for reliable demos
- Clean, readable code

## Example Commands

```bash
# Generate all PDFs
python generate_all.py

# Parse a single AMEX statement
python main.py data/generated_pdfs/amex_statement_1.pdf

# Parse a HDFC VISA statement
python main.py data/generated_pdfs/hdfc_visa_statement_3.pdf

# Parse a HDFC MASTERCARD statement
python main.py data/generated_pdfs/hdfc_mastercard_statement_2.pdf

# Parse and save to file
python main.py data/generated_pdfs/amex_statement_1.pdf > output.json
```

## Future Enhancements (Out of Scope for Phase-1)

- OCR support for scanned PDFs
- Multi-page statement handling
- Additional card networks
- LLM-based parsing
- Database integration
- Web UI
- Batch processing CLI

## License

This is a hackathon project for educational and demonstration purposes only.
