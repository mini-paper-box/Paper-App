import pyodbc
import win32com.client as win32
from datetime import datetime, timedelta
import logging
import os
from pathlib import Path
from configparser import ConfigParser
from typing import List, Optional, Tuple


class OrderRevisionMailer:
    """Send daily email of yesterday's late-shipped order revisions from SQL Server."""

    def __init__(self, config_path: Optional[str] = None):
        """
        Initialize the mailer with configuration.
        
        Args:
            config_path: Path to configuration file. If None, uses config.ini in script directory.
        """
        self.setup_logging()
        self.config_path = config_path or Path(__file__).parent / 'config.ini'
        self.config = self.load_config(self.config_path)
        
        # Database settings
        self.server = self.config.get('Database', 'server', fallback='wbdbserver')
        self.database = self.config.get('Database', 'database', fallback='flute_data')
        
        # Email settings
        self.default_to = self.config.get('Email', 'to', fallback='sang.n@whitebird.ca')
        self.default_cc = self.config.get('Email', 'cc', fallback='')
        self.send_empty_report = self.config.getboolean('Email', 'send_empty_report', fallback=False)
        self.allow_resend = self.config.getboolean('Email', 'allow_resend_same_day', fallback=False)
        
        # Build connection string
        self.conn_str = (
            "DRIVER={ODBC Driver 18 for SQL Server};"
            f"SERVER={self.server};"
            f"DATABASE={self.database};"
            "Trusted_Connection=yes;"
            "Encrypt=no;"
        )

    def setup_logging(self):
        """Configure logging to file and console."""
        log_dir = Path(__file__).parent / 'logs'
        log_dir.mkdir(exist_ok=True)
        
        log_file = log_dir / f"order_mailer_{datetime.now().strftime('%Y%m')}.log"
        
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(log_file),
                logging.StreamHandler()
            ]
        )
        self.logger = logging.getLogger(__name__)

    def load_config(self, config_path: str) -> ConfigParser:
        """
        Load configuration from INI file.
        
        Args:
            config_path: Path to config file.
            
        Returns:
            ConfigParser object with configuration
        """
        config = ConfigParser()
        
        if Path(config_path).exists():
            config.read(config_path)
            self.logger.info(f"Configuration loaded from {config_path}")
        else:
            self.logger.warning(f"Config file not found at {config_path}. Using defaults.")
            # Create a sample config file
            self.create_sample_config(config_path)
            config.read(config_path)
        
        return config

    def create_sample_config(self, config_path: str):
        """Create a sample configuration file."""
        sample_config = ConfigParser()
        
        sample_config['Database'] = {
            'server': 'wbdbserver',
            'database': 'flute_data'
        }
        
        sample_config['Email'] = {
            'to': 'sang.n@whitebird.ca',
            'cc': '',
            'send_empty_report': 'False',
            'allow_resend_same_day': 'False'
        }
        
        sample_config['Tracking'] = {
            '# last_sent_date': 'Automatically updated when email is sent'
        }
        
        with open(config_path, 'w') as f:
            sample_config.write(f)
        
        self.logger.info(f"Sample config file created at {config_path}")

    def get_last_sent_date(self) -> Optional[str]:
        """
        Get the last date an email was sent from config.
        
        Returns:
            Date string in YYYY-MM-DD format or None if never sent
        """
        if not self.config.has_section('Tracking'):
            return None
        return self.config.get('Tracking', 'last_sent_date', fallback=None)

    def update_last_sent_date(self, date_str: str):
        """
        Update the last sent date in the config file.
        
        Args:
            date_str: Date string in YYYY-MM-DD format
        """
        if not self.config.has_section('Tracking'):
            self.config.add_section('Tracking')
        
        self.config.set('Tracking', 'last_sent_date', date_str)
        
        with open(self.config_path, 'w') as f:
            self.config.write(f)
        
        self.logger.info(f"Updated last_sent_date to {date_str}")

    def check_if_already_sent_today(self) -> bool:
        """
        Check if an email has already been sent today.
        
        Returns:
            True if email was already sent today, False otherwise
        """
        last_sent = self.get_last_sent_date()
        today = datetime.now().date().isoformat()
        
        if last_sent == today:
            return True
        return False

    def fetch_yesterday_events(self) -> List[Tuple]:
        """
        Query yesterday's late shipment revision events from SQL Server.
        
        Returns:
            List of tuples containing order revision data
            
        Raises:
            pyodbc.Error: If database connection or query fails
        """
        yesterday = (datetime.today() - timedelta(days=1)).date()
        
        try:
            self.logger.info(f"Connecting to database: {self.server}/{self.database}")
            
            with pyodbc.connect(self.conn_str) as conn:
                cursor = conn.cursor()

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
                
                self.logger.info(f"Retrieved {len(rows)} order revision records for {yesterday}")
                return rows
                
        except pyodbc.Error as e:
            self.logger.error(f"Database error: {e}")
            raise
        except Exception as e:
            self.logger.error(f"Unexpected error fetching data: {e}")
            raise

    def build_html_email(self, rows: List[Tuple], yesterday: datetime.date) -> str:
        """
        Build HTML email body with order revision data.
        
        Args:
            rows: List of order revision records
            yesterday: Date for the report
            
        Returns:
            HTML string for email body
        """
        record_count = len(rows)
        
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
                .summary {{
                    background-color: #e7f3ff;
                    padding: 12px;
                    border-radius: 6px;
                    margin-bottom: 15px;
                    border-left: 4px solid #0066cc;
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
                    font-weight: bold;
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
                .footer {{
                    margin-top: 20px;
                    font-size: 12px;
                    color: #666;
                }}
            </style>
        </head>

        <body>
            <div class="container">
                <div class="summary">
                    <strong>Report Date:</strong> {yesterday}<br>
                    <strong>Total Records:</strong> {record_count}
                </div>
        """

        if rows:
            html += """
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

                # Escape HTML special characters
                customer = str(customer).replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
                reason = str(reason).replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
                full_name = str(full_name).replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')

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

            html += """
                </table>
            """
        else:
            html += """
                <p style="text-align: center; color: #666; padding: 20px;">
                    No late-shipped order revisions recorded for this date.
                </p>
            """

        # Close HTML
        html += """
                <div class="footer">
                    <p>Best regards,<br>Whitebird / Moyy Design</p>
                    <p><em>This is an automated report. Generated at {}</em></p>
                </div>
            </div>
        </body>
        </html>
        """.format(datetime.now().strftime('%Y-%m-%d %H:%M:%S'))

        return html

    def send_email(self, to: Optional[str] = None, cc: Optional[str] = None, 
                   dry_run: bool = False, force: bool = False):
        """
        Send HTML email via Outlook with yesterday's late-shipment events.
        
        Args:
            to: Email recipient(s). If None, uses config default.
            cc: CC recipient(s). If None, uses config default.
            dry_run: If True, generates email but doesn't send it.
            force: If True, bypasses the duplicate send check.
            
        Raises:
            Exception: If email sending fails
        """
        try:
            # Check if already sent today
            if not force and not dry_run and not self.allow_resend:
                if self.check_if_already_sent_today():
                    today = datetime.now().date().isoformat()
                    self.logger.warning(f"Email already sent today ({today}). Skipping. Use --force to override.")
                    print(f"⚠️  Email already sent today. Use --force flag to resend.")
                    return

            rows = self.fetch_yesterday_events()
            yesterday = (datetime.today() - timedelta(days=1)).date()

            # Use defaults if not provided
            to = to or self.default_to
            cc = cc or self.default_cc

            # Check if we should send when no records exist
            if not rows and not self.send_empty_report:
                self.logger.info(f"No order revisions recorded on {yesterday}. No email sent.")
                return

            # Build HTML email
            html = self.build_html_email(rows, yesterday)

            if dry_run:
                self.logger.info("DRY RUN MODE - Email not sent")
                self.logger.info(f"To: {to}")
                self.logger.info(f"CC: {cc}")
                self.logger.info(f"Subject: Order Revision Events - {yesterday}")
                self.logger.info(f"Records: {len(rows)}")
                
                # Optionally save HTML to file for preview
                preview_file = Path(__file__).parent / f"email_preview_{yesterday}.html"
                with open(preview_file, 'w', encoding='utf-8') as f:
                    f.write(html)
                self.logger.info(f"Preview saved to: {preview_file}")
                return

            # Send via Outlook
            self.logger.info("Sending email via Outlook...")
            outlook = win32.Dispatch("Outlook.Application")
            mail = outlook.CreateItem(0)
            mail.To = to
            if cc:
                mail.CC = cc

            mail.Subject = f"Production Update - {yesterday}"
            mail.HTMLBody = html

            mail.Send()

            # Update the last sent date
            today = datetime.now().date().isoformat()
            self.update_last_sent_date(today)

            self.logger.info(f"✓ Email sent successfully to {to} ({len(rows)} records)")
            print(f"✓ Email sent successfully! ({len(rows)} records)")

        except Exception as e:
            self.logger.error(f"Failed to send email: {e}")
            raise


# ============================
#          MAIN
# ============================
if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='Send daily order revision report')
    parser.add_argument('--dry-run', action='store_true', 
                       help='Generate email preview without sending')
    parser.add_argument('--force', action='store_true',
                       help='Force send even if already sent today')
    parser.add_argument('--config', type=str, 
                       help='Path to configuration file')
    parser.add_argument('--to', type=str, 
                       help='Override email recipient')
    parser.add_argument('--cc', type=str, 
                       help='Override CC recipients')
    
    args = parser.parse_args()
    
    try:
        mailer = OrderRevisionMailer(config_path=args.config)
        mailer.send_email(
            to=args.to,
            cc=args.cc,
            dry_run=args.dry_run,
            force=args.force
        )
    except Exception as e:
        logging.error(f"Script execution failed: {e}")
        exit(1)