from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from reportlab.lib.units import inch
from datetime import datetime
import os

class QuickTurnaroundPDF:
    def __init__(self, customer_name, address, total_units, orders, driver_paperwork_attached=True,
                 filename="quick_turnaround.pdf", logo_path=None):
        self.customer_name = customer_name
        self.total_units = total_units
        self.orders = orders
        self.driver_paperwork_attached = driver_paperwork_attached
        self.filename = filename
        self.logo_path = logo_path
        self.address = address

    def _footer_canvas(self, canvas, doc):
        canvas.saveState()
        width, height = A4
        now = datetime.now().strftime("%Y-%m-%d %H:%M")
        footer_text = f"""
Generated on: {now} | Contact: production@whitebird.ca"""
        canvas.setFont('Helvetica', 9)
        canvas.setFillColor(colors.grey)
        # Draw lines right-aligned with margin
        margin = 30
        lines = footer_text.splitlines()
        y = 60  # distance from bottom
        for line in lines:
            text_width = canvas.stringWidth(line, 'Helvetica', 9)
            canvas.drawString(width - margin - text_width, y, line)
            y -= 12
        canvas.restoreState()

    def generate_pdf(self):
        doc = SimpleDocTemplate(
            self.filename,
            pagesize=A4,
            rightMargin=30, leftMargin=30, topMargin=50, bottomMargin=120  # leave space for footer
        )
        elements = []

        # Styles
        styles = getSampleStyleSheet()
        styles.add(ParagraphStyle(name='MainTitle', fontSize=22, leading=26, spaceAfter=12, alignment=1, fontName='Helvetica-Bold'))
        styles.add(ParagraphStyle(name='Bold14', fontSize=14, leading=18, spaceAfter=6, fontName='Helvetica-Bold'))
        styles.add(ParagraphStyle(name='Normal12', fontSize=12, leading=16, spaceAfter=6))

        # Logo
        if self.logo_path and os.path.exists(self.logo_path):
            logo = Image(self.logo_path, width=2*inch, height=2*inch)
            logo.hAlign = 'CENTER'
            elements.append(logo)
            elements.append(Spacer(1, 12))

        # Title
        elements.append(Paragraph("Quick Turnaround Required", styles['MainTitle']))
        elements.append(Spacer(1, 12))

        # Body
        body = f"""
            <b>Request By:</b> Production<br/><br/>
            Dear Team,<br/><br/><br/>

            A shipment is scheduled to go out to <b><u><font size="16">{self.address}</font></u></b>.<br/><br/>
            This shipment will be ready by <b><u><font size="16">12 PM or earlier</font></u></b>.<br/><br/>
            This needs to be delivered to <b><u><font size="16">{self.customer_name}</font></u></b> by end of day.<br/><br/>
            Estimated # of skids: <b><u><font size="16">{self.total_units}</font></u></b>.<br/><br/>
            Driver's paperwork attached: <b><u><font size="16">{'Yes' if self.driver_paperwork_attached else 'No'}</font></u></b>.<br/><br/><br/>

            Please ensure timely processing and verification.
            """
        elements.append(Paragraph(body.upper(), styles['Normal12']))
        elements.append(Spacer(1, 12))

        # Orders table
        if self.orders:
            table_data = [["Order #", "Docket #", "Description", "Order Qty"]]
            total_units_calculated = 0
            for o in self.orders:
                if o.get("num_pallet", "") > 0:
                    desc = str(o.get("docket_description", "")).splitlines()[0]
                    table_data.append([
                        f"""{str(o.get("order_id"))}-{str(o.get("order_line"))}""",
                        str(o.get("docket_id")),
                        Paragraph(desc, styles['Normal']),
                        o.get("order_quantity", "")
                    ])
                    total_units_calculated += o.get("order_quantity", 0)
            table_data.append(["", "","TOTAL", total_units_calculated])

            table_style = TableStyle([
                # Header row
                ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 12),

                # Grid and padding
                ('GRID', (0, 0), (-1, -1), 1, colors.black),
                ('TOPPADDING', (0, 0), (-1, -1), 6),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
            ])

            # --- Add striped backgrounds dynamically ---
            # Suppose you have N rows in your table (including header)
            num_rows = len(table_data)  # Replace with your actual data list length

            for row in range(1, num_rows):  # start after header (row 0)
                bg_color = colors.lightgrey if row % 2 == 0 else colors.whitesmoke
                table_style.add('BACKGROUND', (0, row), (-1, row), bg_color)

            tbl = Table(table_data, colWidths=[1.2*inch, 1*inch, 3*inch, 1.5*inch])
            tbl.setStyle(table_style)
            elements.append(tbl)
            elements.append(Spacer(1, 12))
        body2 = f"""<br/>***IF NO DRIVER PAPERWORK ATTACHED, IT WILL BE COMPLETED IN THE MORNING<br/><br/>
        ***PLEASE INDICATE WHO WILL TAKE DELIVERY IF NOT ON AM TRUCK<br/><br/>
        <br/>TO BE DELIVERED BY :__________________________________________________________<br/>"""
        elements.append(Paragraph(body2.upper(), styles['Normal12']))
        elements.append(Spacer(1, 12))
        # Build PDF with footer on every page
        doc.build(elements, onFirstPage=self._footer_canvas, onLaterPages=self._footer_canvas)
        print(f"PDF generated: {self.filename}")
        return os.path.abspath(self.filename)
