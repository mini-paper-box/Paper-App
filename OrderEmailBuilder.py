import os
import tkinter as tk
import ttkbootstrap as ttk
from ttkbootstrap.tableview import Tableview
from ttkbootstrap.constants import *
from tkinter import messagebox
from pathlib import Path
import html
from datetime import datetime
import win32com.client as win32
from reportlab.lib.pagesizes import LETTER
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib import colors
import math

class OrderEmailBuilder:
    """
    Builds and optionally sends an order email with ship-to address and order line details.
    Can also generate and attach a PDF summary.
    """

    def __init__(self, bill_to:dict, ship_to: dict, orders: list[dict]):
        self.ship_to = ship_to
        self.bill_to = bill_to
        self.orders = self._normalize_orders(orders)
        print(ship_to)
        print(bill_to)
    def _normalize_orders(self, orders):
        """Ensure orders have only the keys we need."""
        normalized = []
        for row in orders:
            order_quantity = row.get("order_quantity", 0)
            unit_qty = row.get("unit_qty", 1)
            
            # Avoid division by zero
            num_pallet = math.ceil(order_quantity / unit_qty) if unit_qty else 0
            normalized.append({
                "order_id": row.get("order_id", ""),
                "order_line": row.get("order_line", ""),
                "docket_id": row.get("docket_id", ""),
                "docket_description": row.get("docket_description", ""),
                "order_quantity": order_quantity,
                "unit_qty" : unit_qty,
                "num_pallet" : num_pallet
            })
        print(normalized)
        return normalized

    def build_email_body(self) -> str:
        """Return a formatted HTML email string."""

        ship_to_html = f"""
        <div style="margin-bottom: 10px;">
            <strong>Ship To:</strong><br>
            {self.ship_to.get('name_1', '')}<br>
            {self.ship_to.get('address_1', '')}<br>
            {self.ship_to.get('city', '')}, {self.ship_to.get('province', '')} {self.ship_to.get('postal_code', '')}<br>
            {self.ship_to.get('country', '')}<br/><br/>
            <strong>They open until {int(self.ship_to.get('end_time', '')) - 12} PM</strong>
        </div>
        """

        order_rows = "".join(f"""
            <tr>
                <td style="padding: 4px; border: 1px solid #ccc;">{o['order_id']}-{o['order_line']}</td>
                <td style="padding: 4px; border: 1px solid #ccc;">{o['docket_id']}</td>
                <td style="padding: 4px; border: 1px solid #ccc; text-align: right;">{o['docket_description']}</td>
                <td style="padding: 4px; border: 1px solid #ccc; text-align: right;">{o['order_quantity']}</td>
            </tr>
        """ for o in self.orders if o.get('num_pallet', 0) > 0)
    

        orders_html = f"""
        <table style="border-collapse: collapse; width: 60%; margin-top: 10px;">
            <thead>
                <tr style="background-color: #f0f0f0;">
                    <th style="padding: 4px; border: 1px solid #ccc;">Order #</th>
                    <th style="padding: 4px; border: 1px solid #ccc;">Docket #</th>
                    <th style="padding: 4px; border: 1px solid #ccc;">Description</th>
                    <th style="padding: 4px; border: 1px solid #ccc;">Order Quantity</th>
                </tr>
            </thead>
            <tbody>{order_rows}</tbody>
        </table>
        """

        return f"""
        <html>
            <body style="font-family: Arial, sans-serif; font-size: 12pt;">
                <p>Hello Team,</p>
                <p>Please find below the shipping details and order information:</p>
                {ship_to_html}
                <strong>Orders:</strong><br>
                {orders_html}
                <p>Please confirm if this is good to proceed.</p>
                <p>Thank you,<br>Production Team</p>
            </body>
        </html>
        """

    def send_email(self, to, cc="", subject="Order Shipping Details", attach_pdf=True, auto_send=False):
        outlook = win32.Dispatch("Outlook.Application")
        mail = outlook.CreateItem(0)
        mail.To = to
        if cc:
            mail.CC = cc
        mail.Subject = subject
        mail.HTMLBody = self.build_email_body()

        if attach_pdf:
            try:
                from QuickTurnaroundPDF import QuickTurnaroundPDF
                pdf_generator = QuickTurnaroundPDF(
                    customer_name=self.ship_to.get('name_1', ''),
                    address=self.ship_to.get('address_1', ''),
                    total_units=sum(order.get("num_pallet", 0) for order in self.orders),
                    orders=self.orders,
                    driver_paperwork_attached=True,
                    filename= f"QTA_{self.orders[0]["order_id"]}.pdf"
                )
                pdf_path = Path(pdf_generator.generate_pdf())
                if pdf_path.exists():
                    mail.Attachments.Add(str(pdf_path))
            except Exception as e:
                print(f"[WARNING] Failed to attach PDF: {e}")

        if auto_send:
            mail.Send()
        else:
            mail.Display()
    
    def verify_and_send(self, to, cc="", subject="Order Shipping Details", attach_pdf=True):
        """Open a ttkbootstrap window to review/edit order details before sending email."""
        root = tk.Toplevel()
        root.title("Verify Order Details")
        root.grab_set()  # modal
        style = ttk.Style("flatly")

        # --- Ship To Info as editable fields ---
        ship_frame = ttk.Frame(root, padding=10)
        ship_frame.grid(row=0, column=0, sticky="ew")
        ship_frame.columnconfigure(1, weight=1)

        ttk.Label(ship_frame, text="Ship To:", font=("Arial", 14, "bold")).grid(row=0, column=0, sticky="w", pady=(0,5))
        ship_entries = {}
        fields = ["name_1", "address_1", "city", "province", "postal_code", "country"]
        for i, key in enumerate(fields, start=1):
            ttk.Label(ship_frame, text=key.replace("_", " ").title() + ":").grid(row=i, column=0, sticky="w", pady=2)
            entry = ttk.Entry(ship_frame)
            entry.grid(row=i, column=1, sticky="ew", pady=2)

            value = self.ship_to.get(key, "")
            if value is None:
                value = ""
            elif isinstance(value, (tuple, list)):
                value = value[0] if value else ""
            else:
                value = str(value)

            entry.insert(0, value)
            ship_entries[key] = entry

        # --- Orders Table ---
        table_frame = ttk.Frame(root)
        table_frame.grid(row=1, column=0, sticky="nsew", padx=10, pady=(10,5))
        root.grid_rowconfigure(1, weight=1)
        root.grid_columnconfigure(0, weight=1)

        columns = ("order_id", "docket_id", "description", "order_qty", "pallets")
        tree = ttk.Treeview(table_frame, columns=columns, show="headings")
        tree.grid(row=0, column=0, sticky="nsew")
        table_frame.grid_rowconfigure(0, weight=1)
        table_frame.grid_columnconfigure(0, weight=1)

        vsb = ttk.Scrollbar(table_frame, orient="vertical", command=tree.yview)
        vsb.grid(row=0, column=1, sticky="ns")
        hsb = ttk.Scrollbar(table_frame, orient="horizontal", command=tree.xview)
        hsb.grid(row=1, column=0, sticky="ew")
        tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)

        for col, text in zip(columns, ["Order #", "Docket #", "Description", "Order Qty", "Pallets"]):
            tree.heading(col, text=text)
            tree.column(col, width=100)

        for o in self.orders:
            tree.insert("", "end", values=(
                f"{o['order_id']}-{o['order_line']}",
                o['docket_id'],
                o['docket_description'],
                o['order_quantity'],
                o['num_pallet']
            ))

        # --- Editable cells ---
        def edit_cell(event):
            item_id = tree.identify_row(event.y)
            col = tree.identify_column(event.x)
            if not item_id or not col:
                return

            x, y, width, height = tree.bbox(item_id, col)
            value = tree.set(item_id, col)
            entry = tk.Entry(root)
            entry.place(x=x, y=y + tree.winfo_y(), width=width, height=height)
            entry.insert(0, value)
            entry.focus()

            def save_edit(event=None):
                col_index = int(col.replace("#",""))-1
                new_val = entry.get()

                # numeric validation for qty and pallets
                if col_index in [3,4]:
                    try:
                        new_val = int(new_val)
                    except ValueError:
                        messagebox.showerror("Invalid input", "Please enter a number")
                        return

                tree.set(item_id, col, new_val)

                # auto-update pallets if order_qty changed
                if col_index == 3:
                    order_qty = int(new_val)
                    unit_qty = 1  # default; replace with actual unit_qty if stored
                    tree.set(item_id, "pallets", math.ceil(order_qty/unit_qty))

                entry.destroy()

            entry.bind("<Return>", save_edit)
            entry.bind("<FocusOut>", lambda e: entry.destroy())

        tree.bind("<Double-1>", edit_cell)

        # --- Buttons ---
        btn_frame = ttk.Frame(root)
        btn_frame.grid(row=2, column=0, sticky="ew", padx=10, pady=(5,10))
        btn_frame.columnconfigure((0,1), weight=1)

        def confirm():
            # update ship_to from entries
            for key, entry in ship_entries.items():
                self.ship_to[key] = entry.get()

            # update orders from tree
            new_orders = []
            for item_id in tree.get_children():
                vals = tree.item(item_id)["values"]
                order_id_split = str(vals[0]).split("-")
                new_orders.append({
                    "order_id": order_id_split[0],
                    "order_line": order_id_split[1] if len(order_id_split)>1 else "1",
                    "docket_id": vals[1],
                    "docket_description": vals[2],
                    "order_quantity": vals[3],
                    "num_pallet": vals[4]
                })
            self.orders = new_orders
            root.destroy()
            self.send_email(to, cc=cc, subject=subject, attach_pdf=attach_pdf,auto_send=True)

        def cancel():
            if messagebox.askyesno("Cancel", "Are you sure you want to cancel?"):
                root.destroy()

        ttk.Button(btn_frame, text="✅ Confirm & Send", bootstyle="success", command=confirm).grid(row=0, column=0, sticky="ew", padx=5)
        ttk.Button(btn_frame, text="❌ Cancel", bootstyle="danger", command=cancel).grid(row=0, column=1, sticky="ew", padx=5)

