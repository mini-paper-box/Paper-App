import tkinter as tk
import tkinter.font as tkFont
from tkinter import filedialog, messagebox
from ttkbootstrap import ttk
from ttkbootstrap import Style
from ttkbootstrap.constants import *
import csv, os, math
from sqlite import make_simple as ms
from emaily import Emaily
from pdf_reader import pdf_reader
from button import ControlButton, PurchaseOrderTree
from custom_class import CustomTreeview
from column_toggle_panel import ColumnTogglePanel
from undo_redo_manager import UndoRedoManager
from settings import *


class NewPurchaseOrderFrame(ttk.Frame):
    def __init__(self, master):
        super().__init__(master)
        self.columns = list(COLUMNS_CONFIG.keys())
        self.path = PO_PATH
        self._sort_column = None
        self._sort_reverse = False
        self.column_toggle_panel = None

        self.grid_rowconfigure(0, weight=0)
        self.grid_rowconfigure(1, weight=1)
        self.grid_rowconfigure(2, weight=0)
        self.grid_columnconfigure(0, weight=1)

        self.custom_font = tkFont.Font(family="Segoe UI", size=11)
        style = Style()
        style.configure("TreeviewPrimary.Treeview", font=self.custom_font, rowheight=28, bootstyle="info")
        style.configure("TreeviewPrimary.Treeview.Heading", font=(self.custom_font.actual("family"), 12, "bold"), bootstyle="info")
        style.map("TreeviewPrimary.Treeview", background=[("selected", "#1f6aa5")], foreground=[("selected", "white")])

        self.search_var = tk.StringVar()

        self.create_searchbar()
        self.create_treeview()
        self.create_buttons()
        self.auto_refresh_treeview()

    def one_click_process(self):
        data = pdf_reader().extract_files_info()
        if not data:
            messagebox.showwarning("No Data", "No purchase order data found.")
            return
        try:
            self.rename(data)
            self.submit_po(data)
            self.import_to_db(data)
            self.move_files(data)
            self.populate_treeview(data)
            messagebox.showinfo("Success", "All process completed successfully.")
        except Exception as e:
            messagebox.showerror("Error", f"An error occurred during the process: {e}")

    def create_searchbar(self):
        search_frame = ttk.Frame(self)
        search_frame.grid(row=0, column=0, sticky="ew", padx=10, pady=(5, 0))
        search_frame.columnconfigure(1, weight=1)

        ttk.Label(search_frame, text="Search:", font=self.custom_font).grid(row=0, column=0, sticky="w", padx=(0,5))
        search_entry = ttk.Entry(search_frame, textvariable=self.search_var, font=self.custom_font)
        search_entry.grid(row=0, column=1, sticky="ew")
        search_entry.bind("<KeyRelease>", lambda e: self.apply_search_filter())

    def create_treeview(self):
        tree_frame = ttk.Frame(self)
        tree_frame.grid(row=1, column=0, sticky="nsew", padx=10, pady=10)
        tree_frame.rowconfigure(0, weight=1)
        tree_frame.columnconfigure(0, weight=1)

        self.tree = CustomTreeview(tree_frame, self.columns)
        scrollbar = ttk.Scrollbar(tree_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)
        self.tree.grid(row=0, column=0, sticky="nsew")
        scrollbar.grid(row=0, column=1, sticky="ns")

        for col in self.columns:
            self.tree.heading(col, text=COLUMNS_CONFIG[col], command=lambda c=col: self.sort_column(c))
            anchor = "w" if col in {'supplier_name', 'material', 'sheet_size', 'purchase_order_number', 'file_name'} else "e"
            self.tree.column(col, width=100, anchor=anchor)

        self.tree.tag_configure("overdue", background="#ffcccc")
        self.tree.tag_configure("upcoming", background="#fff2cc")
        self.tree.tag_configure("even", background="white")
        self.tree.tag_configure("odd", background="#f2f2f2")

    def create_buttons(self):
        btn_frame = ttk.Frame(self)
        btn_frame.grid(row=2, column=0, pady=5)
        ttk.Button(btn_frame, text="One-Click Process", bootstyle="warning", command=self.one_click_process).grid(row=0, column=0, padx=5)

    def populate_treeview(self, data):
        self.tree.delete(*self.tree.get_children())
        rows_to_use = [dict(zip(self.columns, [*d])) for d in data]

        from datetime import datetime, timedelta

        for index, row in enumerate(rows_to_use):
            try:
                width = float(row.get('width', 0))
                length = float(row.get('length', 0))
                qty = int(row.get('ordered_quantity', 0))
                row['ordered_msf'] = f"{width * length / 144 * qty / 1000:.3f}"
            except Exception:
                row['ordered_msf'] = ""

            try:
                req_date = datetime.strptime(row.get('requested_date', ''), '%Y-%m-%d')
                days_until = (req_date - datetime.today()).days
                if days_until < 0:
                    tag = 'overdue'
                elif days_until <= 3:
                    tag = 'upcoming'
                else:
                    tag = 'even' if index % 2 == 0 else 'odd'
            except:
                tag = 'even' if index % 2 == 0 else 'odd'

            values = [row.get(col, "") for col in self.columns]
            self.tree.insert("", "end", values=values, tags=(tag,))

        self.autosize_columns()

    def auto_refresh_treeview(self, interval=5000):
        self.after(interval, self.auto_refresh_treeview, interval)

    def autosize_columns(self):
        for col in self.tree["columns"]:
            header_text = COLUMNS_CONFIG.get(col, col)
            max_width = self.custom_font.measure(header_text) + 20
            for item in self.tree.get_children():
                cell_text = str(self.tree.set(item, col))
                max_width = max(max_width, self.custom_font.measure(cell_text) + 10)
            self.tree.column(col, width=max_width)

    def sort_column(self, col):
        data = [(self.tree.set(k, col), k) for k in self.tree.get_children()]
        def convert(val):
            try: return float(val)
            except: return val
        data.sort(key=lambda t: convert(t[0]), reverse=self._sort_reverse)
        for index, (_, k) in enumerate(data):
            self.tree.move(k, '', index)
        self._sort_reverse = not self._sort_reverse
        self._sort_column = col

    def apply_search_filter(self):
        term = self.search_var.get().lower()
        filtered_rows = []
        for d in pdf_reader().extract_files_info():
            row = dict(zip(self.columns, [*d]))
            if any(term in str(row.get(col, "")).lower() for col in self.columns):
                filtered_rows.append(row)
        self.populate_treeview(filtered_rows)

    def rename(self, data):
        pdf_reader().rename_files()

    def move_files(self, data):
        suppliers = {row[0] for row in data}
        email = Emaily(self)
        for supplier in suppliers:
            email.move_files(supplier)

    def import_to_db(self, data):
        db_data = []
        for row in data:
            row = list(row)
            row[0] = ms().get_supplier_id(row[0])
            db_data.append(row)
        if db_data:
            ms().insert_multiple_purchase_order(db_data)

    def submit_po(self, data):
        suppliers = {row[0] for row in data}
        email = Emaily(self)
        for supplier in suppliers:
            email.send_email(supplier)

    def update_multi_po(self, list_pos):
        ms().update_multi_po(list_pos)
        self.populate_treeview(pdf_reader().extract_files_info())

    def toggle_column_panel(self):
        if self.column_toggle_panel and self.column_toggle_panel.winfo_exists():
            self.column_toggle_panel.lift()
        else:
            self.column_toggle_panel = ColumnTogglePanel(self, self.columns, self.set_column_visibility)

    def set_column_visibility(self, column, visible):
        self.tree.heading(column, text=column if visible else "")
        self.tree.column(column, width=100 if visible else 0)