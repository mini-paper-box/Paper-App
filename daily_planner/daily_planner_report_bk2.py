# daily_planner_report.py
import os
import sqlite3
import pandas as pd
from datetime import datetime, timedelta
from reportlab.lib import colors
from reportlab.lib.colors import HexColor
from reportlab.lib.pagesizes import landscape, A4
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from io import BytesIO


class DailyPlannerReport:
    """
    Daily Planner PDF generator for a single date.
    Can accept in-memory Matplotlib figures to append at the end.
    """

    def __init__(self, db_path, planned_date=None, output_dir=None, chart_figs=None):
        self.db_path = db_path
        self.planned_date = planned_date or datetime.today().strftime("%Y-%m-%d")
        self.output_dir = output_dir or os.getcwd()
        self.conn = None
        self.holiday_dates = set()
        self.next_day = None
        self.pdf_path = None
        self.chart_figs = chart_figs or []

    # -----------------------------
    # Database connection
    # -----------------------------
    def connect(self):
        self.conn = sqlite3.connect(self.db_path)

    # -----------------------------
    # Load holiday dates
    # -----------------------------
    def load_holidays(self):
        try:
            df = pd.read_sql_query("SELECT date FROM holiday", self.conn)
            self.holiday_dates = set(df["date"].tolist())
        except Exception:
            self.holiday_dates = set()

    # -----------------------------
    # Compute next working day
    # -----------------------------
    def next_working_day(self, date_str):
        d = datetime.strptime(date_str, "%Y-%m-%d").date()
        next_day = d + timedelta(days=1)
        while next_day.weekday() >= 5 or next_day.strftime("%Y-%m-%d") in self.holiday_dates:
            next_day += timedelta(days=1)
        return next_day.strftime("%Y-%m-%d")

    # -----------------------------
    # Summary table query
    # -----------------------------
    def get_summary(self):
        query = f"""
        SELECT 
            ws.process_nme AS "Process Name",
            COUNT(DISTINCT ws.order_id) AS "# of Orders Due",
            SUM(r.msf) AS "Total MSF",
            '' AS "Resource",
            '' AS "Material",
            '' AS "Shift"
        FROM workback_schedule ws
        LEFT JOIN order_routing r
            ON ws.order_id = r.order_id
           AND ws.order_line_nbr = r.order_line_nbr
        WHERE date(substr(ws.planned_start,1,10)) = '{self.planned_date}'
          AND ws.process_nme NOT IN ('Farm Out', 'Finished Good')
        GROUP BY ws.process_nme
        ORDER BY ws.process_nme
        """
        df = pd.read_sql_query(query, self.conn)
        if not df.empty:
            df["Total MSF"] = df["Total MSF"].fillna(0).astype(int).map("{:,}".format)
        return df

    # -----------------------------
    # Order details query
    # -----------------------------
    def get_order_details(self, today_processes):
        if not today_processes:
            return pd.DataFrame()
        query = f"""
        SELECT 
            r.order_id || '-' || r.order_line_nbr AS "Order #",
            r.short_name AS "Customer",
            r.all_routing AS "Processes",
            '' AS "Status",
            '' AS "Note",
            CASE WHEN r.quality_watch = 1 THEN 'YES' ELSE '' END AS "QW"
        FROM order_routing r
        WHERE date(substr(r.requested_dte,1,10)) = '{self.next_day}'
          AND r.process_id != 168
          AND r.process_nme IN {today_processes}
          AND r.process_nme NOT IN ('Farm Out', 'Finished Good')
        GROUP BY r.order_id, r.order_line_nbr
        ORDER BY r.order_id, r.order_line_nbr
        """
        return pd.read_sql_query(query, self.conn)

    # -----------------------------
    # Column width helpers
    # -----------------------------
    @staticmethod
    def calc_col_widths_summary(df, first_col_width=250, total_width=760):
        remaining_width = total_width - first_col_width
        other_cols = len(df.columns) - 1
        other_width = remaining_width / other_cols if other_cols > 0 else remaining_width
        return [first_col_width] + [other_width] * other_cols

    @staticmethod
    def calc_col_widths_order_details(df, processes_col="Processes", processes_width=250, total_width=760):
        n_cols = len(df.columns)
        widths = []
        remaining_width = total_width - processes_width
        other_cols = n_cols - 1
        other_width = remaining_width / other_cols if other_cols > 0 else remaining_width
        for col in df.columns:
            widths.append(processes_width if col == processes_col else other_width)
        return widths

    # -----------------------------
    # Build PDF
    # -----------------------------
    def build_pdf(self, summary_df, details_df):
        timestamp = datetime.now().strftime("%H%M")
        self.pdf_path = os.path.join(self.output_dir, f"Daily_Planner_{self.planned_date}_{timestamp}.pdf")

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

        # Title
        elements.append(Paragraph(f"<b>Daily Planner – {self.planned_date}</b>", title_style))
        elements.append(Spacer(1, 12))

        # Summary Table
        elements.append(Paragraph("Summary by Process", heading_style))
        if not summary_df.empty:
            data = [list(summary_df.columns)] + summary_df.values.tolist()
            table = Table(data, colWidths=self.calc_col_widths_summary(summary_df))
            table.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), HexColor("#FAFAFA")),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, HexColor("#F7F7F7")]),
                ("GRID", (0, 0), (-1, -1), 0.25, colors.grey),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("ALIGN", (2, 1), (2, -1), "RIGHT")
            ]))
            elements.append(table)
        else:
            elements.append(Paragraph("No summary data available for this date.", styles["Normal"]))
        elements.append(Spacer(1, 18))

        # Order Details Table
        elements.append(Paragraph(f"Order Details (Due {self.next_day})", heading_style))
        if not details_df.empty:
            data = [list(details_df.columns)] + details_df.values.tolist()
            table = Table(data, colWidths=self.calc_col_widths_order_details(details_df))
            table.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), HexColor("#FAFAFA")),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, HexColor("#F7F7F7")]),
                ("GRID", (0, 0), (-1, -1), 0.25, colors.grey),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("TEXTCOLOR", (5, 1), (5, -1), HexColor("#D55E00")),  # highlight QW
            ]))
            elements.append(table)
        else:
            elements.append(Paragraph(f"No orders due for {self.next_day}.", styles["Normal"]))
        elements.append(Spacer(1, 18))

        # Footer table for risks
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
            ("BACKGROUND", (0, 0), (-1, 0), HexColor("#FAFAFA")),
            ("GRID", (0, 0), (-1, -1), 0.25, colors.grey),
            ("TEXTCOLOR", (2, 1), (2, -1), HexColor("#BABABA")),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, HexColor("#F7F7F7")]),
        ]))
        elements.append(table)
        elements.append(Spacer(1, 36))

        # Append charts at the **end of the PDF**
        for fig in self.chart_figs:
            img_buf = BytesIO()
            fig.savefig(img_buf, format="png", dpi=150, bbox_inches='tight')
            img_buf.seek(0)
            elements.append(Image(img_buf, width=700, height=300))
            elements.append(Spacer(1, 12))

        # Footer
        elements.append(Paragraph("Date: ____________________", footer_style))
        elements.append(Spacer(1, 12))
        elements.append(Paragraph("Plan approved by: ____________________", footer_style))

        doc.build(elements)
        print(f"✅ PDF generated: {self.pdf_path}")
        print(f"Next working day: {self.next_day}")

    # -----------------------------
    # Full workflow
    # -----------------------------
    def generate(self):
        try:
            self.connect()
            self.load_holidays()
            self.next_day = self.next_working_day(self.planned_date)
            summary_df = self.get_summary()
            today_processes = tuple(summary_df["Process Name"].tolist()) or ("NO_PROCESS",)
            details_df = self.get_order_details(today_processes)
            self.build_pdf(summary_df, details_df)
        finally:
            if self.conn:
                self.conn.close()
