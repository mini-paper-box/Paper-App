import tkinter as tk
from ttkbootstrap import ttk
from ttkbootstrap.constants import *
from datetime import datetime
from tkinter import messagebox

class SchedulingFrame(ttk.Frame):
    def __init__(self, master, schedule_callback=None, reschedule_callback=None):
        super().__init__(master, padding=10)
        self.schedule_callback = schedule_callback
        self.reschedule_callback = reschedule_callback
        self.force_schedule = tk.BooleanVar(value=False)

        self.create_widgets()

    def create_widgets(self):
        # Top controls
        control_frame = ttk.Frame(self)
        control_frame.pack(fill=X, pady=5)

        ttk.Label(control_frame, text="Filter Date:").pack(side=LEFT, padx=(0, 5))
        self.date_entry = ttk.Entry(control_frame, width=15)
        self.date_entry.insert(0, datetime.today().strftime('%Y-%m-%d'))
        self.date_entry.pack(side=LEFT)

        ttk.Checkbutton(
            control_frame,
            text="Force Schedule",
            variable=self.force_schedule,
            bootstyle="warning"  # ← FIXED!
        ).pack(side=LEFT, padx=10)


        ttk.Button(control_frame, text="Reschedule All", bootstyle="primary", command=self.on_reschedule_all).pack(side=RIGHT)

        # Treeview for scheduled jobs
        self.tree = ttk.Treeview(self, columns=("Order", "Process", "Date", "MSF", "Note"), show="headings", height=15)
        for col in self.tree["columns"]:
            self.tree.heading(col, text=col)
            self.tree.column(col, anchor=W, width=120)
        self.tree.pack(fill=BOTH, expand=True, pady=(10, 0))

        # Status bar
        self.status = ttk.Label(self, text="Ready", anchor=W)
        self.status.pack(fill=X, pady=(10, 0))

    def on_reschedule_all(self):
        if self.reschedule_callback:
            self.status.config(text="🔄 Rescheduling...")
            try:
                force = self.force_schedule.get()
                self.reschedule_callback(force=force)
                self.status.config(text="✅ Rescheduling complete")
                self.update_tree_data()
            except Exception as e:
                messagebox.showerror("Error", str(e))
                self.status.config(text="❌ Rescheduling failed")

    def update_tree_data(self):
        # Clear tree
        for row in self.tree.get_children():
            self.tree.delete(row)

        # Load new data (placeholder logic; replace with real DB fetch)
        import sqlite3
        conn = sqlite3.connect("prod_db.db")
        cursor = conn.cursor()
        cursor.execute("""
            SELECT order_id, process_nme, schedule_dte, msf
            FROM order_routing
            WHERE schedule_dte IS NOT NULL
            ORDER BY schedule_dte
        """)
        rows = cursor.fetchall()
        for row in rows:
            self.tree.insert("", END, values=row)
        conn.close()
