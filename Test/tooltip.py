# import ttkbootstrap as tb
# from ttkbootstrap.constants import *
# from ttkbootstrap.widgets import Meter, DateEntry
# import sqlite3
# from datetime import datetime, timedelta, date
# from tkinter import messagebox
# from dateutil import parser


# class OrderDashboardApp:
#     def __init__(self):
#         self.app = tb.Window(themename="flatly")
#         self.app.title("Order / PO Dashboard")
#         self.app.geometry("1200x700")

#         self.conn = sqlite3.connect("orders.db")
#         self.conn.row_factory = sqlite3.Row
#         self.cursor = self.conn.cursor()

#         self.setup_database()
#         self.insert_dummy_data()

#         self.build_meters()
#         self.build_filters()
#         self.build_treeview()
#         self.build_buttons()
#         self.build_statusbar()

#         self.refresh_data()
#         self.set_default_dates()

#         self.app.mainloop()

#     def setup_database(self):
#         self.cursor.execute("""
#             CREATE TABLE IF NOT EXISTS orders (
#                 id INTEGER PRIMARY KEY AUTOINCREMENT,
#                 order_id TEXT UNIQUE,
#                 customer TEXT,
#                 date TEXT,
#                 status TEXT,
#                 total TEXT
#             )
#         """)
#         self.cursor.execute("""
#             CREATE TABLE IF NOT EXISTS status_log (
#                 id INTEGER PRIMARY KEY AUTOINCREMENT,
#                 order_id TEXT,
#                 old_status TEXT,
#                 new_status TEXT,
#                 changed_on TEXT
#             )
#         """)
#         self.conn.commit()

#     def insert_dummy_data(self):
#         self.cursor.execute("SELECT COUNT(*) as count FROM orders")
#         if self.cursor.fetchone()["count"] == 0:
#             dummy_orders = [
#                 ("PO1001", "ACME Corp", "2025-06-15", "Shipped", "$1,250"),
#                 ("PO1002", "Globex", "2025-06-18", "Pending", "$840"),
#                 ("PO1003", "ACME Corp", "2025-06-20", "Cancelled", "$500"),
#                 ("PO1004", "Soylent", "2025-06-25", "Shipped", "$2,100"),
#             ]
#             for order in dummy_orders:
#                 try:
#                     self.cursor.execute("INSERT INTO orders (order_id, customer, date, status, total) VALUES (?, ?, ?, ?, ?)", order)
#                 except sqlite3.IntegrityError:
#                     pass
#             self.conn.commit()

#     def build_meters(self):
#         self.top = tb.Frame(self.app)
#         self.top.grid(row=0, column=0, columnspan=2, padx=10, pady=10, sticky="ew")

#         self.meters = [
#             Meter(self.top, bootstyle="info", subtext="Total Orders", amountused=0, metertype='semi'),
#             Meter(self.top, bootstyle="warning", subtext="Pending", amountused=0, metertype='semi'),
#             Meter(self.top, bootstyle="success", subtext="Shipped", amountused=0, metertype='semi'),
#             Meter(self.top, bootstyle="danger", subtext="Cancelled", amountused=0, metertype='semi'),
#             Meter(self.top, bootstyle="secondary", subtext="Total $ Value", amountused=0, metertype='semi'),
#             Meter(self.top, bootstyle="primary", subtext="Target Orders", amountused=0, amounttotal=10, metertype='semi')
#         ]

#         for i, meter in enumerate(self.meters):
#             meter.grid(row=0, column=i, padx=5)

#     def build_filters(self):
#         self.filter_frame = tb.LabelFrame(self.app, text="Filters", padding=10)
#         self.filter_frame.grid(row=1, column=0, columnspan=2, padx=10, sticky="ew")

#         tb.Label(self.filter_frame, text="Start Date").grid(row=0, column=0, padx=5, pady=5)
#         self.start_date = DateEntry(self.filter_frame)
#         self.start_date.grid(row=0, column=1, padx=5)

#         tb.Label(self.filter_frame, text="End Date").grid(row=0, column=2, padx=5)
#         self.end_date = DateEntry(self.filter_frame)
#         self.end_date.grid(row=0, column=3, padx=5)

#         tb.Label(self.filter_frame, text="Customer").grid(row=0, column=4, padx=5)
#         self.customer_filter = tb.Combobox(self.filter_frame, values=["All"], width=15)
#         self.customer_filter.current(0)
#         self.customer_filter.grid(row=0, column=5, padx=5)

#         tb.Label(self.filter_frame, text="Status").grid(row=0, column=6, padx=5)
#         self.status_filter = tb.Combobox(self.filter_frame, values=["All", "Pending", "Shipped", "Cancelled"], width=12)
#         self.status_filter.current(0)
#         self.status_filter.grid(row=0, column=7, padx=5)

#         tb.Button(self.filter_frame, text="Apply Filters", bootstyle="primary", command=self.apply_filters).grid(row=0, column=8, padx=10)

#     def set_default_dates(self):
#         self.start_date.entry.delete(0, 'end')
#         self.start_date.entry.insert(0, (date.today() - timedelta(days=30)).isoformat())
#         self.end_date.entry.delete(0, 'end')
#         self.end_date.entry.insert(0, date.today().isoformat())

#     def build_treeview(self):
#         self.tree_frame = tb.Frame(self.app)
#         self.tree_frame.grid(row=2, column=0, columnspan=2, sticky="nsew", padx=10, pady=10)

#         self.columns = ("Order ID", "Customer", "Date", "Status", "Total")
#         self.tree = tb.Treeview(self.tree_frame, columns=self.columns, show="headings", bootstyle="primary")
#         for col in self.columns:
#             self.tree.heading(col, text=col)
#             self.tree.column(col, width=150, anchor="center")
#         self.tree.grid(row=0, column=0, sticky="nsew")

#         self.tree_frame.rowconfigure(0, weight=1)
#         self.tree_frame.columnconfigure(0, weight=1)

#     def build_buttons(self):
#         self.btn_frame = tb.Frame(self.app)
#         self.btn_frame.grid(row=3, column=0, columnspan=2, pady=5)

#         tb.Button(self.btn_frame, text="Add Order", bootstyle="success", command=self.add_order).grid(row=0, column=0, padx=5)
#         tb.Button(self.btn_frame, text="Edit Order", bootstyle="warning", command=self.edit_order).grid(row=0, column=1, padx=5)
#         tb.Button(self.btn_frame, text="Delete Order", bootstyle="danger", command=self.delete_order).grid(row=0, column=2, padx=5)
#         tb.Button(self.btn_frame, text="Change Status", bootstyle="info", command=self.change_status).grid(row=0, column=3, padx=5)
#         tb.Button(self.btn_frame, text="View Status Log", bootstyle="secondary", command=self.show_status_log).grid(row=0, column=4, padx=5)

#     def build_statusbar(self):
#         self.status_bar = tb.Label(self.app, text="Ready", anchor=W, relief="solid", bootstyle="light")
#         self.status_bar.grid(row=4, column=0, columnspan=2, sticky="ew")

#         self.app.grid_rowconfigure(2, weight=1)
#         self.app.grid_columnconfigure(0, weight=1)
#         self.app.grid_columnconfigure(1, weight=1)


#     def refresh_data(self):
#         self.tree.delete(*self.tree.get_children())
#         self.cursor.execute("SELECT * FROM orders")
#         rows = self.cursor.fetchall()
#         for row in rows:
#             self.tree.insert("", END, values=(row["order_id"], row["customer"], row["date"], row["status"], row["total"]))
#         self.update_meters(rows)
#         self.update_customer_filter()

#     def parse_currency(self, value):
#         try:
#             return float(value.replace('$', '').replace(',', ''))
#         except:
#             return 0
        
#     def change_status(self):
#         selected_items = self.tree.selection()
#         if not selected_items:
#             messagebox.showwarning("No selection", "Please select one or more orders to change status.")
#             return

#         status_options = ["Pending", "Shipped", "Cancelled"]
#         status_window = tb.Toplevel(self.app)
#         status_window.title("Change Status")

#         tb.Label(status_window, text="Select new status:").grid(row=0, column=0, padx=10, pady=10)
#         status_combo = tb.Combobox(status_window, values=status_options, width=15)
#         status_combo.grid(row=0, column=1, padx=10, pady=10)
#         status_combo.current(0)

#         def apply_new_status():
#             new_status = status_combo.get()
#             for item in selected_items:
#                 values = self.tree.item(item, "values")
#                 order_id = values[0]
#                 old_status = values[3]
#                 if old_status != new_status:
#                     self.cursor.execute("UPDATE orders SET status = ? WHERE order_id = ?", (new_status, order_id))
#                     self.cursor.execute(
#                         "INSERT INTO status_log (order_id, old_status, new_status, changed_on) VALUES (?, ?, ?, ?)",
#                         (order_id, old_status, new_status, datetime.now().isoformat())
#                     )
#             self.conn.commit()
#             self.refresh_data()
#             status_window.destroy()

#         tb.Button(status_window, text="Apply", bootstyle="success", command=apply_new_status).grid(row=1, column=0, columnspan=2, pady=10)


#     def update_meters(self, rows):
#         total = len(rows)
#         pending = sum(1 for r in rows if r["status"] == "Pending")
#         shipped = sum(1 for r in rows if r["status"] == "Shipped")
#         cancelled = sum(1 for r in rows if r["status"] == "Cancelled")

#         total_value = sum(self.parse_currency(r["total"]) for r in rows if r["total"])
#         for meter, val in zip(self.meters, [total, pending, shipped, cancelled, total_value, total]):
#             meter.configure(amountused=val)

#     def update_customer_filter(self):
#         self.cursor.execute("SELECT DISTINCT customer FROM orders ORDER BY customer")
#         customers = ["All"] + [row["customer"] for row in self.cursor.fetchall()]
#         self.customer_filter['values'] = customers
#         if self.customer_filter.get() not in customers:
#             self.customer_filter.current(0)

#     def apply_filters(self):
#         query = "SELECT * FROM orders WHERE 1=1"
#         params = []

#         if self.customer_filter.get() != "All":
#             query += " AND customer=?"
#             params.append(self.customer_filter.get())
#         if self.status_filter.get() != "All":
#             query += " AND status=?"
#             params.append(self.status_filter.get())

#         try:
#             start = parser.parse(self.start_date.entry.get()).date()
#             end = parser.parse(self.end_date.entry.get()).date()
#             if start <= end:
#                 query += " AND date BETWEEN ? AND ?"
#                 params.extend([start.isoformat(), end.isoformat()])
#         except Exception:
#             pass

#         self.cursor.execute(query, params)
#         rows = self.cursor.fetchall()

#         self.tree.delete(*self.tree.get_children())
#         for row in rows:
#             self.tree.insert("", END, values=(row["order_id"], row["customer"], row["date"], row["status"], row["total"]))

#         self.update_meters(rows)

#     def get_selected(self):
#         selected = self.tree.selection()
#         if not selected:
#             return None
#         return self.tree.item(selected[0])["values"]

#     def delete_order(self):
#         selected = self.get_selected()
#         if not selected:
#             messagebox.showwarning("Delete", "Select an order to delete.")
#             return
#         confirm = messagebox.askyesno("Confirm Delete", f"Delete order {selected[0]}?")
#         if confirm:
#             self.cursor.execute("DELETE FROM orders WHERE order_id=?", (selected[0],))
#             self.conn.commit()
#             self.refresh_data()

#     def add_order(self):
#         self.open_editor("add")

#     def edit_order(self):
#         selected = self.get_selected()
#         if not selected:
#             messagebox.showwarning("Edit", "Select an order to edit.")
#             return
#         self.open_editor("edit", selected)

#     def open_editor(self, mode="add", existing=None):
#         editor = tb.Toplevel(self.app)
#         editor.title("Add Order" if mode == "add" else "Edit Order")
#         editor.geometry("400x350")

#         labels = ["Order ID", "Customer", "Date (YYYY-MM-DD)", "Status", "Total"]
#         entries = {}

#         for label in labels:
#             tb.Label(editor, text=label).pack(pady=4)
#             ent = tb.Entry(editor)
#             ent.pack(pady=2, fill=X, padx=20)
#             entries[label] = ent

#         if existing:
#             for label, val in zip(labels, existing):
#                 entries[label].insert(0, val)

#         def save():
#             vals = tuple(entries[label].get() for label in labels)
#             if not all(vals):
#                 messagebox.showerror("Error", "All fields are required.")
#                 return
#             try:
#                 datetime.strptime(vals[2], "%Y-%m-%d")
#             except Exception:
#                 messagebox.showerror("Invalid", "Date must be YYYY-MM-DD")
#                 return

#             try:
#                 if mode == "add":
#                     self.cursor.execute("INSERT INTO orders (order_id, customer, date, status, total) VALUES (?, ?, ?, ?, ?)", vals)
#                 else:
#                     self.cursor.execute("UPDATE orders SET order_id=?, customer=?, date=?, status=?, total=? WHERE order_id=?", (*vals, existing[0]))
#                 self.conn.commit()
#             except sqlite3.IntegrityError:
#                 messagebox.showerror("Error", f"Order ID '{vals[0]}' already exists.")
#                 return

#             self.refresh_data()
#             editor.destroy()

#         tb.Button(editor, text="Save", bootstyle="success", command=save).pack(pady=15)

#     def show_status_log(self):
#         log_window = tb.Toplevel(self.app)
#         log_window.title("Status Change Log")
#         log_window.geometry("700x400")

#         log_tree = tb.Treeview(log_window, columns=("Order ID", "Old", "New", "Changed On"), show="headings", bootstyle="info")
#         for col in ("Order ID", "Old", "New", "Changed On"):
#             log_tree.heading(col, text=col)
#             log_tree.column(col, width=150)
#         log_tree.pack(fill=BOTH, expand=YES, padx=10, pady=10)

#         self.cursor.execute("SELECT order_id, old_status, new_status, changed_on FROM status_log ORDER BY changed_on DESC LIMIT 50")
#         for row in self.cursor.fetchall():
#             log_tree.insert("", END, values=(row["order_id"], row["old_status"], row["new_status"], row["changed_on"]))


# if __name__ == "__main__":
#     OrderDashboardApp()

import tkinter as tk
from tkinter import filedialog
from ttkbootstrap import Style, Window
from ttkbootstrap import ttk

class FileTreeViewApp(tk.Frame):
    def __init__(self, master):
        super().__init__(master)
        self.pack(fill='both', expand=True)
        self.create_widgets()

    def create_widgets(self):
        # Configure grid for full expansion
        self.grid_rowconfigure(1, weight=1)  # Treeview expands vertically
        self.grid_columnconfigure(0, weight=1)

        # Input row (file path + browse button)
        input_frame = ttk.Frame(self)
        input_frame.grid(row=0, column=0, sticky="ew", padx=10, pady=10)
        input_frame.columnconfigure(0, weight=1)

        self.file_entry = ttk.Entry(input_frame)
        self.file_entry.grid(row=0, column=0, sticky="ew", padx=(0, 5))

        browse_btn = ttk.Button(input_frame, text="Browse", command=self.browse_file)
        browse_btn.grid(row=0, column=1)

        # Treeview
        tree_frame = ttk.Frame(self)
        tree_frame.grid(row=1, column=0, sticky="nsew", padx=10, pady=(0, 10))
        tree_frame.rowconfigure(0, weight=1)
        tree_frame.columnconfigure(0, weight=1)

        self.tree = ttk.Treeview(tree_frame, columns=("A", "B", "C"), show="headings")
        for col in ("A", "B", "C"):
            self.tree.heading(col, text=col)
            self.tree.column(col, anchor="w", width=120)
        self.tree.grid(row=0, column=0, sticky="nsew")

        scrollbar = ttk.Scrollbar(tree_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)
        scrollbar.grid(row=0, column=1, sticky="ns")

    def browse_file(self):
        filepath = filedialog.askopenfilename(filetypes=[("CSV Files", "*.csv"), ("All Files", "*.*")])
        if filepath:
            self.file_entry.delete(0, tk.END)
            self.file_entry.insert(0, filepath)
            self.load_file(filepath)

    def load_file(self, filepath):
        # Dummy load example — replace with your actual file reading
        self.tree.delete(*self.tree.get_children())
        for i in range(20):
            self.tree.insert("", "end", values=(f"Row {i+1} Col A", f"Row {i+1} Col B", f"Row {i+1} Col C"))

# Create and run the window
if __name__ == "__main__":
    style = Style("flatly")
    app = Window(title="Input + Treeview", themename="flatly", size=(700, 500))
    FileTreeViewApp(app)
    app.mainloop()

