import tkinter as tk
from ttkbootstrap import ttk, Style
from ttkbootstrap.dialogs import Messagebox

class AddressForm(ttk.Frame):
    def __init__(self, parent, on_save=None, on_cancel=None):
        super().__init__(parent, padding=10)
        self.on_save = on_save
        self.on_cancel = on_cancel

        self.vars = {
            "name_1": tk.StringVar(),
            "name_2": tk.StringVar(),
            "address_type": tk.StringVar(value="shipping"),
            "address_1": tk.StringVar(),
            "address_2": tk.StringVar(),
            "city": tk.StringVar(),
            "province": tk.StringVar(),
            "postal_code": tk.StringVar(),
            "country": tk.StringVar(value="Canada"),
            "is_active": tk.BooleanVar(value=True),
        }

        self.create_widgets()

    def create_widgets(self):
        row = 0
        ttk.Label(self, text="Name 1").grid(row=row, column=0, sticky="w", padx=5, pady=2)
        ttk.Entry(self, textvariable=self.vars["name_1"]).grid(row=row, column=1, sticky="ew", padx=5, pady=2)

        row += 1
        ttk.Label(self, text="Name 2").grid(row=row, column=0, sticky="w", padx=5, pady=2)
        ttk.Entry(self, textvariable=self.vars["name_2"]).grid(row=row, column=1, sticky="ew", padx=5, pady=2)

        row += 1
        ttk.Label(self, text="Address Type").grid(row=row, column=0, sticky="w", padx=5, pady=2)
        ttk.Combobox(self, textvariable=self.vars["address_type"], values=["billing", "shipping"], state="readonly")\
            .grid(row=row, column=1, sticky="ew", padx=5, pady=2)

        row += 1
        ttk.Label(self, text="Address 1").grid(row=row, column=0, sticky="w", padx=5, pady=2)
        ttk.Entry(self, textvariable=self.vars["address_1"]).grid(row=row, column=1, sticky="ew", padx=5, pady=2)

        row += 1
        ttk.Label(self, text="Address 2").grid(row=row, column=0, sticky="w", padx=5, pady=2)
        ttk.Entry(self, textvariable=self.vars["address_2"]).grid(row=row, column=1, sticky="ew", padx=5, pady=2)

        row += 1
        ttk.Label(self, text="City").grid(row=row, column=0, sticky="w", padx=5, pady=2)
        ttk.Entry(self, textvariable=self.vars["city"]).grid(row=row, column=1, sticky="ew", padx=5, pady=2)

        row += 1
        ttk.Label(self, text="Province").grid(row=row, column=0, sticky="w", padx=5, pady=2)
        ttk.Entry(self, textvariable=self.vars["province"]).grid(row=row, column=1, sticky="ew", padx=5, pady=2)

        row += 1
        ttk.Label(self, text="Postal Code").grid(row=row, column=0, sticky="w", padx=5, pady=2)
        ttk.Entry(self, textvariable=self.vars["postal_code"]).grid(row=row, column=1, sticky="ew", padx=5, pady=2)

        row += 1
        ttk.Label(self, text="Country").grid(row=row, column=0, sticky="w", padx=5, pady=2)
        ttk.Entry(self, textvariable=self.vars["country"]).grid(row=row, column=1, sticky="ew", padx=5, pady=2)

        row += 1
        ttk.Checkbutton(self, text="Active", variable=self.vars["is_active"]).grid(row=row, column=1, sticky="w", padx=5, pady=2)

        row += 1
        btn_frame = ttk.Frame(self)
        btn_frame.grid(row=row, column=0, columnspan=2, pady=10)
        ttk.Button(btn_frame, text="Save", bootstyle="success", command=self.save).pack(side="left", padx=5)
        ttk.Button(btn_frame, text="Cancel", bootstyle="secondary", command=self.cancel).pack(side="left", padx=5)

        self.columnconfigure(1, weight=1)

    def set_data(self, data):
        """Populate form with existing data."""
        for key, var in self.vars.items():
            if key in data:
                if isinstance(var, tk.BooleanVar):
                    var.set(bool(data[key]))
                else:
                    var.set(data[key])

    def get_data(self):
        """Return form data as dict."""
        return {k: (v.get() if not isinstance(v, tk.BooleanVar) else int(v.get())) for k, v in self.vars.items()}

    def save(self):
        data = self.get_data()
        if not data["name_1"] or not data["address_1"]:
            Messagebox.show_error("Name 1 and Address 1 are required.")
            return
        if self.on_save:
            self.on_save(data)

    def cancel(self):
        if self.on_cancel:
            self.on_cancel()
