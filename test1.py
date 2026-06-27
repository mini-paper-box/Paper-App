import tkinter as tk
import ttkbootstrap as ttk
from ttkbootstrap.constants import *

class CustomerForm(ttk.Frame):
    def __init__(self, parent, title="Customer Information", **kwargs):
        super().__init__(parent, **kwargs)

        # Title label
        ttk.Label(self, text=title, font=("Segoe UI", 14, "bold")).grid(
            row=0, column=0, columnspan=2, pady=(0, 10)
        )

        # --- Customer Name ---
        ttk.Label(self, text="Customer Name:").grid(row=1, column=0, sticky=E, padx=5, pady=5)
        self.name_var = tk.StringVar()
        ttk.Entry(self, textvariable=self.name_var, width=40).grid(row=1, column=1, sticky=W, padx=5, pady=5)

        # --- Billing Address ---
        ttk.Label(self, text="Billing Address", font=("Segoe UI", 12, "bold")).grid(
            row=2, column=0, columnspan=2, sticky=W, padx=5, pady=(10, 5)
        )
        self.bill_street = tk.StringVar()
        self.bill_city = tk.StringVar()
        self.bill_state = tk.StringVar()
        self.bill_postal = tk.StringVar()
        self.bill_country = tk.StringVar()

        self._make_address_fields(3, self.bill_street, self.bill_city, self.bill_state, self.bill_postal, self.bill_country)

        # --- Shipping Address ---
        ttk.Label(self, text="Shipping Address", font=("Segoe UI", 12, "bold")).grid(
            row=8, column=0, columnspan=2, sticky=W, padx=5, pady=(10, 5)
        )
        self.ship_street = tk.StringVar()
        self.ship_city = tk.StringVar()
        self.ship_state = tk.StringVar()
        self.ship_postal = tk.StringVar()
        self.ship_country = tk.StringVar()

        self._make_address_fields(9, self.ship_street, self.ship_city, self.ship_state, self.ship_postal, self.ship_country)

    def _make_address_fields(self, start_row, street, city, state, postal, country):
        ttk.Label(self, text="Street:").grid(row=start_row, column=0, sticky=E, padx=5, pady=2)
        ttk.Entry(self, textvariable=street, width=40).grid(row=start_row, column=1, sticky=W, padx=5, pady=2)

        ttk.Label(self, text="City:").grid(row=start_row+1, column=0, sticky=E, padx=5, pady=2)
        ttk.Entry(self, textvariable=city, width=40).grid(row=start_row+1, column=1, sticky=W, padx=5, pady=2)

        ttk.Label(self, text="State/Province:").grid(row=start_row+2, column=0, sticky=E, padx=5, pady=2)
        ttk.Entry(self, textvariable=state, width=40).grid(row=start_row+2, column=1, sticky=W, padx=5, pady=2)

        ttk.Label(self, text="Postal Code:").grid(row=start_row+3, column=0, sticky=E, padx=5, pady=2)
        ttk.Entry(self, textvariable=postal, width=40).grid(row=start_row+3, column=1, sticky=W, padx=5, pady=2)

        ttk.Label(self, text="Country:").grid(row=start_row+4, column=0, sticky=E, padx=5, pady=2)
        ttk.Entry(self, textvariable=country, width=40).grid(row=start_row+4, column=1, sticky=W, padx=5, pady=2)

    # ---- Helpers ----
    def get_data(self):
        """Return all entered data as dict"""
        return {
            "name": self.name_var.get(),
            "bill_address": {
                "street": self.bill_street.get(),
                "city": self.bill_city.get(),
                "state": self.bill_state.get(),
                "postal_code": self.bill_postal.get(),
                "country": self.bill_country.get()
            },
            "ship_address": {
                "street": self.ship_street.get(),
                "city": self.ship_city.get(),
                "state": self.ship_state.get(),
                "postal_code": self.ship_postal.get(),
                "country": self.ship_country.get()
            }
        }

    def set_data(self, customer_dict):
        """Load data into form"""
        self.name_var.set(customer_dict.get("name", ""))

        bill = customer_dict.get("bill_address", {})
        self.bill_street.set(bill.get("street", ""))
        self.bill_city.set(bill.get("city", ""))
        self.bill_state.set(bill.get("state", ""))
        self.bill_postal.set(bill.get("postal_code", ""))
        self.bill_country.set(bill.get("country", ""))

        ship = customer_dict.get("ship_address", {})
        self.ship_street.set(ship.get("street", ""))
        self.ship_city.set(ship.get("city", ""))
        self.ship_state.set(ship.get("state", ""))
        self.ship_postal.set(ship.get("postal_code", ""))
        self.ship_country.set(ship.get("country", ""))

if __name__ == "__main__":
    root = ttk.Window(themename="flatly")
    form = CustomerForm(root)
    form.pack(padx=20, pady=20, fill="x")

    def show_data():
        print(form.get_data())

    ttk.Button(root, text="Get Data", command=show_data).pack(pady=10)

    root.mainloop()
