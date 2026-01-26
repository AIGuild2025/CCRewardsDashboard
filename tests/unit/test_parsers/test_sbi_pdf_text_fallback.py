from app.parsers.refinements.sbi import SBIParser


def test_sbi_prefers_pdf_text_fallback_when_it_has_more_rows() -> None:
    parser = SBIParser()

    # Primary (Unstructured) text is missing two rows but isn't obviously "corrupt".
    primary_text = (
        "14 Dec 25 FUEL SURCHARGE WAIVER EXCL TAX 20.05 C\n"
        "17 Dec 25 PAYMENT RECEIVED 000DP015351072149NzYtuK 50,000.00 C\n"
        "15 Dec 25 APOLLO PHARMACIES LIMI IN 1,138.82 D\n"
        "15 Dec 25 VALUE AND VARIETY IN 1,475.00 D\n"
        "16 Dec 25 UPI-DWARKAPATI FOODS LL 200.00 D\n"
        "16 Dec 25 UPI-TRAVEL FOOD SERVICELHI TERMINAL 3 PV 569.85 D\n"
        "16 Dec 25 UPI-TRAVEL FOOD SERVICELHI TERMINAL 3 PV 714.00 D\n"
        "22 Dec 25 UPI-Apple Services 250.00 D\n"
        "24 Dec 25 UPI-Apple Services 150.00 D\n"
        "10 Jan 26 UPI-Udemy India LLP 399.00 D\n"
        "14 Jan 26 BLINK COMMERCE PVT LTD IN 811.00 D\n"
        "Previous Balance Earned Redeemed/Expired Closing Balance\n"
    )

    # Fallback (pypdf) text includes all rows.
    parser._pdf_text_override = (
        primary_text
        + "20 Dec 25 PAYMENT RECEIVED 000DP015354113439aZCiOC 62,914.00 C\n"
        + "14 Jan 26 ZOMATO LTD IN 408.43 D\n"
    )

    txns = parser._extract_transactions([], primary_text)
    assert len(txns) == 13
