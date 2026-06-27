import tkinter as tk
from ttkbootstrap import Style
from ttkbootstrap import ttk

# Dummy get_work_area() simulating your screen area retrieval
def get_work_area():
    # Normally you get real screen coordinates here
    class Area:
        left = 100
        top = 100
        right = 1000
        bottom = 700
    return Area()

class OrderAddressFrame(ttk.Frame):
    def __init__(self, parent):
        super().__init__(parent)
        self.create_widgets()

    def create_widgets(self):
        # Example layout: Bill To left, Ship To right, Treeview bottom
        self.grid_rowconfigure(1, weight=1)
        self.grid_columnconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=1)

        # Bill To Frame
        bill_to_frame = ttk.LabelFrame(self, text="Bill To")
        bill_to_frame.grid(row=0, column=0, sticky="nsew", padx=(0,10), pady=10)
        bill_to_frame.columnconfigure(1, weight=1)

        ttk.Label(bill_to_frame, text="Name:").grid(row=0, column=0, sticky="e", pady=2)
        self.bill_name = ttk.Entry(bill_to_frame)
        self.bill_name.grid(row=0, column=1, sticky="ew", pady=2)

        ttk.Label(bill_to_frame, text="Address:").grid(row=1, column=0, sticky="ne", pady=2)
        self.bill_address = tk.Text(bill_to_frame, height=4)
        self.bill_address.grid(row=1, column=1, sticky="ew", pady=2)

        # Ship To Frame
        ship_to_frame = ttk.LabelFrame(self, text="Ship To")
        ship_to_frame.grid(row=0, column=1, sticky="nsew", pady=10)
        ship_to_frame.columnconfigure(1, weight=1)

        ttk.Label(ship_to_frame, text="Name:").grid(row=0, column=0, sticky="e", pady=2)
        self.ship_name = ttk.Entry(ship_to_frame)
        self.ship_name.grid(row=0, column=1, sticky="ew", pady=2)

        ttk.Label(ship_to_frame, text="Address:").grid(row=1, column=0, sticky="ne", pady=2)
        self.ship_address = tk.Text(ship_to_frame, height=4)
        self.ship_address.grid(row=1, column=1, sticky="ew", pady=2)

        # Treeview at bottom spanning 2 columns
        columns = ("item", "description", "qty", "price", "total")
        self.tree = ttk.Treeview(self, columns=columns, show="headings")
        self.tree.grid(row=1, column=0, columnspan=2, sticky="nsew", padx=10, pady=(0,10))

        for col in columns:
            self.tree.heading(col, text=col.title())
            self.tree.column(col, anchor="center", width=100)

        # Vertical scrollbar
        scrollbar = ttk.Scrollbar(self, orient="vertical", command=self.tree.yview)
        scrollbar.grid(row=1, column=2, sticky="ns", pady=(0,10))
        self.tree.configure(yscrollcommand=scrollbar.set)

        # Sample data
        sample_data = [
            ("A123", "Widget", 5, 20.0, 100.0),
            ("B456", "Gadget", 3, 15.5, 46.5),
            ("C789", "Doohickey", 10, 7.75, 77.5),
        ]
        for row in sample_data:
            self.tree.insert("", "end", values=row)

class OrderAddressDialog(tk.Toplevel):
    def __init__(self, parent):
        super().__init__(parent)
        self.title('Order Addresses')

        self.work_area = get_work_area()
        self.width = self.work_area.right - self.work_area.left
        self.height = self.work_area.bottom - self.work_area.top
        self.geometry(f"{self.width}x{self.height - 40}+{self.work_area.left}+{self.work_area.top}")

        self.transient(parent)
        self.grab_set()  # Modal dialog

        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)

        # Add the main content frame
        content = OrderAddressFrame(self)
        content.grid(row=0, column=0, sticky='nsew')

        # You can add buttons here if needed
        btn_frame = ttk.Frame(self)
        btn_frame.grid(row=1, column=0, sticky="e", padx=10, pady=10)
        ttk.Button(btn_frame, text="OK", command=self.on_ok).pack(side="right", padx=5)
        ttk.Button(btn_frame, text="Cancel", command=self.destroy).pack(side="right")

        self.content = content  # Save reference if you want to access data later

    def on_ok(self):
        # Example: gather data and close
        bill = {
            "name": self.content.bill_name.get(),
            "address": self.content.bill_address.get("1.0", "end").strip(),
        }
        ship = {
            "name": self.content.ship_name.get(),
            "address": self.content.ship_address.get("1.0", "end").strip(),
        }
        print("Bill To:", bill)
        print("Ship To:", ship)
        self.destroy()

if __name__ == "__main__":
    root = tk.Tk()
    style = Style(theme="flatly")
    root.withdraw()

    dlg = OrderAddressDialog(root)
    root.mainloop()
