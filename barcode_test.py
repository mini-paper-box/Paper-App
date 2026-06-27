import tkinter as tk
from ttkbootstrap import ttk
from datetime import datetime, timedelta
import sqlite3

DB_PATH = "scheduler.db"

# ---------------------------- DB SETUP ---------------------------- #
def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY,
            order_number TEXT,
            requested_date DATE,
            total_sqft REAL
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS order_routing (
            id INTEGER PRIMARY KEY,
            order_id INTEGER,
            process_name TEXT,
            sqft_needed REAL,
            sequence INTEGER,
            scheduled_start DATE,
            scheduled_end DATE
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS process_capacity (
            process_name TEXT,
            date DATE,
            available_sqft REAL,
            PRIMARY KEY (process_name, date)
        )
    """)
    conn.commit()
    conn.close()

# ---------------------------- UTILS ---------------------------- #
def skip_weekends(date):
    while date.weekday() >= 5:
        date += timedelta(days=1)
    return date

def get_capacity(process_name, date):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""SELECT available_sqft FROM process_capacity WHERE process_name=? AND date=?""",
              (process_name, date.isoformat()))
    row = c.fetchone()
    conn.close()
    return row[0] if row else 0

def reduce_capacity(process_name, date, sqft):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        UPDATE process_capacity
        SET available_sqft = available_sqft - ?
        WHERE process_name = ? AND date = ?
    """, (sqft, process_name, date.isoformat()))
    conn.commit()
    conn.close()

def update_schedule(routing_id, start_date):
    end_date = start_date  # For now, assume 1-day process
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        UPDATE order_routing
        SET scheduled_start=?, scheduled_end=?
        WHERE id=?
    """, (start_date.isoformat(), end_date.isoformat(), routing_id))
    conn.commit()
    conn.close()

# ---------------------------- SCHEDULER ---------------------------- #
def auto_schedule():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    c.execute("SELECT * FROM orders ORDER BY requested_date")
    orders = c.fetchall()

    for order in orders:
        order_id, order_num, req_date_str, total_sqft = order
        req_date = datetime.fromisoformat(req_date_str).date()
        earliest_date = datetime.today().date()

        c.execute("""
            SELECT * FROM order_routing
            WHERE order_id=? ORDER BY sequence
        """, (order_id,))
        processes = c.fetchall()

        for process in processes:
            proc_id, _, process_name, sqft_needed, _, _, _ = process

            # Find best slot within 5 days before deadline, fallback up to 10 days after
            found = False
            for offset in range(-5, 11):
                try_date = skip_weekends(req_date + timedelta(days=offset))
                if get_capacity(process_name, try_date) >= sqft_needed:
                    update_schedule(proc_id, try_date)
                    reduce_capacity(process_name, try_date, sqft_needed)
                    found = True
                    break
            if not found:
                print(f"⚠️ Could not schedule {process_name} for Order {order_num}")

    conn.close()

# ---------------------------- GUI ---------------------------- #
class SchedulerApp(ttk.Frame):
    def __init__(self, master):
        super().__init__(master)
        self.pack(fill="both", expand=True)

        self.tree = ttk.Treeview(self, columns=("Order", "Process", "Sqft", "Start", "End"), show="headings")
        for col in self.tree["columns"]:
            self.tree.heading(col, text=col)
        self.tree.pack(fill="both", expand=True, padx=10, pady=10)

        btn_frame = ttk.Frame(self)
        btn_frame.pack(pady=5)
        ttk.Button(btn_frame, text="Auto Schedule", command=self.run_scheduler).pack(side="left", padx=5)
        ttk.Button(btn_frame, text="Refresh", command=self.load_data).pack(side="left", padx=5)

        self.load_data()

    def run_scheduler(self):
        auto_schedule()
        self.load_data()

    def load_data(self):
        for row in self.tree.get_children():
            self.tree.delete(row)

        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("""
            SELECT o.order_number, r.process_name, r.sqft_needed, r.scheduled_start, r.scheduled_end
            FROM order_routing r
            JOIN orders o ON o.id = r.order_id
        """)
        for row in c.fetchall():
            self.tree.insert("", "end", values=row)
        conn.close()

# ---------------------------- MAIN ---------------------------- #
if __name__ == '__main__':
    init_db()  # Ensure tables exist

    root = tk.Tk()
    root.title("Auto Scheduler")
    root.geometry("800x500")
    app = SchedulerApp(root)
    root.mainloop()
