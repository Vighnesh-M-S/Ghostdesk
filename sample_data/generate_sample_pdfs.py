"""
Run this script once to generate sample PDF attachments for testing:
    python sample_data/generate_sample_pdfs.py

Requires: reportlab (pip install reportlab)
"""
from pathlib import Path
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import cm

OUT_DIR = Path(__file__).parent / "test_attachments"
OUT_DIR.mkdir(exist_ok=True)
styles = getSampleStyleSheet()


def _doc(name: str):
    return SimpleDocTemplate(str(OUT_DIR / name), pagesize=A4, topMargin=2*cm, bottomMargin=2*cm)


def make_invoice_pdf():
    doc = _doc("INV-2024-8834.pdf")
    story = [
        Paragraph("<b>INVOICE</b>", styles["Title"]),
        Spacer(1, 0.5*cm),
        Paragraph("TravelEase Pvt Ltd | support@travelease.example.com", styles["Normal"]),
        Spacer(1, 0.8*cm),
    ]
    data = [
        ["Field", "Value"],
        ["Invoice Number", "INV-2024-8834"],
        ["Booking ID", "BK-459821"],
        ["Invoice Date", "October 15, 2024"],
        ["Customer Reference", "CUST-78234"],
        ["Description", "Round-trip flight booking (DEL → BOM → DEL)"],
        ["Departure Date", "November 5, 2024"],
        ["Ticket Class", "Economy"],
        ["Base Fare", "₹11,200"],
        ["Taxes & Fees", "₹1,300"],
        ["Total Amount", "₹12,500"],
        ["Payment Method", "Credit Card (****4242)"],
        ["Payment Status", "PAID"],
        ["Cancellation Policy", "Full refund if cancelled ≥ 48 hrs before departure"],
    ]
    t = Table(data, colWidths=[7*cm, 10*cm])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1a56db")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.HexColor("#f8f9fa"), colors.white]),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#dee2e6")),
        ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 10),
        ("PADDING", (0, 0), (-1, -1), 6),
    ]))
    story.append(t)
    doc.build(story)
    print("Created:", OUT_DIR / "INV-2024-8834.pdf")


def make_fraud_invoice_pdf():
    doc = _doc("charge_receipt.pdf")
    story = [
        Paragraph("<b>PAYMENT RECEIPT</b>", styles["Title"]),
        Spacer(1, 0.5*cm),
        Paragraph("ShopEasy India | billing@shopeasy.example.com", styles["Normal"]),
        Spacer(1, 0.8*cm),
    ]
    data = [
        ["Field", "Value"],
        ["Receipt Number", "REC-2024-1107"],
        ["Transaction Date", "November 7, 2024"],
        ["Customer ID", "CUST-55123"],
        ["Description", "Annual Premium Subscription"],
        ["Amount", "₹8,500"],
        ["Tax (18% GST)", "₹0 (included)"],
        ["Total Charged", "₹8,500"],
        ["Payment Method", "Credit Card"],
        ["Transaction ID", "TXN-88421-XY"],
        ["Status", "COMPLETED"],
    ]
    t = Table(data, colWidths=[7*cm, 10*cm])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#dc3545")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.HexColor("#f8f9fa"), colors.white]),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#dee2e6")),
        ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 10),
        ("PADDING", (0, 0), (-1, -1), 6),
    ]))
    story.append(t)
    doc.build(story)
    print("Created:", OUT_DIR / "charge_receipt.pdf")


if __name__ == "__main__":
    make_invoice_pdf()
    make_fraud_invoice_pdf()
    print("\nSample PDFs generated in:", OUT_DIR)
