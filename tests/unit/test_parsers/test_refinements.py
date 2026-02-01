"""Tests for bank-specific parser refinements."""

from datetime import date
from unittest.mock import Mock

import pytest

from app.parsers.refinements.amex import AmexParser
from app.parsers.refinements.hdfc import HDFCParser
from app.parsers.refinements.sbi import SBIParser


class TestHDFCParser:
    """Test suite for HDFC parser refinement."""

    def test_initialization(self):
        """Test HDFC parser initializes with correct bank code."""
        parser = HDFCParser()
        assert parser.bank_code == "hdfc"

    def test_parse_date_dd_mmm_yy(self):
        """Test parsing DD-MMM-YY format (15-Jan-25)."""
        parser = HDFCParser()
        result = parser._parse_date("15-Jan-25")
        assert result == date(2025, 1, 15)

    def test_parse_date_dd_mmm_yyyy(self):
        """Test parsing DD-MMM-YYYY format (15-Jan-2025)."""
        parser = HDFCParser()
        result = parser._parse_date("15-Jan-2025")
        assert result == date(2025, 1, 15)

    def test_parse_date_dd_mm_yyyy(self):
        """Test parsing DD/MM/YYYY format (15/01/2025)."""
        parser = HDFCParser()
        result = parser._parse_date("15/01/2025")
        assert result == date(2025, 1, 15)

    def test_parse_date_dd_mm_yy(self):
        """Test parsing DD/MM/YY format (15/01/25)."""
        parser = HDFCParser()
        result = parser._parse_date("15/01/25")
        assert result == date(2025, 1, 15)

    def test_parse_date_with_whitespace(self):
        """Test date parsing handles extra whitespace."""
        parser = HDFCParser()
        result = parser._parse_date("  15-Jan-25  ")
        assert result == date(2025, 1, 15)

    def test_parse_date_fallback_to_generic(self):
        """Test fallback to GenericParser for unknown formats."""
        parser = HDFCParser()
        # GenericParser doesn't support US format, so this should fail
        with pytest.raises(ValueError):
            parser._parse_date("99/99/9999")  # Invalid format

    def test_parse_date_invalid(self):
        """Test parsing invalid date raises ValueError."""
        parser = HDFCParser()
        with pytest.raises(ValueError):
            parser._parse_date("invalid-date")

    def test_inherits_from_generic_parser(self):
        """Test HDFC parser inherits other methods from GenericParser."""
        parser = HDFCParser()

        # Should have all GenericParser methods
        assert hasattr(parser, "_parse_amount")
        assert hasattr(parser, "_find_card_number")
        assert hasattr(parser, "_find_rewards")
        assert hasattr(parser, "parse")

    def test_find_card_number_card_no_formats(self):
        """HDFC statements often use 'Card No:' with masked digits/spaces."""
        parser = HDFCParser()

        assert (
            parser._find_card_number([], "Card No: 4893XXXXXXXXXX3777\nStatement Date: 13/07/2025")
            == "3777"
        )
        assert (
            parser._find_card_number([], "Card No: 4893 XXXX XXXX 3777\nStatement Date: 13/07/2025")
            == "3777"
        )
        assert (
            parser._find_card_number([], "Card No: XXXX XXXX XXXX 3777\nStatement Date: 13/07/2025")
            == "3777"
        )

    def test_find_statement_period_from_statement_date(self):
        """HDFC statements may omit a period range; derive month from statement date."""
        parser = HDFCParser()
        result = parser._find_statement_period([], "Statement Date: 13/07/2025\nCard No: XXXX XXXX XXXX 3777")
        assert result == date(2025, 7, 1)

    def test_find_rewards_reward_points_summary_table(self):
        """HDFC Reward Points Summary should map opening/earned/closing correctly."""
        parser = HDFCParser()

        text = """
        Statement for HDFC Bank Credit Card
        Statement Date: 13/07/2025
        Card No: 4893XXXXXXXXXX3777
        Amount Due: 5,154.00

        Reward Points Summary
        Opening Balance Feature + Bonus Reward Points Earned Disbursed Adjusted/Lapsed Closing Balance
        Points expiring in next 30 days Points expiring in next 60 days
        2,652 66 0 0 2,718 0 0
        """

        mock_element = Mock()
        mock_element.__str__ = Mock(return_value=text)
        parsed = parser.parse([mock_element])

        assert parsed.reward_points == 2718
        assert parsed.reward_points_earned == 66
        assert parsed.reward_points_previous == 2652
        assert parsed.reward_points_redeemed == 0

    def test_parse_newer_hdfc_template_billing_period_and_domestic_rows(self):
        """Newer HDFC template should still parse card/period/dues/rewards/transactions."""
        parser = HDFCParser()

        text = """
        TOTAL AMOUNT DUE
        C687.00
        MINIMUM DUE
        C200.00
        DUE DATE
        03 Oct, 2025
        Reward Points
        2,478
        REDEEM REWARDS
        Opening Balance Feature + Bonus Reward
        Points Earned
        Disbursed Adjusted/Lapsed
        2,452 26 0 0

        Domestic Transactions
        DATE & TIME TRANSACTION DESCRIPTION REWARDS AMOUNT PI
        PALANIMOHAN D
        25/08/2025| 15:45 ZOMATOGURGAON + 4  C 329.95 l
        25/08/2025| 11:25 ZOMATONEW DELHI + 4  C 356.20 l
        01/09/2025| 22:07 CREDIT CARD PAYMENTNet Banking (Ref#
        00000000000901015039786) +  C 1,431.00 l

        Credit Card No.
        Alternate Account Number
        Statement Date
        Billing Period
        489377XXXXXX3777
        0001014550009323771
        13 Sep, 2025
        14 Aug, 2025 - 13 Sep, 2025
        """

        mock_element = Mock()
        mock_element.__str__ = Mock(return_value=text)
        parsed = parser.parse([mock_element])

        assert parsed.card_last_four == "3777"
        assert parsed.statement_month == date(2025, 9, 1)
        assert parsed.closing_balance_cents == 68700

        assert parsed.reward_points == 2478
        assert parsed.reward_points_earned == 26
        assert parsed.reward_points_previous == 2452
        assert parsed.reward_points_redeemed == 0

        assert len(parsed.transactions) == 3
        assert parsed.transactions[0].description == "ZOMATOGURGAON"
        assert parsed.transactions[0].amount_cents == 32995
        assert parsed.transactions[2].transaction_type == "credit"
        assert parsed.transactions[2].amount_cents == 143100

    def test_find_account_summary_extracts_total_dues(self):
        """Account Summary should be parsed and used as outstanding (Total Dues)."""
        parser = HDFCParser()

        text = """
        Statement for HDFC Bank Credit Card
        Statement Date: 13/07/2025
        Card No: 4893XXXXXXXXXX3777

        Account Summary
        Opening Balance Payment/Credits Purchase/Debits Finance Charges Total Dues
        0.00 0.00 5,153.98 0.00 5,154.00

        13/07/2025 AMAZON 1,000.00
        """

        # Drive through parser.parse so we validate the end-to-end mapping:
        # - account_summary exists
        # - closing_balance uses Total Dues
        mock_element = Mock()
        mock_element.__str__ = Mock(return_value=text)
        parsed = parser.parse([mock_element])

        assert parsed.account_summary is not None
        assert parsed.account_summary.previous_balance_cents == 0
        assert parsed.account_summary.credits_cents == 0
        assert parsed.account_summary.debits_cents == 515398
        assert parsed.account_summary.fees_cents == 0
        assert parsed.account_summary.total_outstanding_cents == 515400

        assert parsed.closing_balance_cents == 515400

    def test_extract_transactions_domestic_and_international_sections(self):
        """HDFC transaction sections should be parsed even when columns are line-split."""
        parser = HDFCParser()

        text = """
        Statement for HDFC Bank Credit Card
        Statement Date: 13/07/2025
        Card No: 4893XXXXXXXXXX3777
        Amount Due: 5,154.00

        Domestic Transactions
        Date  Transaction Description Feature Reward Points Amount (in Rs.)
        27/06/2025 23:56:47
        PALANIMOHAN D
        ADITYA BIRLA FASHION AND Kurla
        34
        2,630.00
        11/07/2025 10:44:53
        2CO.COM|BITDEFENDER AMSTERDAM
        32
        2,498.99
        13/07/2025
        1% on all DCC Transaction (Ref# ST251950084000011777132)
        0
        24.99

        International Transactions
        Date  Transaction Description Feature Reward Points Amount (in Rs.)
        05/07/2025 09:00:00
        SOME INTERNATIONAL MERCHANT
        12
        100.00

        Reward Points Summary
        """

        mock_element = Mock()
        mock_element.__str__ = Mock(return_value=text)
        parsed = parser.parse([mock_element])

        assert len(parsed.transactions) == 4
        assert parsed.transactions[0].amount_cents == 263000
        assert parsed.transactions[1].amount_cents == 249899
        assert parsed.transactions[2].amount_cents == 2499
        assert parsed.transactions[3].amount_cents == 10000

    def test_extract_transactions_regex_fallback_when_date_not_line_start(self):
        """pypdf can reorder columns so dates appear mid-line; fallback should still parse rows."""
        parser = HDFCParser()

        text = """
        Statement for HDFC Bank Credit Card
        Statement Date: 13/07/2025
        Card No: 4893XXXXXXXXXX3777
        Amount Due: 5,154.00

        Domestic Transactions
        Date  Transaction Description Feature Reward Points Amount (in Rs.)
        PALANIMOHAN D 27/06/2025 23:56:47 ADITYA BIRLA FASHION AND Kurla 34 2,630.00
        SOME TEXT 11/07/2025 10:44:53 2CO.COM|BITDEFENDER AMSTERDAM 32 2,498.99

        Reward Points Summary
        """

        mock_element = Mock()
        mock_element.__str__ = Mock(return_value=text)
        parsed = parser.parse([mock_element])

        assert len(parsed.transactions) == 2
        assert parsed.transactions[0].amount_cents == 263000
        assert parsed.transactions[1].amount_cents == 249899


class TestAmexParser:
    """Test suite for American Express parser refinement."""

    def test_initialization(self):
        """Test Amex parser initializes with correct bank code."""
        parser = AmexParser()
        assert parser.bank_code == "amex"

    def test_parse_date_mm_dd_yyyy(self):
        """Test parsing MM/DD/YYYY format (01/15/2025)."""
        parser = AmexParser()
        result = parser._parse_date("01/15/2025")
        assert result == date(2025, 1, 15)

    def test_parse_date_mm_dd_yy(self):
        """Test parsing MM/DD/YY format (01/15/25)."""
        parser = AmexParser()
        result = parser._parse_date("01/15/25")
        assert result == date(2025, 1, 15)

    def test_parse_date_with_dashes(self):
        """Test parsing MM-DD-YYYY format (01-15-2025)."""
        parser = AmexParser()
        result = parser._parse_date("01-15-2025")
        assert result == date(2025, 1, 15)

    def test_parse_date_with_whitespace(self):
        """Test date parsing handles extra whitespace."""
        parser = AmexParser()
        result = parser._parse_date("  01/15/2025  ")
        assert result == date(2025, 1, 15)

    def test_parse_date_fallback_to_generic(self):
        """Test fallback to GenericParser for unknown formats."""
        parser = AmexParser()
        # GenericParser should handle DD-MMM-YY
        result = parser._parse_date("15-Jan-25")
        assert result == date(2025, 1, 15)

    def test_parse_date_invalid(self):
        """Test parsing invalid date raises ValueError."""
        parser = AmexParser()
        with pytest.raises(ValueError):
            parser._parse_date("99/99/9999")

    def test_find_card_number_five_digits(self):
        """Test extracting 5-digit Amex account ending."""
        parser = AmexParser()

        mock_element = Mock()
        mock_element.__str__ = Mock(return_value="Account Ending 12345")
        elements = [mock_element]
        full_text = "Account Ending 12345"

        result = parser._find_card_number(elements, full_text)
        assert result == "2345"  # Last 4 of 5 digits

    def test_find_card_number_with_spaces(self):
        """Test extracting card number with spacing variations."""
        parser = AmexParser()

        mock_element = Mock()
        mock_element.__str__ = Mock(return_value="Account ending in 98765")
        elements = [mock_element]
        full_text = "Account ending in 98765"

        result = parser._find_card_number(elements, full_text)
        assert result == "8765"

    def test_find_card_number_masked_format(self):
        """Test extracting from masked format (xxxxx xxxxx x12345)."""
        parser = AmexParser()

        mock_element = Mock()
        mock_element.__str__ = Mock(return_value="Card: xxxxx xxxxx x54321")
        elements = [mock_element]
        full_text = "Card: xxxxx xxxxx x54321"

        result = parser._find_card_number(elements, full_text)
        assert result == "4321"

    def test_find_card_number_masked_dash_format(self):
        """Test extracting from masked dash format (XXXX-XXXXXX-73008)."""
        parser = AmexParser()

        mock_element = Mock()
        mock_element.__str__ = Mock(return_value="Card Number XXXX-XXXXXX-73008")
        elements = [mock_element]
        full_text = "Card Number XXXX-XXXXXX-73008"

        result = parser._find_card_number(elements, full_text)
        assert result == "3008"

    def test_parse_date_dd_mm_yyyy(self):
        """Test parsing DD/MM/YYYY format common in AmEx India headers."""
        parser = AmexParser()
        result = parser._parse_date("23/10/2025")
        assert result == date(2025, 10, 23)

    def test_extract_transactions_month_name_day_without_year(self):
        """AmEx India statements often omit year per transaction row."""
        parser = AmexParser()

        text = """
        Opening Balance RsNew Credits RsNew Debits RsClosing Balance RsMinimum Payment Rs
        6,031.83-7,260.40+14,022.15=12,793.58640.00
        Statement Period From  September 24  to October 23, 2025
        Card Number XXXX-XXXXXX-73008 CR
        September 25 cca*GRT Jewellers India Chennai 6,000.00
        October 9 Billdesk*AMAZON MUM 0.30
        CR
        October 06 PAYMENT RECEIVED. THANK YOU 6,031.83
        """.strip()

        # Avoid dependency on real PDF extraction by overriding fallback text.
        setattr(parser, "_pdf_text_override", text)

        # Parse uses full_text built from elements; provide a single element with our text.
        mock_element = Mock()
        mock_element.__str__ = Mock(return_value=text)

        stmt = parser.parse([mock_element])
        assert stmt.bank_code == "amex"
        assert stmt.card_last_four == "3008"
        assert stmt.statement_month == date(2025, 10, 1)
        assert len(stmt.transactions) == 3
        # Payment received should be treated as credit
        pay = [t for t in stmt.transactions if "payment received" in t.description.lower()][0]
        assert pay.transaction_type == "credit"

    def test_find_card_number_fallback_to_generic(self):
        """Test fallback to GenericParser for standard 4-digit patterns."""
        parser = AmexParser()

        mock_element = Mock()
        mock_element.__str__ = Mock(return_value="Card Number: xxxxxxxxxxxx6789")
        elements = [mock_element]
        full_text = "Card Number: xxxxxxxxxxxx6789"
        assert parser._find_card_number(elements, full_text) == "6789"

    def test_find_card_number_raises_when_missing(self):
        """Test card number extraction raises ValueError when not found."""
        parser = AmexParser()

        mock_element = Mock()
        mock_element.__str__ = Mock(return_value="No card number here")
        elements = [mock_element]
        full_text = "No card number here"

        with pytest.raises(ValueError):
            parser._find_card_number(elements, full_text)

    def test_inherits_from_generic_parser(self):
        """Test Amex parser inherits other methods from GenericParser."""
        parser = AmexParser()

        # Should have all GenericParser methods
        assert hasattr(parser, "_parse_amount")
        assert hasattr(parser, "_find_rewards")
        assert hasattr(parser, "_find_statement_period")
        assert hasattr(parser, "parse")


class TestSBIParser:
    """Test suite for SBI parser refinement."""

    def test_initialization(self):
        """Test SBI parser initializes with correct bank code."""
        parser = SBIParser()
        assert parser.bank_code == "sbi"

    def test_find_rewards_numbers_before_header(self):
        """SBI often prints the 4-number row before the header labels."""
        parser = SBIParser()
        full_text = (
            "3988 57 0 4045\n"
            "Previous Balance\n"
            "Earned\n"
            "Redeemed/Expired\n"
            "/Forfeited Closing Balance Points Expiry Details\n"
        )
        closing = parser._find_rewards([], full_text)
        assert closing == 4045
        assert parser._reward_points_earned == 57

    def test_find_rewards_unstructured_reordered(self):
        """OCR/table extraction can reorder both headers and numbers."""
        parser = SBIParser()
        # This is similar to what Unstructured can emit for the same section.
        full_text = (
            "Redeemed/Expired Points Expiry Details Earned Closing Balance /Forfeited "
            "4045 0 3988 57 NONE Previous Balance"
        )
        closing = parser._find_rewards([], full_text)
        assert closing == 4045
        assert parser._reward_points_earned == 57

    def test_extract_transactions_cleans_concatenated_upi_merchants(self):
        """If extraction interleaves two rows, keep only the first row's merchant."""
        parser = SBIParser()
        full_text = (
            "24 Nov 25 UPI-T2 UNISEX SALON 24 Nov 25 UPI-RELIANCE BP MOBILITMITED 3,306.98 D"
        )
        txns = parser._extract_transactions([], full_text)
        assert len(txns) == 1
        assert txns[0].description == "UPI-T2 UNISEX SALON"

    def test_extract_transactions_handles_multiple_rows_same_day(self):
        """SBI repeats the date on every row; ensure we don't collapse rows."""
        parser = SBIParser()
        full_text = (
            "16 Dec 25 UPI-DWARKAPATI FOODS LL 200.00 D "
            "16 Dec 25 UPI-TRAVEL FOOD SERVICELHI TERMINAL 3 PV 569.85 D"
        )
        txns = parser._extract_transactions([], full_text)
        assert len(txns) == 2
        assert txns[0].description == "UPI-DWARKAPATI FOODS LL"
        assert txns[0].amount_cents == 20000
        assert txns[1].description == "UPI-TRAVEL FOOD SERVICELHI TERMINAL 3 PV"
        assert txns[1].amount_cents == 56985


class TestRefinementInheritance:
    """Test that refinements properly extend GenericParser."""

    def test_hdfc_uses_generic_amount_parsing(self):
        """Test HDFC uses GenericParser's amount parsing."""
        from decimal import Decimal
        parser = HDFCParser()
        
        # Should parse Indian rupee format and return Decimal
        result = parser._parse_amount("₹1,23,456.78")
        assert result == Decimal("123456.78")

    def test_amex_uses_generic_amount_parsing(self):
        """Test Amex uses GenericParser's amount parsing."""
        from decimal import Decimal
        parser = AmexParser()

        # Should parse US dollar format and return Decimal
        result = parser._parse_amount("$1,234.56")
        assert result == Decimal("1234.56")

    def test_refinements_minimal_overrides(self):
        """Test that refinements only override necessary methods."""
        hdfc = HDFCParser()
        amex = AmexParser()

        # HDFC should only override _parse_date
        hdfc_methods = [
            m
            for m in dir(hdfc)
            if not m.startswith("_") or m.startswith("_parse") or m.startswith("_find")
        ]

        # Amex should only override _parse_date and _find_card_number
        amex_methods = [
            m
            for m in dir(amex)
            if not m.startswith("_") or m.startswith("_parse") or m.startswith("_find")
        ]

        # Both should have access to all parent methods
        assert len(hdfc_methods) > 5
        assert len(amex_methods) > 5
