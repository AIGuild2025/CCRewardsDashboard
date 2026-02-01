from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib.enums import TA_CENTER, TA_RIGHT
from datetime import datetime, timedelta
import random
import os


CUSTOMERS = [
    "Rahul Mehta",
    "Ananya Sharma",
    "Vikram Iyer",
    "Neha Kapoor",
    "Amit Verma",
    "Priya Nair",
    "Rohan Malhotra"
]

CARD_NAMES = [
    "Amex Gold",
    "Amex Platinum",
    "Amex SmartEarn",
    "Amex MRCC",
    "Amex Travel Platinum"
]

STATEMENT_PERIODS = [
    "01/01/2025 - 31/01/2025",
    "01/02/2025 - 28/02/2025",
    "01/03/2025 - 31/03/2025",
    "01/04/2025 - 30/04/2025",
    "01/05/2025 - 31/05/2025"
]

MERCHANTS = {
    "ecommerce": ["AMAZON INDIA ONLINE SERVICES PVT LTD BANGALORE", "FLIPKART INTERNET PVT LTD"],
    "food": ["SWIGGY", "ZOMATO"],
    "travel": ["INDIGO AIRLINES", "IRCTC RAILWAY BOOKING"],
    "utilities": ["AIRTEL PREPAID", "JIO RECHARGE"],
    "retail": ["RELIANCE RETAIL STORE"]
}

AMOUNT_FORMATS = [
    lambda x: f"{x:.2f}",
    lambda x: f"{x:,.2f}",
    lambda x: f"INR {x:.2f}"
]


def get_transactions(count, include_fx=False):
    transactions = []
    start_date = datetime(2025, 1, 5)

    categories = ["ecommerce", "food", "travel", "utilities", "retail"]

    for i in range(count):
        category = categories[i % len(categories)]
        merchant = random.choice(MERCHANTS[category])
        amount = round(random.uniform(500, 15000), 2)
        date = start_date + timedelta(days=random.randint(0, 25))

        transactions.append({
            "date": date.strftime("%d/%m/%Y"),
            "description": merchant,
            "amount": amount
        })

    if include_fx:
        fx_date = start_date + timedelta(days=random.randint(0, 25))
        transactions.append({
            "date": fx_date.strftime("%d/%m/%Y"),
            "description": "USD 120.00 (Converted INR 9,960.00)",
            "amount": 9960.00
        })

    transactions.sort(key=lambda x: datetime.strptime(x["date"], "%d/%m/%Y"))
    return transactions


def generate_amex_pdf(output_path, pdf_number):
    doc = SimpleDocTemplate(output_path, pagesize=letter)
    elements = []
    styles = getSampleStyleSheet()

    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=24,
        textColor=colors.HexColor('#006FCF'),
        spaceAfter=30,
        alignment=TA_CENTER,
        fontName='Helvetica-Bold'
    )

    customer = random.choice(CUSTOMERS)
    card_name = CARD_NAMES[pdf_number - 1]
    statement_period = STATEMENT_PERIODS[pdf_number - 1]
    card_last4 = f"{1000 + pdf_number:04d}"

    title = Paragraph("AMERICAN EXPRESS", title_style)
    elements.append(title)
    elements.append(Spacer(1, 0.2 * inch))

    header_data = [
        ["Statement Period:", statement_period],
        ["Cardholder Name:", customer],
        ["Card Type:", card_name],
        ["Card Number:", f"XXXX-XXXXXX-X{card_last4}"],
    ]

    header_table = Table(header_data, colWidths=[2*inch, 4*inch])
    header_table.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
        ('TEXTCOLOR', (0, 0), (-1, -1), colors.black),
        ('ALIGN', (0, 0), (0, -1), 'LEFT'),
        ('ALIGN', (1, 0), (1, -1), 'LEFT'),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
    ]))

    elements.append(header_table)
    elements.append(Spacer(1, 0.3 * inch))

    transaction_counts = [10, 12, 15, 11, 14]
    include_fx = (pdf_number == 2)
    transactions = get_transactions(transaction_counts[pdf_number - 1], include_fx)

    elements.append(Paragraph("<b>Transaction Details</b>", styles['Heading2']))
    elements.append(Spacer(1, 0.1 * inch))

    amount_formatter = AMOUNT_FORMATS[(pdf_number - 1) % len(AMOUNT_FORMATS)]

    trans_data = [["Date", "Description", "Amount"]]
    for trans in transactions:
        trans_data.append([
            trans["date"],
            trans["description"],
            amount_formatter(trans["amount"])
        ])

    trans_table = Table(trans_data, colWidths=[1*inch, 3.5*inch, 1.5*inch])
    trans_table.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 10),
        ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 1), (-1, -1), 9),
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#006FCF')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('ALIGN', (2, 0), (2, -1), 'RIGHT'),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
    ]))

    elements.append(trans_table)
    elements.append(Spacer(1, 0.3 * inch))

    total_amount = sum(t["amount"] for t in transactions)

    rewards_points = int(total_amount / 50)

    rewards_data = [
        ["Membership Rewards Summary", ""],
        ["Points Earned This Period:", f"{rewards_points:,}"],
        ["Total Amount Spent:", amount_formatter(total_amount)]
    ]

    rewards_table = Table(rewards_data, colWidths=[3*inch, 2*inch])
    rewards_table.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 12),
        ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 1), (-1, -1), 10),
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#F0F0F0')),
        ('ALIGN', (0, 0), (0, -1), 'LEFT'),
        ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
    ]))

    elements.append(rewards_table)

    doc.build(elements)
    return {
        "bank": "AMEX",
        "network": "AMEX",
        "card_name": card_name,
        "card_last4": card_last4,
        "statement_period": statement_period,
        "transactions": transactions
    }


def generate_all_amex_pdfs(output_dir):
    os.makedirs(output_dir, exist_ok=True)
    metadata_list = []

    for i in range(1, 6):
        output_path = os.path.join(output_dir, f"amex_statement_{i}.pdf")
        metadata = generate_amex_pdf(output_path, i)
        metadata_list.append(metadata)
        print(f"Generated: {output_path}")

    return metadata_list


if __name__ == "__main__":
    output_dir = "../data/generated_pdfs"
    generate_all_amex_pdfs(output_dir)
