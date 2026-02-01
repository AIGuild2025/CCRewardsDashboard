import os
import sys
from main import parse_pdf


def test_all_pdfs():
    pdf_dir = "data/generated_pdfs"

    if not os.path.exists(pdf_dir):
        print(f"Error: Directory {pdf_dir} not found")
        sys.exit(1)

    pdf_files = sorted([f for f in os.listdir(pdf_dir) if f.endswith('.pdf')])

    if not pdf_files:
        print(f"Error: No PDFs found in {pdf_dir}")
        sys.exit(1)

    print("=" * 70)
    print(f"Testing PDF Parsing: {len(pdf_files)} PDFs")
    print("=" * 70)

    results = []
    for pdf_file in pdf_files:
        pdf_path = os.path.join(pdf_dir, pdf_file)
        print(f"\n[{len(results) + 1}/{len(pdf_files)}] Parsing: {pdf_file}")

        try:
            result = parse_pdf(pdf_path)
            transaction_count = len(result['transactions'])

            print(f"  ✓ Card: {result['card_name']}")
            print(f"  ✓ Period: {result['statement_period']}")
            print(f"  ✓ Transactions: {transaction_count}")

            results.append({
                "file": pdf_file,
                "success": True,
                "transaction_count": transaction_count,
                "card_name": result['card_name']
            })

        except Exception as e:
            print(f"  ✗ Failed: {e}")
            results.append({
                "file": pdf_file,
                "success": False,
                "error": str(e)
            })

    print("\n" + "=" * 70)
    print("Summary")
    print("=" * 70)

    success_count = sum(1 for r in results if r['success'])
    failed_count = len(results) - success_count
    total_transactions = sum(r.get('transaction_count', 0) for r in results if r['success'])

    print(f"Total PDFs: {len(results)}")
    print(f"Successful: {success_count}")
    print(f"Failed: {failed_count}")
    print(f"Total Transactions Parsed: {total_transactions}")

    if failed_count > 0:
        print("\nFailed PDFs:")
        for r in results:
            if not r['success']:
                print(f"  - {r['file']}: {r.get('error', 'Unknown error')}")

    print("=" * 70)


if __name__ == "__main__":
    test_all_pdfs()
