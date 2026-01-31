from app.parsers.refinements.sbi import SBIParser


def test_sbi_transaction_table_sample_parses_all_rows() -> None:
    parser = SBIParser()
    sample = (
        "14 Dec 25 FUEL SURCHARGE WAIVER EXCL TAX 20.05 C\n"
        "17 Dec 25 PAYMENT RECEIVED 000DP015351072149NzYtuK 50,000.00C\n"
        "20 Dec 25 PAYMENT RECEIVED 000DP015354113439aZCiOC 62,914.00 C\n"
        "TRANSACTIONS FOR MOHAMMAD IQBAL\n"
        "15 Dec 25 APOLLO PHARMACIES LIMI IN 1,138.82 D\n"
        "15 Dec 25 VALUE AND VARIETY IN 1,475.00 D\n"
        "16 Dec 25 UPI-DWARKAPATI FOODS LL 200.00 D\n"
        "16 Dec 25 UPI-TRAVEL FOOD SERVICELHI TERMINAL 3 PV 569.85 D\n"
        "16 Dec 25 UPI-TRAVEL FOOD SERVICELHI TERMINAL 3 PV 714.00 D\n"
        "22 Dec 25 UPI-Apple Services 250.00 D\n"
        "24 Dec 25 UPI-Apple Services 150.00 D\n"
        "10 Jan 26 UPI-Udemy India LLP 399.00D\n"
        "14 Jan 26 BLINK COMMERCE PVT LTD IN 811.00 D\n"
        "14 Jan 26 ZOMATO LTD IN 408.43 D\n"
        "Previous Balance Earned Redeemed/Expired Closing Balance\n"
    )

    txns = parser._extract_transactions([], sample)
    assert len(txns) == 13
    assert txns[0].description.startswith("FUEL SURCHARGE WAIVER")
    assert txns[0].transaction_type == "credit"
    assert txns[3].description.startswith("APOLLO")
    assert txns[3].transaction_type == "debit"
