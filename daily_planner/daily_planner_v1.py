import os
import webbrowser
from datetime import datetime, timedelta, date
from calendar import Calendar, month_name
import ttkbootstrap as ttk
from ttkbootstrap.constants import *
from ttkbootstrap.dialogs import Messagebox
from PyPDF2 import PdfMerger
from daily_planner_report import DailyPlannerReport
from daily_planner_chart import ProcessTrendChart  # chart generator


class DailyPlannerGUI(ttk.Window):
    def __init__(self, db_path):
        super().__init__(title="📅 Daily Planner Generator", themename="flatly")
        self.db_path = db_path
        self.geometry("600x500")
        self.resizable(False, False)
        self.pdf_path = None
        self.setup_ui()

    # ----------------------------
    # UI SETUP
    # ----------------------------
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

        # Generate button
        ttk.Button(
            self,
            text="Generate Combined Planner PDF",
            bootstyle=SUCCESS,
            width=35,
            command=self.generate_combined_report
        ).pack(pady=20)

        # View button
        self.view_btn = ttk.Button(
            self,
            text="📄 View Last Generated PDF",
            bootstyle=INFO,
            width=35,
            command=self.open_pdf,
            state=DISABLED
        )
        self.view_btn.pack(pady=5)

        self.status_label = ttk.Label(self, text="", font=("Segoe UI", 10))
        self.status_label.pack(pady=10)

    # ----------------------------
    # CALENDAR POPUP
    # ----------------------------
    def open_calendar(self, target_var):
        top = ttk.Toplevel(self)
        top.title("Select Date")
        top.geometry("480x380")
        top.resizable(False, False)

        self.cal_target = target_var
        self.cal_year = datetime.today().year
        self.cal_month = datetime.today().month

        header_frame = ttk.Frame(top)
        header_frame.pack(pady=5)

        self.month_label = ttk.Label(
            header_frame,
            text=f"{month_name[self.cal_month]} {self.cal_year}",
            font=("Segoe UI", 12, "bold")
        )
        self.month_label.pack(side=TOP, pady=4)

        btn_frame = ttk.Frame(header_frame)
        btn_frame.pack()
        ttk.Button(btn_frame, text="◀ Prev", width=10, command=lambda: self.change_month(-1)).pack(side=LEFT, padx=5)
        ttk.Button(btn_frame, text="Next ▶", width=10, command=lambda: self.change_month(1)).pack(side=LEFT, padx=5)

        self.days_frame = ttk.Frame(top)
        self.days_frame.pack(pady=10)
        self.render_calendar(self.cal_year, self.cal_month)
        self.calendar_window = top

    def render_calendar(self, year, month):
        for widget in self.days_frame.winfo_children():
            widget.destroy()

        weekdays = ["Su", "Mo", "Tu", "We", "Th", "Fr", "Sa"]
        for c, d in enumerate(weekdays):
            ttk.Label(self.days_frame, text=d, width=5, font=("Segoe UI", 10, "bold")).grid(row=0, column=c, pady=2)

        cal = Calendar(firstweekday=6)
        month_days = cal.monthdayscalendar(year, month)
        today = date.today()

        for r, week in enumerate(month_days, start=1):
            for c, day in enumerate(week):
                if day == 0:
                    ttk.Label(self.days_frame, text="", width=5).grid(row=r, column=c)
                else:
                    day_date = date(year, month, day)
                    is_today = day_date == today
                    is_weekend = day_date.weekday() in (5, 6)
                    style = INFO if is_today else (SECONDARY if is_weekend else LIGHT)
                    b = ttk.Button(
                        self.days_frame,
                        text=str(day),
                        width=5,
                        bootstyle=style,
                        command=lambda d=day: self.pick_date(self.calendar_window, year, month, d)
                    )
                    b.grid(row=r, column=c, padx=4, pady=4)

    def change_month(self, offset):
        self.cal_month += offset
        if self.cal_month < 1:
            self.cal_month = 12
            self.cal_year -= 1
        elif self.cal_month > 12:
            self.cal_month = 1
            self.cal_year += 1
        self.month_label.config(text=f"{month_name[self.cal_month]} {self.cal_year}")
        self.render_calendar(self.cal_year, self.cal_month)

    def pick_date(self, window, year, month, day):
        picked = date(year, month, day).strftime("%Y-%m-%d")
        self.cal_target.set(picked)
        window.destroy()

    # ----------------------------
    # GENERATE COMBINED REPORT WITH CHARTS AT END
    # ----------------------------
    def generate_combined_report(self):
        start = self.start_var.get().strip()
        end = self.end_var.get().strip()

        try:
            start_d = datetime.strptime(start, "%Y-%m-%d").date()
            end_d = datetime.strptime(end, "%Y-%m-%d").date()
        except ValueError:
            Messagebox.show_error("Please select valid date(s).", "Invalid Date Format")
            return

        if end_d < start_d:
            Messagebox.show_error("End date cannot be before start date.", "Invalid Range")
            return

        pdf_list = []
        chart_files = []
        output_dir = os.path.expanduser("~/Desktop")
        combined_pdf = os.path.join(output_dir, f"Daily_Planner_{start}_to_{end}.pdf")

        try:
            current = start_d
            merger = PdfMerger()

            while current <= end_d:
                # Generate daily planner WITHOUT charts
                planner = DailyPlannerReport(
                    db_path=self.db_path,
                    planned_date=current.strftime("%Y-%m-%d"),
                    output_dir=output_dir,
                    chart_files=[]
                )
                planner.generate()
                if os.path.exists(planner.pdf_path):
                    merger.append(planner.pdf_path)
                    pdf_list.append(planner.pdf_path)

                # Collect chart PNGs for each day
                chart_gen = ProcessTrendChart(
                    db_path=self.db_path,
                    start_date=current.strftime("%Y-%m-%d"),
                    output_dir=output_dir
                )
                chart_files.extend(chart_gen.generate())

                current += timedelta(days=1)

            # Create PDF for charts only
            if chart_files:
                chart_pdf_report = DailyPlannerReport(
                    db_path=self.db_path,
                    planned_date=start,  # dummy date
                    output_dir=output_dir,
                    chart_files=chart_files
                )
                chart_pdf_report.generate()
                if os.path.exists(chart_pdf_report.pdf_path):
                    merger.append(chart_pdf_report.pdf_path)

            # Merge all PDFs
            merger.write(combined_pdf)
            merger.close()
            self.pdf_path = combined_pdf
            self.view_btn.config(state=NORMAL)
            self.status_label.config(text=f"✅ Combined PDF ready: {os.path.basename(combined_pdf)}", foreground="green")
            Messagebox.show_info(f"Combined planner created:\n{combined_pdf}", "Success")

            # Cleanup temporary files
            for f in pdf_list + chart_files:
                try:
                    os.remove(f)
                except:
                    pass

        except Exception as e:
            Messagebox.show_error(f"Error: {e}", "Generation Failed")
            self.status_label.config(text=f"Error: {e}", foreground="red")
            self.view_btn.config(state=DISABLED)

    # ----------------------------
    # OPEN LAST PDF
    # ----------------------------
    def open_pdf(self):
        if self.pdf_path and os.path.exists(self.pdf_path):
            webbrowser.open(self.pdf_path)
        else:
            Messagebox.show_warning("No file found to open.", "Missing File")


if __name__ == "__main__":
    db_path = r"C:\Users\sang.n\OneDrive - whitebird.ca\Paper App\prod_db.db"
    app = DailyPlannerGUI(db_path)
    app.mainloop()
