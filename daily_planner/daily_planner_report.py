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
    
    EXCLUDED_PROCESSES = ('Farm Out', 'Finished Good', 'Corrugator', 'Elitron', 'United Rotary 66x113 4 Colour', 'TableSaw', 'Nozomi Press Approval', 'Langston Saturn 50x110', 'Haire Gluer', 'Eterna',
                          'Stax Third Party Diecutting', 'Pack & Protect A-1', 'Astrapac - Glue', 'Bobst Specialty Gluer 115"', 'Slitter 90"', 'Stripping',
                          'Pack & Protect A-2','Pack & Protect B-1','Pack & Protect B-2', 'Pack & Protect D-1', 'Colex ICutter', 'Bundling', 'Boxxer - James - co-packing', 'Box King',
                          'Pack & Protect C-1','Pack & Protect C-2','Pack & Protect C-3')
    EXCLUDED_PROCESS_ID = (168,69)
    
    DEFAULT_TABLE_WIDTH = 760
    SUMMARY_FIRST_COL_WIDTH = 250
    PROCESSES_COL_WIDTH = 250
    PLANNED_ORDERS_PROCESS_COL_WIDTH = 150
    PLANNED_ORDERS_SQFT_COL_WIDTH = 50
    PLANNED_ORDERS_TIME_COL_WIDTH = 50
    PLANNED_ORDERS_INK_COL_WIDTH = 110
    PLANNED_ORDERS_MATERIAL_COL_WIDTH = 100
    PLANNED_ORDERS_TOOLING_COL_WIDTH = 110
    PLANNED_ORDERS_CUSTOMER_COL_WIDTH = 100
    
    HEADER_BG_COLOR = HexColor("#FAFAFA")
    ALT_ROW_COLOR = HexColor("#F7F7F7")
    QW_TEXT_COLOR = HexColor("#D55E00")
    RISK_TEXT_COLOR = HexColor("#BABABA")
    
    CHART_DPI = 150
    CHART_WIDTH = 700
    CHART_HEIGHT = 300
    
    DATE_FORMAT = "%Y-%m-%d"
    TIMESTAMP_FORMAT = "%H%M"


class DailyPlannerReport:
    """
    Daily Planner PDF generator with comprehensive exception handling.
    """

    def __init__(
        self, 
        db_path: str, 
        planned_date: Optional[str] = None, 
        output_dir: Optional[str] = None, 
        chart_figs: Optional[List] = None,
        include_trend_charts: bool = False
    ):
        """Initialize the Daily Planner Report generator."""
        if not os.path.exists(db_path):
            raise FileNotFoundError(f"Database not found: {db_path}")
        
        self.db_path = db_path
        self.planned_date = planned_date or datetime.today().strftime(DailyPlannerConfig.DATE_FORMAT)
        self._validate_date_format(self.planned_date)
        
        self.output_dir = output_dir or os.getcwd()
        try:
            os.makedirs(self.output_dir, exist_ok=True)
        except PermissionError as e:
            raise PermissionError(f"Cannot create output directory {self.output_dir}: {e}")
        except Exception as e:
            raise Exception(f"Failed to create output directory: {e}")
        
        self.conn: Optional[sqlite3.Connection] = None
        self.holiday_dates: set = set()
        self.next_day: Optional[str] = None
        self.pdf_path: Optional[str] = None
        self.chart_figs: List = chart_figs or []
        self.include_trend_charts: bool = include_trend_charts

    @staticmethod
    def _validate_date_format(date_str: str) -> None:
        """Validate date string format."""
        try:
            datetime.strptime(date_str, DailyPlannerConfig.DATE_FORMAT)
        except ValueError as e:
            raise ValueError(
                f"Invalid date format: {date_str}. Expected {DailyPlannerConfig.DATE_FORMAT}"
            ) from e

    def connect(self) -> None:
        """Establish database connection with error handling."""
        try:
            self.conn = sqlite3.connect(self.db_path)
            logger.info(f"Connected to database: {self.db_path}")
        except sqlite3.OperationalError as e:
            logger.error(f"Cannot open database file: {e}")
            raise sqlite3.OperationalError(f"Database connection failed: {e}")
        except sqlite3.Error as e:
            logger.error(f"SQLite error during connection: {e}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error connecting to database: {e}")
            raise

    def load_holidays(self) -> None:
        """Load holiday dates from the database."""
        try:
            query = "SELECT date FROM holiday"
            df = pd.read_sql_query(query, self.conn)
            self.holiday_dates = set(df["date"].tolist())
            logger.info(f"Loaded {len(self.holiday_dates)} holiday dates")
        except sqlite3.OperationalError as e:
            logger.warning(f"Holiday table not found: {e}. Proceeding without holidays.")
            self.holiday_dates = set()
        except sqlite3.Error as e:
            logger.warning(f"Database error loading holidays: {e}. Proceeding without holidays.")
            self.holiday_dates = set()
        except pd.errors.DatabaseError as e:
            logger.warning(f"Pandas database error: {e}. Proceeding without holidays.")
            self.holiday_dates = set()
        except Exception as e:
            logger.warning(f"Unexpected error loading holidays: {e}. Proceeding without holidays.")
            self.holiday_dates = set()

    def next_working_day(self, date_str: str) -> str:
        """Calculate the next working day (excluding weekends and holidays)."""
        try:
            d = datetime.strptime(date_str, DailyPlannerConfig.DATE_FORMAT).date()
            next_day = d + timedelta(days=1)
            
            max_iterations = 30  # Prevent infinite loop
            iterations = 0
            
            while (next_day.weekday() >= 5 or 
                   next_day.strftime(DailyPlannerConfig.DATE_FORMAT) in self.holiday_dates):
                next_day += timedelta(days=1)
                iterations += 1
                if iterations >= max_iterations:
                    logger.warning(f"Could not find working day within {max_iterations} days")
                    break
            
            return next_day.strftime(DailyPlannerConfig.DATE_FORMAT)
        except ValueError as e:
            logger.error(f"Invalid date format in next_working_day: {e}")
            raise
        except Exception as e:
            logger.error(f"Error calculating next working day: {e}")
            raise

    def get_summary(self) -> pd.DataFrame:
        """Query summary data by process for the planned date."""
        try:
            query = """
            SELECT 
                r.process_nme AS "Process Name",
                COUNT(r.order_id) AS "# of Orders Due",
                SUM(r.msf) AS "Total MSF",
                SUM(r.est_run_speed) AS Time,
                '' AS "Resource",
                '' AS "Material",
                '' AS "Shift"
            FROM order_routing r
            WHERE DATE(substr(r.schedule_dte,1,10)) = ?
            AND r.process_nme NOT IN ({})
            GROUP BY r.process_nme
            ORDER BY r.process_nme
            """.format(','.join(['?'] * len(DailyPlannerConfig.EXCLUDED_PROCESSES)))
            
            params = [self.planned_date] + list(DailyPlannerConfig.EXCLUDED_PROCESSES)
            df = pd.read_sql_query(query, self.conn, params=params)
            
            #format number with commas
            if not df.empty:
                if "Total MSF" in df.columns:
                    df["Total MSF"] = df["Total MSF"].fillna(0).astype(int).map("{:,}".format)
                if "Time" in df.columns:
                    df["Time"] = df["Time"].fillna(0).astype(int).apply(lambda x: f"{x // 60:02d}:{x % 60:02d}")
            
            logger.info(f"Retrieved {len(df)} process summaries")
            return df
            
        except sqlite3.OperationalError as e:
            logger.error(f"Table 'order_routing' not found or query failed: {e}")
            return pd.DataFrame()
        except sqlite3.Error as e:
            logger.error(f"Database error in get_summary: {e}")
            return pd.DataFrame()
        except pd.errors.DatabaseError as e:
            logger.error(f"Pandas database error in get_summary: {e}")
            return pd.DataFrame()
        except Exception as e:
            logger.error(f"Unexpected error in get_summary: {e}")
            return pd.DataFrame()

    def get_order_details(self, today_processes: Tuple[str, ...]) -> pd.DataFrame:
        """Query order details for processes scheduled today."""
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
            WHERE date(substr(r.scheduled_dte,1,10)) = ?
              AND r.process_id NOT IN ({','.join(['?'] * len(DailyPlannerConfig.EXCLUDED_PROCESS_ID))})
              AND r.process_nme IN ({placeholders})
              AND r.process_nme NOT IN ({','.join(['?'] * len(DailyPlannerConfig.EXCLUDED_PROCESSES))})
            GROUP BY r.order_id, r.order_line_nbr
            ORDER BY r.order_id, r.order_line_nbr
            """
            
            params = (
                [self.next_day]
                + list(DailyPlannerConfig.EXCLUDED_PROCESS_ID)
                + list(today_processes)
                + list(DailyPlannerConfig.EXCLUDED_PROCESSES)
            )
            
            df = pd.read_sql_query(query, self.conn, params=params)
            logger.info(f"Retrieved {len(df)} order details for next day")
            return df
            
        except sqlite3.OperationalError as e:
            logger.error(f"Query failed in get_order_details: {e}")
            return pd.DataFrame()
        except sqlite3.Error as e:
            logger.error(f"Database error in get_order_details: {e}")
            return pd.DataFrame()
        except Exception as e:
            logger.error(f"Unexpected error in get_order_details: {e}")
            return pd.DataFrame()

    def get_orders_on_planned_date(self) -> pd.DataFrame:
        """Query all orders scheduled on the planned date."""
        try:
            query = """
            SELECT 
                r.order_id || '-' || r.order_line_nbr AS "Order #",
                r.short_name AS "Customer",
                r.process_nme AS "Process",
                r.msf AS "SQFT",
                r.est_run_speed AS "Time",
                r.receipt_status_with_location AS "Material",
                CASE 
                    WHEN r.process_nme LIKE 'United%' OR r.process_nme LIKE 'Langston%' 
                    THEN r.ink_dsc1 
                    ELSE '' 
                END AS "Ink",
                r.tooling_dsc AS "Tooling"
            FROM order_routing r
            WHERE date(substr(r.schedule_dte,1,10)) = ?
              AND r.process_nme NOT IN ({})
            GROUP BY r.process_id, r.order_id, r.order_line_nbr
            ORDER BY r.process_nme, r.order_id, r.order_line_nbr
            """.format(','.join(['?'] * len(DailyPlannerConfig.EXCLUDED_PROCESSES)))
            
            params = [self.planned_date] + list(DailyPlannerConfig.EXCLUDED_PROCESSES)
            df = pd.read_sql_query(query, self.conn, params=params)
            
            if not df.empty:
                if "SQFT" in df.columns:
                    df["SQFT"] = df["SQFT"].fillna(0).astype(int).map("{:,}".format)
                
                if "Ink" in df.columns:
                    df["Ink"] = df["Ink"].fillna("").apply(
                        lambda x: x.replace(",", "\n") if isinstance(x, str) else x
                    )
                
                if "Time" in df.columns:
                    df["Time"] = df["Time"].fillna(0).astype(int).apply(lambda x: f"{x // 60:02d}:{x % 60:02d}")

                if "Material" in df.columns:
                    df["Material"] = df["Material"].fillna("").apply(
                        lambda x: "" if x == "No P.O." else x
                    )
            
            logger.info(f"Retrieved {len(df)} orders scheduled on planned date")
            return df
            
        except sqlite3.Error as e:
            logger.error(f"Database error in get_orders_on_planned_date: {e}")
            return pd.DataFrame()
        except Exception as e:
            logger.error(f"Unexpected error in get_orders_on_planned_date: {e}")
            return pd.DataFrame()

    def _generate_trend_charts(self) -> None:
        """Generate 20-day process trend charts."""
        try:
            logger.info("=" * 60)
            logger.info("STARTING TREND CHART GENERATION")
            logger.info("=" * 60)
            
            try:
                from daily_planner_chart import ProcessTrendChart
                logger.info("✅ ProcessTrendChart imported")
            except ImportError as e:
                logger.error(f"❌ ProcessTrendChart module not found: {e}")
                logger.warning("Continuing without trend charts")
                return
            
            try:
                logger.info(f"Creating ProcessTrendChart with db_path={self.db_path}, start_date={self.planned_date}")
                chart_gen = ProcessTrendChart(
                    db_path=self.db_path,
                    start_date=self.planned_date
                )
                logger.info("✅ ProcessTrendChart instance created")
                
                logger.info("Calling chart_gen.generate()...")
                trend_charts = chart_gen.generate()
                logger.info(f"✅ chart_gen.generate() returned: {type(trend_charts)}")
                
                if not trend_charts:
                    logger.warning("❌ No trend charts were generated (empty dict)")
                    return
                
                logger.info(f"✅ Received {len(trend_charts)} trend charts")
                
                charts_added = 0
                for process_name, fig in trend_charts.items():
                    if fig is not None:
                        logger.info(f"  Adding chart: {process_name} (type: {type(fig)})")
                        self.chart_figs.append(fig)
                        charts_added += 1
                    else:
                        logger.warning(f"  Skipping {process_name}: figure is None")
                
                logger.info(f"✅ Added {charts_added} charts to self.chart_figs")
                logger.info(f"✅ Total charts in self.chart_figs: {len(self.chart_figs)}")
                logger.info("=" * 60)
                
            except FileNotFoundError as e:
                logger.error(f"❌ Database file not found for trend charts: {e}")
                logger.warning("Continuing without trend charts")
            except Exception as e:
                logger.error(f"❌ Error generating trend charts: {e}", exc_info=True)
                logger.warning("Continuing without trend charts")
                
        except Exception as e:
            logger.error(f"❌ Unexpected error in _generate_trend_charts: {e}", exc_info=True)
            logger.warning("Continuing without trend charts")

    @staticmethod
    def calc_col_widths_summary(df: pd.DataFrame, 
                                first_col_width: int = DailyPlannerConfig.SUMMARY_FIRST_COL_WIDTH,
                                total_width: int = DailyPlannerConfig.DEFAULT_TABLE_WIDTH) -> List[float]:
        """Calculate column widths for summary table."""
        remaining_width = total_width - first_col_width
        other_cols = len(df.columns) - 1
        other_width = remaining_width / other_cols if other_cols > 0 else remaining_width
        return [first_col_width] + [other_width] * other_cols

    @staticmethod
    def calc_col_widths_order_details(df: pd.DataFrame,
                                      processes_col: str = "Processes",
                                      processes_width: int = DailyPlannerConfig.PROCESSES_COL_WIDTH,
                                      total_width: int = DailyPlannerConfig.DEFAULT_TABLE_WIDTH) -> List[float]:
        """Calculate column widths for order details table."""
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
        """Calculate column widths for planned orders table."""
        if df.empty:
            return []
        
        total_width = DailyPlannerConfig.DEFAULT_TABLE_WIDTH
        process_width = DailyPlannerConfig.PLANNED_ORDERS_PROCESS_COL_WIDTH
        sqft_width = DailyPlannerConfig.PLANNED_ORDERS_SQFT_COL_WIDTH
        time_width = DailyPlannerConfig.PLANNED_ORDERS_TIME_COL_WIDTH
        material_width = DailyPlannerConfig.PLANNED_ORDERS_MATERIAL_COL_WIDTH
        ink_width = DailyPlannerConfig.PLANNED_ORDERS_INK_COL_WIDTH
        tooling_width = DailyPlannerConfig.PLANNED_ORDERS_TOOLING_COL_WIDTH
        customer_width = DailyPlannerConfig.PLANNED_ORDERS_CUSTOMER_COL_WIDTH
        
        remaining_width = (total_width - process_width - sqft_width - time_width - material_width - 
                          ink_width - tooling_width - customer_width)
        order_col_width = remaining_width
        
        widths = []
        for col in df.columns:
            if col == "Process":
                widths.append(process_width)
            elif col == "SQFT":
                widths.append(sqft_width)
            elif col == "Time":
                widths.append(time_width)
            elif col == "Material":
                widths.append(material_width)
            elif col == "Ink":
                widths.append(ink_width)
            elif col == "Tooling":
                widths.append(tooling_width)
            elif col == "Customer":
                widths.append(customer_width)
            else:
                widths.append(order_col_width)
        
        return widths

    def build_pdf(self, summary_df: pd.DataFrame, 
                  details_df: pd.DataFrame, 
                  planned_orders_df: pd.DataFrame) -> None:
        """Build the PDF document with all sections."""
        try:
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

            title_style = ParagraphStyle(name="TitleStyle", parent=styles["Title"], fontSize=16)
            heading_style = ParagraphStyle(name="HeadingStyle", parent=styles["Heading2"], fontSize=16)
            footer_style = ParagraphStyle(name="Footer", parent=styles["Normal"], fontSize=14)

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
                    ("ALIGN", (2, 1), (3, -1), "RIGHT")
                ]))
                elements.append(table)
            else:
                elements.append(Paragraph("No summary data available.", styles["Normal"]))
            elements.append(Spacer(1, 18))

            # Order Details
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

            # Planned Orders
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
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("ALIGN", (3, 1), (4, -1), "RIGHT"),
                ]))
                elements.append(table)
            else:
                elements.append(Paragraph(f"No orders scheduled.", styles["Normal"]))
            elements.append(Spacer(1, 18))

            # Risk Assessment
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

            # Footer
            elements.append(Paragraph("Date: ____________________", footer_style))
            elements.append(Spacer(1, 12))
            elements.append(Paragraph("Plan approved by: ____________________", footer_style))

            # CRITICAL: Add charts AFTER all other content
            logger.info(f"Chart count before adding to PDF: {len(self.chart_figs)}")
            if self.chart_figs and len(self.chart_figs) > 0:
                logger.info("Adding page break before charts")
                from reportlab.platypus import PageBreak
                elements.append(PageBreak())
                elements.append(Spacer(1, 12))
                elements.append(Paragraph("<b>Process Trend Charts (20-Day Forecast)</b>", heading_style))
                elements.append(Spacer(1, 12))
                self._add_charts_to_elements(elements)
            else:
                logger.info("No charts to add to PDF")

            doc.build(elements)
            logger.info(f"PDF generated: {self.pdf_path}")
            
        except PermissionError as e:
            logger.error(f"Cannot write PDF file (permission denied): {e}")
            raise PermissionError(f"Cannot save PDF to {self.pdf_path}: {e}")
        except Exception as e:
            logger.error(f"Error building PDF: {e}", exc_info=True)
            raise

    def _add_charts_to_elements(self, elements: List) -> None:
        """Add chart figures to PDF elements."""
        if not self.chart_figs:
            logger.info("No charts to add to PDF")
            return
        
        logger.info(f"Adding {len(self.chart_figs)} charts to PDF")
        
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
                
                # Add image to PDF elements
                img = Image(
                    img_buf, 
                    width=DailyPlannerConfig.CHART_WIDTH, 
                    height=DailyPlannerConfig.CHART_HEIGHT
                )
                elements.append(img)
                elements.append(Spacer(1, 12))
                
                logger.info(f"✅ Added chart {i+1}/{len(self.chart_figs)} to PDF")
                
                # Close figure to free memory
                try:
                    import matplotlib.pyplot as plt
                    plt.close(fig)
                except Exception as e:
                    logger.warning(f"Could not close figure {i+1}: {e}")
                
            except Exception as e:
                logger.error(f"Failed to add chart {i+1}: {e}", exc_info=True)

    def generate(self) -> Optional[str]:
        """Generate the complete daily planner report."""
        conn_opened = False
        try:
            logger.info(f"=" * 70)
            logger.info(f"STARTING GENERATE() for {self.planned_date}")
            logger.info(f"include_trend_charts = {self.include_trend_charts}")
            logger.info(f"chart_figs count at start = {len(self.chart_figs)}")
            logger.info(f"=" * 70)
            
            self.connect()
            conn_opened = True
            self.load_holidays()
            
            try:
                self.next_day = self.next_working_day(self.planned_date)
            except Exception as e:
                logger.error(f"Failed to calculate next working day: {e}")
                self.next_day = self.planned_date
            
            # Generate trend charts BEFORE getting data
            if self.include_trend_charts:
                logger.info("=" * 70)
                logger.info("TREND CHARTS ENABLED - Calling _generate_trend_charts()")
                logger.info(f"chart_figs count BEFORE: {len(self.chart_figs)}")
                self._generate_trend_charts()
                logger.info(f"chart_figs count AFTER: {len(self.chart_figs)}")
                logger.info("=" * 70)
            else:
                logger.info("Trend charts not requested")
            
            logger.info(f"Getting summary data...")
            summary_df = self.get_summary()
            today_processes = tuple(summary_df["Process Name"].tolist()) if not summary_df.empty else ()
            
            if not today_processes:
                logger.warning("No processes scheduled for this date")
                today_processes = ("NO_PROCESS",)
            
            logger.info(f"Getting order details...")
            details_df = self.get_order_details(today_processes)
            
            logger.info(f"Getting planned orders...")
            planned_orders_df = self.get_orders_on_planned_date()
            
            # CRITICAL: Check chart_figs count BEFORE building PDF
            logger.info("=" * 70)
            logger.info(f"BEFORE build_pdf() - chart_figs count = {len(self.chart_figs)}")
            logger.info("=" * 70)
            
            # Build PDF with charts
            self.build_pdf(summary_df, details_df, planned_orders_df)
            
            logger.info(f"=" * 70)
            logger.info(f"GENERATE() COMPLETED - PDF: {self.pdf_path}")
            logger.info(f"=" * 70)
            
            return self.pdf_path
            
        except FileNotFoundError as e:
            logger.error(f"Required file not found: {e}")
            raise
        except sqlite3.Error as e:
            logger.error(f"Database error: {e}", exc_info=True)
            raise
        except PermissionError as e:
            logger.error(f"Permission denied: {e}")
            raise
        except Exception as e:
            logger.error(f"Failed to generate report: {e}", exc_info=True)
            raise
        finally:
            if conn_opened and self.conn:
                try:
                    self.conn.close()
                    logger.info("Database connection closed")
                except Exception as e:
                    logger.error(f"Error closing database: {e}")


if __name__ == "__main__":
    try:
        planner = DailyPlannerReport(
            db_path="prod_db.db",
            planned_date="2025-11-11",
            output_dir="./reports",
            include_trend_charts=True
        )
        pdf_path = planner.generate()
        print(f"✅ Report generated: {pdf_path}")
        
    except FileNotFoundError as e:
        print(f"❌ File not found: {e}")
    except sqlite3.Error as e:
        print(f"❌ Database error: {e}")
    except PermissionError as e:
        print(f"❌ Permission denied: {e}")
    except Exception as e:
        print(f"❌ Failed to generate report: {e}")