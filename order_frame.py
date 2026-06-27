import tkinter as tk
import tkinter.font as tkFont
from tkinter import filedialog, messagebox
import ttkbootstrap as ttk
from ttkbootstrap.constants import *
from ttkbootstrap import Style
from ttkbootstrap.widgets import DateEntry
from settings import *
import csv, os, shutil, logging
import win32clipboard
import win32con
from button import MainButton
from datetime import date, datetime, timedelta
from edit_form_popup import EditFormPopup
from database import MakeSimpleSql
from custom_class import CustomMeter, CustomTreeview
from dateutil import parser
from pdf_reader_singleton import get_pdf_reader, PDFReaderSingleton

logger = logging.getLogger(__name__)


class Orders(ttk.Frame):
    def __init__(self, master):
        super().__init__(master)
        self.columns = list(ORDERS_COLUMN_CONFIG.keys())
        self._sort_column = None
        self._sort_reverse = False
        
        # Grid configuration
        self.grid_rowconfigure(0, weight=0)  
        self.grid_rowconfigure(1, weight=0)  
        self.grid_rowconfigure(2, weight=1) 
        self.grid_rowconfigure(3, weight=0) 
        self.grid_columnconfigure(0, weight=1)    

        # Style configuration
        style = Style('flatly')
        style.configure("TreeviewPrimary.Treeview", font=("Segoe UI", 10), rowheight=28, bootstyle='info')
        style.configure("TreeviewPrimary.Treeview.Heading", font=("Segoe UI", 11), bootstyle='info')
        style.map("TreeviewPrimary.Treeview",
                background=[("selected", "#1f6aa5")],
                foreground=[("selected", "white")])
        
        # Use singleton PDFReader instance
        self.reader = get_pdf_reader()
        
        # Load data
        self.data = MakeSimpleSql().get_orders()
        self.filtered_data = self.data.copy() if self.data else []  # Store filtered results
        self.suppliers = ["All"]
        self.get_suppliers()
        
        # Create UI components
        self.create_filters()
        self.create_widgets()
        self.create_buttons()
        self.populate_treeview()
        self.update_meters(self.data)

        # Add space at the bottom
        self.blank_frame = ttk.Frame(self, height=40)
        self.blank_frame.grid(row=5, column=0, pady=5)
        self.blank_frame.propagate(False)
        
        logger.info(f"Orders frame initialized with {len(self.data)} records")

    def create_widgets(self):
        """Create the main treeview widget."""
        tree_frame = ttk.Frame(self)
        tree_frame.grid(row=2, column=0, columnspan=2, sticky="nsew", padx=10, pady=10)
        tree_frame.rowconfigure(0, weight=1)
        tree_frame.columnconfigure(0, weight=1)

        self.tree = CustomTreeview(tree_frame, self.columns, "extended")
        
        scrollbar = ttk.Scrollbar(tree_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)
        
        self.tree.grid(row=0, column=0, sticky="nsew")
        scrollbar.grid(row=0, column=1, sticky="ns")
        
        # Configure columns
        columns = tuple()
        for col in self.columns:
            if col not in ["width", "length", "id"]:
                columns = columns + (col,)
            self.tree.heading(col, text=ORDERS_COLUMN_CONFIG[col], 
                            command=lambda c=col: self.sort_column(c))
        self.tree['displaycolumns'] = columns

        # Context menu
        self.context_menu = tk.Menu(self, tearoff=0)
        self.context_menu.add_command(label="Receipt", command=self.context_receipt)
        self.context_menu.add_separator()
        for item in ORDER_STATUS:
            self.context_menu.add_command(label=item, 
                                         command=lambda i=item: self.context_status_change(i))

        # Bind events
        self.tree.bind("<Button-3>", self.show_context_menu)
        self.tree.bind("<Double-1>", self.on_double_click)
        self.tree.bind("<Control-a>", self.select_all)

    def create_filters(self):
        """Create filter widgets."""
        def get_last_day_of_month(date_obj):
            next_month = date_obj.replace(day=28) + timedelta(days=4)
            return next_month - timedelta(days=next_month.day)
        
        self.filter_frame = ttk.LabelFrame(self, text="Filters", padding=10)
        self.filter_frame.grid(row=1, column=0, columnspan=2, padx=10, sticky="nsew")

        # Date filters
        ttk.Label(self.filter_frame, text="Start Date").grid(row=0, column=0, padx=5, pady=5, sticky="e")
        self.start_date = DateEntry(self.filter_frame, width=12)
        self.start_date.grid(row=0, column=1, padx=5, pady=5)

        ttk.Label(self.filter_frame, text="End Date").grid(row=0, column=2, padx=5, pady=5, sticky="e")
        self.end_date = DateEntry(self.filter_frame, width=12)
        self.end_date.grid(row=0, column=3, padx=5, pady=5)

        # Set default date range (this month)
        today = datetime.today()
        first_day = today.replace(day=1)
        last_day = get_last_day_of_month(today).date()
        self.end_date.entry.delete(0, "end")
        self.end_date.entry.insert(0, last_day.strftime("%Y-%m-%d")) 
        self.start_date.entry.delete(0, "end")
        self.start_date.entry.insert(0, first_day.strftime("%Y-%m-%d"))

        # Date presets
        preset_options = ["Custom", "Today", "Yesterday", "Last 7 Days", 
                         "Next 7 Days", "This Month"]
        self.preset_combo = ttk.Combobox(self.filter_frame, values=preset_options, 
                                        state="readonly", width=15)
        self.preset_combo.set("This Month")
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
                return
            
            self.start_date.entry.delete(0, "end")
            self.start_date.entry.insert(0, s.strftime("%Y-%m-%d")) 
            self.end_date.entry.delete(0, "end")
            self.end_date.entry.insert(0, e.strftime("%Y-%m-%d"))
            self.apply_filters()

        self.preset_combo.bind("<<ComboboxSelected>>", apply_preset)

        # Supplier filter
        ttk.Label(self.filter_frame, text="Supplier").grid(row=0, column=5, padx=5)
        self.supplier_filter = ttk.Combobox(self.filter_frame, values=self.suppliers, width=15)
        self.supplier_filter.current(0)
        self.supplier_filter.grid(row=0, column=6, padx=5)

        # Status filter
        ttk.Label(self.filter_frame, text="Status").grid(row=0, column=7, padx=5)
        self.status_filter = ttk.Combobox(self.filter_frame, 
                                         values=(["All"] + STATUS), width=12)
        self.status_filter.current(0)
        self.status_filter.grid(row=0, column=8, padx=5)

        # Filter buttons
        ttk.Button(self.filter_frame, text="Apply Filters", 
                  bootstyle="primary", command=self.apply_filters).grid(row=0, column=9, padx=10)
        ttk.Button(self.filter_frame, text="Reset", 
                  bootstyle="secondary", command=self.reset_filters).grid(row=0, column=10, padx=5)
        
        # Refresh suppliers button
        ttk.Button(self.filter_frame, text="🔄", 
                  bootstyle="info-outline", 
                  command=self.refresh_suppliers_ui,
                  width=3).grid(row=0, column=11, padx=2)

        # Search box with label
        ttk.Label(self.filter_frame, text="Search:").grid(row=0, column=12, padx=(10, 0))
        self.search_var = tk.StringVar()
        self.search_entry = ttk.Entry(self.filter_frame, textvariable=self.search_var, width=20)
        self.search_entry.grid(row=0, column=13, padx=(0, 5))
        
        # Bind search to real-time filtering
        self.search_var.trace('w', lambda *args: self.apply_wildcard_filter())
        
        # Clear search button
        ttk.Button(self.filter_frame, text="✕", 
                  bootstyle="secondary-outline",
                  width=3,
                  command=self.clear_search).grid(row=0, column=14, padx=0)
        
        # Second row for additional filters
        # Include Closed Orders checkbox
        ttk.Label(self.filter_frame, text="Options:").grid(row=1, column=0, padx=5, pady=5, sticky="e")
        
        self.include_closed_var = tk.BooleanVar(value=False)
        self.include_closed_check = ttk.Checkbutton(
            self.filter_frame,
            text="Include Closed Orders",
            variable=self.include_closed_var,
            command=self.apply_filters,
            bootstyle="primary-round-toggle"
        )
        self.include_closed_check.grid(row=1, column=1, columnspan=2, padx=5, pady=5, sticky="w")
        
        # Search in closed only checkbox
        self.closed_only_var = tk.BooleanVar(value=False)
        self.closed_only_check = ttk.Checkbutton(
            self.filter_frame,
            text="Closed Orders Only",
            variable=self.closed_only_var,
            command=self.toggle_closed_only,
            bootstyle="info-round-toggle"
        )
        self.closed_only_check.grid(row=1, column=3, columnspan=2, padx=5, pady=5, sticky="w")
        
        # Status summary label
        self.status_summary_label = ttk.Label(
            self.filter_frame,
            text="",
            font=("Segoe UI", 9),
            foreground="gray"
        )
        self.status_summary_label.grid(row=1, column=5, columnspan=4, padx=5, pady=5, sticky="w")

    def clear_search(self):
        """Clear the search field."""
        self.search_var.set("")
        self.search_entry.focus()

    def toggle_closed_only(self):
        """Handle closed orders only toggle."""
        if self.closed_only_var.get():
            # If "Closed Only" is checked, automatically check "Include Closed"
            self.include_closed_var.set(True)
            # Disable the include closed checkbox
            self.include_closed_check.config(state="disabled")
        else:
            # Re-enable the include closed checkbox
            self.include_closed_check.config(state="normal")
        
        # Apply filters
        self.apply_filters()

    def refresh_suppliers_ui(self):
        """Refresh suppliers and update the filter dropdown."""
        try:
            PDFReaderSingleton.refresh_suppliers()
            
            # Reload suppliers into the filter
            old_selection = self.supplier_filter.get()
            self.suppliers = ["All"]
            self.get_suppliers()
            self.supplier_filter['values'] = self.suppliers
            
            # Restore selection if still valid
            if old_selection in self.suppliers:
                self.supplier_filter.set(old_selection)
            else:
                self.supplier_filter.current(0)
            
            messagebox.showinfo("Success", 
                              f"Refreshed {len(self.suppliers)-1} suppliers from database")
            logger.info(f"Supplier filter updated with {len(self.suppliers)-1} suppliers")
            
        except Exception as e:
            logger.error(f"Error refreshing supplier UI: {e}")
            messagebox.showerror("Error", f"Could not refresh suppliers: {e}")

    def create_buttons(self):
        """Create action buttons."""
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

    def populate_treeview(self, rows=None):
        """Populate the Treeview with given rows or fallback to filtered_data."""
        self.tree.delete(*self.tree.get_children())

        dataset = rows if rows is not None else self.filtered_data
        if not dataset:
            return

        for index, row in enumerate(dataset):
            dict_row = dict(row)
            values = [dict_row.get(col, "") for col in self.tree["columns"]]
            self.tree.insert("", "end", values=values)

        # Setup tags
        self.tree.tag_configure("even_overdue", background="#ffdddd")
        self.tree.tag_configure("odd_overdue", background="#ffcccc")
        self.tree.tag_configure("even_overdue_over_shipped", background="#ffe4e1")
        self.tree.tag_configure("odd_overdue_over_shipped", background="#ffcccc")
        self.tree.tag_configure("even_over_shipped", background="#e4f1b1")
        self.tree.tag_configure("odd_over_shipped", background="#dff395")
        
        logger.debug(f"Populated treeview with {len(dataset)} rows")

    def get_suppliers(self):
        """Load suppliers from database."""
        suppliers = MakeSimpleSql().get_suppliers()
        if suppliers:
            for supplier in suppliers:
                self.suppliers.append(supplier[0])
        logger.debug(f"Loaded {len(self.suppliers)-1} suppliers")

    def apply_filters(self):
        """Apply date, supplier, status, and closed order filters to data."""
        try:
            # Get filter values
            start_date_str = self.start_date.entry.get().strip()
            end_date_str = self.end_date.entry.get().strip()
            supplier_val = self.supplier_filter.get().strip()
            status_val = self.status_filter.get().strip()
            include_closed = self.include_closed_var.get()
            closed_only = self.closed_only_var.get()

            # Start with all data
            filtered = list(self.data)

            # Apply closed orders filter FIRST
            if closed_only:
                # Show only closed orders
                filtered = [r for r in filtered 
                           if dict(r).get("status", "").lower() in ["closed", "completed", "cancelled"]]
                logger.debug("Filtering for closed orders only")
            elif not include_closed:
                # Exclude closed orders (default behavior)
                filtered = [r for r in filtered 
                           if dict(r).get("status", "").lower() not in ["closed", "completed", "cancelled"]]
                logger.debug("Excluding closed orders")

            # Apply date filter
            if start_date_str and end_date_str:
                try:
                    start_date = datetime.strptime(start_date_str, "%Y-%m-%d").date()
                    end_date = datetime.strptime(end_date_str, "%Y-%m-%d").date()
                    
                    def date_in_range(row):
                        # Adjust column name based on your data structure
                        row_date_str = dict(row).get("order_date") or dict(row).get("due_date")
                        if not row_date_str:
                            return True
                        try:
                            row_date = datetime.strptime(str(row_date_str), "%Y-%m-%d").date()
                            return start_date <= row_date <= end_date
                        except:
                            return True
                    
                    filtered = [r for r in filtered if date_in_range(r)]
                except Exception as e:
                    logger.error(f"Date filter error: {e}")

            # Apply supplier filter
            if supplier_val and supplier_val != "All":
                filtered = [r for r in filtered 
                           if dict(r).get("supplier", "").lower() == supplier_val.lower()]

            # Apply status filter (only if not using closed_only)
            if status_val and status_val != "All" and not closed_only:
                filtered = [r for r in filtered 
                           if dict(r).get("status", "").lower() == status_val.lower()]

            # Store filtered data
            self.filtered_data = filtered
            
            # Update status summary
            self.update_status_summary(filtered)
            
            # Apply search if there's a search term
            search_term = self.search_var.get().strip()
            if search_term:
                self.apply_wildcard_filter()
            else:
                self.populate_treeview(filtered)
            
            logger.info(f"Filters applied: {len(filtered)} of {len(self.data)} records shown")
            
        except Exception as e:
            logger.error(f"Error applying filters: {e}", exc_info=True)
            messagebox.showerror("Filter Error", f"Error applying filters: {e}")

    def apply_wildcard_filter(self):
        """Apply search/wildcard filter on top of other filters."""
        wildcard_val = self.search_var.get().strip().lower()
        
        # Start with filtered data (after date/supplier/status filters)
        base_data = self.filtered_data if hasattr(self, 'filtered_data') else self.data
        
        if not wildcard_val:
            # No search term, show all filtered data
            self.populate_treeview(base_data)
            return
        
        def match(row):
            """Check if search term matches any field in the row."""
            dict_row = dict(row)
            # Search through all visible columns
            for col in self.columns:
                value = str(dict_row.get(col, "")).lower()
                if wildcard_val in value:
                    return True
            return False

        filtered = [r for r in base_data if match(r)]
        self.populate_treeview(filtered)
        
        logger.debug(f"Search filter applied: '{wildcard_val}' - {len(filtered)} results")

    def reset_filters(self):
        """Reset all filters to default values."""
        self.supplier_filter.current(0)
        self.status_filter.current(0)
        self.start_date.entry.delete(0, 'end')
        self.end_date.entry.delete(0, 'end')
        self.search_var.set("")
        self.include_closed_var.set(False)
        self.closed_only_var.set(False)
        self.include_closed_check.config(state="normal")
        
        # Reset to show all data
        self.filtered_data = list(self.data)
        self.populate_treeview(self.data)
        self.update_status_summary(self.data)
        
        logger.info("Filters reset")

    def on_double_click(self, event):
        """Handle double-click on a row."""
        selected_item = self.tree.selection()
        if not selected_item:
            return

        item_id = selected_item[0]
        values = self.tree.item(item_id, "values")
        columns = self.tree["columns"]

        row_data = dict(zip(columns, values))
        order_id = row_data.get("order_id")

        if order_id is None:
            logger.warning("order_id missing in selected row")
            return

        # Find the full record in self.data
        full_record = next(
            (dict(row) for row in self.data 
             if str(row.get("order_id")) == str(order_id)),
            None
        )

        if full_record:
            self.open_order_details(full_record)
        else:
            logger.warning(f"Could not find full record for order_id: {order_id}")

    def select_all(self, event=None):
        """Select all visible rows in treeview."""
        self.tree.selection_set(self.tree.get_children())
        return "break"

    def show_context_menu(self, event):
        """Show context menu on right-click."""
        rowid = self.tree.identify_row(event.y)
        if not rowid:
            return
        
        selected = self.tree.selection()
        if rowid not in selected:
            self.tree.selection_set(rowid)
        else:
            self.tree.focus(rowid)

        self.context_menu_rowid = rowid
        self.context_menu.post(event.x_root, event.y_root)

    def context_receipt(self):
        """Handle receipt context menu action."""
        rowid = getattr(self, 'context_menu_rowid', None)
        if rowid:
            col = self.tree['column']
            values = self.tree.item(rowid)["values"]
            kv = dict(zip(col, values))
            self.open_receipt_docket(kv.get("purchase_order_number"))

    def context_status_change(self, command):
        """Handle status change from context menu."""
        logger.info(f"Changing status to: {command}")
        selected_rows = self.tree.selection()
        if not selected_rows:
            logger.warning("No rows selected for status change")
            return

        for rowid in selected_rows:
            self.tree.set(rowid, "status", command)

        self.update_record()

    def update_record(self, rowid=None):
        """Update database records."""
        try:
            items = [rowid] if rowid else self.tree.selection()
            for item_id in items:
                values = self.tree.item(item_id)["values"]
                columns = self.tree["columns"]
                kv = dict(zip(columns, values))

                if not kv.get("order_id"):
                    continue

                MakeSimpleSql().update_order_status(kv)
            
            # Reload data and reapply filters
            self.data = MakeSimpleSql().get_orders()
            self.apply_filters()
            
            logger.info("Records updated successfully")

        except Exception as e:
            logger.error(f"Update error: {e}", exc_info=True)
            messagebox.showerror("Error", str(e))

    def sort_column(self, col):
        """Sort treeview by column."""
        data = [(self.tree.set(k, col), k) for k in self.tree.get_children('')]
        
        # Determine if we should reverse
        reverse = (self._sort_column == col and not self._sort_reverse)
        
        try:
            # Try numeric sort first
            data.sort(key=lambda t: float(t[0]) if t[0] else 0, reverse=reverse)
        except ValueError:
            # Fall back to string sort
            data.sort(key=lambda t: str(t[0]).lower(), reverse=reverse)

        for index, (_, k) in enumerate(data):
            self.tree.move(k, '', index)

        # Update column headers with arrows
        for c in self.tree["columns"]:
            arrow = ""
            if c == col:
                arrow = " ↓" if reverse else " ↑"
            self.tree.heading(c, text=ORDERS_COLUMN_CONFIG.get(c, c) + arrow)

        self._sort_column = col
        self._sort_reverse = reverse
        
        logger.debug(f"Sorted by {col} (reverse={reverse})")

    def export_csv(self):
        """Export visible data to CSV."""
        file_path = filedialog.asksaveasfilename(
            defaultextension=".csv", 
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")]
        )
        if not file_path:
            return

        try:
            with open(file_path, mode='w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                # Write headers
                writer.writerow(self.columns)
                # Write data
                for row_id in self.tree.get_children():
                    writer.writerow(self.tree.item(row_id)['values'])
            
            messagebox.showinfo("Export", f"Data exported successfully to:\n{file_path}")
            logger.info(f"Data exported to {file_path}")
            
        except Exception as e:
            logger.error(f"Export error: {e}", exc_info=True)
            messagebox.showerror("Error", f"Failed to export: {e}")

    def main_action_press(self, params):
        """Handle main button actions."""
        logger.debug(f"Action pressed: {params}")
        # Implement your button actions here
        pass

    def update_meters(self, rows):
        """Update dashboard meters."""
        # Implement your meter update logic here
        pass

    def open_receipt_docket(self, purchase_order=None):
        """Open receipt/delivery docket window."""
        from main import DeliveryDocket
        DeliveryDocket(self, purchase_order)

    def open_new_po_window(self):
        """Open new purchase order window."""
        from main import NewPurchaseOrder
        NewPurchaseOrder(self)

    def open_order_details(self, order_detail):
        """Open order details window."""
        from main import MainOrderDetails
        print(order_detail)
        MainOrderDetails(self, order_detail["order_id"], order_detail["customer_id"])

    def submit_po(self):
        """Submit purchase order."""
        self.reader.update_record()
        self.data = MakeSimpleSql().get_purchase_order()
        self.filtered_data = list(self.data)
        self.populate_treeview()

    def to_base_16(self, value):
        """Convert decimal to base 16 (for sheet sizes)."""
        # Implement your conversion logic
        pass

    def update_status_summary(self, rows):
        """Update the status summary label."""
        if not rows:
            self.status_summary_label.config(text="No records")
            return
        
        # Count by status
        status_counts = {}
        for row in rows:
            status = dict(row).get("status", "Unknown")
            status_counts[status] = status_counts.get(status, 0) + 1
        
        # Build summary text
        summary_parts = []
        total = len(rows)
        
        # Show total first
        summary_parts.append(f"Total: {total}")
        
        # Show top 3 statuses
        sorted_statuses = sorted(status_counts.items(), key=lambda x: x[1], reverse=True)
        for status, count in sorted_statuses[:3]:
            percentage = (count / total * 100) if total > 0 else 0
            summary_parts.append(f"{status}: {count} ({percentage:.0f}%)")
        
        summary_text = " | ".join(summary_parts)
        self.status_summary_label.config(text=summary_text)
        
        logger.debug(f"Status summary: {summary_text}")