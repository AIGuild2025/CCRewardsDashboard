from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib.enums import TA_CENTER, TA_LEFT
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
    "HDFC Regalia VISA",
    "HDFC Millennia VISA",
    "HDFC MoneyBack VISA",
    "HDFC Diners VISA",
    "HDFC Freedom VISA"
]

STATEMENT_PERIODS = [
    "01/01/2025 - 31/01/2025",
    "01/02/2025 - 28/02/2025",
    "01/03/2025 - 31/03/2025",
    "01/04/2025 - 30/04/2025",
    "01/05/2025 - 31/05/2025"
]

MERCHANTS = {
    "ecommerce": ["AMAZON.IN", "FLIPKART"],
    "food": ["SWIGGY", "ZOMATO"],
    "travel": ["INDIGO", "IRCTC"],
    "utilities": ["AIRTEL", "JIO"],
    "retail": ["RELIANCE STORE"]
}

AMOUNT_FORMATS = [
    lambda x: f"{x:.2f}",
    lambda x: f"{x:,.2f}",
    lambda x: f"INR {x:.2f}"
]


def get_transactions(count):
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

    transactions.sort(key=lambda x: datetime.strptime(x["date"], "%d/%m/%Y"))
    return transactions


def generate_hdfc_visa_pdf(output_path, pdf_number):
    doc = SimpleDocTemplate(output_path, pagesize=letter)
    elements = []
    styles = getSampleStyleSheet()

    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=20,
        textColor=colors.HexColor('#004C8F'),
        spaceAfter=20,
        alignment=TA_CENTER,
        fontName='Helvetica-Bold'
    )

    customer = random.choice(CUSTOMERS)
    card_name = CARD_NAMES[pdf_number - 1]
    statement_period = STATEMENT_PERIODS[pdf_number - 1]
    card_last4 = f"{2000 + pdf_number:04d}"

    title = Paragraph("HDFC BANK", title_style)
    elements.append(title)

    subtitle = Paragraph("Credit Card Statement", styles['Heading2'])
    elements.append(subtitle)
    elements.append(Spacer(1, 0.2 * inch))

    header_data = [
        ["Statement Period:", statement_period],
        ["Cardholder:", customer],
        ["Card:", card_name],
        ["Card Number:", f"XXXX XXXX XXXX {card_last4}"],
        ["Network:", "VISA"],
    ]

    header_table = Table(header_data, colWidths=[2*inch, 4*inch])
    header_table.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
        ('TEXTCOLOR', (0, 0), (-1, -1), colors.black),
        ('ALIGN', (0, 0), (0, -1), 'LEFT'),
        ('ALIGN', (1, 0), (1, -1), 'LEFT'),
        ('TOPPADDING', (0, 0), (-1, -1), 5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
    ]))

    elements.append(header_table)
    elements.append(Spacer(1, 0.3 * inch))

    transaction_counts = [10, 12, 15, 11, 14]
    transactions = get_transactions(transaction_counts[pdf_number - 1])

    elements.append(Paragraph("<b>Transactions</b>", styles['Heading3']))
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
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#004C8F')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('ALIGN', (2, 0), (2, -1), 'RIGHT'),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ('TOPPADDING', (0, 0), (-1, -1), 5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
    ]))

    elements.append(trans_table)
    elements.append(Spacer(1, 0.3 * inch))

    total_amount = sum(t["amount"] for t in transactions)
    reward_points = int(total_amount / 100)

    summary_data = [
        ["Reward Points Summary", ""],
        ["Points Earned:", f"{reward_points:,}"],
        ["Total Spent:", amount_formatter(total_amount)]
    ]

    summary_table = Table(summary_data, colWidths=[3*inch, 2*inch])
    summary_table.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 11),
        ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 1), (-1, -1), 10),
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#E8E8E8')),
        ('ALIGN', (0, 0), (0, -1), 'LEFT'),
        ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
        ('TOPPADDING', (0, 0), (-1, -1), 5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
    ]))

    elements.append(summary_table)

    doc.build(elements)
    return {
        "bank": "HDFC",
        "network": "VISA",
        "card_name": card_name,
        "card_last4": card_last4,
        "statement_period": statement_period,
        "transactions": transactions
    }


def generate_all_hdfc_visa_pdfs(output_dir):
    os.makedirs(output_dir, exist_ok=True)
    metadata_list = []

    for i in range(1, 6):
        output_path = os.path.join(output_dir, f"hdfc_visa_statement_{i}.pdf")
        metadata = generate_hdfc_visa_pdf(output_path, i)
        metadata_list.append(metadata)
        print(f"Generated: {output_path}")

    return metadata_list


if __name__ == "__main__":
    output_dir = "../data/generated_pdfs"
    generate_all_hdfc_visa_pdfs(output_dir)
