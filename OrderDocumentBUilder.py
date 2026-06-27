from reportlab.lib.pagesizes import LETTER
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib import colors
import os

class OrderDocumentBuilder:
    """
    Builds a PDF with shipping request details.
    """

    def __init__(self, ship_to: dict, orders: list[dict]):
        self.ship_to = ship_to
        self.orders = orders

    def build_pdf(self, output_path: str, driver_paperwork_attached: bool = False):
        """
        Generate a PDF file with the request information.
        :param output_path: Path where the PDF should be saved.
        :param driver_paperwork_attached: True/False to indicate paperwork presence.
        """
        doc = SimpleDocTemplate(output_path, pagesize=LETTER, title="Quick Turnaround Request")
        styles = getSampleStyleSheet()
        content = []

        # === TITLE ===
        title_style = ParagraphStyle(name="Title", fontSize=16, leading=20, alignment=1, spaceAfter=12)
        content.append(Paragraph("Quick Turnaround Required", title_style))

        # === BODY TEXT ===
        customer_name = self.ship_to.get("name_1", "Unknown Customer")
        total_units = sum(order.get("units", 0) for order in self.orders)

        body_text = f"""
        <b>Request by:</b> Production<br/><br/>
        Hi Team,<br/><br/>
        We have a shipment due to go out to <b>{customer_name}</b>.<br/>
        Shipment should be ready after 12 PM or earlier.<br/>
        This needs to be delivered to <b>{customer_name}</b> by today.<br/><br/>
        The approximate skids will be <b>{total_units}</b>.<br/><br/>
        Driver's paperwork attached: <b>{"Yes" if driver_paperwork_attached else "No"}</b>
        """
        content.append(Paragraph(body_text, styles["Normal"]))
        content.append(Spacer(1, 20))

        # === OPTIONAL ORDER SUMMARY TABLE ===
        if self.orders:
            table_data = [["Order #", "Line", "Units"]]
            for order in self.orders:
                table_data.append([order.get("order_id", ""), order.get("line_number", ""), order.get("units", 0)])

            table = Table(table_data, hAlign="LEFT")
            table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.lightgrey),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
                ('ALIGN', (2, 1), (2, -1), 'RIGHT'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ]))
            content.append(table)

        # Build the PDF
        doc.build(content)
        return os.path.abspath(output_path)
