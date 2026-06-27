# import ttkbootstrap as ttk
# from ttkbootstrap.constants import *
# import itertools

# # Flashing colors
# flash_colors = itertools.cycle(["red", "white"])

# def flash_row():
#     # Alternate row tag background color
#     color = next(flash_colors)
#     tree.tag_configure("warning", background=color)
#     tree.after(500, flash_row)  # Repeat every 500ms

# # App setup
# app = ttk.Window("Treeview Flash Row", themename="flatly", size=(600, 300))

# # Create Treeview
# tree = ttk.Treeview(app, columns=("Item", "Status"), show="headings", bootstyle="info")
# tree.heading("Item", text="Item")
# tree.heading("Status", text="Status")
# tree.pack(fill="both", expand=True, padx=20, pady=20)

# # Sample rows
# tree.insert("", "end", values=("Task A", "OK"))
# tree.insert("", "end", values=("Task B", "Running"))
# tree.insert("", "end", values=("Task C", "Error"), tags=("warning",))
# tree.insert("", "end", values=("Task D", "OK"))

# # Start flashing
# flash_row()

# app.mainloop()

# import tkinter as tk
# from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
# import matplotlib.pyplot as plt
# import random
# from datetime import datetime, timedelta

# class LiveBarGraph(tk.Frame):
#     def __init__(self, master):
#         super().__init__(master)
#         self.pack(fill="both", expand=True)
        
#         # Prepare figure and axes
#         self.fig, self.ax = plt.subplots(figsize=(8, 4))
#         self.canvas = FigureCanvasTkAgg(self.fig, master=self)
#         self.canvas.get_tk_widget().pack(fill="both", expand=True)
        
#         # Initialize data: last 7 days
#         self.days = [(datetime.now() - timedelta(days=i)).strftime("%m-%d") for i in reversed(range(7))]
#         self.values = [0]*7  # initial zero counts
        
#         self.bars = self.ax.bar(self.days, self.values, color="skyblue")
#         self.ax.set_ylim(0, 10)  # adjust max as needed
#         self.ax.set_title("Daily Counts")
#         self.ax.set_ylabel("Count")
        
#         # Start periodic update
#         self.update_graph()
    
#     def update_graph(self):
#         # Here you fetch new data - replace this random data with real daily data
#         self.values = [random.randint(0, 10) for _ in self.days]

#         for bar, val in zip(self.bars, self.values):
#             bar.set_height(val)
        
#         self.ax.set_ylim(0, max(self.values) + 1)
#         self.canvas.draw()
        
#         # Schedule next update in 3000 ms (3 seconds)
#         self.after(3000, self.update_graph)

# if __name__ == "__main__":
#     root = tk.Tk()
#     root.title("Live Daily Bar Graph")
#     root.geometry("600x400")
    
#     graph = LiveBarGraph(root)
    
#     root.mainloop()

import sqlite3
import csv
from datetime import datetime, timedelta
# Define database and CSV file
# db_path = "prod_db.db"
# csv_path = "process_capacity.csv"

# # Connect to the database
# conn = sqlite3.connect(db_path)
# cursor = conn.cursor()

# # Read CSV and insert into table
# with open(csv_path, newline='', encoding='utf-8') as csvfile:
#     reader = csv.DictReader(csvfile)
    
#     columns = reader.fieldnames
#     placeholders = ", ".join(["?"] * len(columns))
#     insert_sql = f"""
#     INSERT INTO process_capacity ({", ".join(columns)})
#     VALUES ({placeholders})
#     """

#     for row in reader:
#         values = [row[col] if row[col] != '' else None for col in columns]
#         cursor.execute(insert_sql, values)

# conn.commit()
# conn.close()
# Setup (only once in your app)
sqlite3.register_adapter(datetime.date, lambda d: d.isoformat())
sqlite3.register_converter("DATE", lambda s: datetime.date.fromisoformat(s.decode("utf-8")))

# Use this in your code
conn = sqlite3.connect("prod_db.db", detect_types=sqlite3.PARSE_DECLTYPES)

def find_next_available_day(process_name, sqft, earliest_date=None):
    import sqlite3
    from datetime import datetime, timedelta

    db_path = "prod_db.db"
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    base_date = datetime.fromisoformat(earliest_date).date() if earliest_date else datetime.today().date()
    base_date = skip_weekends(base_date)

    for i in range(30):  # Look ahead up to 30 days
        check_date = base_date + timedelta(days=i)

        if check_date.weekday() >= 5:
            continue

        # Check capacity
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
            conn.commit()

        # Current usage
        cursor.execute("""
            SELECT COALESCE(SUM(msf), 0), COUNT(*) 
            FROM order_routing 
            WHERE process_nme = ? AND substr(schedule_dte, 1, 10) = ?
        """, (process_name, check_date))
        used_sqft, used_jobs = cursor.fetchone()

        # ✅ Case 1: Standard fit
        if used_sqft + sqft <= max_sqft and used_jobs < max_jobs:
            conn.close()
            return check_date

        # ✅ Case 2: Light day, try to split or schedule with reserved next day
        elif used_sqft / max_sqft <= 0.5 and used_jobs < max_jobs:
            avail_sqft = max_sqft - used_sqft
            spillover_sqft = sqft - avail_sqft if sqft > avail_sqft else 0

            # Look ahead to next working day
            next_check_day = skip_weekends(check_date + timedelta(days=1))

            # Check next day's capacity
            cursor.execute("""
                SELECT max_sqft, max_jobs 
                FROM process_capacity 
                WHERE process_name = ? AND date = ?
            """, (process_name, next_check_day))
            row = cursor.fetchone()
            if row:
                next_max_sqft, next_max_jobs = row
            else:
                next_max_sqft = 200000
                next_max_jobs = 5
                cursor.execute("""
                    INSERT INTO process_capacity (process_name, date, max_sqft, max_jobs) 
                    VALUES (?, ?, ?, ?)
                """, (process_name, next_check_day, next_max_sqft, next_max_jobs))
                conn.commit()

            cursor.execute("""
                SELECT COALESCE(SUM(msf), 0), COUNT(*) 
                FROM order_routing 
                WHERE process_nme = ? AND substr(schedule_dte, 1, 10) = ?
            """, (process_name, next_check_day))
            next_used_sqft, next_used_jobs = cursor.fetchone()

            # ✅ Confirm spillover fits in next day
            if next_used_sqft + spillover_sqft <= next_max_sqft:
                conn.close()
                return check_date  # Schedule today, knowing tomorrow is light

    conn.close()
    return None  # No slot found


def skip_weekends(date):
    while date.weekday() >= 5:
        date += timedelta(days=1)
    return date

def auto_schedule_process(order_routing_id, process_name, sqft_needed, earliest_date=None):
        date = find_next_available_day(process_name, sqft_needed, earliest_date)
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

def skip_weekends(date):
    """Skip weekends, return next weekday."""
    while date.weekday() >= 5:
        date += timedelta(days=1)
    return date

def schedule_job(order_id, line_number):
    import sqlite3

    db_path = "prod_db.db"
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Get all processes for this order + line, sorted by order_seq
    cursor.execute("""
        SELECT order_routing_id, process_nme, msf, schedule_dte, requested_dte
        FROM order_routing 
        WHERE order_id = ? AND order_line_nbr = ?
        ORDER BY order_seq, requested_dte
    """, (order_id, line_number))
    
    process_steps = cursor.fetchall()
    conn.close()

    # Start scheduling from today (skip weekends)
    earliest_date = skip_weekends(datetime.today().date())

    for track_id, process_name, msf, schedule_dte, requested_dte in process_steps:
        scheduled_date = auto_schedule_process(track_id, process_name, msf, earliest_date.isoformat())
        
        if scheduled_date:
            # Convert scheduled date string back to date
            dt = datetime.fromisoformat(str(scheduled_date))
            # Next process can only start the day after
            earliest_date = skip_weekends(dt + timedelta(days=1))
        else:
            print(f"⚠️ Failed to schedule {process_name} for track_id {track_id}")

def reschudule_all_jobs():
    db_path = "prod_db.db"
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    cursor.execute("""UPDATE order_routing SET schedule_dte = '2025-12-12';
                   """)
    # Step 1: Get count of entries for this order + line
    cursor.execute("""
        SELECT 
            order_id, 
            order_line_nbr, 
            MIN(requested_dte) AS first_requested_dte, 
            COUNT(*) AS job_count
        FROM order_routing 
        GROUP BY order_id, order_line_nbr
        ORDER BY first_requested_dte;
    """)
    
    

    groups = cursor.fetchall()
    conn.close()
    for o_id, line_nbr,schedule_dte, count in groups:
        schedule_job(o_id,line_nbr)

reschudule_all_jobs()

# import tkinter as tk
# from tkinter import ttk, messagebox
# from ttkbootstrap.widgets import DateEntry
# import sqlite3
# from datetime import datetime, timedelta

# # Database file name
# DB = 'capacity_schedule.db'

# # Create a new database connection
# def connect_db():
#     return sqlite3.connect(DB)

# # Initialize the database with schema and seed data
# def init_db():
#     conn = connect_db()
#     cursor = conn.cursor()
#     # Define tables for capacity and scheduled jobs
#     cursor.executescript("""
#     CREATE TABLE IF NOT EXISTS process_capacity (
#         id INTEGER PRIMARY KEY AUTOINCREMENT,
#         process_name TEXT,
#         date TEXT,
#         max_sqft INTEGER,
#         max_jobs INTEGER
#     );

#     CREATE TABLE IF NOT EXISTS scheduled_processes (
#         id INTEGER PRIMARY KEY AUTOINCREMENT,
#         process_name TEXT,
#         date TEXT,
#         sqft INTEGER,
#         job_id INTEGER
#     );
#     """)
#     conn.commit()

#     # Populate sample capacity data for 10 days
#     cursor.execute("SELECT COUNT(*) FROM process_capacity")
#     if cursor.fetchone()[0] == 0:
#         for i in range(10):
#             day = (datetime.today() + timedelta(days=i)).date().isoformat()
#             for proc in ["Cutting", "Gluing", "Packing"]:
#                 cursor.execute("INSERT INTO process_capacity (process_name, date, max_sqft, max_jobs) VALUES (?, ?, ?, ?)",
#                                (proc, day, 5000, 5))

#     conn.commit()
#     conn.close()

# # Retrieve all scheduled jobs
# def get_schedule():
#     conn = connect_db()
#     cursor = conn.cursor()
#     cursor.execute("SELECT rowid, job_id, process_name, date, sqft FROM scheduled_processes ORDER BY job_id, date")
#     rows = cursor.fetchall()
#     conn.close()
#     return rows

# # Check if scheduling more sqft on a day exceeds capacity
# # (Unused in new logic, but left for conflict highlighting)
# def can_update_schedule(process_name, date, sqft):
#     conn = connect_db()
#     cursor = conn.cursor()
#     cursor.execute("SELECT COALESCE(SUM(sqft), 0), COUNT(*) FROM scheduled_processes WHERE process_name = ? AND date = ?",
#                    (process_name, date))
#     used_sqft, used_jobs = cursor.fetchone()
#     cursor.execute("SELECT max_sqft, max_jobs FROM process_capacity WHERE process_name = ? AND date = ?",
#                    (process_name, date))
#     row = cursor.fetchone()
#     conn.close()
#     if row:
#         max_sqft, max_jobs = row
#         return (used_sqft + sqft <= max_sqft) and (used_jobs + 1 <= max_jobs)
#     return False

# # Find the next available date with enough capacity for a process (used per chunk)
# def find_next_available_day(process_name, sqft, earliest_date=None):
#     conn = connect_db()
#     cursor = conn.cursor()
#     base_date = datetime.today().date() if not earliest_date else datetime.fromisoformat(earliest_date).date()
#     for i in range(30):  # Look ahead up to 30 days
#         check_date = (base_date + timedelta(days=i)).isoformat()
#         cursor.execute("SELECT max_sqft FROM process_capacity WHERE process_name = ? AND date = ?",
#                        (process_name, check_date))
#         row = cursor.fetchone()
#         if row:
#             max_sqft = row[0]
#         else:
#             max_sqft = 5000
#             cursor.execute("INSERT INTO process_capacity (process_name, date, max_sqft, max_jobs) VALUES (?, ?, ?, ?)",
#                            (process_name, check_date, max_sqft, 5))
#             conn.commit()

#         cursor.execute("SELECT COALESCE(SUM(sqft), 0) FROM scheduled_processes WHERE process_name = ? AND date = ?",
#                        (process_name, check_date))
#         used = cursor.fetchone()[0]
#         if used < max_sqft:
#             conn.close()
#             return check_date
#     conn.close()
#     return None

# # Schedule a job process across dates based on capacity, even if it exceeds one day's max sqft
# def schedule_process(job_id, process_name, sqft, earliest_date=None):
#     remaining = sqft
#     current_date = earliest_date or datetime.today().date().isoformat()
#     while remaining > 0:
#         date = find_next_available_day(process_name, remaining, current_date)
#         if not date:
#             break
#         conn = connect_db()
#         cursor = conn.cursor()
#         cursor.execute("SELECT COALESCE(SUM(sqft), 0) FROM scheduled_processes WHERE process_name = ? AND date = ?",
#                        (process_name, date))
#         used = cursor.fetchone()[0]
#         cursor.execute("SELECT max_sqft FROM process_capacity WHERE process_name = ? AND date = ?",
#                        (process_name, date))
#         row = cursor.fetchone()
#         max_sqft = row[0] if row else 5000
#         available = max_sqft - used
#         allocate = min(available, remaining)
#         if allocate <= 0:
#             current_date = (datetime.fromisoformat(date) + timedelta(days=1)).isoformat()
#             continue
#         cursor.execute("INSERT INTO scheduled_processes (job_id, process_name, date, sqft) VALUES (?, ?, ?, ?)",
#                        (job_id, process_name, date, allocate))
#         conn.commit()
#         conn.close()
#         remaining -= allocate
#         current_date = (datetime.fromisoformat(date) + timedelta(days=1)).isoformat()
#     return current_date

# # Try to update a row; if conflict, auto-move to next available date
# def update_schedule_entry(rowid, new_date):
#     conn = connect_db()
#     cursor = conn.cursor()
#     cursor.execute("SELECT job_id, process_name, sqft FROM scheduled_processes WHERE rowid = ?", (rowid,))
#     result = cursor.fetchone()
#     if not result:
#         conn.close()
#         return False, "Entry not found."

#     job_id, process_name, sqft = result

#     if can_update_schedule(process_name, new_date, sqft):
#         cursor.execute("UPDATE scheduled_processes SET date = ? WHERE rowid = ?", (new_date, rowid))
#         conn.commit()
#         conn.close()
#         return True, "Date updated successfully."
#     else:
#         alt_date = find_next_available_day(process_name, sqft, earliest_date=new_date)
#         if alt_date:
#             cursor.execute("UPDATE scheduled_processes SET date = ? WHERE rowid = ?", (alt_date, rowid))
#             conn.commit()
#             conn.close()
#             return True, f"Capacity full on {new_date}. Auto-moved to {alt_date}."

#     conn.close()
#     return False, "No available date found."

# # Reschedule all processes for all jobs
# def reschedule_all_jobs():
#     conn = connect_db()
#     cursor = conn.cursor()
#     cursor.execute("SELECT DISTINCT job_id, MAX(sqft) FROM scheduled_processes GROUP BY job_id")
#     jobs = cursor.fetchall()
#     cursor.execute("DELETE FROM scheduled_processes")
#     conn.commit()
#     conn.close()
#     for job_id, sqft in jobs:
#         last_date = None
#         for proc in ["Cutting", "Gluing", "Packing"]:
#             last_date = schedule_process(job_id, proc, sqft, last_date)
#             if last_date:
#                 last_date = (datetime.fromisoformat(last_date) + timedelta(days=1)).isoformat()

# # GUI Application class
# class CapacitySchedulerApp(tk.Tk):
#     def __init__(self):
#         super().__init__()
#         self.title("Capacity-Based Auto Scheduler")
#         self.geometry("700x550")

#         self.tree = ttk.Treeview(self, columns=("RowID", "Job ID", "Process", "Date", "Sqft"), show="headings")
#         for col in self.tree["columns"]:
#             self.tree.heading(col, text=col)
#             self.tree.column(col, anchor="center")
#         self.tree.pack(fill="both", expand=True, padx=10, pady=10)

#         self.form_frame = ttk.Frame(self)
#         self.form_frame.pack(pady=5)

#         ttk.Label(self.form_frame, text="Job ID:").grid(row=0, column=0)
#         self.job_entry = ttk.Entry(self.form_frame, width=10)
#         self.job_entry.grid(row=0, column=1)

#         ttk.Label(self.form_frame, text="Sqft:").grid(row=0, column=2)
#         self.sqft_entry = ttk.Entry(self.form_frame, width=10)
#         self.sqft_entry.grid(row=0, column=3)

#         self.schedule_btn = ttk.Button(self.form_frame, text="Schedule Job", command=self.schedule_job)
#         self.schedule_btn.grid(row=0, column=4, padx=5)

#         ttk.Label(self.form_frame, text="Update RowID:").grid(row=1, column=0)
#         self.update_rowid = ttk.Entry(self.form_frame, width=10)
#         self.update_rowid.grid(row=1, column=1)

#         ttk.Label(self.form_frame, text="New Date:").grid(row=1, column=2)
#         self.update_date = DateEntry(self.form_frame, width=12, dateformat="%Y-%m-%d")
#         self.update_date.grid(row=1, column=3)

#         self.update_btn = ttk.Button(self.form_frame, text="Update Schedule", command=self.update_schedule)
#         self.update_btn.grid(row=1, column=4, padx=5)

#         self.reschedule_btn = ttk.Button(self.form_frame, text="Reschedule All", command=self.reschedule_all)
#         self.reschedule_btn.grid(row=2, column=0, columnspan=5, pady=10, sticky="ew")

#         self.load_schedule()

#     def schedule_job(self):
#         job_id = int(self.job_entry.get())
#         sqft = int(self.sqft_entry.get())
#         last_date = None
#         for proc in ["Cutting", "Gluing", "Packing"]:
#             last_date = schedule_process(job_id, proc, sqft, last_date)
#             if last_date:
#                 last_date = (datetime.fromisoformat(last_date) + timedelta(days=1)).isoformat()
#         self.load_schedule()

#     def update_schedule(self):
#         try:
#             rowid = int(self.update_rowid.get())
#             new_date = self.update_date.entry.get()
#             datetime.strptime(new_date, "%Y-%m-%d")
#             success, msg = update_schedule_entry(rowid, new_date)
#             if success:
#                 messagebox.showinfo("Updated", msg)
#                 self.load_schedule()
#             else:
#                 messagebox.showwarning("Schedule Conflict", msg)
#         except Exception as e:
#             messagebox.showerror("Update Error", str(e))

#     def reschedule_all(self):
#         if messagebox.askyesno("Confirm", "This will erase and reallocate all scheduled processes. Continue?"):
#             reschedule_all_jobs()
#             self.load_schedule()

#     def load_schedule(self):
#         for row in self.tree.get_children():
#             self.tree.delete(row)
#         for row in get_schedule():
#             tags = []
#             if not can_update_schedule(row[2], row[3], row[4]):
#                 tags = ["conflict"]
#             self.tree.insert("", "end", values=row, tags=tags)
#         self.tree.tag_configure("conflict", background="#ffcccc")

# if __name__ == "__main__":
#     init_db()
#     app = CapacitySchedulerApp()
#     app.mainloop()
