import sqlite3
import tkinter as tk
import ttkbootstrap as tb
from ttkbootstrap.constants import *
from tkinter import messagebox

class SchedulerChainFrame(tb.Frame):
    def __init__(self, master, db_path="prod_db.db"):
        super().__init__(master, padding=10)
        self.db_path = db_path
        self.grid(sticky="nsew")

        # Configure row/column weights for resizing
        master.rowconfigure(0, weight=1)
        master.columnconfigure(0, weight=1)
        self.rowconfigure(2, weight=1)
        self.columnconfigure(0, weight=1)

        # ---- Input form ----
        tb.Label(self, text="Job Size (MSF):").grid(row=0, column=0, sticky=W, padx=5, pady=5)
        self.job_size_var = tk.StringVar(value="20000")
        tb.Entry(self, textvariable=self.job_size_var, width=10).grid(row=0, column=1, sticky=W, padx=5, pady=5)

        tb.Button(self, text="Run Schedule", bootstyle=SUCCESS, command=self.run_schedule).grid(row=0, column=3, sticky=W, padx=10, pady=5)

        # ---- Process selection frame ----
        proc_frame = tb.Frame(self)
        proc_frame.grid(row=1, column=0, columnspan=4, sticky="nsew", padx=5, pady=5)
        proc_frame.columnconfigure(0, weight=1)
        proc_frame.columnconfigure(1, weight=1)
        proc_frame.rowconfigure(1, weight=1)

        # Load processes from DB
        self.load_processes()

        # Available Processes Listbox
        tb.Label(proc_frame, text="Available Processes").grid(row=0, column=0, sticky=W)
        self.available_listbox = tk.Listbox(proc_frame, selectmode=tk.SINGLE, height=10, exportselection=False)
        self.available_listbox.grid(row=1, column=0, sticky="nsew", padx=5, pady=5)

        # Selected Sequence Listbox
        tb.Label(proc_frame, text="Selected Sequence").grid(row=0, column=1, sticky=W)
        self.selected_listbox = tk.Listbox(proc_frame, selectmode=tk.SINGLE, height=10, exportselection=False)
        self.selected_listbox.grid(row=1, column=1, sticky="nsew", padx=5, pady=5)

        # Enable drag-and-drop for reordering
        self.enable_drag_and_drop(self.selected_listbox)

        # Buttons for add/remove
        btn_frame = tb.Frame(proc_frame)
        btn_frame.grid(row=1, column=2, sticky="ns", padx=5, pady=5)
        tb.Button(btn_frame, text="Add →", bootstyle=PRIMARY, command=self.add_process).grid(row=0, column=0, sticky="ew", pady=2)
        tb.Button(btn_frame, text="← Remove", bootstyle=WARNING, command=self.remove_process).grid(row=1, column=0, sticky="ew", pady=2)

        # Populate available_listbox
        for pid, pname in self.processes:
            self.available_listbox.insert(END, f"{pid} - {pname}")

        # ---- Results treeview ----
        self.tree = tb.Treeview(
            self,
            columns=("seq", "process", "start", "end", "capacity", "breakdown", "chain_start", "chain_end"),
            show="headings"
        )
        self.tree.grid(row=2, column=0, columnspan=4, sticky="nsew", padx=5, pady=10)
        self.rowconfigure(2, weight=1)
        self.columnconfigure(3, weight=1)

        for col, text in zip(
            ("seq", "process", "start", "end", "capacity", "breakdown", "chain_start", "chain_end"),
            ("Seq", "Process", "Start Date", "End Date", "Capacity", "Breakdown", "Chain Start", "Chain End")
        ):
            self.tree.heading(col, text=text)
            self.tree.column(col, width=120, anchor=W)

    def init_connection(self):
        return sqlite3.connect(self.db_path)

    def load_processes(self):
        """Load available processes from DB"""
        try:
            conn = self.init_connection()
            cur = conn.cursor()
            cur.execute("SELECT id, process_name FROM process ORDER BY id;")
            self.processes = cur.fetchall()  # [(id, name), ...]
            conn.close()
        except Exception as e:
            messagebox.showerror("Database Error", str(e))
            self.processes = []

    # ---- Process selection helpers ----
    def add_process(self):
        sel = self.available_listbox.curselection()
        if not sel: return
        idx = sel[0]
        item = self.available_listbox.get(idx)
        if item not in self.selected_listbox.get(0, END):
            self.selected_listbox.insert(END, item)

    def remove_process(self):
        sel = self.selected_listbox.curselection()
        if not sel: return
        idx = sel[0]
        self.selected_listbox.delete(idx)

    def enable_drag_and_drop(self, listbox):
        """Enable drag-and-drop reordering of a Listbox"""
        listbox.bind("<Button-1>", self.on_drag_start)
        listbox.bind("<B1-Motion>", self.on_drag_motion)
        listbox.bind("<ButtonRelease-1>", self.on_drag_drop)

    def on_drag_start(self, event):
        widget = event.widget
        self.drag_start_index = widget.nearest(event.y)

    def on_drag_motion(self, event):
        widget = event.widget
        i = widget.nearest(event.y)
        if i < 0 or i >= widget.size():
            return
        widget.selection_clear(0, END)
        widget.selection_set(i)

    def on_drag_drop(self, event):
        widget = event.widget
        drag_end_index = widget.nearest(event.y)
        if drag_end_index == self.drag_start_index:
            return
        item = widget.get(self.drag_start_index)
        widget.delete(self.drag_start_index)
        widget.insert(drag_end_index, item)
        widget.selection_clear(0, END)

    # ---- Scheduling ----
    def run_schedule(self):
        try:
            job_size = int(self.job_size_var.get())
        except ValueError:
            messagebox.showwarning("Invalid Input", "Please enter a valid integer for job size (MSF).")
            return

        selected = []
        for i in range(self.selected_listbox.size()):
            item = self.selected_listbox.get(i)
            pid = int(item.split(" - ")[0])
            selected.append(pid)

        if not selected:
            messagebox.showwarning("No Processes", "Please select at least one process.")
            return

        query = self.build_query(job_size, selected)

        try:
            conn = self.init_connection()
            cur = conn.cursor()
            cur.execute(query)
            rows = cur.fetchall()
            conn.close()
        except Exception as e:
            messagebox.showerror("Query Error", str(e))
            return

        # Clear treeview
        for i in self.tree.get_children():
            self.tree.delete(i)

        # Insert results
        for row in rows:
            self.tree.insert("", END, values=row)

    def build_query(self, job_size, process_ids):
        print(process_ids)
        """Build SQL dynamically using process sequence from selected_listbox"""
        values = ",\n        ".join(f"({i+1}, {pid})" for i, pid in enumerate(process_ids))

        sql = f"""
WITH params AS (
    SELECT {job_size} AS job_msf, 15 AS max_consec_days
),
process_sequence(seq_order, pid) AS (
    VALUES
        {values}
),
process_list AS (
    SELECT p.id, p.process_name, s.seq_order
    FROM process_sequence s
    JOIN process p ON p.id = s.pid
    ORDER BY s.seq_order
),
process_count AS (
    SELECT COUNT(*) AS n FROM process_list
),
future_dates AS (
    SELECT date('now', '+8 day') AS d
    UNION ALL
    SELECT date(d, '+1 day')
    FROM future_dates
    WHERE d < date('now', '+60 day')
),
capacity_per_day AS (
    SELECT 
        fd.d AS date,
        pl.seq_order,
        pl.process_name,
        COALESCE(pc.max_sqft,
                 (SELECT max_sqft FROM process_capacity
                  WHERE process_name = pl.process_name AND date IS NULL)
        )
        - COALESCE((SELECT SUM(CAST(o.msf AS REAL))
                    FROM order_routing o
                    WHERE o.process_nme = pl.process_name
                      AND substr(o.scheduled_dte,1,10) = fd.d
                  ),0) AS available_sqft
    FROM future_dates fd
    JOIN process_list pl
    LEFT JOIN process_capacity pc
           ON pc.date = fd.d AND pc.process_name = pl.process_name
    WHERE strftime('%w', fd.d) NOT IN ('0','6')
),
windows AS (
    SELECT 
        seq_order,
        process_name,
        date AS start_date,
        date AS end_date,
        available_sqft,
        available_sqft AS total_available,
        1 AS days_used,
        date || ':' || available_sqft AS breakdown
    FROM capacity_per_day
    WHERE available_sqft > 0

    UNION ALL

    SELECT
        w.seq_order,
        w.process_name,
        w.start_date,
        c.date AS end_date,
        c.available_sqft,
        w.total_available + c.available_sqft AS total_available,
        w.days_used + 1 AS days_used,
        w.breakdown || ' | ' || c.date || ':' || c.available_sqft AS breakdown
    FROM windows w
    JOIN capacity_per_day c
      ON c.process_name = w.process_name
     AND c.date = (
           SELECT MIN(fd2.date)
           FROM capacity_per_day fd2
           WHERE fd2.process_name = w.process_name
             AND fd2.date > w.end_date
             AND fd2.available_sqft > 0
       )
    JOIN params p
      ON w.total_available < p.job_msf
     AND w.days_used < p.max_consec_days
),
feasible_windows AS (
    SELECT w.* FROM windows w, params
    WHERE w.total_available >= params.job_msf
),
chain AS (
    SELECT
        f.seq_order,
        f.process_name,
        f.start_date,
        f.end_date,
        f.total_available,
        f.breakdown,
        f.start_date AS chain_start,
        f.end_date   AS chain_end
    FROM feasible_windows f
    WHERE f.seq_order = 1
      AND f.start_date = (SELECT MIN(start_date) FROM feasible_windows WHERE seq_order = 1)
      AND f.end_date = (
            SELECT MIN(end_date)
            FROM feasible_windows
            WHERE seq_order = 1
              AND start_date = (SELECT MIN(start_date) FROM feasible_windows WHERE seq_order = 1)
        )

    UNION ALL

    SELECT
        n.seq_order,
        n.process_name,
        n.start_date,
        n.end_date,
        n.total_available,
        n.breakdown,
        ch.chain_start,
        n.end_date AS chain_end
    FROM chain ch
    JOIN feasible_windows n
      ON n.seq_order = ch.seq_order + 1
     AND n.start_date >= date(ch.end_date, '+1 day')
    WHERE n.start_date = (
            SELECT MIN(start_date)
            FROM feasible_windows x
            WHERE x.seq_order = ch.seq_order + 1
              AND x.start_date >= date(ch.end_date, '+1 day')
        )
      AND n.end_date = (
            SELECT MIN(end_date)
            FROM feasible_windows x
            WHERE x.seq_order = ch.seq_order + 1
              AND x.start_date = (
                    SELECT MIN(start_date)
                    FROM feasible_windows y
                    WHERE y.seq_order = ch.seq_order + 1
                      AND y.start_date >= date(ch.end_date, '+1 day')
              )
        )
),
earliest_complete_chain AS (
    SELECT MIN(chain_start) AS chain_start
    FROM chain
    WHERE seq_order = (SELECT n FROM process_count)
)
SELECT
    ch.seq_order,
    ch.process_name,
    ch.start_date,
    ch.end_date,
    ch.total_available,
    ch.breakdown,
    ec.chain_start AS chain_start_date,
    (SELECT MAX(end_date) FROM chain WHERE chain_start = ec.chain_start) AS chain_end_date
FROM chain ch
CROSS JOIN earliest_complete_chain ec
WHERE ch.chain_start = ec.chain_start
ORDER BY ch.seq_order;
"""
        return sql


if __name__ == "__main__":
    app = tb.Window(themename="flatly")
    SchedulerChainFrame(app, db_path="prod_db.db")
    app.mainloop()
