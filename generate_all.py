import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

from generators.amex_generator import generate_all_amex_pdfs
from generators.hdfc_visa_generator import generate_all_hdfc_visa_pdfs
from generators.hdfc_mastercard_generator import generate_all_hdfc_mastercard_pdfs


def main():
    output_dir = os.path.join(os.path.dirname(__file__), "data", "generated_pdfs")
    os.makedirs(output_dir, exist_ok=True)

    print("=" * 60)
    print("Generating Credit Card Statement PDFs")
    print("=" * 60)

    print("\n[1/3] Generating AMEX Statements (5 PDFs)...")
    amex_metadata = generate_all_amex_pdfs(output_dir)
    print(f"Generated {len(amex_metadata)} AMEX PDFs")

    print("\n[2/3] Generating HDFC VISA Statements (5 PDFs)...")
    visa_metadata = generate_all_hdfc_visa_pdfs(output_dir)
    print(f"Generated {len(visa_metadata)} HDFC VISA PDFs")

    print("\n[3/3] Generating HDFC MASTERCARD Statements (5 PDFs)...")
    mastercard_metadata = generate_all_hdfc_mastercard_pdfs(output_dir)
    print(f"Generated {len(mastercard_metadata)} HDFC MASTERCARD PDFs")

    print("\n" + "=" * 60)
    print(f"Total PDFs Generated: {len(amex_metadata) + len(visa_metadata) + len(mastercard_metadata)}")
    print(f"Output Directory: {output_dir}")
    print("=" * 60)


if __name__ == "__main__":
    main()
