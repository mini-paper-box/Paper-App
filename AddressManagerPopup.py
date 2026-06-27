import tkinter as tk
from ttkbootstrap import ttk, Style
from ttkbootstrap.dialogs import Messagebox
from AddressForm import AddressForm

class AddressManagerPopup(tk.Toplevel):
    def __init__(self, parent, database, customer_id, on_select=None):
        super().__init__(parent)
        self.title("Manage Addresses")
        self.geometry("800x600")
        self.transient(parent)
        self.grab_set()

        self.database = database
        self.customer_id = customer_id
        self.on_select = on_select
        self.selected_address_id = None

        # === TOP FRAME: TREEVIEW ===
        tree_frame = ttk.Frame(self)
        tree_frame.pack(fill="both", expand=True, padx=10, pady=5)

        columns = ("address_id", "name_1", "address_1", "city", "province", "postal_code", "is_active")
        self.tree = ttk.Treeview(tree_frame, columns=columns, show="headings", height=8)
        for col in columns:
            self.tree.heading(col, text=col.replace("_", " ").title())
            self.tree.column(col, width=100, anchor="w")
        self.tree.pack(side="left", fill="both", expand=True)

        scrollbar = ttk.Scrollbar(tree_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side="right", fill="y")

        self.tree.bind("<<TreeviewSelect>>", self.on_tree_select)
        self.tree.bind("<Double-1>", lambda e: self.use_selected())

        # === MIDDLE FRAME: ADDRESS FORM ===
        self.form = AddressForm(self, on_save=self.save_address)
        self.form.pack(fill="x", padx=10, pady=5)

        # === BOTTOM FRAME: BUTTONS ===
        btn_frame = ttk.Frame(self)
        btn_frame.pack(fill="x", pady=5)
        ttk.Button(btn_frame, text="Add New", bootstyle="primary", command=self.clear_form).pack(side="left", padx=5)
        ttk.Button(btn_frame, text="Delete", bootstyle="danger", command=self.delete_address).pack(side="left", padx=5)
        ttk.Button(btn_frame, text="Use Selected", bootstyle="success", command=self.use_selected).pack(side="right", padx=5)
        ttk.Button(btn_frame, text="Close", bootstyle="secondary", command=self.destroy).pack(side="right", padx=5)

        self.load_addresses()

    def load_addresses(self):
        """Fetch addresses from DB, populate treeview, and cache them."""
        self.tree.delete(*self.tree.get_children())
        query = """
        SELECT address_id, name_1, address_1, city, province, postal_code,country, is_active
        FROM addresses WHERE customer_id = ? ORDER BY is_active DESC, name_1
        """
        try:
            # ✅ Store results so other methods can use them
            self.addresses = self.database.get_customer_addresses(query, (self.customer_id,))

            for row in self.addresses:
                display_values = [
                    row["address_id"],
                    row["name_1"],
                    row["address_1"],
                    row["city"],
                    row["province"],
                    row["postal_code"],
                    row["country"],
                    "Yes" if row["is_active"] else "No"
                ]
                self.tree.insert("", "end", values=display_values)

            return self.addresses  # still returns for convenience

        except Exception as e:
            print(f"Error loading addresses: {e}")
            self.addresses = []  # ✅ Ensure attribute always exists
            return []


    def on_tree_select(self, event):
        """Populate form when a row is selected, using cached data."""
        selected = self.tree.selection()
        if not selected:
            return

        values = self.tree.item(selected[0], "values")
        self.selected_address_id = values[0]

        # Look up full record in self.addresses (populated by load_addresses)
        full_record = next(
            (row for row in self.addresses if str(row["address_id"]) == str(self.selected_address_id)),
            None
        )

        if full_record:
            self.form.set_data(full_record)

    def clear_form(self):
        """Reset form for new address."""
        self.selected_address_id = None
        self.form.set_data({})  # clears form

    def save_address(self, data):
        print("test")
        """Insert or update address in DB."""
        if self.selected_address_id:
            # Update
            query = """
            UPDATE addresses
            SET name_1=?, name_2=?, address_type=?, address_1=?, address_2=?, city=?, 
                province=?, postal_code=?, country=?, is_active=?
            WHERE address_id=?
            """
            params = (
                data["name_1"], data["name_2"], data["address_type"], data["address_1"], data["address_2"],
                data["city"], data["province"], data["postal_code"], data["country"], data["is_active"],
                self.selected_address_id
            )
            self.database.execute(query, params)
        else:
            # Insert
            query = """
            INSERT INTO addresses (customer_id, name_1, name_2, address_type, address_1, address_2, 
                                   city, province, postal_code, country, is_active)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """
            params = (
                self.customer_id, data["name_1"], data["name_2"], data["address_type"], data["address_1"],
                data["address_2"], data["city"], data["province"], data["postal_code"], data["country"],
                data["is_active"]
            )
            self.database.execute(query, params)

        self.load_addresses()
        self.clear_form()

    def delete_address(self):
        """Delete selected address."""
        if not self.selected_address_id:
            Messagebox.show_warning("No address selected.")
            return
        self.database.execute("DELETE FROM addresses WHERE address_id=?", (self.selected_address_id,))
        self.load_addresses()
        self.clear_form()

    def use_selected(self):
        """Send selected address back to caller (for Ship-To update)."""
        if not self.selected_address_id:
            Messagebox.show_warning("No address selected.")
            return

        # Find the selected record from self.addresses (cached data)
        selected_record = next(
            (row for row in self.addresses if str(row["address_id"]) == str(self.selected_address_id)),
            None
        )

        if self.on_select and selected_record:
            self.on_select(selected_record)

        self.destroy()
