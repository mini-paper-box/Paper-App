# main.py
import tkinter as tk
import ttkbootstrap as ttk
from ttkbootstrap.constants import *
from PIL import Image, ImageTk
from settings import *
from purchasing_frame import TreeviewFrame
from order_frame import Orders
from new_po_frame import NewPurchaseOrderFrame
from delivery_docket_frame import DeliveryDocketFrame
from import_orders import *
from import_customer import *
from order_details_frame import *
from add_orders_to_purchase_order import *
from import_order_details import ImportOrderDetails
from OrderRoutingImporter import OrderRoutingImporter
from scheduling_frame import SchedulingFrame
from schedule_chain_frame import SchedulerChainFrame
from csv_watcher import CSVWatcher
from order_crm import OrderAddressDialog
from win10toast import ToastNotifier
from plyer import notification
from pdf_reader import PDFReader
import os, shutil, time
try:
    from ctypes import windll, byref, sizeof, c_int, wintypes
    import win32clipboard
    import win32con
except:
    pass

def screen_size():
    try:
        user32 = windll.user32
        return((int(user32.GetSystemMetrics(0)),int(user32.GetSystemMetrics(1))))
    except:
        pass

def get_work_area():
    # Get the working area (excluding taskbar) using Windows API
    SPI_GETWORKAREA = 0x0030
    rect = wintypes.RECT()
    windll.user32.SystemParametersInfoW(SPI_GETWORKAREA, 0, byref(rect), 0)
    return rect

def maximize_window(top):
    hwnd = windll.user32.GetParent(top.winfo_id())
    SW_MAXIMIZE = 3
    windll.user32.ShowWindow(hwnd, SW_MAXIMIZE)

class BaseTopLevel(tk.Toplevel):
    def __init__(self, parent, title="Dialog"):
        super().__init__(parent)
        self.parent = parent
        self.title(title)

        # Place near parent
        self.geometry("+{}+{}".format(parent.winfo_rootx() + 50,
                                      parent.winfo_rooty() + 50))

        # Bind Esc key
        self.bind_all("<Escape>", self.on_escape, add="+" )

        # Optional: Make it modal
        self.transient(parent)
        self.lift() 
        self.focus_force()
        self.grab_set() #convert to modal (this must be close before )

    def on_escape(self, event=None):
        """Only close if this window is the active one."""
        # Check if this window is the one in focus
        if self.focus_get() is not None and self.focus_get().winfo_toplevel() == self:
            self.close_window()

    def close_window(self, event=None):
        """Closes this dialog"""
        self.destroy()

class Purchasing(BaseTopLevel):
    def __init__(self, parent):
        super().__init__(parent)
        self.title('Purchase Order')
        self.state('zoomed')

        self.grid_rowconfigure(0, weight=1)  
        self.grid_columnconfigure(0, weight=1)   

        TreeviewFrame(self).grid(row=0, column=0, sticky='nsew')

class MainOrders(BaseTopLevel):
    def __init__(self, parent):
        super().__init__(parent)
        self.title('Orders')
        self.state('zoomed')

        self.grid_rowconfigure(0, weight=1)  
        self.grid_columnconfigure(0, weight=1)   

        Orders(self).grid(row=0, column=0, sticky='nsew')

class MainOrderDetails(BaseTopLevel):
    def __init__(self, parent, order_id, customer_id):
        super().__init__(parent)
        self.title('Orders')
        self.state('zoomed')
        self.grid_rowconfigure(0, weight=1)  
        self.grid_columnconfigure(0, weight=1)   
        OrderDetails(self, order_id, customer_id).grid(row=0, column=0, sticky='nsew')

class OrderAddressDialog(BaseTopLevel):
    def __init__(self, parent):
        super().__init__(parent)
        self.title('Order')
        self.work_area = get_work_area()
        self.width = self.work_area.right - self.work_area.left
        self.height = self.work_area.bottom - self.work_area.top
        self.geometry(f"{self.width}x{self.height - 40}+{self.work_area.left}+{self.work_area.top}")
        self.transient(parent)

        self.grid_rowconfigure(0, weight=1)  
        self.grid_columnconfigure(0, weight=1) 

        # app = OrderAddressDialog(self)
        # app.grid(row=0, column=0, sticky='nsew')

class Scheduler(BaseTopLevel):
    def __init__(self, parent):
        super().__init__(parent)
        self.title('Scheduling')
        self.work_area = get_work_area()
        self.width = self.work_area.right - self.work_area.left
        self.height = self.work_area.bottom - self.work_area.top
        self.geometry(f"{self.width}x{self.height - 40}+{self.work_area.left}+{self.work_area.top}")
        self.lift()
        self.transient(parent)

        self.grid_rowconfigure(0, weight=1)  
        self.grid_columnconfigure(0, weight=1) 

        app = SchedulingFrame(self)
        app.pack(fill="both", expand=True)

class SchedulerChain(BaseTopLevel):
    def __init__(self, parent):
        super().__init__(parent)
        self.title('Chain Lookup')
        self.work_area = get_work_area()
        self.width = self.work_area.right - self.work_area.left
        self.height = self.work_area.bottom - self.work_area.top
        self.geometry(f"{self.width}x{self.height - 40}+{self.work_area.left}+{self.work_area.top}")
        self.lift()
        self.transient(parent)

        self.grid_rowconfigure(0, weight=1)  
        self.grid_columnconfigure(0, weight=1) 

        app = SchedulerChainFrame(self)
        app.pack(fill="both", expand=True)

class NewPurchaseOrder(BaseTopLevel):
    def __init__(self, parent):
        super().__init__(parent)
        self.title('New Purchase Order')
        # self.work_area = get_work_area()
        # self.width = self.work_area.right - self.work_area.left
        # self.height = self.work_area.bottom - self.work_area.top
        # self.geometry(f"{self.width}x{self.height - 40}+{self.work_area.left}+{self.work_area.top}")
        # self.lift()
        # self.transient(parent)

        # self.grid_rowconfigure(0, weight=1)  
        # self.grid_columnconfigure(0, weight=1) 

        app = NewPurchaseOrderFrame(self)
        app.pack(fill="both", expand=True)

class DeliveryDocket(BaseTopLevel):
    def __init__(self, parent, purchase_order= None):
        super().__init__(parent)
        self.title('Delivery Docket')
        self.geometry("800x600")
        # self.geometry(f"{screen_size[0]}x{screen_size[1]}+0+0")
        self.transient(parent)
        self.purchase_order = purchase_order
        self.rowconfigure(0, weight=1)
        self.columnconfigure(0, weight=1)
        if self.purchase_order:
            app = DeliveryDocketFrame(self, self.purchase_order)
        else:
            app = DeliveryDocketFrame(self)
        app.grid(row=0, column=0, sticky='nsew')
    

class Toolbar(tk.Frame):
    def __init__(self, parent):
        super().__init__(parent)
        self.columnconfigure(0, weight=0)
        self.rowconfigure(0,weight = 0)
        self.grid(row=0, column=0, sticky="nesw")

        self.reader = PDFReader()
        self.auto_refresh_clipboard()
        # # Load icons (can be PNG or GIF)

        new_icon = tk.PhotoImage(file="icons/new.png")
        purchase_icon = tk.PhotoImage(file="icons/complex-pie.png", height=32, width=32)
        save_icon = tk.PhotoImage(file="icons/exit.png")
        lookup_icon = tk.PhotoImage(file="icons/arrow-up-and-three-steps-18200.png")

        # Add buttons to toolbar
        ttk.Button(self, image=new_icon, command=self.open_order).grid(row=0, column=0, padx=5)
        ttk.Button(self, image=purchase_icon, command=self.open_purchasing).grid(row=0, column=1, padx=5)
        ttk.Button(self, image=save_icon, command=self.open_delivery_docket).grid(row=0, column=2, padx=5)
        ttk.Button(self, image=lookup_icon, command=self.open_scheduler_chain).grid(row=0, column=3, padx=5)
        # ttk.Button(self, image=new_icon, command=open_new_po).pack(side="left", padx=2)
        # ttk.Button(self, image=purchase_icon, command=open_purchasing).pack(side="left", padx=2)
        # ttk.Button(self, image=save_icon, command=open_delivery_docket).pack(side="left", padx=2)

        # Keep references to icons to prevent garbage collection
        self.new_icon = new_icon
        self.purchase_icon = purchase_icon
        self.save_icon = save_icon
        # self.pack(side="top", fill="x")
    def open_scheduler(self):
        Scheduler(self)

    def open_order(self):
        MainOrders(self)

    def open_purchasing(self):
        Purchasing(self)

    def open_delivery_docket(self):
        DeliveryDocket(self, screen_size())

    def open_scheduler_chain(self):
        SchedulerChain(self)

    def on_exit(self):
        self.quit()
    
    def clear_clipboard(self):
        try:
            win32clipboard.OpenClipboard()
            win32clipboard.EmptyClipboard()
        finally:
            win32clipboard.CloseClipboard()
    
    def safe_open_clipboard(self, retries=3, delay=0.1):
        for _ in range(retries):
            try:
                win32clipboard.OpenClipboard()
                return True
            except Exception:
                time.sleep(delay)
        return False

    def get_clipboard_files(self):
        if not self.safe_open_clipboard():
            return []

        try:
            if win32clipboard.IsClipboardFormatAvailable(win32con.CF_HDROP):
                files = win32clipboard.GetClipboardData(win32con.CF_HDROP)
                return list(files)
        finally:
            win32clipboard.CloseClipboard()
        return []

    def auto_refresh_clipboard(self, interval=5000):
            try:
                files = self.get_clipboard_files()
                if files:
                    for file_path in files:
                        if self.reader.extract_files_info(file_path):
                            if os.path.isfile(file_path):
                                shutil.copy(file_path, CPO_PATH)
                                notification.notify(
                                    title="Process Complete",
                                    message="Files uploaded successfully!",
                                    timeout=5)
                            elif os.path.isdir(file_path):
                                folder_name = os.path.basename(file_path)
                                shutil.copytree(file_path, os.path.join(CPO_PATH, folder_name))
                            else:
                                print(f"Unknown file type: {file_path}")
                    self.clear_clipboard()
            except Exception as e:
                print(f"Clipboard check failed: {e}")

            self.after(interval, self.auto_refresh_clipboard, interval)

class PaperBox(ttk.Window):
    def __init__(self):
        super().__init__(themename="flatly")
        self.title("Paper Box")
        # root.wm_attributes('-topmost', False)
        self.state('zoomed')

        watcher = CSVWatcher("schedule_listing.csv")
        if watcher.has_update():
            self.import_order()
            self.import_order_routing()
            self.update_order()
            self.import_order_details()

        
        # -------------------------------
        # Top Menu Bar
        # -------------------------------
        menubar = tk.Menu(self)

        # --- File Menu ---
        file_menu = tk.Menu(menubar, tearoff=0)
        file_menu.add_command(label="New", command=self.import_order)
        # file_menu.add_command(label="Open", command=open_purchasing)
        # file_menu.add_command(label="Save", command=open_delivery_docket)
        # file_menu.add_separator()
        # file_menu.add_command(label="Exit", command=on_exit)
        menubar.add_cascade(label="File", menu=file_menu)

        # --- Import Menu ---
        import_menu = tk.Menu(menubar, tearoff=0)
        import_menu.add_command(label="Import Orders", command=self.import_order)
        import_menu.add_command(label="Import Orders Routing", command=self.import_order_routing)
        import_menu.add_command(label="Import Customers", command=self.import_customer)
        menubar.add_cascade(label="Import", menu=import_menu)

        # --- Update Menu ---
        update_menu = tk.Menu(menubar, tearoff=0)
        update_menu.add_command(label="Update Orders", command=self.update_order)
        menubar.add_cascade(label="Update", menu=update_menu)

        # Attach the complete menu to the window
        self.config(menu=menubar)

        # -------------------------------
        # Toolbar (buttons with icons)
        # -------------------------------

        tb = Toolbar(self)
        tb.grid(row=0,column=0)

        # Content area
        content = ttk.Label(self, text="Main Content Area", font=("Segoe UI", 16), anchor="center")
        content.grid(row=1, column=0, padx=20, pady=20, sticky="nsew")

        self.rowconfigure(1, weight=1)
        self.columnconfigure(0, weight=1)

        


        self.mainloop()
    # tb.pack(side="top", fill="x")
    def import_order(self):
        import_order = ImportOrder()
        import_order.run()

    def import_order_routing(self):
        import_order_routing = OrderRoutingImporter()
        import_order_routing.run()

    def import_order_details(self):
        order_details = ImportOrderDetails()
        order_details.run()

    def import_customer(self):
        import_customerr = ImportCustomer()
        import_customerr.run()

    def update_order(self):
        update_order = AddOrdersToPurchaseOrder()
        update_order.run()
    
if __name__ == "__main__":
    PaperBox()
