import tkinter as tk
import tkinter.font as tkFont
from tkinter import filedialog, messagebox
from ttkbootstrap import ttk
from ttkbootstrap import Style
from ttkbootstrap.constants import *
import csv, os, math
from database import MakeSimpleSql
from emaily import Emaily
from pdf_reader import PDFReader as pr
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
        self.reader = pr()
        self.data = self.reader.extract_files_info()

        self.create_searchbar()
        self.create_treeview()
        self.create_buttons()
        self.populate_treeview()
        self.auto_refresh_treeview()

    def one_click_process(self):
        self.disable_buttons()
        self.status_message("Starting process...")

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

        self.tree = CustomTreeview(tree_frame, self.columns, mode = "extended")
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
        self.submit_button = ttk.Button(btn_frame, text="Send to Supplier", bootstyle="success", command=self.submit_po).grid(row=0, column=0, padx=5)
        ttk.Button(btn_frame, text="Export CSV", bootstyle="danger", command=self.export_csv).grid(row=0, column=1, padx=5)
        self.import_button = ttk.Button(btn_frame, text="Import to DB", bootstyle="info", command=self.import_to_db).grid(row=0, column=2, padx=5)
        self.rename_button = ttk.Button(btn_frame, text="Rename Files", bootstyle="secondary", command=self.rename).grid(row=0, column=3, padx=5)
        self.move_button = ttk.Button(btn_frame, text="Move Files", bootstyle="secondary", command=self.move_files).grid(row=0, column=4, padx=5)
        ttk.Button(btn_frame, text="Auto-Size Columns", bootstyle="secondary", command=self.autosize_columns).grid(row=0, column=5, padx=5)
        self.process_button = ttk.Button(btn_frame, text="One-Click Process", bootstyle="warning", command=self.one_click_process).grid(row=0, column=6, padx=5)

    def populate_treeview(self, rows=None):
        self.tree.delete(*self.tree.get_children())
        rows_to_use = rows if rows is not None else [dict(zip(self.columns, [*d])) for d in self.data]

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

        self.all_data = list(self.data)
        self.autosize_columns()

    def auto_refresh_treeview(self, interval=5000):
        new_data = self.reader.extract_files_info()
        if new_data != self.data:
            self.data = new_data
            self.populate_treeview()
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
        for d in self.data:
            row = dict(zip(self.columns, [*d]))
            if any(term in str(row.get(col, "")).lower() for col in self.columns):
                filtered_rows.append(row)
        self.populate_treeview(rows=filtered_rows)

    def export_csv(self):
        file_path = filedialog.asksaveasfilename(defaultextension=".csv", filetypes=[("CSV files", "*.csv")])
        if not file_path: return
        try:
            with open(file_path, mode='w', newline='') as f:
                writer = csv.writer(f)
                writer.writerow(self.columns)
                for row_id in self.tree.get_children():
                    writer.writerow(self.tree.item(row_id)['values'])
            messagebox.showinfo("Export", "Data exported successfully.")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to export: {e}")

    def rename(self):
        self.reader.rename_files()
        self.data = self.reader.extract_files_info()
        self.populate_treeview()

    def move_files(self):
        suppliers = {self.tree.item(item)['values'][0] for item in self.tree.get_children()}
        email = Emaily(self)
        for supplier in suppliers:
            email.move_files(supplier)
        self.data = self.reader.extract_files_info()
        self.populate_treeview()

    def import_to_db(self):
        data = []
        for item in self.tree.get_children():
            row = self.tree.item(item)['values']
            row[0] = MakeSimpleSql().get_supplier_id(row[0])
            data.append(row)
        if data:
            MakeSimpleSql().in_or_up_purchase_order(data)

    def submit_po(self):
        suppliers = {self.tree.item(item)['values'][0] for item in self.tree.get_children()}
        email = Emaily(self)
        for supplier in suppliers:
            email.send_email(supplier)

    def update_multi_po(self, list_pos):
        MakeSimpleSql().update_multi_po(list_pos)
        self.populate_treeview()

    def toggle_column_panel(self):
        if self.column_toggle_panel and self.column_toggle_panel.winfo_exists():
            self.column_toggle_panel.lift()
        else:
            self.column_toggle_panel = ColumnTogglePanel(self, self.columns, self.set_column_visibility)

    def set_column_visibility(self, column, visible):
        self.tree.heading(column, text=column if visible else "")
        self.tree.column(column, width=100 if visible else 0)

    def one_click_process(self):
        self.disable_buttons()  # Optional: disable UI during processing
        self.status_message("Starting process...")

        # Step 1: Rename
        self.after(100, self._do_rename)

    def _do_rename(self):
        try:
            self.rename()
            self.status_message("Renamed successfully.")
            self.after(100, self._do_submit_po)
        except Exception as e:
            self._handle_error("Rename failed", e)

    def _do_submit_po(self):
        try:
            self.submit_po()
            self.status_message("PO submitted.")
            self.after(100, self._do_import_db)
        except Exception as e:
            self._handle_error("Submit PO failed", e)

    def _do_import_db(self):
        try:
            self.import_to_db()
            self.status_message("Imported to DB.")
            self.after(100, self._do_move_files)
        except Exception as e:
            self._handle_error("Import to DB failed", e)

    def _do_move_files(self):
        try:
            self.move_files()
            self.status_message("Files moved.")
            # messagebox.showinfo("Success", "Purchase order processed successfully.")
        except Exception as e:
            self._handle_error("Move files failed", e)
        finally:
            self.enable_buttons()

    def _handle_error(self, title, error):
        print(f"{title}: {error}")
        messagebox.showerror("Error", f"{title}\n{error}")
        self.status_message("Process failed.")
        self.enable_buttons()

    def status_message(self, msg):
        print(msg)  # or update a label in your UI

    def disable_buttons(self):
        try:
            self.rename_button.config(state="disabled")
            self.submit_button.config(state="disabled")
            self.import_button.config(state="disabled")
            self.move_button.config(state="disabled")
            self.process_button.config(state="disabled")  # one-click button
        except AttributeError:
            pass  # in case some buttons are not yet initialized

    def enable_buttons(self):
        try:
            self.rename_button.config(state="normal")
            self.submit_button.config(state="normal")
            self.import_button.config(state="normal")
            self.move_button.config(state="normal")
            self.process_button.config(state="normal")
        except AttributeError:
            pass
