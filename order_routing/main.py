# Full Corrugator Scheduler with CSV-based auto-schedule

import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from ttkbootstrap import Style
from datetime import datetime, timedelta
import sqlite3
import csv

conn = sqlite3.connect(":memory:")
c = conn.cursor()

c.execute("""
CREATE TABLE CorrugatorJobs (
    job_id INTEGER PRIMARY KEY AUTOINCREMENT,
    product TEXT,
    machine TEXT,
    status TEXT,
    start_time TEXT,
    end_time TEXT
)
""")

def times_overlap(s1, e1, s2, e2):
    return s1 < e2 and s2 < e1

def check_conflicts(job_id, machine, start_str, end_str):
    fmt = "%Y-%m-%d %H:%M"
    reasons = []
    try:
        start = datetime.strptime(start_str, fmt)
        end = datetime.strptime(end_str, fmt)
    except:
        return False, []

    rows = c.execute("""
        SELECT job_id, product, status, start_time, end_time FROM CorrugatorJobs
        WHERE machine=? AND job_id != ? AND start_time != '' AND end_time != ''
    """, (machine, job_id if job_id else -1)).fetchall()

    for other_id, product, status, o_start_str, o_end_str in rows:
        o_start = datetime.strptime(o_start_str, fmt)
        o_end = datetime.strptime(o_end_str, fmt)
        if times_overlap(start, end, o_start, o_end):
            if status == "Maintenance":
                reasons.append(f"Conflicts with Maintenance from {o_start_str} to {o_end_str}.")
            else:
                reasons.append(f"Overlaps with Job #{other_id} ({product}) [{status}] from {o_start_str} to {o_end_str}.")
    return (len(reasons) > 0), reasons

def find_next_available_slot_any_machine(duration_minutes=60, from_time=None):
    if from_time is None:
        from_time = datetime.now()
    fmt = "%Y-%m-%d %H:%M"
    delta = timedelta(minutes=duration_minutes)
    best_slot = None
    machines = c.execute("SELECT DISTINCT machine FROM CorrugatorJobs").fetchall()
    for (machine,) in machines:
        rows = c.execute("""
            SELECT start_time, end_time FROM CorrugatorJobs
            WHERE machine=? AND start_time != '' AND end_time != ''
            ORDER BY start_time
        """, (machine,)).fetchall()
        intervals = [(datetime.strptime(s, fmt), datetime.strptime(e, fmt)) for s, e in rows]
        check_start = from_time
        while True:
            check_end = check_start + delta
            if all(not times_overlap(check_start, check_end, s, e) for s, e in intervals):
                if not best_slot or check_start < best_slot[1]:
                    best_slot = (machine, check_start, check_end)
                break
            overlapping = [e for s, e in intervals if times_overlap(check_start, check_end, s, e)]
            if overlapping:
                check_start = max(overlapping)
            else:
                check_start += timedelta(minutes=5)
    return best_slot

def auto_schedule_batch(jobs):
    fmt = "%Y-%m-%d %H:%M"
    now = datetime.now()
    for product, duration_minutes in jobs:
        slot = find_next_available_slot_any_machine(duration_minutes, now)
        if slot:
            machine, start, end = slot
            c.execute("""
                INSERT INTO CorrugatorJobs (product, machine, status, start_time, end_time)
                VALUES (?, ?, ?, ?, ?)
            """, (product, machine, "Scheduled", start.strftime(fmt), end.strftime(fmt)))
            now = start
    conn.commit()

def auto_schedule_from_csv(path):
    jobs = []
    with open(path, newline='') as f:
        reader = csv.DictReader(f)
        for row in reader:
            product = row.get('product') or row.get('Product')
            duration = int(row.get('duration', 60))
            jobs.append((product, duration))
    auto_schedule_batch(jobs)

class CorrugatorApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Corrugator Scheduler")
        self.geometry("800x500")
        Style("flatly")

        top = ttk.Frame(self)
        top.pack(fill="x", pady=5)
        ttk.Button(top, text="Auto-Schedule CSV", command=self.load_csv).pack(side="left", padx=5)

        self.tree = ttk.Treeview(self, columns=("id", "product", "machine", "status", "start", "end"), show="headings")
        for col in self.tree["columns"]:
            self.tree.heading(col, text=col.capitalize())
        self.tree.pack(fill="both", expand=True)
        self.populate_jobs()

    def load_csv(self):
        path = filedialog.askopenfilename(filetypes=[("CSV Files", "*.csv")])
        if path:
            auto_schedule_from_csv(path)
            self.populate_jobs()

    def populate_jobs(self):
        for i in self.tree.get_children():
            self.tree.delete(i)
        rows = c.execute("SELECT * FROM CorrugatorJobs ORDER BY start_time").fetchall()
        for row in rows:
            self.tree.insert("", "end", values=row)

if __name__ == "__main__":
    CorrugatorApp().mainloop()
