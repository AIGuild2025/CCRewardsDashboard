import sys
import json
import os
from parser.text_extractor import extract_text
from parser.metadata_extractor import extract_metadata
from parser.transaction_parser import parse_transactions


def parse_pdf(pdf_path):
    if not os.path.exists(pdf_path):
        print(f"Error: File not found: {pdf_path}", file=sys.stderr)
        sys.exit(1)

    text_lines = extract_text(pdf_path)

    if not text_lines:
        print(f"Error: Failed to extract text from PDF", file=sys.stderr)
        sys.exit(1)

    metadata = extract_metadata(text_lines)

    transactions = parse_transactions(text_lines)

    result = {
        "card_name": metadata["card_name"],
        "statement_period": metadata["statement_period"],
        "transactions": transactions
    }

    return result


def main():
    if len(sys.argv) != 2:
        print("Usage: python main.py <path_to_pdf>", file=sys.stderr)
        sys.exit(1)

    pdf_path = sys.argv[1]

    result = parse_pdf(pdf_path)

    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
