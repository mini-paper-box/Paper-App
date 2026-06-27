import tkinter as tk
from tkinter import filedialog, messagebox
import ttkbootstrap as ttk
from ttkbootstrap.constants import *
import csv
from sqlite import make_simple as ms
from pdf_reader import pdf_reader as pr
from column_toggle_panel import ColumnTogglePanel
from undo_redo_manager import UndoRedoManager

columns_config = {
            "supplier":"Supplier",
             "purchase_order_number" :"Purchase Order #", 
             "material":"Material", 
             "price":"Price", 
             "width":"Width", 
             "length":"Length",  
             "ordered_quantity":"Ordered Quantity",
             "shipped_quantity":"Shipped Quantity",
             "ordered_msf":"Ordered MSF", 
             "shipped_msf":"Ordered MSF", 
             "purchase_date":"Purchase Date", 
             "requested_date":"Requested Date", 
             "status":"Status"
        }

class TreeviewFrame(tk.Frame):
    def __init__(self, master):
        super().__init__(master)
        
        columns = list(columns_config.keys())
        self.columns = list(columns_config.keys())
        self._sort_column = None
        self._sort_reverse = False


        self.data = (ms().get_purchase_order())

        self.undo_redo = UndoRedoManager()

        self.create_filters()
        self.create_widgets()
        self.populate_treeview()

    def create_widgets(self):
        # Toolbar
        toolbar = tk.Frame(self)
        toolbar.pack(fill=tk.X, padx=5, pady=2)

        ttk.Button(toolbar, text="Export CSV", command=self.export_csv).pack(side=tk.RIGHT)
        ttk.Button(toolbar, text="Undo", command=self.undo_redo.undo).pack(side=tk.RIGHT, padx=5)
        ttk.Button(toolbar, text="Redo", command=self.undo_redo.redo).pack(side=tk.RIGHT)
        # ttk.Button(toolbar, text="Email", command=self.toggle_column_panel).pack(side=tk.RIGHT, padx=5)
        ttk.Button(toolbar, text="Update", command=self.submit_po).pack(side=tk.RIGHT, padx=5)
        ttk.Button(toolbar, text="Import Data", command=self.submit_po).pack(side=tk.RIGHT, padx=5)

        tk.Label(toolbar, text="Filter:").pack(side=tk.LEFT)
        self.filter_val = tk.StringVar()
        self.wildcard_filter = ttk.Entry(toolbar, textvariable=self.filter_val)
        self.wildcard_filter.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(5, 10))
        self.wildcard_filter.bind("<KeyRelease>", lambda e: self.apply_filters())

        # Add a vertical scrollbar
        self.vertial_scrollbar = ttk.Scrollbar(self, orient="vertical")

        # Treeview
        self.tree = ttk.Treeview(self, columns=self.columns, show="headings", yscrollcommand=self.vertial_scrollbar.set)
        self.vertial_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.tree.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        for col in self.columns:
            self.tree.heading(col, text=columns_config[col], command=lambda c=col: self.sort_column(c))
            if col == 'supplier' or col == 'material' or col == 'purchase_order_number':
                self.tree.column(col, width=100, anchor="w")
            else:
                self.tree.column(col, width=100, anchor="e")

        

        # Attach scrollbar to Treeview
        self.vertial_scrollbar.configure(command=self.tree.yview)

        # Context menu
        self.context_menu = tk.Menu(self, tearoff=0)
        self.context_menu.add_command(label="Cancelled", command=self.context_cancelled)
        self.context_menu.add_command(label="Confirmed", command=self.context_confirmed)
        self.context_menu.add_command(label="Completed", command=self.context_completed)
        self.context_menu.add_command(label="Rejected", command=self.context_rejected)
        self.context_menu.add_command(label="Partial Rejected", command=self.context_partial_rejected)
        self.context_menu.add_command(label="Delete", command=self.context_delete)

        self.tree.bind("<Button-3>", self.show_context_menu)
        self.tree.bind("<Double-1>", self.edit_cell)
        self.tree.bind("<ButtonPress-1>", self.drag_start)
        self.tree.bind("<B1-Motion>", self.drag_motion)
        self.tree.bind("<ButtonRelease-1>", self.drag_end)


        self.drag_data = {"item": None}

        self.column_toggle_panel = None

    def create_filters(self):
        filter_frame = ttk.Frame(self, padding=5)
        filter_frame.pack(side=tk.TOP, fill=tk.X)

        ttk.Label(filter_frame, text="Vendor:").pack(side=tk.LEFT)
        self.name_filter = ttk.Entry(filter_frame)
        self.name_filter.pack(side=tk.LEFT, padx=5)
        self.name_filter.bind("<KeyRelease>", lambda e: self.apply_filters())

        ttk.Label(filter_frame, text="Status:").pack(side=tk.LEFT)
        self.status_filter = ttk.Combobox(filter_frame, values=["", "Pending", "Confirmed", "Cancelled", "Completed", "Partial"], state="readonly")
        self.status_filter.pack(side=tk.LEFT, padx=5)
        self.status_filter.bind("<<ComboboxSelected>>", lambda e: self.apply_filters())

        ttk.Label(filter_frame, text="MSF >=").pack(side=tk.LEFT)
        self.msf_filter = ttk.Entry(filter_frame, width=5)
        self.msf_filter.pack(side=tk.LEFT, padx=5)
        self.msf_filter.bind("<KeyRelease>", lambda e: self.apply_filters())

    def populate_treeview(self, rows=None):
        self.tree.delete(*self.tree.get_children()) #Clear treeview
        columns = self.data[0].keys()
        for row in rows or self.data:
            columns.extend(['shipped_msf','ordered_msf'])
            dict_row = dict(row) #convert to dict - add new attribute * sqlite.Row is readyonly
            dict_row['ordered_msf'] = f"{row['width'] * row['length'] / 144 * row['ordered_quantity'] / 1000:.3f}"
            dict_row['shipped_msf'] = f"{row['width'] * row['length'] / 144 * row['shipped_quantity'] / 1000:.3f}"
            
            self.tree.insert("", "end", values=[dict_row[col] for col in self.tree['column']])
        # for a, b, c, d, width, length, qty, h, i, j, k in rows or self.data:
            # msf = f"{((width * length / 144) * qty) / 1000:.3f}"
        #     self.tree.insert("", "end", values=(a, b, c, d, width, length, qty,msf, h, i, j, k))
        
        self.all_data = list(self.data)

    def apply_filters(self):
        name_val = self.name_filter.get().strip().lower()
        status_val = self.status_filter.get().strip()
        msf_val = self.msf_filter.get().strip()
        wildcard_val = self.wildcard_filter.get().lower()
        def match(row):
            if wildcard_val and wildcard_val not in " ".join(map(str, row)).lower():
                return False
            if name_val and name_val not in row[0].lower():
                return False
            if status_val and row[10] != status_val:
                return False
            if msf_val:
                try:
                    msf = (row[4]*row[5])/144 * row[6] / 1000
                    if msf < int(msf_val):
                        return False
                except ValueError:
                    return False
            return True

        filtered = [r for r in self.data if match(r)]
        self.populate_treeview(filtered)

    def show_context_menu(self, event):
        rowid = self.tree.identify_row(event.y)
        if rowid:
            self.tree.selection_set(rowid)
            self.context_menu.post(event.x_root, event.y_root)
            self.context_menu_rowid = rowid

    def context_cancelled(self):
        rowid = getattr(self, 'context_menu_rowid', None)
        if rowid:
            self.tree.set(rowid, "status", 'Cancelled')
            self.update_record(rowid)
            # self.data = (ms().get_purchase_order())

    def context_confirmed(self):
        rowid = getattr(self, 'context_menu_rowid', None)
        if rowid:
            self.tree.set(rowid, "status", 'Confirmed')
            self.update_record(rowid)
            # self.data = (ms().get_purchase_order())

    def context_completed(self):
        rowid = getattr(self, 'context_menu_rowid', None)
        if rowid:
            self.tree.set(rowid, "status", 'Completed')
            self.update_record(rowid)
            # self.data = (ms().get_purchase_order())

    def context_partial_rejected(self):
        rowid = getattr(self, 'context_menu_rowid', None)
        if rowid:
            self.tree.set(rowid, "status", 'Partial Rejected')
            self.update_record(rowid)
            # self.data = (ms().get_purchase_order())

    def context_rejected(self):
        rowid = getattr(self, 'context_menu_rowid', None)
        if rowid:
            self.tree.set(rowid, "status", 'Rejected')
            self.update_record(rowid)
            # self.data = (ms().get_purchase_order())

    def update_record(self, row):    
        for i in self.tree.selection():
            #remove element before call sqlite
            temp_var = self.tree.item(i)["values"]
            temp_var.pop(7)
            list_item = [tuple(temp_var)]
        pass

    def context_delete(self):
        rowid = getattr(self, 'context_menu_rowid', None)
        if not rowid:
            return
        values = self.tree.item(rowid, 'values')
        index = self.tree.index(rowid)
        ms().delete_record(values[1])

        self.undo_redo.record(
            undo_action=lambda: self.tree.insert("", index, iid=rowid, values=values),
            redo_action=lambda: self.tree.delete(rowid)
        )

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
                arrow = " ↓" if self._sort_reverse else " ↑"
            self.tree.heading(c, text=c + arrow)

        self._sort_column = col
        self._sort_reverse = not (self._sort_column == col and self._sort_reverse)
        
    def edit_cell(self, event):
        
        rowid = self.tree.identify_row(event.y)
        column = self.tree.identify_column(event.x)
        col_index = int(column[1:]) - 1
        if not rowid:
            return

        if self.columns[col_index] == "ordered_msf" or self.columns[col_index] == "shipped_msf":
            return
        
        x, y, width, height = self.tree.bbox(rowid, column)
        value = self.tree.set(rowid, self.columns[col_index])

        entry = ttk.Entry(self.tree)
        entry.place(x=x, y=y, width=width, height=height)
        entry.insert(0, value)
        entry.focus()

        def on_edit(event):
            new_value = entry.get()
            old_value = self.tree.set(rowid, self.columns[col_index])
            # Apply change and record undo
            self.undo_redo.record(lambda: self.tree.set(rowid, self.columns[col_index], old_value),
                                  lambda: self.tree.set(rowid, self.columns[col_index], new_value))
            self.tree.set(rowid, self.columns[col_index], new_value)
            entry.destroy()
            self.update_record(rowid)

            # If editing Qty or Price, recalculate Total
            if self.columns[col_index] in ("width", "length", "ordered_quantity", "shipped_quantity"):
                try:
                    width = float(self.tree.set(rowid, "width"))
                    length = float(self.tree.set(rowid, "length"))
                    o_qty = float(self.tree.set(rowid, "ordered_quantity"))
                    s_qty = float(self.tree.set(rowid, "shipped_quantity"))
                    o_msf = f"{((width * length / 144) * o_qty) / 1000:.3f}"
                    s_msf = f"{((width * length / 144) * s_qty) / 1000:.3f}"
                    self.tree.set(rowid, "ordered_msf", o_msf)
                    self.tree.set(rowid, "shipped_msf", s_msf)
                except ValueError:
                    self.tree.set(rowid, "ordered_msf", "")
                    self.tree.set(rowid, "shipped_msf", "")

        entry.bind("<Return>", on_edit)
        entry.bind("<FocusOut>", on_edit)

    def drag_start(self, event):
        self.drag_data["item"] = self.tree.identify_row(event.y)

    def drag_motion(self, event):
        target = self.tree.identify_row(event.y)
        if target and target != self.drag_data["item"]:
            self.tree.move(self.drag_data["item"], '', self.tree.index(target))

    def drag_end(self, event):
        self.drag_data["item"] = None

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
    def submit_po(self):
        pr().update_record()
        self.data = (ms().get_purchase_order())
        self.populate_treeview()
        
    def update_multi_po(self, list_pos):
        ms().update_multi_po(list_pos)
        self.populate_treeview()

    def toggle_column_panel(self):
        if self.column_toggle_panel and self.column_toggle_panel.winfo_exists():
            self.column_toggle_panel.lift()
        else:
            self.column_toggle_panel = ColumnTogglePanel(self, self.columns, self.set_column_visibility)

    def set_column_visibility(self, column, visible):
        self.tree.heading(column, text=column if visible else "")
        self.tree.column(column, width=100 if visible else 0)

    