import sqlite3
import win32com.client as win32
from datetime import datetime, timedelta

class OrderRevisionMailer:
    """Send daily email of yesterday's order_revision_events."""

    def __init__(self, db_path=r"C:\Users\sang.n\OneDrive - whitebird.ca\Paper App\prod_db.db"):
        self.db_path = db_path

    def fetch_yesterday_events(self):
        """Fetch yesterday's order revision events from SQLite."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        yesterday = (datetime.today() - timedelta(days=1)).date()

        cursor.execute("""
            SELECT order_revision_id,
                   full_name,
                   customer_name,
                   order_id,
                   order_line_nbr,
                   delivery_status_txt,
                   shipped_date
            FROM order_revision_events
            WHERE DATE(revision_date) = ?
              AND emailed = 0
              AND shipped_date > requested_dte
            ORDER BY revision_date, order_id
        """, (yesterday.isoformat(),))

        rows = cursor.fetchall()
        conn.close()
        return rows

    def mark_emailed(self, revision_ids):
        """Mark the given revisions as emailed."""
        if not revision_ids:
            return
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        placeholders = ",".join("?" for _ in revision_ids)
        cursor.execute(f"UPDATE order_revision_events SET emailed=1 WHERE order_revision_id IN ({placeholders})", revision_ids)
        conn.commit()
        conn.close()
        print(f"✅ Marked {len(revision_ids)} revisions as emailed.")

    def send_email(self, to, cc=None):
        """Send HTML email via Outlook with yesterday's events."""
        rows = self.fetch_yesterday_events()
        yesterday = (datetime.today() - timedelta(days=1)).date()

        if not rows:
            print(f"No order revisions recorded on {yesterday}.")
            return

        # Build HTML table
        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <style>
                table {{border-collapse: collapse; width: 100%;}}
                th, td {{border:1px solid #ddd; padding:8px;}}
                th {{background-color:#f0f0f0;}}
                tr:nth-child(even){{background-color:#f9f9f9;}}
            </style>
        </head>
        <body style="font-family: Arial, sans-serif; background-color:#f4f4f4; margin:0; padding:0;">
            <table width="100%" cellpadding="20" style="background-color:#f4f4f4;">
                <tr>
                    <td align="center">
                        <table width="800" cellpadding="10" style="background-color:#ffffff; border-radius:8px; border-collapse:collapse;">
                            <tr style="background-color:#4CAF50; color:#ffffff; font-size:20px;">
                                <td colspan="6" align="center">Order Revision Events for {yesterday}</td>
                            </tr>
                            <tr style="background-color:#f0f0f0; font-weight:bold;">
                                <th>Customer</th>
                                <th>Order ID</th>
                                <th>Line</th>
                                <th>Reason</th>
                                <th>Modified By</th>
                                <th>Updated Ship Date</th>
                            </tr>
        """

        for i, row in enumerate(rows):
            bg_color = "#ffffff" if i % 2 == 0 else "#f9f9f9"
            rev_id, full_name, customer, order_id, line, reason, shipped_date = row
            html += f"""
                <tr style="background-color:{bg_color};">
                    <td>{customer}</td>
                    <td>{order_id}</td>
                    <td>{line}</td>
                    <td>{reason}</td>
                    <td>{full_name}</td>
                    <td>{shipped_date}</td>
                </tr>
            """

        html += """
                        </table>
                        <p style="margin-top:20px;">Best regards,<br/>Moyy Design</p>
                    </td>
                </tr>
            </table>
        </body>
        </html>
        """

        # Send email via Outlook
        outlook = win32.Dispatch('Outlook.Application')
        mail = outlook.CreateItem(0)
        mail.To = to
        if cc:
            mail.CC = cc
        mail.Subject = f"Order Revision Events - {yesterday}"
        mail.HTMLBody = html
        mail.Display()  # use mail.Send() to send automatically

        # Mark emailed
        revision_ids = [r[0] for r in rows]
        self.mark_emailed(revision_ids)


# ================= Main =================
if __name__ == "__main__":
    mailer = OrderRevisionMailer()
    mailer.send_email(
        to="sang.n@whitebird.ca"
    )
