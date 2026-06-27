import tkinter as tk
import tkinter.font as tkFont
from tkinter import filedialog, messagebox
import ttkbootstrap as ttk
from ttkbootstrap.constants import *
from ttkbootstrap import Style
from ttkbootstrap.widgets import DateEntry
from settings import *
import csv, os, shutil
import win32clipboard
import win32con
from button import MainButton
from datetime import date, datetime, timedelta
from edit_form_popup import EditFormPopup
from database import MakeSimpleSql
from custom_class import CustomMeter, CustomTreeview
from dateutil import parser
from pdf_reader import PDFReader as pr

class TreeviewFrame(ttk.Frame):
    def __init__(self, master):
        super().__init__(master)
        self.columns = list(PURCHASING_COLUMN_CONFIG.keys())
        self._sort_column = None
        self._sort_reverse = False
        self.grid_rowconfigure(0, weight=0)  
        self.grid_rowconfigure(1, weight=0)  
        self.grid_rowconfigure(2, weight=1) 
        self.grid_rowconfigure(3, weight=0) 
        self.grid_columnconfigure(0, weight=1)    

        style = Style('flatly')

        # Define multiple custom Treeview styles
        style.configure("TreeviewPrimary.Treeview", font=("Segoe UI", 10), rowheight = 28, bootstyle = 'info')
        style.configure("TreeviewPrimary.Treeview.Heading", font=("Segoe UI", 11), bootstyle = 'info')

        # Map style to show selected row
        style.map("TreeviewPrimary.Treeview",
                background=[("selected", "#1f6aa5")],
                foreground=[("selected", "white")])
        self.database = MakeSimpleSql()
        self.data = (self.database.get_purchase_order())

        self.suppliers =["All"]
        self.get_suppliers()
        self.reader = pr()
        # self.auto_refresh_clipboard()
        # l1 = ttk.Label(self, text="Test", background='red')
        # l2 = ttk.Label(self, text="Test", background='green')
        # l3 = ttk.Label(self, text="Test", background='blue')
        # l4 = ttk.Label(self, text="Test", background='black')

        # l1.grid(row= 0, column= 0, sticky='nsew')
        # l2.grid(row= 1, column= 3, sticky='nsew')
        # l3.grid(row= 2, column= 0, sticky='nsew')
        # l4.grid(row= 3, column= 0, sticky='nsew')
        self.create_meters()
        self.create_filters()
        self.create_widgets()
        self.create_buttons()
        self.populate_treeview()
        self.update_meters(self.data)

        #add space at the button
        self.blank_frame = ttk.Frame(self, height=40)
        self.blank_frame.grid(row=5, column=0, pady=5)
        self.blank_frame.propagate(False)

    def create_meters(self):
        m_frame = ttk.Frame(self)
        m_frame.grid(row=0, column=0, columnspan=2, padx=10, pady=10, sticky="ew")
        m_frame.rowconfigure(2, weight=1)
        m_frame.configure(style='Primary.TFrame')
        self.meters = [CustomMeter(m_frame,0, 0, "info", "Total Orders",0, "total_order", self.meter_clicked),
            CustomMeter(m_frame,0, 1, "warning", "Pending",0,"pending", self.meter_clicked),
            CustomMeter(m_frame,0, 2, "primary", "Confirmed",0,"confirmed", self.meter_clicked),
            CustomMeter(m_frame,0, 3, "success", "Shipped",0,"shipped", self.meter_clicked),
            CustomMeter(m_frame,0, 4, "danger", "Cancelled",0, "cancelled", self.meter_clicked),
            CustomMeter(m_frame,0, 5, "secondary", "Total MSF",0,"total_msf", self.meter_clicked)]

    def create_widgets(self):
        tree_frame = ttk.Frame(self)
        tree_frame.grid(row=2, column=0, columnspan=2, sticky="nsew", padx=10, pady=10)
        tree_frame.rowconfigure(0, weight=1)
        tree_frame.columnconfigure(0, weight=1)

        self.tree = CustomTreeview(tree_frame, self.columns, "extended")
        
        scrollbar = ttk.Scrollbar(tree_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)
        
        self.tree.grid(row=0, column=0, sticky="nsew")
        scrollbar.grid(row=0, column=1, sticky="ns")
        columns = tuple()
        for col in self.columns:
            if col not in "width, length, id":
                columns = columns + (col,)
            self.tree.heading(col, text=PURCHASING_COLUMN_CONFIG[col], command=lambda c=col: self.sort_column(c))
            if col in ['supplier_name', 'material', 'sheet_size', 'purchase_order_number', 'file_name']:
                self.tree.column(col, width=100, anchor="w")
            else:
                self.tree.column(col, width=100, anchor="e")
        self.tree['displaycolumns'] = columns

        # Context menu
        self.context_menu = tk.Menu(self, tearoff=0)
        self.context_menu.add_command(label="Receipt", command=self.context_receipt)
        self.context_menu.add_separator()
        for item in STATUS:
            self.context_menu.add_command(label=item, command=lambda i=item: self.context_status_change(i))

        self.tree.bind("<Button-3>", self.show_context_menu)
        self.tree.bind("<Double-1>", self.edit_cell)
        self.tree.bind("<Alt-e>", self.open_edit_form)
        # self.tree.bind("<ButtonPress-1>", self.drag_start)
        # self.tree.bind("<B1-Motion>", self.drag_motion)
        # self.tree.bind("<ButtonRelease-1>", self.drag_end)
        self.tree.bind("<Control-a>", self.select_all)

        self.drag_data = {"item": None}

        self.column_toggle_panel = None

    def create_buttons(self):
        self.btn_frame = ttk.Frame(self)
        self.btn_frame.grid(row=4, column=0, pady=5)

        for button_key, data in MAIN_BUTTONS.items():
            MainButton(parent=self.btn_frame,
                       col=data['col'],
                       row=data['row'],
                       text=data['text'],
                       bootstyle=data['style'],
                       func=self.main_action_press,
                       params=button_key)
    
    def create_filters(self):
        def get_last_day_of_month(date_obj):
            next_month = date_obj.replace(day=28) + timedelta(days=4)
            return next_month - timedelta(days=next_month.day)
        
        self.filter_frame = ttk.LabelFrame(self, text="Filters", padding=10)
        self.filter_frame.grid(row=1, column=0, columnspan=2, padx=10, sticky="nsew")

        ttk.Label(self.filter_frame, text="Start Date").grid(row=0, column=0, padx=5, pady=5, sticky="e")
        self.start_date = DateEntry(self.filter_frame, width=12)
        self.start_date.grid(row=0, column=1, padx=5, pady=5)

        # End Date
        ttk.Label(self.filter_frame, text="End Date").grid(row=0, column=2, padx=5, pady=5, sticky="e")
        self.end_date = DateEntry(self.filter_frame, width=12)
        
        self.end_date.grid(row=0, column=3, padx=5, pady=5)

        today = datetime.today()
        first_day = today.replace(day=1)
        last_day = get_last_day_of_month(today).date()
        self.end_date.entry.delete(0, "end")
        self.end_date.entry.insert(0, last_day.strftime("%Y-%m-%d")) 
        self.start_date.entry.delete(0, "end")
        self.start_date.entry.insert(0, first_day.strftime("%Y-%m-%d")) 

        preset_options = ["Custom", "Today", "Yesterday", "Last 7 Days","Next 7 Days", "This Month"]
        self.preset_combo = ttk.Combobox(self.filter_frame, values=preset_options, state="readonly", width=15)
        self.preset_combo.set("Custom")
        self.preset_combo.grid(row=0, column=4, padx=5, pady=10)

        def apply_preset(event=None):
            today = datetime.today()
            preset = self.preset_combo.get()
            if preset == "Today":
                s = e = today
            elif preset == "Yesterday":
                s = e = today - timedelta(days=1)
            elif preset == "Last 7 Days":
                s = today - timedelta(days=6)
                e = today
            elif preset == "Next 7 Days":
                s = today
                e = today + timedelta(days=6)
            elif preset == "This Month":
                s = today.replace(day=1)
                e = get_last_day_of_month(today).date()
            else:
                return  # Custom: do nothing
            
            self.start_date.entry.delete(0, "end")
            self.start_date.entry.insert(0, s.strftime("%Y-%m-%d")) 
            self.end_date.entry.delete(0, "end")
            self.end_date.entry.insert(0, e.strftime("%Y-%m-%d")) 

        self.preset_combo.bind("<<ComboboxSelected>>", apply_preset)

        ttk.Label(self.filter_frame, text="Supplier").grid(row=0, column=5, padx=5)
        self.supplier_filter = ttk.Combobox(self.filter_frame, values=self.suppliers, width=15)
        self.supplier_filter.current(0)
        self.supplier_filter.grid(row=0, column=6, padx=5)

        ttk.Label(self.filter_frame, text="Status").grid(row=0, column=7, padx=5)
        self.status_filter = ttk.Combobox(self.filter_frame, values=(["All"] + STATUS), width=12)
        self.status_filter.current(0)
        self.status_filter.grid(row=0, column=8, padx=5)

        ttk.Button(self.filter_frame, text="Apply Filters", bootstyle="primary", command=self.apply_filters).grid(row=0, column=9, padx=10)
        ttk.Button(self.filter_frame, text="Reset", bootstyle="secondary", command=self.reset_filters).grid(row=0, column=10, padx=5)

        self.search_var = tk.StringVar()
        self.search_entry = ttk.Entry(self.filter_frame, textvariable=self.search_var)
        self.search_entry.grid(row=0, column=11, padx=5)
        # ttk.Button(self.filter_frame, text="Search", command=self.apply_wildcard_filter).grid(row=0, column=12)
        self.search_entry.bind("<KeyRelease>", lambda event: self.apply_wildcard_filter())

    def populate_treeview(self, rows=None):
        self.tree.delete(*self.tree.get_children()) #Clear treeview
        columns = self.data[0].keys()
        columns.extend(['shipped_msf','ordered_msf', 'total_msf']) #adding columns
        total_msf = 0.0
        for index, row in enumerate(rows or self.data):
            dict_row = dict(row) #convert to dict - add new attribute * sqlite.Row is readyonly
            # dict_row['sheet_size'] = f"{row['width']} x {row['length']} Sheet"
            if row["order_line"]:
                dict_row['order_id'] = f"{row["order_id"]}-{row["order_line"]}"
            if dict_row["customer_name"] is None:
                dict_row["customer_name"] = ""
            if row["po_line"]:    
                dict_row['purchase_order_number'] = f"{row["po_number"]}-{row["po_line"]}{row["suffix"]}"
            else:
                dict_row['purchase_order_number'] = f"{row["po_number"]}"

            dict_row['sheet_size'] = f"{self.to_base_16(row['width'])} x {self.to_base_16(row['length'])} Sheet"
            dict_row['ordered_msf'] = f"{row['width'] * row['length'] / 144 * row['ordered_quantity'] / 1000:.3f}"
            total_msf += float(dict_row['ordered_msf'])
            dict_row['total_msf'] = f'{total_msf:.3f}'
            dict_row['shipped_msf'] = f"{row['width'] * row['length'] / 144 * row['total_shipped'] / 1000:.3f}"

            #adding zebra strip
            tag = 'even' if index % 2 == 0 else 'odd'
            #Overdue Logic
            if row["requested_date"] < date.today().isoformat() and row["status"] not in ["Completed", "Closed", "Cancelled"]:
                tag += "_overdue"

            # Over shipped logic (> 110% of ordered quantity)
            try:
                if float(row["total_shipped"]) > float(row["ordered_quantity"]) * 1.1:
                    tag += "_over_shipped"
            except (ValueError, TypeError):
                pass    

            values = [dict_row[col] for col in self.tree['column']]
            self.tree.insert("", "end", values=values, tags=(tag,))

            self.tree.tag_configure("even_overdue", background="#ffdddd")
            self.tree.tag_configure("odd_overdue", background="#ffcccc")
            self.tree.tag_configure("even_overdue_over_shipped", background="#ffe4e1")
            self.tree.tag_configure("odd_overdue_over_shipped", background="#ffcccc")
            self.tree.tag_configure("even_over_shipped", background="#e4f1b1")
            self.tree.tag_configure("odd_over_shipped", background="#dff395")

    def to_base_16(self, value):
        base_value = int((value - int(value) + 0.005) * 16) # round up to avoid rounding
        if base_value < 10:
            str_base_value = "0"+ str(base_value)
        else:
            str_base_value = str(base_value)
        return f"{int(value)}.{str_base_value}"
    
    def main_action_press(self, params):
        option = params
        match option:
            case "add_new":
                self.open_new_po_window()
            case "receipt_po":
                self.open_receipt_docket()
            case "export_csv":
                self.export_csv()
            case "paste_files_to_directory":
                self.paste_files_to_directory(CPO_PATH)
            case _:
                print("Unknown option")

    def meter_clicked(self, key,value):
        option = key
        match option:
            case "confirmed":
                self.status_filter.set("Confirmed")
            case "shipped":
                self.status_filter.set("Shipped")
            case "pending":
                self.status_filter.set("Pending")
            case "cancelled":
                self.status_filter.set("Cancelled")
            case "total_order":
                self.status_filter.set("All")
                last_day = "2099-12-12"
                last_day_dt = datetime.strptime(last_day, "%Y-%m-%d")
                self.end_date.entry.delete(0, "end")
                self.end_date.entry.insert(0, last_day_dt.strftime("%Y-%m-%d"))
            case "paste_files_to_directory":
                self.paste_files_to_directory(CPO_PATH)
            case _:
                print("Unknown option")
        self.apply_filters()
        
    def update_meters(self, rows):
        total = len(rows)
        pending = sum(1 for r in rows if r["status"] == "Pending")
        confirmed = sum(1 for r in rows if r["status"] == "Confirmed")
        shipped = sum(1 for r in rows if r["status"] == "Shipped")
        cancelled = sum(1 for r in rows if r["status"] == "Cancelled")
        total_o_msf = round(sum((r["width"] * r["length"] / 144 * r["ordered_quantity"] / 1000) or 0 for r in rows), 2)
        total_r_msf = round(sum((r["width"] * r["length"] / 144 * r["total_shipped"] / 1000) or 0 for r in rows), 2)

        values = [total, pending, confirmed, shipped, cancelled, total_r_msf]

        for meter, val in zip(self.meters, values):
            if meter.key != "total_msf":
                meter.configure(amountused=val)
            else:
                subtext = f"{total_o_msf} MSF"
                meter.configure(amountused=val, subtext=subtext)


    def apply_filters(self):
        query = """SELECT * FROM po_view WHERE 1=1
        """
        params = []

        if self.supplier_filter.get() != "All":
            supplier_id = MakeSimpleSql().get_supplier_id(self.supplier_filter.get())
            query += " AND supplier_name = ? COLLATE NOCASE"
            params.append(self.supplier_filter.get())

        if self.status_filter.get() != "All":
            query += " AND status = ? COLLATE NOCASE"
            params.append(self.status_filter.get())

        try:
            start = parser.parse(self.start_date.entry.get()).date()
            end = parser.parse(self.end_date.entry.get()).date()
            if start <= end:
                query += " AND requested_date BETWEEN ? AND ?"
                params.extend([start.isoformat(), end.isoformat()])
        except Exception:
            pass

        self.data = MakeSimpleSql().get_purchase_order_with_query(query, params)
        self.populate_treeview(self.data)
        self.update_meters(self.data)

    def apply_wildcard_filter(self):
        wildcard_val = self.search_var.get().strip().lower()
        def match(row):
            row_text = " ".join(map(str, row)).lower()
            return wildcard_val in row_text if wildcard_val else True

        filtered = [r for r in self.data if match(r)]
        self.populate_treeview(filtered)
    
    def dispatch(self, command):
        dispatcher = {
            "add_new": self.open_new_po_window
        }

        if command in dispatcher:
            return dispatcher[command]()  # Call the corresponding function
        else:
            raise ValueError(f"Unknown command: {command}")

    def select_all(self, event=None):
        self.tree.selection_set(self.tree.get_children())
        return "break"  # Prevent default behavior

    def open_edit_form(self, event):
        rowid = self.tree.identify_row(event.y)
        if not rowid:
            return

        values = self.tree.item(rowid, "values")
        columns = self.tree["columns"]
        row_data = dict(zip(columns, values))

        field_config = {
            "supplier_name": {"label": "Supplier", "type": "text"},
            "material": {"label": "Material", "type": "text"},
            "width": {"label": "Width", "type": "number"},
            "length": {"label": "Length", "type": "number"},
            "ordered_quantity": {"label": "Ordered Qty", "type": "number"},
            "price": {"label": "Price", "type": "number", "validate": False},
            "status": {
                "label": "Status",
                "type": "dropdown",
                "options": STATUS
            },
            "requested_date": {"label": "Requested Date", "type": "date"},
            "purchase_date": {"label": "Purchase Date", "type": "date"},
        }

        def on_submit(updated_data):
            updated_data["purchase_order_number"] = row_data["purchase_order_number"]
            MakeSimpleSql().update_po_fields(updated_data)
            self.data = MakeSimpleSql().get_purchase_order()
            self.apply_filters()

        EditFormPopup(self, "Edit Purchase Order", field_config, row_data, on_submit)

    def get_suppliers(self):
        suppliers = self.database.get_suppliers()
        if suppliers:
            for supplier in suppliers:
                self.suppliers.append(supplier)
                
    def show_context_menu(self, event):
        rowid = self.tree.identify_row(event.y)
        if not rowid:
            return
        
        selected = self.tree.selection()

        if rowid not in selected:
            # Right-clicked on unselected row: clear selection and select only this row
            self.tree.selection_set(rowid)
        else:
            # Right-clicked on a selected row: keep the current multi-selection
            self.tree.focus(rowid)  # optional, set keyboard focus for clarity

        self.context_menu_rowid = rowid
        self.context_menu.post(event.x_root, event.y_root)

    def context_receipt(self):
        rowid = getattr(self, 'context_menu_rowid', None)
        if rowid:
            col = self.tree['column']
            values = self.tree.item(rowid)["values"]
            kv = dict(zip(col,values))
            self.open_receipt_docket(kv["purchase_order_number"])
            
    def context_status_change(self, command):
        print(f"Changing status to: {command}")
        selected_rows = self.tree.selection()
        if not selected_rows:
            print("No rows selected")
            return

        for rowid in selected_rows:
            self.tree.set(rowid, "status", command)

        # Pass selected rows to update_record so it updates all
        self.update_record()

    def update_record(self, rowid=None):
        try:
            items = [rowid] if rowid else self.tree.selection()
            for item_id in items:
                values = self.tree.item(item_id)["values"]
                columns = self.tree["columns"]

                # Convert to dict
                kv = dict(zip(columns, values))

                # Skip if PO number missing
                if not kv.get("purchase_order_number"):
                    continue

                MakeSimpleSql().update_po_fields(kv)  # You’ll define this in your DAO
            self.data = MakeSimpleSql().get_purchase_order()
            self.apply_filters()
        except Exception as e:
            print("Update error:", e)
            messagebox.showerror("Error", str(e))
    
    def update_all_record(self, rows = None):    
        for i in self.tree.selection():
            po = self.tree.item(i)["values"][1]
            shipped_qty = self.tree.item(i)["values"][7]
            status = self.status_update.get()
            MakeSimpleSql().update_status(po,status,shipped_qty)
        self.data = MakeSimpleSql().get_purchase_order()
        self.apply_filters()

    def context_delete(self):
        rowid = getattr(self, 'context_menu_rowid', None)
        if not rowid:
            return
        values = self.tree.item(rowid, 'values')
        index = self.tree.index(rowid)
        MakeSimpleSql().delete_record(values[1])

        self.tree.delete(rowid)

    def sort_by_column(self, col):
        data = [(self.tree.set(k, col), k) for k in self.tree.get_children('')]
        try:
            data.sort(key=lambda t: float(t[0]))
        except ValueError:
            data.sort(key=lambda t: t[0])

        for index, (_, k) in enumerate(data):
            self.tree.move(k, '', index)

    def sort_column(self, col):
        data = [(self.tree.set(k, col), k) for k in self.tree.get_children('')]
        try:
            data.sort(key=lambda t: float(t[0]), reverse=self._sort_column == col and not self._sort_reverse)
        except ValueError:
            data.sort(key=lambda t: t[0], reverse=self._sort_column == col and not self._sort_reverse)

        for index, (_, k) in enumerate(data):
            self.tree.move(k, '', index)

        for c in self.tree["columns"]:
            arrow = ""
            if c == col:
                self._sort_reverse = not (self._sort_column == col and self._sort_reverse)
                arrow = " ↓" if self._sort_reverse else " ↑"
            self.tree.heading(c, text=PURCHASING_COLUMN_CONFIG[c] + arrow)

        self._sort_column = col
        self._sort_reverse = not (self._sort_column == col and self._sort_reverse)
        
    from ttkbootstrap.widgets import DateEntry

    def edit_cell(self, event):
        rowid = self.tree.identify_row(event.y)
        column = self.tree.identify_column(event.x)
        col_index = int(column[1:]) - 1

        if not rowid or col_index < 0 or col_index >= len(self.columns):
            return

        column_name = self.columns[col_index]
        if column_name in ["ordered_msf", "shipped_msf", "total_msf", "sheet_size"]:
            return
        
        if column_name in ["purchase_order_number"]:
            file_path = self.tree.set(rowid, "file_name")
            print(file_path)
            os.startfile(file_path)

        x, y, width, height = self.tree.bbox(rowid, column)
        old_value = self.tree.set(rowid, column_name)

        widget = None

        def commit(new_value):
            self.tree.set(rowid, column_name, new_value)
            widget.destroy()
            self.update_record(rowid)

            # Recalculate MSF if editing affects dimensions or qty
            if column_name in ("width", "length", "ordered_quantity", "shipped_quantity"):
                try:
                    width = float(self.tree.set(rowid, "width"))
                    length = float(self.tree.set(rowid, "length"))
                    o_qty = float(self.tree.set(rowid, "ordered_quantity"))
                    s_qty = float(self.tree.set(rowid, "shipped_quantity"))
                    o_msf = f"{(width * length / 144 * o_qty / 1000):.3f}"
                    s_msf = f"{(width * length / 144 * s_qty / 1000):.3f}"
                    self.tree.set(rowid, "ordered_msf", o_msf)
                    self.tree.set(rowid, "shipped_msf", s_msf)
                    self.tree.set(rowid, "sheet_size", f"{self.to_base_16(width)} x {self.to_base_16(length)} Sheet")
                except ValueError:
                    self.tree.set(rowid, "ordered_msf", "")
                    self.tree.set(rowid, "shipped_msf", "")

        # Dropdown for status
        if column_name == "status":
            widget = ttk.Combobox(self.tree, values=["Pending", "Confirmed", "Shipped", "Completed", "Cancelled", "Rejected", "Partial Rejected"], state="readonly")
            widget.set(old_value)

            def on_select(event=None):
                commit(widget.get())

            widget.bind("<<ComboboxSelected>>", on_select)
            widget.bind("<FocusOut>", on_select)

        # Date picker
        elif "date" in column_name:
            widget = DateEntry(self.tree, dateformat="%Y-%m-%d", width=width, bootstyle="secondary")
            widget.set_date(old_value)

            def on_date_selected(event=None):
                commit(widget.entry.get())

            widget.entry.bind("<Return>", on_date_selected)
            widget.entry.bind("<FocusOut>", on_date_selected)

        # Default text entry
        else:
            widget = ttk.Entry(self.tree)
            widget.insert(0, old_value)

            def on_entry(event=None):
                commit(widget.get())

            widget.bind("<Return>", on_entry)
            widget.bind("<FocusOut>", on_entry)

        widget.place(x=x, y=y, width=width, height=height)
        widget.focus()

    def export_csv(self):
        file_path = filedialog.asksaveasfilename(defaultextension=".csv", filetypes=[("CSV files", "*.csv")])
        if not file_path:
            return

        try:
            with open(file_path, mode='w', newline='') as f:
                writer = csv.writer(f)
                writer.writerow(self.columns)
                for row_id in self.tree.get_children():
                    writer.writerow(self.tree.item(row_id)['values'])
            messagebox.showinfo("Export", "Data exported successfully.")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to export: {e}")
    
    def reset_filters(self):
        self.supplier_filter.current(0)
        self.status_filter.current(0)
        self.start_date.entry.delete(0, 'end')
        self.end_date.entry.delete(0, 'end')
        self.apply_filters()

    def open_receipt_docket(self, purchase_order=None):
        from main import DeliveryDocket
        DeliveryDocket(self, purchase_order)

    def open_new_po_window(self):
        from main import NewPurchaseOrder
        NewPurchaseOrder(self)

    def submit_po(self):
        pr().update_record()
        self.data = (MakeSimpleSql().get_purchase_order())
        self.populate_treeview()
        
    def update_multi_po(self, list_pos):
        MakeSimpleSql().update_multi_po(list_pos)
        self.populate_treeview()

    def set_column_visibility(self, column, visible):
        self.tree.heading(column, text=column if visible else "")
        self.tree.column(column, width=100 if visible else 0)

    