import pyodbc
import pandas as pd
import win32com.client as win32
from datetime import datetime, timedelta
import logging
from pathlib import Path
from configparser import ConfigParser
from typing import Optional

# ✅ RELATIVE import (package-safe)
from .charts.on_time_chart import OnTimeChart
from ..data.sql_manager import SQLManager


class OnTimeDeliveryMailer:
    """Send weekly on-time delivery summary with embedded chart."""

    def __init__(self, config_path: Optional[str] = None):
        self.setup_logging()
        self.base_dir = Path(__file__).parent
        self.config_path = config_path or self.base_dir / "config.ini"
        self.config = self.load_config(self.config_path)

        # DB
        self.db = SQLManager()
        self.server = self.config.get("Database", "server", fallback="wbdbserver")
        self.database = self.config.get("Database", "database", fallback="flute_data")

        # Email
        self.default_to = self.config.get("Email", "to", fallback="sang.n@whitebird.ca")
        self.default_cc = self.config.get("Email", "cc", fallback="")
        self.send_empty_report = self.config.getboolean("Email", "send_empty_report", fallback=False)

        self.conn_str = (
            "DRIVER={ODBC Driver 18 for SQL Server};"
            f"SERVER={self.server};"
            f"DATABASE={self.database};"
            "Trusted_Connection=yes;"
            "Encrypt=no;"
        )

    # ----------------------------------------------------
    # LOGGING
    # ----------------------------------------------------
    def setup_logging(self):
        log_dir = Path(__file__).parent / "logs"
        log_dir.mkdir(exist_ok=True)
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s - %(levelname)s - %(message)s",
            handlers=[
                logging.FileHandler(log_dir / "on_time_delivery.log"),
                logging.StreamHandler(),
            ],
        )
        self.logger = logging.getLogger(__name__)

    # ----------------------------------------------------
    # CONFIG
    # ----------------------------------------------------
    def load_config(self, path: Path) -> ConfigParser:
        config = ConfigParser()
        if path.exists():
            config.read(path)
        else:
            config["Database"] = {"server": "wbdbserver", "database": "flute_data"}
            config["Email"] = {"to": "sang.n@whitebird.ca", "cc": ""}
            with open(path, "w") as f:
                config.write(f)
        return config

    # ----------------------------------------------------
    # METRICS
    # ----------------------------------------------------
    def get_summary_metrics(self, df_ytd: pd.DataFrame, df_weekly: pd.DataFrame) -> str:
        """Generate mobile-responsive HTML table with YTD and previous week summary metrics."""
        if df_ytd.empty:
            return "<p>No data available</p>"
        
        # Calculate YTD metrics
        ytd_metrics = OnTimeChart.get_week_metrics(df_ytd)
        
        # Calculate previous week metrics
        weekly_metrics = OnTimeChart.get_week_metrics(df_weekly)
        
        # Get date range for previous week
        week_start, week_end = OnTimeChart.get_previous_week_range()
        
        return f"""
        <table class="metrics-table" role="presentation" cellspacing="0" cellpadding="0" border="0" style="width: 100%; border-collapse: collapse; margin: 10px 0;">
            <thead>
                <tr style="background: #34495e; color: white;">
                    <th style="padding: 12px 8px; text-align: left; font-size: 13px; font-weight: 600; border-bottom: 2px solid #2c3e50;">Metric</th>
                    <th style="padding: 12px 8px; text-align: right; font-size: 13px; font-weight: 600; border-bottom: 2px solid #2c3e50;">Last Week<br><span style="font-size: 10px; font-weight: normal;">({week_start:%b %d}-{week_end:%b %d})</span></th>
                    <th style="padding: 12px 8px; text-align: right; font-size: 13px; font-weight: 600; border-bottom: 2px solid #2c3e50;">Year-to-Date</th>
                </tr>
            </thead>
            <tbody>
                <tr style="background: #f8f9fa;">
                    <td style="padding: 10px 8px; border-bottom: 1px solid #dee2e6; font-size: 14px; font-weight: 600;">Total Orders</td>
                    <td style="padding: 10px 8px; text-align: right; border-bottom: 1px solid #dee2e6; font-size: 14px; font-weight: bold;">{weekly_metrics['total_orders']:,}</td>
                    <td style="padding: 10px 8px; text-align: right; border-bottom: 1px solid #dee2e6; font-size: 14px; font-weight: bold;">{ytd_metrics['total_orders']:,}</td>
                </tr>
                <tr>
                    <td style="padding: 10px 8px; border-bottom: 1px solid #dee2e6; font-size: 14px; font-weight: 600;">On-Time Deliveries</td>
                    <td style="padding: 10px 8px; text-align: right; border-bottom: 1px solid #dee2e6; font-size: 14px; font-weight: bold;">{weekly_metrics['on_time_count']:,}</td>
                    <td style="padding: 10px 8px; text-align: right; border-bottom: 1px solid #dee2e6; font-size: 14px; font-weight: bold;">{ytd_metrics['on_time_count']:,}</td>
                </tr>
                <tr style="background: #f8f9fa;">
                    <td style="padding: 10px 8px; border-bottom: 1px solid #dee2e6; font-size: 14px; font-weight: 600;">On-Time Rate</td>
                    <td style="padding: 10px 8px; text-align: right; border-bottom: 1px solid #dee2e6; font-size: 14px; font-weight: bold; color: {'#28a745' if weekly_metrics['on_time_pct'] >= 90 else '#ffc107' if weekly_metrics['on_time_pct'] >= 75 else '#dc3545'};">
                        {weekly_metrics['on_time_pct']:.1f}%
                    </td>
                    <td style="padding: 10px 8px; text-align: right; border-bottom: 1px solid #dee2e6; font-size: 14px; font-weight: bold; color: {'#28a745' if ytd_metrics['on_time_pct'] >= 90 else '#ffc107' if ytd_metrics['on_time_pct'] >= 75 else '#dc3545'};">
                        {ytd_metrics['on_time_pct']:.1f}%
                    </td>
                </tr>
                <tr>
                    <td style="padding: 10px 8px; font-size: 14px; font-weight: 600;">Avg. Lead Time (days)</td>
                    <td style="padding: 10px 8px; text-align: right; font-size: 14px; font-weight: bold;">{weekly_metrics['avg_days']:.1f}</td>
                    <td style="padding: 10px 8px; text-align: right; font-size: 14px; font-weight: bold;">{ytd_metrics['avg_days']:.1f}</td>
                </tr>
            </tbody>
        </table>
        """

    # ----------------------------------------------------
    # EMAIL BODY - MOBILE RESPONSIVE
    # ----------------------------------------------------
    def build_html(self, metrics_html: str) -> str:
        return f"""
        <!DOCTYPE html>
        <html lang="en">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <meta http-equiv="X-UA-Compatible" content="IE=edge">
            <title>Production Performance Dashboard</title>
            <style>
                /* Reset styles */
                body, table, td, a {{ 
                    -webkit-text-size-adjust: 100%; 
                    -ms-text-size-adjust: 100%; 
                }}
                table, td {{ 
                    mso-table-lspace: 0pt; 
                    mso-table-rspace: 0pt; 
                }}
                img {{ 
                    -ms-interpolation-mode: bicubic; 
                    border: 0; 
                    height: auto; 
                    line-height: 100%; 
                    outline: none; 
                    text-decoration: none; 
                }}
                
                /* Base styles */
                body {{
                    margin: 0 !important;
                    padding: 0 !important;
                    width: 100% !important;
                    font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
                    background-color: #f5f5f5;
                }}
                
                .email-container {{
                    max-width: 600px;
                    margin: 0 auto;
                    background: white;
                }}
                
                .content-wrapper {{
                    padding: 20px;
                }}
                
                h1 {{
                    color: #2c3e50;
                    font-size: 24px;
                    margin: 0 0 20px 0;
                    padding-bottom: 15px;
                    border-bottom: 3px solid #3498db;
                }}
                
                h2 {{
                    color: #34495e;
                    font-size: 18px;
                    margin: 30px 0 15px 0;
                    padding-left: 10px;
                    border-left: 4px solid #3498db;
                }}
                
                .metrics-section {{
                    background: #f8f9fa;
                    padding: 15px;
                    border-radius: 4px;
                    margin: 15px 0;
                }}
                
                .chart-container {{
                    margin: 20px 0;
                    text-align: center;
                    background: #fafafa;
                    padding: 15px;
                    border-radius: 4px;
                }}
                
                .chart-container img {{
                    max-width: 100%;
                    height: auto;
                    border: 1px solid #ddd;
                    border-radius: 4px;
                }}
                
                .footer {{
                    margin-top: 30px;
                    padding-top: 20px;
                    border-top: 1px solid #eee;
                    font-size: 12px;
                    color: #7f8c8d;
                    text-align: center;
                }}
                
                .footer p {{
                    margin: 5px 0;
                }}
                
                /* Mobile styles */
                @media only screen and (max-width: 600px) {{
                    .content-wrapper {{
                        padding: 15px !important;
                    }}
                    
                    h1 {{
                        font-size: 20px !important;
                    }}
                    
                    h2 {{
                        font-size: 16px !important;
                        margin: 20px 0 10px 0 !important;
                    }}
                    
                    .metrics-table th,
                    .metrics-table td {{
                        padding: 8px 5px !important;
                        font-size: 12px !important;
                    }}
                    
                    .metrics-table th {{
                        font-size: 11px !important;
                    }}
                    
                    .chart-container {{
                        padding: 10px !important;
                    }}
                    
                    .footer {{
                        font-size: 11px !important;
                    }}
                }}
                
                /* Extra small mobile devices */
                @media only screen and (max-width: 480px) {{
                    h1 {{
                        font-size: 18px !important;
                    }}
                    
                    h2 {{
                        font-size: 15px !important;
                    }}
                    
                    .metrics-table th,
                    .metrics-table td {{
                        padding: 6px 4px !important;
                        font-size: 11px !important;
                    }}
                }}
            </style>
        </head>
        <body style="margin: 0; padding: 0; width: 100%; background-color: #f5f5f5;">
            <!-- Wrapper table for Outlook -->
            <table role="presentation" cellspacing="0" cellpadding="0" border="0" width="100%" style="background-color: #f5f5f5;">
                <tr>
                    <td align="center" style="padding: 20px 10px;">
                        <!-- Email container -->
                        <table role="presentation" cellspacing="0" cellpadding="0" border="0" width="600" class="email-container" style="max-width: 600px; background: white; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1);">
                            <tr>
                                <td class="content-wrapper" style="padding: 20px;">
                                    
                                    <!-- Header -->
                                    <h1>📊 Production Performance Dashboard</h1>
                                    
                                    <!-- Metrics Section -->
                                    <div class="metrics-section">
                                        <h2>Performance Summary</h2>
                                        {metrics_html}
                                    </div>
                                    
                                    <!-- Weekly Chart -->
                                    <h2>📈 Last Week Performance</h2>
                                    <div class="chart-container">
                                        <img src="cid:weekly_chart" alt="Weekly Performance Trend" style="max-width: 100%; height: auto;">
                                    </div>
                                    
                                    <!-- YTD Chart -->
                                    <h2>📊 Year-to-Date Performance</h2>
                                    <div class="chart-container">
                                        <img src="cid:ytd_chart" alt="Year-to-Date Summary" style="max-width: 100%; height: auto;">
                                    </div>
                                    
                                    <!-- Footer -->
                                    <div class="footer">
                                        <p>📅 Report Generated: {datetime.now():%Y-%m-%d %H:%M}</p>
                                        <p>📦 Source: Whitebird Flute Data Warehouse</p>
                                    </div>
                                    
                                </td>
                            </tr>
                        </table>
                    </td>
                </tr>
            </table>
        </body>
        </html>
        """

    # ----------------------------------------------------
    # SEND EMAIL
    # ----------------------------------------------------
    def send(self, dry_run: bool = False):
        # 1. Fetch ALL YTD Data
        df_ytd = self.db.fetch_on_time_report()
        
        if df_ytd.empty:
            self.logger.info("No data found for YTD.")
            if not self.send_empty_report:
                return
        
        # 2. Create chart instance
        chart_dir = self.base_dir / "charts_output"
        chart_dir.mkdir(exist_ok=True)
        chart = OnTimeChart(output_dir=chart_dir)
        
        # 3. Filter "Last Week" using the helper method
        df_weekly = chart.filter_previous_week(df_ytd, date_column='ship_date')
        
        # Log the date range
        start_date, end_date = chart.get_previous_week_range()
        self.logger.info(f"Previous week range: {start_date.date()} to {end_date.date()}")
        self.logger.info(f"YTD data: {len(df_ytd)} rows")
        self.logger.info(f"Weekly data: {len(df_weekly)} rows")
        
        # 4. Generate Charts
        path_weekly = chart.build_weekly_trend(df_weekly)
        path_ytd = chart.build_ytd_summary(df_ytd)
        
        # 5. Build Email Components - PASS BOTH DATAFRAMES
        metrics_html = self.get_summary_metrics(df_ytd, df_weekly)
        html_body = self.build_html(metrics_html)
        
        if dry_run:
            preview_path = self.base_dir / "preview.html"
            preview_path.write_text(html_body, encoding='utf-8')
            self.logger.info(f"Preview saved to {preview_path}")
            
            # Open in browser for testing
            import webbrowser
            webbrowser.open(f'file://{preview_path.absolute()}')
            return
        
        # 6. Outlook Integration
        try:
            outlook = win32.Dispatch("Outlook.Application")
            mail = outlook.CreateItem(0)
            mail.To = self.default_to
            if self.default_cc:
                mail.CC = self.default_cc
            mail.Subject = f"Production OTD Report - {datetime.now():%Y-%m-%d}"
            
            # Attach both images with Content IDs
            for path, cid in [(path_weekly, "weekly_chart"), (path_ytd, "ytd_chart")]:
                if path and Path(path).exists():
                    attachment = mail.Attachments.Add(str(path))
                    attachment.PropertyAccessor.SetProperty(
                        "http://schemas.microsoft.com/mapi/proptag/0x3712001F", cid
                    )
            
            mail.HTMLBody = html_body
            mail.Send()
            
            self.logger.info("Email sent successfully")
        
        except Exception as e:
            self.logger.error(f"Failed to send email: {e}")
            raise


# ----------------------------------------------------
# ENTRYPOINT
# ----------------------------------------------------
if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Send YTD Production Delivery Report")
    parser.add_argument("--dry-run", action="store_true", help="Generate preview.html instead of sending")
    args = parser.parse_args()
    
    mailer = OnTimeDeliveryMailer()
    mailer.send(dry_run=args.dry_run)