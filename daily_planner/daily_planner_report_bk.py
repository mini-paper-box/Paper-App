# daily_planner_report.py
import os
import sqlite3
import pandas as pd
import logging
from datetime import datetime, timedelta
from typing import List, Optional, Tuple
from reportlab.lib import colors
from reportlab.lib.colors import HexColor
from reportlab.lib.pagesizes import landscape, A4
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from io import BytesIO


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class DailyPlannerConfig:
    """Configuration constants for the Daily Planner Report."""
    
    # Process exclusions
    EXCLUDED_PROCESSES = ('Farm Out', 'Finished Good')
    EXCLUDED_PROCESS_ID = 168
    
    # Table dimensions
    DEFAULT_TABLE_WIDTH = 760
    SUMMARY_FIRST_COL_WIDTH = 250
    PROCESSES_COL_WIDTH = 250
    PLANNED_ORDERS_PROCESS_COL_WIDTH = 200
    PLANNED_ORDERS_SQFT_COL_WIDTH = 60
    PLANNED_ORDERS_INK_COL_WIDTH = 150
    
    # Colors
    HEADER_BG_COLOR = HexColor("#FAFAFA")
    ALT_ROW_COLOR = HexColor("#F7F7F7")
    QW_TEXT_COLOR = HexColor("#D55E00")
    RISK_TEXT_COLOR = HexColor("#BABABA")
    
    # Chart settings
    CHART_DPI = 150
    CHART_WIDTH = 700
    CHART_HEIGHT = 300
    
    # Date format
    DATE_FORMAT = "%Y-%m-%d"
    TIMESTAMP_FORMAT = "%H%M"


class DailyPlannerReport:
    """
    Daily Planner PDF generator for a single date.
    
    Generates a comprehensive daily production planning report including:
    - Summary by process
    - Order details
    - Risk assessment section
    - Optional visualization charts
    
    Attributes:
        db_path (str): Path to the SQLite database
        planned_date (str): Date for the report in YYYY-MM-DD format
        output_dir (str): Directory for PDF output
        chart_figs (List): Optional list of Matplotlib figure objects
    """

    def __init__(
        self, 
        db_path: str, 
        planned_date: Optional[str] = None, 
        output_dir: Optional[str] = None, 
        chart_figs: Optional[List] = None
    ):
        """
        Initialize the Daily Planner Report generator.
        
        Args:
            db_path: Path to the SQLite database
            planned_date: Report date (YYYY-MM-DD). Defaults to today.
            output_dir: Output directory. Defaults to current directory.
            chart_figs: List of Matplotlib figures to append. Defaults to empty list.
            
        Raises:
            ValueError: If planned_date format is invalid
            FileNotFoundError: If db_path doesn't exist
        """
        if not os.path.exists(db_path):
            raise FileNotFoundError(f"Database not found: {db_path}")
        
        self.db_path = db_path
        self.planned_date = planned_date or datetime.today().strftime(DailyPlannerConfig.DATE_FORMAT)
        self._validate_date_format(self.planned_date)
        
        self.output_dir = output_dir or os.getcwd()
        os.makedirs(self.output_dir, exist_ok=True)
        
        self.conn: Optional[sqlite3.Connection] = None
        self.holiday_dates: set = set()
        self.next_day: Optional[str] = None
        self.pdf_path: Optional[str] = None
        self.chart_figs: List = chart_figs or []

    @staticmethod
    def _validate_date_format(date_str: str) -> None:
        """
        Validate date string format.
        
        Args:
            date_str: Date string to validate
            
        Raises:
            ValueError: If date format is invalid
        """
        try:
            datetime.strptime(date_str, DailyPlannerConfig.DATE_FORMAT)
        except ValueError as e:
            raise ValueError(
                f"Invalid date format: {date_str}. Expected {DailyPlannerConfig.DATE_FORMAT}"
            ) from e

    # -----------------------------
    # Database connection
    # -----------------------------
    def connect(self) -> None:
        """Establish database connection."""
        try:
            self.conn = sqlite3.connect(self.db_path)
            logger.info(f"Connected to database: {self.db_path}")
        except sqlite3.Error as e:
            logger.error(f"Failed to connect to database: {e}")
            raise

    # -----------------------------
    # Load holiday dates
    # -----------------------------
    def load_holidays(self) -> None:
        """Load holiday dates from the database."""
        try:
            query = "SELECT date FROM holiday"
            df = pd.read_sql_query(query, self.conn)
            self.holiday_dates = set(df["date"].tolist())
            logger.info(f"Loaded {len(self.holiday_dates)} holiday dates")
        except sqlite3.Error as e:
            logger.warning(f"Could not load holidays: {e}. Proceeding without holiday data.")
            self.holiday_dates = set()
        except Exception as e:
            logger.warning(f"Unexpected error loading holidays: {e}")
            self.holiday_dates = set()

    # -----------------------------
    # Compute next working day
    # -----------------------------
    def next_working_day(self, date_str: str) -> str:
        """
        Calculate the next working day (excluding weekends and holidays).
        
        Args:
            date_str: Starting date in YYYY-MM-DD format
            
        Returns:
            Next working day in YYYY-MM-DD format
        """
        d = datetime.strptime(date_str, DailyPlannerConfig.DATE_FORMAT).date()
        next_day = d + timedelta(days=1)
        
        # Skip weekends (5=Saturday, 6=Sunday) and holidays
        while (next_day.weekday() >= 5 or 
               next_day.strftime(DailyPlannerConfig.DATE_FORMAT) in self.holiday_dates):
            next_day += timedelta(days=1)
        
        return next_day.strftime(DailyPlannerConfig.DATE_FORMAT)

    # -----------------------------
    # Summary table query
    # -----------------------------
    def get_summary(self) -> pd.DataFrame:
        """
        Query summary data by process for the planned date.
        
        Returns:
            DataFrame with process summary information
        """
        try:
            query = """
            SELECT 
                ws.process_nme AS "Process Name",
                COUNT(ws.order_id) AS "# of Orders Due",
                SUM(r.msf) AS "Total MSF",
                '' AS "Resource",
                '' AS "Material",
                '' AS "Shift"
            FROM workback_schedule ws
            LEFT JOIN order_routing r
                ON ws.order_id = r.order_id
               AND ws.order_line_nbr = r.order_line_nbr
               AND ws.process_id = r.process_id
            WHERE date(substr(ws.planned_start,1,10)) = ?
              AND ws.process_nme NOT IN ({})
            GROUP BY ws.process_nme
            ORDER BY ws.process_nme
            """.format(','.join(['?'] * len(DailyPlannerConfig.EXCLUDED_PROCESSES)))
            
            params = [self.planned_date] + list(DailyPlannerConfig.EXCLUDED_PROCESSES)
            df = pd.read_sql_query(query, self.conn, params=params)
            
            if not df.empty:
                df["Total MSF"] = df["Total MSF"].fillna(0).astype(int).map("{:,}".format)
            
            logger.info(f"Retrieved {len(df)} process summaries")
            return df
            
        except sqlite3.Error as e:
            logger.error(f"Database error in get_summary: {e}")
            return pd.DataFrame()
        except Exception as e:
            logger.error(f"Unexpected error in get_summary: {e}")
            return pd.DataFrame()

    # -----------------------------
    # Order details query (Next Day)
    # -----------------------------
    def get_order_details(self, today_processes: Tuple[str, ...]) -> pd.DataFrame:
        """
        Query order details for processes scheduled today, showing orders due the next working day.
        
        Args:
            today_processes: Tuple of process names to filter by
            
        Returns:
            DataFrame with order details for next day
        """
        if not today_processes:
            logger.info("No processes scheduled for today")
            return pd.DataFrame()
        
        try:
            placeholders = ','.join(['?'] * len(today_processes))
            query = f"""
            SELECT 
                r.order_id || '-' || r.order_line_nbr AS "Order #",
                r.short_name AS "Customer",
                r.all_routing AS "Processes",
                '' AS "Status",
                '' AS "Note",
                CASE WHEN r.quality_watch = 1 THEN 'YES' ELSE '' END AS "QW"
            FROM order_routing r
            WHERE date(substr(r.requested_dte,1,10)) = ?
              AND r.process_id != ?
              AND r.process_nme IN ({placeholders})
              AND r.process_nme NOT IN ({','.join(['?'] * len(DailyPlannerConfig.EXCLUDED_PROCESSES))})
            GROUP BY r.order_id, r.order_line_nbr
            ORDER BY r.order_id, r.order_line_nbr
            """
            
            params = ([self.next_day, DailyPlannerConfig.EXCLUDED_PROCESS_ID] + 
                     list(today_processes) + 
                     list(DailyPlannerConfig.EXCLUDED_PROCESSES))
            
            df = pd.read_sql_query(query, self.conn, params=params)
            logger.info(f"Retrieved {len(df)} order details for next day")
            return df
            
        except sqlite3.Error as e:
            logger.error(f"Database error in get_order_details: {e}")
            return pd.DataFrame()
        except Exception as e:
            logger.error(f"Unexpected error in get_order_details: {e}")
            return pd.DataFrame()

    # -----------------------------
    # Orders scheduled ON planned date
    # -----------------------------
    def get_orders_on_planned_date(self) -> pd.DataFrame:
        """
        Query all orders scheduled on the planned date.
        Only shows ink for processes starting with 'United' or 'Langston'.
        
        Returns:
            DataFrame with orders scheduled for the planned date
        """
        try:
            query = """
            SELECT 
                r.order_id || '-' || r.order_line_nbr AS "Order #",
                r.short_name AS "Customer",
                ws.process_nme AS "Process",
                r2.msf AS "SQFT",
                r.receipt_status AS "Material",
                CASE 
                    WHEN ws.process_nme LIKE 'United%' OR ws.process_nme LIKE 'Langston%' 
                    THEN r.ink_dsc1 
                    ELSE '' 
                END AS "Ink",
                '' AS "Note"
            FROM order_routing r
            JOIN workback_schedule ws
                ON r.order_id = ws.order_id
               AND r.order_line_nbr = ws.order_line_nbr
            LEFT JOIN order_routing r2
                ON ws.order_id = r2.order_id
               AND ws.order_line_nbr = r2.order_line_nbr
               AND ws.process_id = r2.process_id
            WHERE date(substr(ws.planned_start,1,10)) = ?
              AND ws.process_nme NOT IN ({})
            GROUP BY r.order_id, r.order_line_nbr
            ORDER BY ws.process_nme, r.order_id, r.order_line_nbr
            """.format(','.join(['?'] * len(DailyPlannerConfig.EXCLUDED_PROCESSES)))
            
            params = [self.planned_date] + list(DailyPlannerConfig.EXCLUDED_PROCESSES)
            df = pd.read_sql_query(query, self.conn, params=params)
            
            # Format SQFT column
            if not df.empty and "SQFT" in df.columns:
                df["SQFT"] = df["SQFT"].fillna(0).astype(int).map("{:,}".format)
            
            # Format Ink column: replace commas with new lines
            if not df.empty and "Ink" in df.columns:
                df["Ink"] = df["Ink"].fillna("").apply(lambda x: x.replace(",", "\n") if isinstance(x, str) else x)
            
            # Replace "No P.O." with empty string in Material column
            if not df.empty and "Material" in df.columns:
                df["Material"] = df["Material"].fillna("").apply(lambda x: "" if x == "No P.O." else x)
            
            logger.info(f"Retrieved {len(df)} orders scheduled on planned date")
            return df
            
        except sqlite3.Error as e:
            logger.error(f"Database error in get_orders_on_planned_date: {e}")
            return pd.DataFrame()
        except Exception as e:
            logger.error(f"Unexpected error in get_orders_on_planned_date: {e}")
            return pd.DataFrame()

    # -----------------------------
    # Column width helpers
    # -----------------------------
    @staticmethod
    def calc_col_widths_summary(
        df: pd.DataFrame, 
        first_col_width: int = DailyPlannerConfig.SUMMARY_FIRST_COL_WIDTH,
        total_width: int = DailyPlannerConfig.DEFAULT_TABLE_WIDTH
    ) -> List[float]:
        """
        Calculate column widths for summary table.
        
        Args:
            df: DataFrame to calculate widths for
            first_col_width: Width of first column
            total_width: Total table width
            
        Returns:
            List of column widths
        """
        remaining_width = total_width - first_col_width
        other_cols = len(df.columns) - 1
        other_width = remaining_width / other_cols if other_cols > 0 else remaining_width
        return [first_col_width] + [other_width] * other_cols

    @staticmethod
    def calc_col_widths_order_details(
        df: pd.DataFrame,
        processes_col: str = "Processes",
        processes_width: int = DailyPlannerConfig.PROCESSES_COL_WIDTH,
        total_width: int = DailyPlannerConfig.DEFAULT_TABLE_WIDTH
    ) -> List[float]:
        """
        Calculate column widths for order details table.
        
        Args:
            df: DataFrame to calculate widths for
            processes_col: Name of the processes column
            processes_width: Width for processes column
            total_width: Total table width
            
        Returns:
            List of column widths
        """
        n_cols = len(df.columns)
        widths = []
        remaining_width = total_width - processes_width
        other_cols = n_cols - 1
        other_width = remaining_width / other_cols if other_cols > 0 else remaining_width
        
        for col in df.columns:
            widths.append(processes_width if col == processes_col else other_width)
        return widths

    @staticmethod
    def calc_col_widths_planned_orders(df: pd.DataFrame) -> List[float]:
        """
        Calculate column widths for orders scheduled on planned date table.
        Total width matches other tables (760px).
        Process: 200px, SQFT: 60px, Ink: 150px, remaining width distributed.
        
        Args:
            df: DataFrame to calculate widths for
            
        Returns:
            List of column widths
        """
        if df.empty:
            return []
        
        # Calculate remaining width after Process (200), SQFT (60), and Ink (150)
        # Table has 7 columns: Order #, Customer, Process, SQFT, Material, Ink, Note
        total_width = DailyPlannerConfig.DEFAULT_TABLE_WIDTH
        process_width = DailyPlannerConfig.PLANNED_ORDERS_PROCESS_COL_WIDTH
        sqft_width = DailyPlannerConfig.PLANNED_ORDERS_SQFT_COL_WIDTH
        ink_width = DailyPlannerConfig.PLANNED_ORDERS_INK_COL_WIDTH
        
        # Remaining width for 4 other columns
        remaining_width = total_width - process_width - sqft_width - ink_width
        other_col_width = remaining_width / 4  # 4 columns: Order #, Customer, Material, Note
        
        widths = []
        for col in df.columns:
            if col == "Process":
                widths.append(process_width)
            elif col == "SQFT":
                widths.append(sqft_width)
            elif col == "Ink":
                widths.append(ink_width)
            else:
                widths.append(other_col_width)
        
        return widths

    # -----------------------------
    # Build PDF
    # -----------------------------
    def build_pdf(self, summary_df: pd.DataFrame, details_df: pd.DataFrame, planned_orders_df: pd.DataFrame) -> None:
        """
        Build the PDF document with all sections.
        
        Args:
            summary_df: Summary data by process
            details_df: Order details for next working day
            planned_orders_df: Orders scheduled on the planned date
        """
        timestamp = datetime.now().strftime(DailyPlannerConfig.TIMESTAMP_FORMAT)
        self.pdf_path = os.path.join(
            self.output_dir, 
            f"Daily_Planner_{self.planned_date}_{timestamp}.pdf"
        )

        doc = SimpleDocTemplate(
            self.pdf_path,
            pagesize=landscape(A4),
            rightMargin=30,
            leftMargin=30,
            topMargin=40,
            bottomMargin=30,
        )

        styles = getSampleStyleSheet()
        elements = []

        # Custom styles
        title_style = ParagraphStyle(name="TitleStyle", parent=styles["Title"], fontSize=16)
        heading_style = ParagraphStyle(name="HeadingStyle", parent=styles["Heading2"], fontSize=16)
        footer_style = ParagraphStyle(name="Footer", parent=styles["Normal"], fontSize=14)

        # Title
        elements.append(Paragraph(f"<b>Daily Planner – {self.planned_date}</b>", title_style))
        elements.append(Spacer(1, 12))

        # Summary Table
        elements.append(Paragraph("Summary by Process", heading_style))
        if not summary_df.empty:
            data = [list(summary_df.columns)] + summary_df.values.tolist()
            table = Table(data, colWidths=self.calc_col_widths_summary(summary_df))
            table.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), DailyPlannerConfig.HEADER_BG_COLOR),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), 
                 [colors.white, DailyPlannerConfig.ALT_ROW_COLOR]),
                ("GRID", (0, 0), (-1, -1), 0.25, colors.grey),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("ALIGN", (2, 1), (2, -1), "RIGHT")
            ]))
            elements.append(table)
        else:
            elements.append(Paragraph("No summary data available for this date.", styles["Normal"]))
        elements.append(Spacer(1, 18))

        # Order Details Table (Next Day)
        elements.append(Paragraph(f"Order Details (Due {self.next_day})", heading_style))
        if not details_df.empty:
            data = [list(details_df.columns)] + details_df.values.tolist()
            table = Table(data, colWidths=self.calc_col_widths_order_details(details_df))
            table.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), DailyPlannerConfig.HEADER_BG_COLOR),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), 
                 [colors.white, DailyPlannerConfig.ALT_ROW_COLOR]),
                ("GRID", (0, 0), (-1, -1), 0.25, colors.grey),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("TEXTCOLOR", (5, 1), (5, -1), DailyPlannerConfig.QW_TEXT_COLOR),
            ]))
            elements.append(table)
        else:
            elements.append(Paragraph(f"No orders due for {self.next_day}.", styles["Normal"]))
        elements.append(Spacer(1, 18))

        # Orders Scheduled ON Planned Date
        elements.append(Paragraph(f"Orders Scheduled on {self.planned_date}", heading_style))
        if not planned_orders_df.empty:
            data = [list(planned_orders_df.columns)] + planned_orders_df.values.tolist()
            table = Table(data, colWidths=self.calc_col_widths_planned_orders(planned_orders_df))
            table.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), DailyPlannerConfig.HEADER_BG_COLOR),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), 
                 [colors.white, DailyPlannerConfig.ALT_ROW_COLOR]),
                ("GRID", (0, 0), (-1, -1), 0.25, colors.grey),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),  # Top alignment for multi-line cells
                ("ALIGN", (3, 1), (3, -1), "RIGHT"),  # Right align SQFT column
            ]))
            elements.append(table)
        else:
            elements.append(Paragraph(f"No orders scheduled on {self.planned_date}.", styles["Normal"]))
        elements.append(Spacer(1, 18))

        # Risk Assessment Table
        elements.append(Paragraph("Potential Problems / Risks", heading_style))
        risks_df = pd.DataFrame({
            "Area": ["Equipment", "Staffing", "Materials", "Logistics"],
            "Risk Description": ["", "", "", ""],
            "Impact Level (circle one)": ["Low / Med / High"] * 4,
            "Mitigation Plan": ["", "", "", ""]
        })
        data = [list(risks_df.columns)] + risks_df.values.tolist()
        table = Table(data, colWidths=self.calc_col_widths_summary(risks_df))
        table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), DailyPlannerConfig.HEADER_BG_COLOR),
            ("GRID", (0, 0), (-1, -1), 0.25, colors.grey),
            ("TEXTCOLOR", (2, 1), (2, -1), DailyPlannerConfig.RISK_TEXT_COLOR),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), 
             [colors.white, DailyPlannerConfig.ALT_ROW_COLOR]),
        ]))
        elements.append(table)
        elements.append(Spacer(1, 36))

        # Append charts at the end of the PDF
        self._add_charts_to_elements(elements)

        # Footer
        elements.append(Paragraph("Date: ____________________", footer_style))
        elements.append(Spacer(1, 12))
        elements.append(Paragraph("Plan approved by: ____________________", footer_style))

        # Build the PDF
        doc.build(elements)
        logger.info(f"PDF generated: {self.pdf_path}")
        logger.info(f"Next working day: {self.next_day}")

    def _add_charts_to_elements(self, elements: List) -> None:
        """
        Add chart figures to PDF elements and clean up.
        
        Args:
            elements: List of PDF elements to append charts to
        """
        for i, fig in enumerate(self.chart_figs):
            try:
                img_buf = BytesIO()
                fig.savefig(
                    img_buf, 
                    format="png", 
                    dpi=DailyPlannerConfig.CHART_DPI, 
                    bbox_inches='tight'
                )
                img_buf.seek(0)
                elements.append(Image(
                    img_buf, 
                    width=DailyPlannerConfig.CHART_WIDTH, 
                    height=DailyPlannerConfig.CHART_HEIGHT
                ))
                elements.append(Spacer(1, 12))
                
                # Close figure to free memory
                fig.clf()
                logger.info(f"Added chart {i+1}/{len(self.chart_figs)} to PDF")
                
            except Exception as e:
                logger.error(f"Failed to add chart {i+1}: {e}")

    # -----------------------------
    # Full workflow
    # -----------------------------
    def generate(self) -> Optional[str]:
        """
        Generate the complete daily planner report.
        
        Returns:
            Path to generated PDF file, or None if generation failed
            
        Raises:
            Exception: If critical errors occur during generation
        """
        try:
            self.connect()
            self.load_holidays()
            self.next_day = self.next_working_day(self.planned_date)
            
            summary_df = self.get_summary()
            today_processes = tuple(summary_df["Process Name"].tolist()) if not summary_df.empty else ()
            
            if not today_processes:
                logger.warning("No processes scheduled for this date")
                today_processes = ("NO_PROCESS",)
            
            details_df = self.get_order_details(today_processes)
            planned_orders_df = self.get_orders_on_planned_date()
            self.build_pdf(summary_df, details_df, planned_orders_df)
            
            return self.pdf_path
            
        except Exception as e:
            logger.error(f"Failed to generate report: {e}", exc_info=True)
            raise
        finally:
            if self.conn:
                self.conn.close()
                logger.info("Database connection closed")


# -----------------------------
# Example usage
# -----------------------------
if __name__ == "__main__":
    # Basic usage
    try:
        planner = DailyPlannerReport(
            db_path="production.db",
            planned_date="2025-10-20",
            output_dir="./reports"
        )
        pdf_path = planner.generate()
        print(f"✅ Report generated successfully: {pdf_path}")
        
    except Exception as e:
        print(f"❌ Failed to generate report: {e}")
    
    # With charts
    # import matplotlib.pyplot as plt
    # 
    # fig1, ax1 = plt.subplots()
    # ax1.plot([1, 2, 3, 4], [10, 20, 15, 25])
    # ax1.set_title("Production Trend")
    # ax1.set_xlabel("Week")
    # ax1.set_ylabel("Output (MSF)")
    # 
    # fig2, ax2 = plt.subplots()
    # ax2.bar(['Process A', 'Process B', 'Process C'], [45, 60, 38])
    # ax2.set_title("Orders by Process")
    # 
    # planner_with_charts = DailyPlannerReport(
    #     db_path="production.db",
    #     planned_date="2025-10-20",
    #     chart_figs=[fig1, fig2]
    # )
    # planner_with_charts.generate()