import tkinter as tk
import tkinter.font as tkFont
from tkinter import filedialog, messagebox
from ttkbootstrap import ttk
from ttkbootstrap import Style
from ttkbootstrap.constants import *
from ttkbootstrap.widgets import DateEntry
import csv, os, math
import pandas as pd
from dateutil import parser
from database import MakeSimpleSql
from emaily import Emaily
from dr_reader import DeliveryReceiptReader
from button import ControlButton, PurchaseOrderTree
from settings import *

class DeliveryDocketFrame(ttk.Frame):
    def __init__(self, master, purchase_order = None):
        super().__init__(master)
        self.columns = list(DELIVERY_DOCKET_COLUMN_CONFIG.keys())
        self.path = PO_PATH
        self._sort_column = None
        self._sort_reverse = False

        self.grid_rowconfigure(2, weight=1)
        self.grid_columnconfigure(0, weight=1)

        self.custom_font = tkFont.Font(family="Segoe UI", size=11)
        style = Style()
        style.configure("TreeviewPrimary.Treeview", font=self.custom_font, rowheight=28, bootstyle="info")
        style.configure("TreeviewPrimary.Treeview.Heading", font=(self.custom_font.actual("family"), 12, "bold"), bootstyle="info")
        style.map("TreeviewPrimary.Treeview", background=[("selected", "#1f6aa5")], foreground=[("selected", "white")])

        self.data = []
        self.filepath = ''
        self.database = MakeSimpleSql()
        self.suppliers =["All"]
        self.get_suppliers()
        self.path = r"C:\Users\sang.n\OneDrive - whitebird.ca\Paper App\suppliers"
        self.create_widgets()
        self.purchase_order = purchase_order
        if self.purchase_order:
            rows = [dict(zip(self.columns, [self.purchase_order,0]))]
            self.populate_treeview(rows)

    def create_widgets(self):
        self.filter_frame = ttk.LabelFrame(self, text="Filters", padding=10)
        self.filter_frame.grid(row=1, column=0, sticky="ew", padx=10, pady=(0, 5))
        for i in range(8):
            self.filter_frame.grid_columnconfigure(i, weight=1)

        ttk.Label(self.filter_frame, text="PDF File:").grid(row=0, column=0, padx=5, sticky="e")
        self.file_entry = ttk.Entry(self.filter_frame, width=50)
        self.file_entry.grid(row=0, column=1, columnspan=5, padx=5, pady=2, sticky="ew")
        ttk.Button(self.filter_frame, text="Browse", command=self.browse_file).grid(row=0, column=6, padx=5, pady=2, sticky="ew")

        ttk.Label(self.filter_frame, text="Shipped Date:").grid(row=1, column=0, padx=5, pady=2, sticky="e")
        self.shipped_date = DateEntry(self.filter_frame)
        self.shipped_date.grid(row=1, column=1, padx=5, pady=2, sticky="ew")

        ttk.Label(self.filter_frame, text="Delivery Date:").grid(row=1, column=2, padx=5, pady=2, sticky="e")
        self.delivery_date = DateEntry(self.filter_frame)
        self.delivery_date.grid(row=1, column=3, padx=5, pady=2, sticky="ew")

        ttk.Label(self.filter_frame, text="Status:").grid(row=2, column=0, padx=5, pady=2, sticky="e")
        self.status_var = tk.StringVar(value="Closed")
        self.status_dropdown = ttk.Combobox(
            self.filter_frame, textvariable=self.status_var, values=["Shipped", "Completed", "Closed"], state="readonly", width=20
        )
        self.status_dropdown.grid(row=2, column=1, padx=5, pady=2, sticky="ew")

        ttk.Label(self.filter_frame, text="Docket ID:").grid(row=2, column=2, padx=5, pady=2, sticky="e")
        self.filter_val = tk.StringVar()
        self.docket_id = ttk.Entry(self.filter_frame, textvariable=self.filter_val)
        self.docket_id.grid(row=2, column=3, padx=5, pady=2, sticky="ew")

        button_config = {
            "padx": 5,
            "pady": (10, 0),
            "sticky": "ew"
        }

        buttons = [
            ("Move Files", "success", self.move_delivery_docket),
            ("One Click", "success", self.receipts_and_move_all_files),
            ("Import", "success", self.import_to_db),
            ("Add", "info", self.add_new_line),
            ("Delete", "warning", self.delete_selected_row),
            ("Close", "danger", self.close_window),
        ]

        for i, (text, style, cmd) in enumerate(buttons):
            CustomButton(self.filter_frame, text=text, bootstyle=style, command=cmd).grid(
                row=3, column=i+1, **button_config
            )

        self.tree = PurchaseOrderTree(self, self.columns, ttk.Scrollbar(self, orient="vertical"))
        for col in self.columns:
            self.tree.heading(col, text=DELIVERY_DOCKET_COLUMN_CONFIG[col], command=lambda c=col: self.sort_column(c))
            # anchor = "w" if col in {"supplier", "material", "purchase_order_number"} else "e"
            self.tree.column(col, width=100, anchor="w")

        self.tree.bind("<Double-1>", self.edit_cell)
        self.tree.grid(row=2, column=0, sticky="nsew", padx=10, pady=(0, 10))
        self.tree.bind_all("<Control-Return>", lambda e: self.import_to_db())# CTRL + ENTER to import
        self.tree.bind("<Delete>", lambda event: self.delete_selected_row())# DELETE key

    def browse_file(self):
        filepath = filedialog.askopenfilename(filetypes=[("CSV Files", "*.csv"), ("PDF Files", "*.pdf")])
        if filepath:
            self.file_entry.delete(0, tk.END)
            self.file_entry.insert(0, filepath)
            ext = os.path.splitext(filepath)[1].lower()  # get extension and lowercase
            if ext == ".pdf":
                self.load_pdf(filepath)
            elif ext == ".csv":
                self.load_csv(filepath)
            else:
                tk.messagebox.showerror("Invalid file", "Please select a CSV or PDF file.")

    def load_pdf(self, filepath):
        try:
            #Get FileName and set to Docket ID
            filename = os.path.basename(filepath)
            self.filter_val.set(os.path.splitext(filename)[0])

            rows = DeliveryReceiptReader().reader(filepath)
            rows = [dict(zip(self.columns, row)) for row in rows]
            self.populate_treeview(rows)
            # messagebox.showinfo("Success", "PDF loaded successfully.")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to read PDF:\n{e}")

    def load_csv(self, filepath):
        self.df = pd.read_csv(filepath)
        with open(filepath, newline='', encoding='utf-8') as csvfile:
            reader = csv.DictReader(csvfile, delimiter=',')  # comma-separated
            for row in reader:
                self.data.append(row)


    def move_delivery_docket(self):
        if not self.tree.get_children():
            messagebox.showwarning("No Data", "No rows to process.")
            return
        #Get Supplier
        first_item_id = self.tree.get_children()[0]
        po = self.tree.item(first_item_id)["values"][0]
        if po:
            vendor = MakeSimpleSql().get_supplier_name_by_po(po)
        file_path = self.file_entry.get()
        email = Emaily(self)
        try:
            email.move_delivery_docket(file_path, vendor)
        except Exception as e:
            pass

    def receipts_and_move_all_files(self):
        file_path = self.file_entry.get()
        ext = os.path.splitext(file_path)[1].lower()  # get extension and lowercase
        if ext == ".pdf":
            for file_name in os.listdir(self.path):
                if file_name.lower().endswith(".pdf"):
                    file_path = os.path.join(self.path, file_name)
                    self.file_entry.delete(0, tk.END)
                    self.file_entry.insert(0,file_path)
                    self.load_pdf(file_path)
                    self.import_to_db()
                    self.move_delivery_docket()
        elif ext == ".csv":
            po = self.database.get_pending_purchase_order()
            if po:
                for record in po:
                    # Find matching record in CSV
                    receipt_record = self.search_csv(record['po_number'], record['po_line'])
                    if receipt_record:
                        # Extract fields safely
                        docket_id = receipt_record.get('supplier_shipping_num', '')
                        shipped_date = receipt_record.get('receipt_dte', '')
                        shipped_qty = receipt_record.get('receipt_qty', 0)

                        # Prepare data for DB insert
                        data = {
                            'purchase_order_number': record['po_number'],
                            'purchase_line_nbr': record['po_line'],
                            'shipped_quantity': shipped_qty
                        }
                        print(docket_id)
                        # Insert into DB
                        self.database.insert_delivery_docket(
                            docket_number=docket_id,
                            shipped_date=shipped_date,
                            delivery_date=shipped_date,
                            dict_data=[data],
                            status="Closed"
                        )
    
    def search_csv(self, purchase_id, purchase_line_nbr):
        if not hasattr(self, "df") or self.df.empty:
            print("CSV not loaded or empty.")
            return None

        # Ensure required columns exist
        required_cols = {'purchase_id', 'purchase_line_nbr'}
        if not required_cols.issubset(self.df.columns):
            print("Missing required columns in CSV.")
            return None

        # Normalize types for comparison
        df = self.df.astype({'purchase_id': str, 'purchase_line_nbr': str})

        # Filter rows
        result = df[
            (df['purchase_id'] == str(purchase_id)) &
            (df['purchase_line_nbr'] == str(purchase_line_nbr))
        ]

        # Return the first matching row as a dict (or None)
        return result.iloc[0].to_dict() if not result.empty else None


    def autosize_columns(self):
        for col in self.tree["columns"]:
            header_text = DELIVERY_DOCKET_COLUMN_CONFIG.get(col, col)
            max_width = self.custom_font.measure(header_text) + 20
            for item in self.tree.get_children():
                cell_text = str(self.tree.set(item, col))
                max_width = max(max_width, self.custom_font.measure(cell_text) + 10)
            self.tree.column(col, width=max_width)

    def populate_treeview(self, rows):
        self.tree.delete(*self.tree.get_children())
        for i, row in enumerate(rows):
            values = [row.get(col, "") for col in self.columns]
            self.tree.insert("", "end", values=values, tags=('even' if i % 2 == 0 else 'odd',))
        self.autosize_columns()

    def edit_cell(self, event):
        rowid = self.tree.identify_row(event.y)
        column = self.tree.identify_column(event.x)
        col_index = int(column[1:]) - 1
        if not rowid:
            return

        x, y, width, height = self.tree.bbox(rowid, column)
        value = self.tree.set(rowid, self.columns[col_index])

        entry = ttk.Entry(self.tree)
        entry.place(x=x, y=y, width=width, height=height)
        entry.insert(0, value)
        entry.focus()

        def on_edit(event):
            new_value = entry.get()
            self.tree.set(rowid, self.columns[col_index], new_value)
            entry.destroy()

        entry.bind("<Return>", on_edit)
        entry.bind("<FocusOut>", on_edit)

    def calculate_msf(self, width, length, qty):
        try:
            return f"{((float(width) * float(length) / 144) * float(qty)) / 1000:.3f}"
        except (ValueError, TypeError):
            return ""

    def get_suppliers(self):
        suppliers = MakeSimpleSql().get_suppliers()
        if suppliers:
            for supplier in suppliers:
                self.suppliers.append(supplier[0])

    def sort_column(self, col):
        data = [(self.tree.set(child, col), child) for child in self.tree.get_children()]
        try:
            data.sort(key=lambda x: float(x[0]) if x[0].replace('.', '', 1).isdigit() else x[0])
        except Exception:
            data.sort(key=lambda x: x[0])

        reverse = self._sort_column == col and not self._sort_reverse
        for index, (_, child) in enumerate(reversed(data) if reverse else data):
            self.tree.move(child, '', index)

        self._sort_column = col
        self._sort_reverse = reverse

    def import_to_db(self, data=None):
        data = self.get_treeview_data()
        docket_id = self.docket_id.get()
        status = self.status_dropdown.get()
        try:
            shipped_date = parser.parse(self.shipped_date.entry.get()).date()
            delivery_date = parser.parse(self.delivery_date.entry.get()).date()
        except Exception as e:
            messagebox.showerror("Invalid Date", f"Please provide valid dates.\n{e}")
            return
        if data:
            try:
                MakeSimpleSql().insert_delivery_docket(docket_id, shipped_date, delivery_date, data, status)
                messagebox.showinfo("Success", "Delivery docket imported into database.")
            except Exception as e:
                messagebox.showerror("Database Error", f"Could not insert into database.\n{e}")


    def add_new_line(self):
        current_data = self.get_treeview_data()
        current_data.append(dict.fromkeys(self.columns, ""))
        self.populate_treeview(current_data)
        rowid = self.tree.get_children()[-1]
        return rowid

    def delete_selected_row(self):
        selected_item = self.tree.selection()
        if not selected_item:
            messagebox.showwarning("No Selection", "Please select a row to delete.")
            return

        if messagebox.askyesno("Confirm Delete", "Are you sure you want to delete the selected row?"):
            for item in selected_item:
                self.tree.delete(item)


    def get_treeview_data(self):
        all_data = []
        for row_id in self.tree.get_children():
            item = self.tree.item(row_id)["values"]
            row = dict(zip(self.columns, item))
            all_data.append(row)
        return all_data

    def close_window(self):
        # if messagebox.askyesno("Confirm", "Are you sure you want to close this window?"):
        self.winfo_toplevel().destroy()

class CustomButton(ttk.Button):
    def __init__(self, master, text, command, bootstyle="secondary", **kwargs):
        super().__init__(
            master,
            text=text,
            command=command,
            bootstyle=bootstyle,
            **kwargs
        )