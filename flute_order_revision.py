import pyodbc
import win32com.client as win32
from datetime import datetime, timedelta


class OrderRevisionMailer:
    """Send daily email of yesterday's late-shipped order revisions from SQL Server."""

    def __init__(self, server="wbdbserver", database="flute_data"):
        self.server = server
        self.database = database

        self.conn_str = (
            "DRIVER={ODBC Driver 18 for SQL Server};"
            f"SERVER={self.server};"
            f"DATABASE={self.database};"
            "Trusted_Connection=yes;"
            "Encrypt=no;"
        )

    def fetch_yesterday_events(self):
        """Query yesterday's late shipment revision events from SQL Server."""
        conn = pyodbc.connect(self.conn_str)
        cursor = conn.cursor()

        yesterday = (datetime.today() - timedelta(days=1)).date()

        query = """
        SELECT
            r.order_revision_id,
            LTRIM(RTRIM(u.user_first_name)) + ' ' +
               LEFT(LTRIM(RTRIM(u.user_last_name)), 1) + '.' AS full_name,
            c.short_name AS customer_name,
            r.order_id,
            od.order_line_nbr,
            od.delivery_status_txt AS reason,
            od.scheduled_dte AS shipped_date,
            r.revision_date
        FROM order_revisions r
        JOIN order_details od ON r.order_id = od.order_id
        JOIN users u ON r.user_id = u.user_id
        JOIN order_header oh ON r.order_id = oh.order_id
        JOIN customer c ON oh.customer_id = c.customer_id
        WHERE CAST(r.revision_date AS DATE) = ?
          AND od.scheduled_dte > od.requested_dte
          AND r.status_id = 3
          AND r.revision_dsc NOT IN ('Order Processed', 'Printed (New)', 'Order sent to Pronto')
        ORDER BY r.revision_date, r.order_id;
        """

        cursor.execute(query, (yesterday,))
        rows = cursor.fetchall()
        conn.close()

        return rows

    def send_email(self, to, cc=None):
        """Send HTML email via Outlook with yesterday's late-shipment events."""
        rows = self.fetch_yesterday_events()
        yesterday = (datetime.today() - timedelta(days=1)).date()

        if not rows:
            print(f"No order revisions recorded on {yesterday}.")
            return

        # --------------------------
        # Build HTML Table (70% width + right-aligned dates)
        # --------------------------
        html = f"""
        <html>
        <head>
            <meta charset="UTF-8">
            <style>
                body {{
                    font-family: Arial, sans-serif;
                    background-color: #f4f4f6;
                    padding: 20px;
                    text-align: center;
                }}
                .container {{
                    display: inline-block;
                    width: 70%;
                    background: #fff;
                    border-radius: 10px;
                    padding: 20px;
                    box-shadow: 0 2px 6px rgba(0,0,0,0.15);
                    text-align: left;
                }}
                h2 {{
                    background: #FF8C00; /* Dark orange header */
                    color: white;
                    padding: 12px;
                    border-radius: 6px;
                    text-align: center;
                    margin-top: 0;
                    display: none; /* Removed title */
                }}
                table {{
                    width: 100%;
                    border-collapse: collapse;
                    font-size: 14px;
                    margin-top: 10px;
                }}
                th {{
                    background-color: #e9ecef;
                    padding: 8px;
                    border: 1px solid #ccc;
                }}
                td {{
                    padding: 8px;
                    border: 1px solid #ddd;
                }}
                .right {{
                    text-align: right;
                }}
                tr:nth-child(even) {{
                    background-color: #f9f9f9;
                }}
            </style>
        </head>

        <body>
            <div class="container">
                <table>
                    <tr>
                        <th>Customer</th>
                        <th>Order ID</th>
                        <th>Line</th>
                        <th>Reason</th>
                        <th>Modified By</th>
                        <th>Modified Date</th>
                        <th>Updated Ship Date</th>
                    </tr>
        """

        # Add data rows
        for r in rows:
            (rev_id, full_name, customer, order_id,
             line, reason, shipped_date, revision_date) = r

            # Format dates (remove time)
            if isinstance(shipped_date, datetime):
                shipped_date = shipped_date.date()

            if isinstance(revision_date, datetime):
                revision_date = revision_date.date()

            html += f"""
                <tr>
                    <td>{customer}</td>
                    <td>{order_id}</td>
                    <td>{line}</td>
                    <td>{reason}</td>
                    <td>{full_name}</td>
                    <td class="right">{revision_date}</td>
                    <td class="right">{shipped_date}</td>
                </tr>
            """

        # Close HTML
        html += """
                </table>
                <p style="margin-top:20px;">Best regards,<br>Whitebird / Moyy Design</p>
            </div>
        </body>
        </html>
        """

        # --------------------------
        # Send Outlook Email
        # --------------------------
        outlook = win32.Dispatch("Outlook.Application")
        mail = outlook.CreateItem(0)
        mail.To = to
        if cc:
            mail.CC = cc

        mail.Subject = f"Order Revision Events - {yesterday}"
        mail.HTMLBody = html

        mail.Display()

        print("📨 Email sent successfully!")


# ============================
#          MAIN
# ============================
if __name__ == "__main__":
    mailer = OrderRevisionMailer()
    mailer.send_email(
        to="sang.n@whitebird.ca"
    )
