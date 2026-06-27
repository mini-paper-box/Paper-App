import tkinter as tk
from tkinter import ttk
from ttkbootstrap import Style
import tkinter.font as tkFont
from collections import defaultdict
from ttkbootstrap.widgets import DateEntry
from datetime import datetime, timedelta
import sqlite3

class ScheduleTreeviewFrame(ttk.Frame):
    def __init__(self, master, db_path="prod_db.db"):
        super().__init__(master)
        self.pack(fill="both", expand=True)
        self.columns = ["short_name", "order_id", "order_line_nbr", "order_seq", "process_nme", "schedule_dte","requested_dte", "msf", "receipt_status", "run_date", "status_dsc", "press_fin_qty", "plant_name"]

        self.db_path = db_path
        self.sort_column = None
        self.sort_reverse = False

        self.custom_font = tkFont.Font(family="Segoe UI", size=11)
        style = Style()
        style.configure("TreeviewPrimary.Treeview", font=self.custom_font, rowheight=28, bootstyle="info")
        style.configure("TreeviewPrimary.Treeview.Heading", font=(self.custom_font.actual("family"), 12, "bold"), bootstyle="info")
        style.map("TreeviewPrimary.Treeview", background=[("selected", "#1f6aa5")], foreground=[("selected", "white")])

        self.create_widgets()
        self.load_data()

    def create_widgets(self):
        self.style = Style("flatly")

        # Filter Frame
        filter_frame = ttk.Frame(self)
        filter_frame.pack(fill="x", padx=10, pady=(10, 0))

        ttk.Label(filter_frame, text="Filter by Process:").pack(side="left", padx=(0, 5))

        self.process_var = tk.StringVar(value="All")
        self.process_filter = ttk.Combobox(
            filter_frame, textvariable=self.process_var,
            state="readonly", width=20
        )
        self.process_filter.pack(side="left")
        self.process_filter.bind("<<ComboboxSelected>>", lambda e: self.load_data())

        # Treeview
        self.tree = ttk.Treeview(self, columns=self.columns, show="headings", bootstyle="info", style="TreeviewPrimary.Treeview")
        for col in self.columns:
            self.tree.heading(col, text=col.replace("_", " ").title(), command=lambda c=col: self.sort_by_column(c))
            self.tree.column(col, width=100, anchor="w")
        self.tree.pack(fill="both", expand=True, padx=10, pady=10)

        self.tree.bind("<Double-1>", self.edit_cell)

        # Scrollbars
        ysb = ttk.Scrollbar(self, orient="vertical", command=self.tree.yview)
        xsb = ttk.Scrollbar(self, orient="horizontal", command=self.tree.xview)
        self.tree.configure(yscroll=ysb.set, xscroll=xsb.set)
        ysb.pack(side="right", fill="y")
        xsb.pack(side="bottom", fill="x")

    def load_data(self):
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute(f"SELECT {', '.join(self.columns)} FROM order_routing")
            rows = cursor.fetchall()
            conn.close()

            process_selected = self.process_var.get() if hasattr(self, "process_var") else "All"

            # Convert to dicts
            row_dicts = [dict(zip(self.columns, row)) for row in rows]

            # Get process list and update combobox values once
            if hasattr(self, "process_filter"):
                processes = sorted({row["process_nme"] for row in row_dicts})
                self.process_filter["values"] = ["All"] + processes

            # Filter by selected process
            if process_selected and process_selected != "All":
                row_dicts = [row for row in row_dicts if row["process_nme"] == process_selected]

            # Group and sort
            grouped = defaultdict(list)
            for row in row_dicts:
                group_key = (row["order_id"], row["order_line_nbr"])
                grouped[group_key].append(row)

            sorted_rows = []
            for group in grouped.values():
                sorted_group = sorted(group, key=lambda x: int(x["order_seq"]))
                sorted_rows.extend(sorted_group)

            self.tree.delete(*self.tree.get_children())
            for row in sorted_rows:
                self.tree.insert("", "end", values=[row[col] for col in self.columns])

        except Exception as e:
            print("Failed to load data:", e)


    def sort_by_column(self, col):
        data = [(self.tree.set(child, col), child) for child in self.tree.get_children()]
        try:
            data.sort(key=lambda x: float(x[0]) if x[0].replace('.', '', 1).isdigit() else x[0])
        except:
            data.sort(key=lambda x: x[0])

        self.sort_reverse = not self.sort_reverse if self.sort_column == col else False
        self.sort_column = col
        for index, (_, item) in enumerate(reversed(data) if self.sort_reverse else data):
            self.tree.move(item, '', index)

    def edit_cell(self, event):
        rowid = self.tree.identify_row(event.y)
        column = self.tree.identify_column(event.x)
        col_index = int(column[1:]) - 1
        col_name = self.columns[col_index]
        if not rowid:
            return

        # Only allow editing the 'schedule_dte' column
        if col_name != "schedule_dte":
            return

        x, y, width, height = self.tree.bbox(rowid, column)
        value = self.tree.set(rowid, col_name)

        # Create DateEntry from ttkbootstrap
        cal = DateEntry(self.tree, bootstyle="primary", dateformat="%Y-%m-%d")
        cal.place(x=x, y=y, width=width, height=height)
        try:
            cal.set_date(value)
        except Exception:
            pass
        cal.focus()

        def on_select(event=None):
            new_value = cal.entry.get()
            self.tree.set(rowid, col_name, new_value)
            cal.destroy()

        cal.bind("<FocusOut>", lambda e: cal.destroy())
        cal.bind("<Return>", lambda e: on_select())
    
    def find_next_available_day(self,process_name, sqft, earliest_date=None):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        base_date = datetime.today().date() if not earliest_date else datetime.fromisoformat(earliest_date).date()
        for i in range(30):  # Look ahead up to 30 days
            check_date = (base_date + timedelta(days=i)).isoformat()
            cursor.execute("SELECT max_sqft FROM process_capacity WHERE process_name = ? AND date = ?",
                        (process_name, check_date))
            row = cursor.fetchone()
            if row:
                max_sqft = row[0]
            else:
                max_sqft = 5000
                cursor.execute("INSERT INTO process_capacity (process_name, date, max_sqft, max_jobs) VALUES (?, ?, ?, ?)",
                            (process_name, check_date, max_sqft, 5))
                conn.commit()

            cursor.execute("SELECT COALESCE(SUM(sqft), 0) FROM scheduled_processes WHERE process_name = ? AND date = ?",
                        (process_name, check_date))
            used = cursor.fetchone()[0]
            if used < max_sqft:
                conn.close()
                return check_date
        conn.close()
        return None
    
    def schedule_process(self, job_id, process_name, sqft_needed, earliest_date=None):
        date = self.find_next_available_day(process_name, sqft_needed, earliest_date)
        if date:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO scheduled_processes (job_id, process_name, date, sqft)
                VALUES (?, ?, ?, ?)
            """, (job_id, process_name, date, sqft_needed))
            conn.commit()
            conn.close()
            return date
        return None
    
    def schedule_job(self):
        job_id = int(self.job_entry.get())
        sqft = int(self.sqft_entry.get())
        last_date = None
        for proc in ["Cutting", "Gluing", "Packing"]:
            last_date = self.schedule_process(job_id, proc, sqft, last_date)
            if last_date:
                last_date = (datetime.fromisoformat(last_date) + timedelta(days=1)).isoformat()
        self.load_schedule()

if __name__ == "__main__":
    root = tk.Tk()
    root.title("Scheduling Viewer")
    root.geometry("900x500")
    ScheduleTreeviewFrame(root)
    root.mainloop()