import sqlite3
import pandas as pd
from datetime import datetime, timedelta
import matplotlib.pyplot as plt
from matplotlib.ticker import StrMethodFormatter
from matplotlib.backends.backend_pdf import PdfPages
from typing import Dict, List, Optional
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class ProcessTrendChart:
    """
    Generates bar charts for selected processes for 20 working days
    starting from a given date, using 'order_routing.schedule_dte'.
    Charts can be returned in-memory or exported to a single PDF file.
    """

    def __init__(self, db_path: str, start_date: Optional[str] = None):
        self.db_path = db_path
        self.start_date = start_date or datetime.today().strftime("%Y-%m-%d")
        self.conn = None
        self.holiday_dates = set()
        self.target_processes = ["Langston%", "United%", "Nozomi%", "Eterna%", "Bobst%"]
        self.df = pd.DataFrame()
        self.processes = []
        self.days = []
        
        self._validate_date(self.start_date)

    def __enter__(self):
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    @staticmethod
    def _validate_date(date_str: str) -> None:
        """Validate date format."""
        try:
            datetime.strptime(date_str, "%Y-%m-%d")
        except ValueError as e:
            raise ValueError(f"Invalid date format '{date_str}'. Expected YYYY-MM-DD.") from e

    def connect(self) -> None:
        """Establish database connection."""
        try:
            self.conn = sqlite3.connect(self.db_path)
            logger.info(f"Connected to database: {self.db_path}")
        except sqlite3.Error as e:
            logger.error(f"Failed to connect to database: {e}")
            raise

    def close(self) -> None:
        """Close database connection."""
        if self.conn:
            self.conn.close()
            logger.info("Database connection closed")

    def load_holidays(self) -> None:
        """Load holiday dates from database."""
        try:
            df = pd.read_sql_query("SELECT date FROM holiday", self.conn)
            self.holiday_dates = set(df["date"].tolist())
            logger.info(f"Loaded {len(self.holiday_dates)} holidays")
        except Exception as e:
            logger.warning(f"Failed to load holidays: {e}. Continuing without holiday data.")
            self.holiday_dates = set()

    def _is_working_day(self, date_obj) -> bool:
        """Check if a date is a working day (not weekend or holiday)."""
        return (
            date_obj.weekday() < 5 and 
            date_obj.strftime("%Y-%m-%d") not in self.holiday_dates
        )

    def next_working_day(self, date_obj) -> datetime.date:
        """Get the next working day after the given date."""
        next_day = date_obj + timedelta(days=1)
        while not self._is_working_day(next_day):
            next_day += timedelta(days=1)
        return next_day

    def get_next_20_working_days(self) -> List[str]:
        """Generate list of next 20 working days from start_date."""
        days = []
        current = datetime.strptime(self.start_date, "%Y-%m-%d").date()
        
        # Ensure start date is a working day
        while not self._is_working_day(current):
            current += timedelta(days=1)
        
        for _ in range(20):
            days.append(current.strftime("%Y-%m-%d"))
            current = self.next_working_day(current)
        
        return days

    def fetch_data(self) -> None:
        """Fetch MSF totals per process/date from order_routing table."""
        self.days = self.get_next_20_working_days()
        start_day = self.days[0]
        end_day = self.days[-1]

        # Build parameterized query to prevent SQL injection
        placeholders = " OR ".join([f"process_nme LIKE ?" for _ in self.target_processes])
        
        query = f"""
            SELECT 
                process_nme,
                date(substr(schedule_dte, 1, 10)) AS day,
                SUM(msf) AS total_msf
            FROM order_routing
            WHERE ({placeholders})
              AND day BETWEEN ? AND ?
            GROUP BY process_nme, day
            ORDER BY process_nme, day
        """

        params = self.target_processes + [start_day, end_day]
        
        try:
            df_all = pd.read_sql_query(query, self.conn, params=params)
        except Exception as e:
            logger.error(f"Failed to fetch data: {e}")
            self.df = pd.DataFrame()
            return

        if df_all.empty:
            logger.warning("No data found for given period or processes.")
            self.df = pd.DataFrame()
            return

        # Pivot data: rows = process, columns = day
        self.df = (
            df_all.pivot(index="process_nme", columns="day", values="total_msf")
            .reindex(columns=self.days, fill_value=0)
            .fillna(0)
            .astype(int)
        )
        self.processes = self.df.index.tolist()
        logger.info(f"Fetched data for {len(self.processes)} processes over {len(self.days)} days")

    def build_charts(self) -> Dict[str, plt.Figure]:
        """Build matplotlib charts for each process."""
        if self.df.empty:
            logger.warning("No data available to build charts")
            return {}

        charts = {}
        colors = plt.cm.tab10.colors

        for i, process in enumerate(self.df.index):
            color = colors[i % len(colors)]
            fig, ax = plt.subplots(figsize=(12, 5))
            values = self.df.loc[process]

            ax.bar(values.index, values.values, color=color)
            ax.set_title(f"{process} – 20-Day MSF Trend", fontsize=14, fontweight='bold')
            ax.set_xlabel("Date", fontsize=11)
            ax.set_ylabel("Total MSF", fontsize=11)

            plt.setp(ax.get_xticklabels(), rotation=45, ha='right', fontsize=9)
            ax.yaxis.set_major_formatter(StrMethodFormatter("{x:,.0f}"))
            ax.grid(axis='y', alpha=0.3, linestyle='--')

            # Label bars with values
            for j, val in enumerate(values):
                if val > 0:
                    ax.text(j, val, f"{val:,}", ha='center', va='bottom', fontsize=8)

            plt.tight_layout()
            charts[process] = fig

        return charts

    def export_to_pdf(self, output_path: str) -> None:
        """Export all charts to a single PDF file."""
        if self.df.empty:
            logger.error("No data to export. Run generate() first.")
            return

        charts = self.build_charts()
        
        try:
            with PdfPages(output_path) as pdf:
                for process, fig in charts.items():
                    pdf.savefig(fig, bbox_inches='tight')
                    plt.close(fig)
            
            logger.info(f"Exported {len(charts)} charts to PDF: {output_path}")
        except Exception as e:
            logger.error(f"Failed to export PDF: {e}")
            # Close any remaining figures
            for fig in charts.values():
                plt.close(fig)
            raise

    def generate(self) -> Dict[str, plt.Figure]:
        """Full generation workflow - returns in-memory charts."""
        try:
            self.load_holidays()
            self.fetch_data()
            
            if self.df.empty:
                return {}
            
            charts = self.build_charts()
            logger.info(f"Generated {len(charts)} in-memory charts for 20-day trends")
            return charts
            
        except Exception as e:
            logger.error(f"Error during chart generation: {e}")
            raise


# Usage example with context manager (recommended)
if __name__ == "__main__":
    db_path = r"C:\Users\sang.n\OneDrive - whitebird.ca\Paper App\prod_db.db"
    pdf_path = r"C:\Users\sang.n\OneDrive - whitebird.ca\Paper App\Process_Trend_Report.pdf"
    today = datetime.now().strftime("%Y-%m-%d")
    try:
        with ProcessTrendChart(db_path, start_date=today) as chart_gen:
            charts = chart_gen.generate()
            
            if charts:
                chart_gen.export_to_pdf(pdf_path)
                
                # If you want to display charts interactively:
                # for process, fig in charts.items():
                #     plt.show()
                
                # Close figures to free memory
                for fig in charts.values():
                    plt.close(fig)
            else:
                logger.warning("No charts generated")
                
    except Exception as e:
        logger.error(f"Application error: {e}")