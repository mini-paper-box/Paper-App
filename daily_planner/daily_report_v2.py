import os
import webbrowser
from datetime import datetime, timedelta, date
from calendar import monthcalendar, month_name
import ttkbootstrap as ttk
from ttkbootstrap.constants import *
from ttkbootstrap.dialogs import Messagebox
from PyPDF2 import PdfMerger
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import sqlite3
import pandas as pd

# ----------------------------
# DAILY PLANNER REPORT CLASS
# ----------------------------
class DailyPlannerReport:
    def __init__(self, db_path, planned_date=None, output_dir=None):
        self.db_path = db_path
        self.planned_date = planned_date or datetime.now().strftime("%Y-%m-%d")
        self.output_dir = output_dir or os.getcwd()
        self.conn = None
        self.holiday_dates = set()
        self.next_day = None
        self.pdf_path = None

    def connect(self):
        self.conn = sqlite3.connect(self.db_path)

    def load_holidays(self):
        try:
            df = pd.read_sql_query("SELECT date FROM holiday", self.conn)
            self.holiday_dates = set(df["date"].tolist())
        except Exception:
            self.holiday_dates = set()

    def next_working_day(self, date_str):
        d = datetime.strptime(date_str, "%Y-%m-%d").date()
        next_day = d + timedelta(days=1)
        while next_day.weekday() >= 5 or next_day.strftime("%Y-%m-%d") in self.holiday_dates:
            next_day += timedelta(days=1)
        return next_day.strftime("%Y-%m-%d")

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
          AND ws.process_nme NOT IN ('Farm out','Finished Good')
        GROUP BY ws.process_nme
        ORDER BY ws.process_nme
        """
        df = pd.read_sql_query(query, self.conn)
        if not df.empty:
            df["Total MSF"] = df["Total MSF"].fillna(0).astype(int).map("{:,}".format)
        return df

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
          AND r.process_nme NOT IN ('Farm out','Finished Good')
        GROUP BY r.order_id, r.order_line_nbr
        ORDER BY r.order_id, r.order_line_nbr
        """
        return pd.read_sql_query(query, self.conn)

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

    def build_pdf(self, summary_df, details_df):
        from reportlab.lib import colors
        from reportlab.lib.colors import HexColor
        from reportlab.lib.pagesizes import landscape, A4
        from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle

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

        elements.append(Paragraph(f"<b>Daily Planner – {self.planned_date}</b>", title_style))
        elements.append(Spacer(1, 12))

        # SUMMARY
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

        # ORDER DETAILS
        elements.append(Paragraph(f"Order Details (Due {self.next_day})", heading_style))
        if not details_df.empty:
            data = [list(details_df.columns)] + details_df.values.tolist()
            table = Table(data, colWidths=self.calc_col_widths_order_details(details_df))
            table.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), HexColor("#FAFAFA")),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, HexColor("#F7F7F7")]),
                ("GRID", (0, 0), (-1, -1), 0.25, colors.grey),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("TEXTCOLOR", (5, 1), (5, -1), HexColor("#D55E00")),  # QW
            ]))
            elements.append(table)
        else:
            elements.append(Paragraph(f"No orders due for {self.next_day}.", styles["Normal"]))
        elements.append(Spacer(1, 18))

        # RISKS
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

        # Footer
        elements.append(Paragraph("Date: ____________________", footer_style))
        elements.append(Spacer(1, 12))
        elements.append(Paragraph("Plan approved by: ____________________", footer_style))

        doc.build(elements)
        print(f"✅ PDF generated: {self.pdf_path}")
        print(f"Next working day: {self.next_day}")

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


# ----------------------------
# PROCESS TREND CHART CLASS
# ----------------------------
class ProcessTrendChart:
    def __init__(self, db_path, start_date=None, output_dir=None):
        self.db_path = db_path
        self.start_date = start_date or datetime.today().strftime("%Y-%m-%d")
        self.output_dir = output_dir or os.getcwd()
        self.conn = None
        self.holiday_dates = set()
        self.charts = []

    def connect(self):
        self.conn = sqlite3.connect(self.db_path)

    def load_holidays(self):
        try:
            df = pd.read_sql_query("SELECT date FROM holiday", self.conn)
            self.holiday_dates = set(df["date"].tolist())
        except Exception:
            self.holiday_dates = set()

    def next_working_day(self, date_obj):
        next_day = date_obj + timedelta(days=1)
        while next_day.weekday() >= 5 or next_day.strftime("%Y-%m-%d") in self.holiday_dates:
            next_day += timedelta(days=1)
        return next_day

    def get_next_5_working_days(self):
        days = []
        current = datetime.strptime(self.start_date, "%Y-%m-%d").date()
        for _ in range(5):
            current = self.next_working_day(current) if days else current
            days.append(current.strftime("%Y-%m-%d"))
        return days

    def fetch_data(self):
        days = self.get_next_5_working_days()
        query = """
        SELECT DISTINCT r.process_nme AS process
        FROM order_routing r
        WHERE r.process_nme NOT IN ('Farm out', 'Finished Good')
        """
        processes_df = pd.read_sql_query(query, self.conn)
        self.processes = processes_df['process'].tolist()
        self.days = days

        data = []
        for process in self.processes:
            row = []
            for d in days:
                q = f"""
                SELECT SUM(r.msf) AS total_msf
                FROM workback_schedule ws
                LEFT JOIN order_routing r
                    ON ws.order_id = r.order_id
                   AND ws.order_line_nbr = r.order_line_nbr
                WHERE date(substr(ws.planned_start,1,10)) = '{d}'
                  AND ws.process_nme = '{process}'
                  AND r.process_nme NOT IN ('Farm out', 'Finished Good')
                """
                df = pd.read_sql_query(q, self.conn)
                row.append(int(df["total_msf"].iloc[0]) if df["total_msf"].iloc[0] else 0)
            data.append(row)
        self.df = pd.DataFrame(data, index=self.processes, columns=days)

    def build_charts(self):
        self.charts = []
        for process in self.df.index:
            plt.figure(figsize=(8, 4))
            plt.bar(self.df.columns, self.df.loc[process], color="#4CAF50")
            plt.title(f"{process} – 5-Day MSF Trend", fontsize=14)
            plt.xlabel("Date")
            plt.ylabel("Total MSF")
            for i, val in enumerate(self.df.loc[process]):
                plt.text(i, val + 0.5, f"{val:,}", ha='center', va='bottom', fontsize=10)
            plt.tight_layout()
            path = os.path.join(self.output_dir, f"{process}_{self.start_date}.png")
            plt.savefig(path)
            plt.close()
            self.charts.append(path)

    def generate(self):
        try:
            self.connect()
            self.load_holidays()
            self.fetch_data()
            self.build_charts()
        finally:
            if self.conn:
                self.conn.close()
        return self.charts


# ----------------------------
# DAILY PLANNER GUI
# ----------------------------
class DailyPlannerGUI(ttk.Window):
    def __init__(self, db_path):
        super().__init__(title="📅 Daily Planner Generator", themename="flatly")
        self.db_path = db_path
        self.geometry("600x700")
        self.resizable(False, False)
        self.pdf_path = None
        self.chart_index = 0
        self.chart_figures = []
        self.canvas = None
        self.nav_frame = None
        self.setup_ui()

    def setup_ui(self):
        ttk.Label(self, text="Select Date Range:", font=("Segoe UI", 13, "bold")).pack(pady=15)
        frame = ttk.Frame(self)
        frame.pack(pady=5)

        # Start Date
        ttk.Label(frame, text="Start Date:").grid(row=0, column=0, padx=5, pady=5, sticky=W)
        self.start_var = ttk.StringVar(value=datetime.today().strftime("%Y-%m-%d"))
        ttk.Entry(frame, textvariable=self.start_var, width=15).grid(row=0, column=1, padx=5)
        ttk.Button(frame, text="📅", width=3, command=lambda: self.open_calendar(self.start_var)).grid(row=0, column=2)

        # End Date
        ttk.Label(frame, text="End Date:").grid(row=1, column=0, padx=5, pady=5, sticky=W)
        self.end_var = ttk.StringVar(value=datetime.today().strftime("%Y-%m-%d"))
        ttk.Entry(frame, textvariable=self.end_var, width=15).grid(row=1, column=1, padx=5)
        ttk.Button(frame, text="📅", width=3, command=lambda: self.open_calendar(self.end_var)).grid(row=1, column=2)

        ttk.Button(
            self,
            text="Generate Combined Planner PDF",
            bootstyle=SUCCESS,
            width=30,
            command=self.generate_combined_report
        ).pack(pady=10)

        ttk.Button(
            self,
            text="Generate 5-Day Process Charts",
            bootstyle=INFO,
            width=30,
            command=self.generate_process_chart
        ).pack(pady=5)

        self.view_btn = ttk.Button(
            self,
            text="📄 View Last Generated PDF",
            bootstyle=INFO,
            width=30,
            command=self.open_pdf,
            state=DISABLED
        )
        self.view_btn.pack(pady=5)

        self.status_label = ttk.Label(self, text="", font=("Segoe UI", 10))
        self.status_label.pack(pady=10)

    # Calendar methods (same as previous version) ...

    # PDF generation (same as previous version) ...

    # ----------------------------
    # PROCESS CHART
    # ----------------------------
    def generate_process_chart(self):
        start = self.start_var.get().strip()
        try:
            datetime.strptime(start, "%Y-%m-%d")
        except ValueError:
            Messagebox.show_error("Please select a valid start date.", "Invalid Date")
            return

        try:
            output_dir = os.path.expanduser("~/Desktop")
            charter = ProcessTrendChart(db_path=self.db_path, start_date=start, output_dir=output_dir)
            charts = charter.generate()

            if not charts:
                Messagebox.show_warning("No charts generated.", "No Data")
                return

            self.chart_figures = charts
            self.chart_index = 0
            self.show_chart(self.chart_index)

        except Exception as e:
            self.status_label.config(text=f"Error: {e}", foreground="red")
            Messagebox.show_error(f"Error generating charts:\n{e}", "Failed")

    def show_chart(self, index):
        if self.canvas:
            self.canvas.get_tk_widget().destroy()
        fig = plt.figure(figsize=(6, 3))
        img = plt.imread(self.chart_figures[index])
        plt.imshow(img)
        plt.axis('off')
        plt.tight_layout()
        self.canvas = FigureCanvasTkAgg(fig, master=self)
        self.canvas.draw()
        self.canvas.get_tk_widget().pack(pady=10)

        # Navigation buttons
        if not self.nav_frame:
            self.nav_frame = ttk.Frame(self)
            self.nav_frame.pack(pady=5)
            self.prev_btn = ttk.Button(self.nav_frame, text="◀ Prev", command=self.prev_chart)
            self.prev_btn.grid(row=0, column=0, padx=5)
            self.next_btn = ttk.Button(self.nav_frame, text="Next ▶", command=self.next_chart)
            self.next_btn.grid(row=0, column=1, padx=5)
        self.update_nav_buttons()

    def prev_chart(self):
        if self.chart_index > 0:
            self.chart_index -= 1
            self.show_chart(self.chart_index)

    def next_chart(self):
        if self.chart_index < len(self.chart_figures) - 1:
            self.chart_index += 1
            self.show_chart(self.chart_index)

    def update_nav_buttons(self):
        self.prev_btn.config(state=NORMAL if self.chart_index > 0 else DISABLED)
        self.next_btn.config(state=NORMAL if self.chart_index < len(self.chart_figures) - 1 else DISABLED)
        self.status_label.config(text=f"Viewing chart {self.chart_index + 1} of {len(self.chart_figures)}", foreground="blue")

    def open_pdf(self):
        if self.pdf_path and os.path.exists(self.pdf_path):
            webbrowser.open(self.pdf_path)
        else:
            Messagebox.show_warning("No file found to open.", "Missing File")


# ----------------------------
# RUN
# ----------------------------
if __name__ == "__main__":
    db_path = r"C:\Users\sang.n\OneDrive - whitebird.ca\Paper App\prod_db.db"
    app = DailyPlannerGUI(db_path)
    app.mainloop()
