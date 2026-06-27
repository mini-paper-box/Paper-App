import os
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, KeepTogether
from reportlab.lib import colors
from reportlab.graphics.barcode import createBarcodeDrawing
from reportlab.lib.styles import getSampleStyleSheet
import win32com.client as win32

def create_pdf_with_layout(filename):
    doc = SimpleDocTemplate(filename, pagesize=A4, rightMargin=30, leftMargin=30, topMargin=30, bottomMargin=18)
    styles = getSampleStyleSheet()
    elements = []

    # Ship To Address
    ship_to = [
        Paragraph("<b>Ship To:</b>", styles['Normal']),
        Paragraph("Acme Corp.", styles['Normal']),
        Paragraph("123 Industrial Way", styles['Normal']),
        Paragraph("Springfield, IL 62704", styles['Normal']),
        Paragraph("USA", styles['Normal'])
    ]

    # Order Info Table (top right)
    order_data = [
        ["Order No:", "1234"],
        ["Date:", "2025-08-06"],
        ["Customer:", "John Doe"]
    ]
    order_table = Table(order_data, hAlign='RIGHT', colWidths=[60, 100])
    order_table.setStyle(TableStyle([
        ("ALIGN", (0, 0), (-1, -1), "LEFT"),
        ("FONTNAME", (0, 0), (-1, -1), "Helvetica"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))

    # Combine ship to and order info side-by-side
    top_layout = Table([
        [ship_to, order_table]
    ], colWidths=[300, 200])

    top_layout.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("BOX", (0, 0), (-1, -1), 0, colors.white),
    ]))

    elements.append(top_layout)
    elements.append(Spacer(1, 24))

    # Product Table
    product_data = [
        ["Item", "Description", "Quantity", "Price"],
        ["001", "Widget A", 10, "$5.00"],
        ["002", "Widget B", 20, "$8.00"],
        ["003", "Widget C", 5, "$12.00"],
    ]
    product_table = Table(product_data, colWidths=[60, 200, 80, 80])
    product_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#d0d0d0")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.black),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("GRID", (0, 0), (-1, -1), 1, colors.black),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
    ]))

    elements.append(Paragraph("Product List", styles['Heading2']))
    elements.append(product_table)
    elements.append(Spacer(1, 24))

    # Barcode
    barcode_value = "ORD-001-ABC"
    barcode = createBarcodeDrawing(
        'Code128',
        value=barcode_value,
        barHeight=40,
        barWidth=1.2,
        humanReadable=True
    )

    elements.append(Paragraph(f"Barcode: {barcode_value}", styles['Heading3']))
    elements.append(barcode)

    doc.build(elements)
    print(f"✅ PDF saved as: {filename}")

def send_outlook_email_with_attachment(to_email, subject, body, attachment_path):
    outlook = win32.Dispatch("outlook.application")
    mail = outlook.CreateItem(0)
    mail.To = to_email
    mail.Subject = subject
    mail.Body = body
    mail.Attachments.Add(os.path.abspath(attachment_path))
    mail.Display()
    print(f"📧 Email sent to {to_email} with attachment: {attachment_path}")

# === USAGE ===
pdf_path = "order_report_with_layout.pdf"
create_pdf_with_layout(pdf_path)

send_outlook_email_with_attachment(
    to_email="recipient@example.com",
    subject="Order Report with Barcode",
    body="Hi,\n\nPlease find the attached order report.\n\nThanks.",
    attachment_path=pdf_path
)
