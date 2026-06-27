import sqlite3
import csv
import tkinter as tk
from tkinter import ttk, messagebox
from ttkbootstrap import Style
from ttkbootstrap.widgets import DateEntry
from datetime import datetime, timedelta
import matplotlib.pyplot as plt

MAX_DELAY_DAYS = 10
DELAYED_JOBS_LOG = []

def skip_weekends(date):
    while date.weekday() >= 5:
        date += timedelta(days=1)
    return date

def safe_parse_iso(dt_str):
    if dt_str is None:
        return None
    if isinstance(dt_str, datetime):
        return dt_str
    try:
        return datetime.fromisoformat(str(dt_str))
    except Exception:
        parts = str(dt_str).split(" ")
        return datetime.fromisoformat(parts[0]) if parts else None

def try_schedule_on_date(cursor, process_name, sqft, check_date):
    cursor.execute("""
        SELECT max_sqft, max_jobs 
        FROM process_capacity 
        WHERE process_name = ? AND date = ?
    """, (process_name, check_date))
    row = cursor.fetchone()

    if row:
        max_sqft, max_jobs = row
    else:
        max_sqft = 200000
        max_jobs = 5
        cursor.execute("""
            INSERT INTO process_capacity (process_name, date, max_sqft, max_jobs) 
            VALUES (?, ?, ?, ?)
        """, (process_name, check_date, max_sqft, max_jobs))

    cursor.execute("""
        SELECT COALESCE(SUM(msf), 0), COUNT(*) 
        FROM order_routing 
        WHERE process_nme = ? AND substr(schedule_dte, 1, 10) = ?
    """, (process_name, check_date))
    used_sqft, used_jobs = cursor.fetchone()

    if used_sqft + sqft <= max_sqft and used_jobs < max_jobs:
        return True

    return False

def find_next_available_day(process_name, sqft, earliest_date=None, requested_date=None):
    db_path = "prod_db.db"
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    today = skip_weekends(datetime.today().date())
    requested = safe_parse_iso(str(requested_date)).date() if requested_date else today

    preferred_start = max(skip_weekends(requested - timedelta(days=5)), today)
    preferred_end = requested
    fallback_start = skip_weekends(requested + timedelta(days=1))
    fallback_end = requested + timedelta(days=MAX_DELAY_DAYS)

    for i in range((preferred_end - preferred_start).days + 1):
        check_date = skip_weekends(preferred_start + timedelta(days=i))
        if try_schedule_on_date(cursor, process_name, sqft, check_date):
            conn.commit()
            conn.close()
            return check_date

    for i in range((fallback_end - fallback_start).days + 1):
        check_date = skip_weekends(fallback_start + timedelta(days=i))
        if try_schedule_on_date(cursor, process_name, sqft, check_date):
            DELAYED_JOBS_LOG.append((process_name, check_date, requested))
            conn.commit()
            conn.close()
            return check_date

    conn.close()
    return None

def auto_schedule_process(order_routing_id, process_name, sqft_needed, earliest_date=None, requested_date=None):
    date = find_next_available_day(process_name, sqft_needed, earliest_date, requested_date)
    if date:
        db_path = "prod_db.db"
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE order_routing 
            SET schedule_dte = ?
            WHERE order_routing_id = ?
        """, (date, order_routing_id))
        conn.commit()
        conn.close()
        return date
    return None

def schedule_job(order_id, line_number):
    db_path = "prod_db.db"
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    cursor.execute("""
        SELECT order_routing_id, process_nme, msf, schedule_dte, requested_dte
        FROM order_routing 
        WHERE order_id = ? AND order_line_nbr = ?
        ORDER BY order_seq, requested_dte
    """, (order_id, line_number))

    process_steps = cursor.fetchall()
    conn.close()

    earliest_date = skip_weekends(datetime.today().date())

    for track_id, process_name, msf, schedule_dte, requested_dte in process_steps:
        requested = safe_parse_iso(str(requested_dte)).date() if requested_dte else None
        scheduled_date = auto_schedule_process(
            track_id, process_name, msf,
            earliest_date.isoformat(), requested
        )
        if scheduled_date:
            earliest_date = skip_weekends(scheduled_date + timedelta(days=1))
        else:
            print(f"⚠️ Failed to schedule {process_name} (track_id={track_id})")

def export_delayed_jobs_to_csv():
    if not DELAYED_JOBS_LOG:
        return
    with open("delayed_jobs.csv", "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["Process", "Scheduled Date", "Requested Date", "Delay (Days)"])
        for process, sched_date, req_date in DELAYED_JOBS_LOG:
            writer.writerow([process, sched_date, req_date, (sched_date - req_date).days])

def reschedule_all_jobs():
    db_path = "prod_db.db"
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    cursor.execute("UPDATE order_routing SET schedule_dte = NULL;")
    conn.commit()

    cursor.execute("""
        SELECT order_id, order_line_nbr, MIN(requested_dte)
        FROM order_routing 
        GROUP BY order_id, order_line_nbr
        ORDER BY MIN(requested_dte);
    """)
    groups = cursor.fetchall()
    conn.close()

    for order_id, line_nbr, requested_dte in groups:
        schedule_job(order_id, line_nbr)

    export_delayed_jobs_to_csv()
    print("✅ Rescheduling complete.")

def show_gantt_chart_for_order(order_id, line_nbr):
    conn = sqlite3.connect("prod_db.db")
    cursor = conn.cursor()
    cursor.execute("""
        SELECT process_nme, schedule_dte, requested_dte
        FROM order_routing 
        WHERE order_id = ? AND order_line_nbr = ?
        ORDER BY order_seq
    """, (order_id, line_nbr))
    data = cursor.fetchall()
    conn.close()

    fig, ax = plt.subplots(figsize=(10, 4))
    for i, (proc, sched, req) in enumerate(data):
        sched = safe_parse_iso(str(sched)).date()
        req = safe_parse_iso(str(req)).date()
        ax.barh(proc, 1, left=sched, color='green' if sched <= req else 'red')
        ax.text(sched, i, sched.isoformat(), va='center', ha='left')
    ax.set_title(f"Gantt Chart: Order {order_id} Line {line_nbr}")
    ax.set_xlabel("Date")
    plt.tight_layout()
    plt.show()

class ManualScheduler(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Manual Scheduler")
        self.geometry("1000x600")
        self.style = Style("superhero")

        self.tree = ttk.Treeview(self, columns=("Order", "Line", "Process", "Requested", "Scheduled", "Delay"), show="headings")
        for col in self.tree["columns"]:
            self.tree.heading(col, text=col)
        self.tree.pack(fill="both", expand=True)
        self.tree.bind("<<TreeviewSelect>>", self.on_row_select)

        frame = ttk.Frame(self)
        frame.pack(pady=10)
        ttk.Label(frame, text="New Schedule Date:").pack(side="left", padx=5)
        self.date_picker = DateEntry(frame, width=15, bootstyle="success")
        self.date_picker.pack(side="left")
        self.update_btn = ttk.Button(frame, text="Update Date", command=self.update_date)
        self.update_btn.pack(side="left", padx=10)

        self.selected_item = None
        self.load_data()

    def load_data(self):
        self.tree.delete(*self.tree.get_children())
        conn = sqlite3.connect("prod_db.db")
        cursor = conn.cursor()
        cursor.execute("""
            SELECT order_routing_id, order_id, order_line_nbr, process_nme, requested_dte, schedule_dte
            FROM order_routing 
            ORDER BY order_id, order_line_nbr, order_seq
        """)
        rows = cursor.fetchall()
        for row in rows:
            track_id, order_id, line, process, requested, scheduled = row
            requested = safe_parse_iso(requested).date()
            scheduled = safe_parse_iso(scheduled).date() if scheduled else None
            delay = (scheduled - requested).days if scheduled else "❌"
            color = "green" if scheduled and scheduled <= requested else "yellow" if scheduled else "red"
            self.tree.insert("", "end", iid=str(track_id), values=(order_id, line, process, requested, scheduled, delay), tags=(color,))
        self.tree.tag_configure("green", background="lightgreen")
        self.tree.tag_configure("yellow", background="khaki")
        self.tree.tag_configure("red", background="lightcoral")
        conn.close()

    def on_row_select(self, event):
        selected = self.tree.selection()
        if selected:
            self.selected_item = selected[0]
            current = self.tree.item(self.selected_item)["values"][4]
            if current:
                self.date_picker.set_date(current)

    def update_date(self):
        if not self.selected_item:
            messagebox.showwarning("Select a row", "Please select a job to update.")
            return

        new_date = self.date_picker.entry.get()
        try:
            new_dt = datetime.strptime(new_date, "%Y-%m-%d").date()
        except Exception as e:
            messagebox.showerror("Invalid date", f"Could not parse selected date: {e}")
            return

        conn = sqlite3.connect("prod_db.db")
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE order_routing SET schedule_dte = ? WHERE order_routing_id = ?
        """, (new_dt, self.selected_item))
        conn.commit()
        conn.close()

        messagebox.showinfo("Success", f"Schedule updated to {new_dt}")
        self.load_data()

if __name__ == "__main__":
    reschedule_all_jobs()
    app = ManualScheduler()
    app.mainloop()
