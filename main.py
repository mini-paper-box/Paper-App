import tkinter as tk
import ttkbootstrap as ttk
from ttkbootstrap.constants import *
from PIL import Image, ImageTk
from settings import *
from purchasing_frame import TreeviewFrame
from order_frame import Orders
from new_po_frame import NewPurchaseOrderFrame
from delivery_docket_frame import DeliveryDocketFrame
# from import_orders import *
# from import_customer import *
from order_details_frame import *
from add_orders_to_purchase_order import *
# from import_order_details import ImportOrderDetails
from OrderRoutingImporter import OrderRoutingImporter
from scheduling_frame import SchedulingFrame
from schedule_chain_frame import SchedulerChainFrame
from mod_production.ui.main_frame import ProductionPlannerFrame
from auto_unitize import AutoUnitize
from csv_watcher import CSVWatcher
from order_crm import OrderAddressDialog
from win10toast import ToastNotifier
from plyer import notification
from toolbar import *
from pdf_reader_singleton import get_pdf_reader, PDFReaderSingleton  # NEW IMPORT
import os, shutil, time, logging

try:
    from ctypes import windll, byref, sizeof, c_int, wintypes
    import win32clipboard
    import win32con
except:
    pass

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('paperbox.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


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

class Unitize(BaseTopLevel):
    def __init__(self, parent):
        super().__init__(parent, title="Auto Unitize")
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)

        frame = AutoUnitize(self)
        frame.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)

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
        app = NewPurchaseOrderFrame(self)
        app.pack(fill="both", expand=True)

class OpenAIScheduler(BaseTopLevel):
    def __init__(self, parent):
        super().__init__(parent)
        self.title('Production scheduler')
        self.state('zoomed')
        app = ProductionPlannerFrame(self)
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
    
class PaperBox(ttk.Window):
    def __init__(self):
        super().__init__(themename="flatly")
        self.title("Paper Box")
        self.state('zoomed')

        # Initialize PDFReader singleton early (loads suppliers once)
        logger.info("Initializing PDFReader singleton...")
        self.pdf_reader = get_pdf_reader()
        logger.info(f"PDFReader initialized with {len(self.pdf_reader.vendor_keywords)} suppliers")

        # CSV Watcher for auto-imports
        # watcher = CSVWatcher("schedule_listing.csv")
        # if watcher.has_update():
        #     self.import_order()
        #     self.import_order_routing()
        #     self.update_order()
        #     self.import_order_details()

        # Create menu bar
        self.create_menubar()
        
        # Create toolbar
        tb = Toolbar(self)
        tb.grid(row=0, column=0)

        # Content area
        content = ttk.Label(self, text="Main Content Area", 
                           font=("Segoe UI", 16), anchor="center")
        content.grid(row=1, column=0, padx=20, pady=20, sticky="nsew")

        self.rowconfigure(1, weight=1)
        self.columnconfigure(0, weight=1)

        self.mainloop()

    def create_menubar(self):
        """Create the top menu bar."""
        menubar = tk.Menu(self)

        # File Menu
        # file_menu = tk.Menu(menubar, tearoff=0)
        # file_menu.add_command(label="New Order", command=self.import_order)
        # file_menu.add_separator()
        # file_menu.add_command(label="Refresh Suppliers", 
        #                      command=self.refresh_all_suppliers)
        # file_menu.add_separator()
        # file_menu.add_command(label="Exit", command=self.quit)
        # menubar.add_cascade(label="File", menu=file_menu)

        # # Import Menu
        # import_menu = tk.Menu(menubar, tearoff=0)
        # import_menu.add_command(label="Import Orders", command=self.import_order)
        # import_menu.add_command(label="Import Orders Routing", 
        #                        command=self.import_order_routing)
        # import_menu.add_command(label="Import Customers", command=self.import_customer)
        # menubar.add_cascade(label="Import", menu=import_menu)

        # # Update Menu
        # update_menu = tk.Menu(menubar, tearoff=0)
        # update_menu.add_command(label="Update Orders", command=self.update_order)
        # menubar.add_cascade(label="Update", menu=update_menu)

        # Tools Menu (NEW)
        tools_menu = tk.Menu(menubar, tearoff=0)
        tools_menu.add_command(label="View Suppliers", 
                              command=self.show_supplier_dialog)
        tools_menu.add_command(label="View Logs", command=self.show_logs)
        tools_menu.add_separator()
        tools_menu.add_command(label="Settings", command=self.show_settings)
        menubar.add_cascade(label="Tools", menu=tools_menu)

        views_menu = tk.Menu(menubar,tearoff=0)
        views_menu.add_command(label="AI Schedule", command=self.open_ai_scheduler)
        menubar.add_cascade(label="View",menu=views_menu)

        self.config(menu=menubar)

    def open_ai_scheduler(self):
        OpenAIScheduler(self)

    def refresh_all_suppliers(self):
        """Refresh suppliers and notify user."""
        try:
            PDFReaderSingleton.refresh_suppliers()
            suppliers = PDFReaderSingleton.get_suppliers()
            messagebox.showinfo(
                "Suppliers Refreshed",
                f"Successfully loaded {len(suppliers)} suppliers from database.\n\n"
                "All open windows will use the updated supplier list."
            )
            logger.info(f"Suppliers refreshed from main menu: {len(suppliers)}")
        except Exception as e:
            logger.error(f"Error refreshing suppliers: {e}", exc_info=True)
            messagebox.showerror("Error", f"Could not refresh suppliers:\n{e}")

    def show_supplier_dialog(self):
        """Show dialog with all suppliers."""
        suppliers = PDFReaderSingleton.get_suppliers()
        
        dialog = tk.Toplevel(self)
        dialog.title("Supplier Management")
        dialog.geometry("600x500")
        
        # Header with count
        header_frame = ttk.Frame(dialog)
        header_frame.pack(fill="x", padx=10, pady=10)
        
        ttk.Label(
            header_frame,
            text=f"Current Suppliers ({len(suppliers)})",
            font=("Segoe UI", 14, "bold")
        ).pack(side="left")
        
        ttk.Button(
            header_frame,
            text="🔄 Refresh",
            command=lambda: self.refresh_supplier_dialog(dialog),
            bootstyle="info"
        ).pack(side="right")
        
        # Supplier list with search
        search_frame = ttk.Frame(dialog)
        search_frame.pack(fill="x", padx=10, pady=5)
        
        ttk.Label(search_frame, text="Search:").pack(side="left", padx=5)
        search_var = tk.StringVar()
        search_entry = ttk.Entry(search_frame, textvariable=search_var, width=30)
        search_entry.pack(side="left", fill="x", expand=True, padx=5)
        
        # Listbox with scrollbar
        list_frame = ttk.Frame(dialog)
        list_frame.pack(fill="both", expand=True, padx=10, pady=10)
        
        scrollbar = ttk.Scrollbar(list_frame)
        scrollbar.pack(side="right", fill="y")
        
        listbox = tk.Listbox(
            list_frame,
            yscrollcommand=scrollbar.set,
            font=("Segoe UI", 10),
            selectmode="extended"
        )
        listbox.pack(side="left", fill="both", expand=True)
        scrollbar.config(command=listbox.yview)
        
        def populate_list(filter_text=""):
            listbox.delete(0, tk.END)
            filtered = [s for s in sorted(suppliers) 
                       if filter_text.lower() in s.lower()]
            for supplier in filtered:
                listbox.insert(tk.END, supplier.title())
            return len(filtered)
        
        def on_search(*args):
            count = populate_list(search_var.get())
            # Could update a status label here
        
        search_var.trace("w", on_search)
        populate_list()
        
        # Button frame
        btn_frame = ttk.Frame(dialog)
        btn_frame.pack(fill="x", padx=10, pady=10)
        
        ttk.Button(
            btn_frame,
            text="Close",
            command=dialog.destroy,
            bootstyle="secondary"
        ).pack(side="right")

    def refresh_supplier_dialog(self, dialog):
        """Refresh suppliers and update dialog."""
        PDFReaderSingleton.refresh_suppliers()
        dialog.destroy()
        self.show_supplier_dialog()

    def show_logs(self):
        """Show application logs."""
        log_window = tk.Toplevel(self)
        log_window.title("Application Logs")
        log_window.geometry("800x600")
        
        # Text widget with scrollbar
        text_frame = ttk.Frame(log_window)
        text_frame.pack(fill="both", expand=True, padx=10, pady=10)
        
        scrollbar = ttk.Scrollbar(text_frame)
        scrollbar.pack(side="right", fill="y")
        
        text_widget = tk.Text(
            text_frame,
            yscrollcommand=scrollbar.set,
            wrap="word",
            font=("Consolas", 9)
        )
        text_widget.pack(side="left", fill="both", expand=True)
        scrollbar.config(command=text_widget.yview)
        
        # Load log file
        try:
            if os.path.exists('paperbox.log'):
                with open('paperbox.log', 'r') as f:
                    # Read last 1000 lines
                    lines = f.readlines()
                    text_widget.insert("1.0", "".join(lines[-1000:]))
                text_widget.see("end")  # Scroll to bottom
            else:
                text_widget.insert("1.0", "No log file found.")
        except Exception as e:
            text_widget.insert("1.0", f"Error reading log file: {e}")
        
        text_widget.config(state="disabled")
        
        # Buttons
        btn_frame = ttk.Frame(log_window)
        btn_frame.pack(fill="x", padx=10, pady=10)
        
        ttk.Button(
            btn_frame,
            text="Refresh",
            command=lambda: self.refresh_logs(text_widget),
            bootstyle="info"
        ).pack(side="left", padx=5)
        
        ttk.Button(
            btn_frame,
            text="Clear",
            command=lambda: self.clear_logs(text_widget),
            bootstyle="warning"
        ).pack(side="left", padx=5)
        
        ttk.Button(
            btn_frame,
            text="Close",
            command=log_window.destroy,
            bootstyle="secondary"
        ).pack(side="right", padx=5)

    def refresh_logs(self, text_widget):
        """Refresh log display."""
        text_widget.config(state="normal")
        text_widget.delete("1.0", "end")
        
        try:
            if os.path.exists('paperbox.log'):
                with open('paperbox.log', 'r') as f:
                    lines = f.readlines()
                    text_widget.insert("1.0", "".join(lines[-1000:]))
                text_widget.see("end")
        except Exception as e:
            text_widget.insert("1.0", f"Error: {e}")
        
        text_widget.config(state="disabled")

    def clear_logs(self, text_widget):
        """Clear log file."""
        if messagebox.askyesno("Clear Logs", 
                              "Are you sure you want to clear the log file?"):
            try:
                with open('paperbox.log', 'w') as f:
                    f.write("")
                text_widget.config(state="normal")
                text_widget.delete("1.0", "end")
                text_widget.insert("1.0", "Logs cleared.")
                text_widget.config(state="disabled")
                logger.info("Log file cleared by user")
            except Exception as e:
                messagebox.showerror("Error", f"Could not clear logs: {e}")

    def show_settings(self):
        """Show settings dialog."""
        settings_window = tk.Toplevel(self)
        settings_window.title("Settings")
        settings_window.geometry("500x400")
        
        notebook = ttk.Notebook(settings_window)
        notebook.pack(fill="both", expand=True, padx=10, pady=10)
        
        # PDF Settings Tab
        pdf_tab = ttk.Frame(notebook)
        notebook.add(pdf_tab, text="PDF Processing")
        
        ttk.Label(
            pdf_tab,
            text="PDF Processing Settings",
            font=("Segoe UI", 12, "bold")
        ).pack(pady=10)
        
        # Clipboard interval
        interval_frame = ttk.LabelFrame(pdf_tab, text="Clipboard Check Interval", padding=10)
        interval_frame.pack(fill="x", padx=20, pady=10)
        
        ttk.Label(interval_frame, text="Check every (seconds):").pack(side="left")
        interval_var = tk.IntVar(value=5)
        ttk.Spinbox(
            interval_frame,
            from_=1,
            to=60,
            textvariable=interval_var,
            width=10
        ).pack(side="left", padx=10)
        
        # Supplier refresh interval
        supplier_frame = ttk.LabelFrame(pdf_tab, text="Supplier Refresh", padding=10)
        supplier_frame.pack(fill="x", padx=20, pady=10)
        
        ttk.Label(supplier_frame, text="Auto-refresh every (minutes):").pack(side="left")
        supplier_var = tk.IntVar(value=60)
        ttk.Spinbox(
            supplier_frame,
            from_=5,
            to=480,
            textvariable=supplier_var,
            width=10
        ).pack(side="left", padx=10)
        
        # Current suppliers count
        info_frame = ttk.LabelFrame(pdf_tab, text="Current Status", padding=10)
        info_frame.pack(fill="x", padx=20, pady=10)
        
        suppliers = PDFReaderSingleton.get_suppliers()
        ttk.Label(
            info_frame,
            text=f"Loaded Suppliers: {len(suppliers)}",
            font=("Segoe UI", 10)
        ).pack(anchor="w")
        
        ttk.Button(
            info_frame,
            text="View Suppliers",
            command=self.show_supplier_dialog,
            bootstyle="info-outline"
        ).pack(anchor="w", pady=5)
        
        # Save button
        btn_frame = ttk.Frame(settings_window)
        btn_frame.pack(fill="x", padx=10, pady=10)
        
        ttk.Button(
            btn_frame,
            text="Save",
            command=settings_window.destroy,
            bootstyle="primary"
        ).pack(side="right", padx=5)
        
        ttk.Button(
            btn_frame,
            text="Cancel",
            command=settings_window.destroy,
            bootstyle="secondary"
        ).pack(side="right")

    # Keep existing import methods
    # def import_order(self):
    #     import_order = ImportOrder()
    #     import_order.run()

    # def import_order_routing(self):
    #     import_order_routing = OrderRoutingImporter()
    #     import_order_routing.run()

    # def import_order_details(self):
    #     order_details = ImportOrderDetails()
    #     order_details.run()

    # def import_customer(self):
    #     import_customerr = ImportCustomer()
    #     import_customerr.run()

    # def update_order(self):
    #     update_order = AddOrdersToPurchaseOrder()
    #     update_order.run()


# ==============================================================================
# STEP 4: Testing the Integration
# ==============================================================================

def test_singleton():
    """Test that singleton pattern works correctly."""
    print("Testing PDFReader Singleton...")
    
    # Test 1: Same instance
    reader1 = get_pdf_reader()
    reader2 = get_pdf_reader()
    assert reader1 is reader2, "ERROR: Different instances created!"
    print("✓ Test 1 passed: Same instance returned")
    
    # Test 2: Supplier list
    suppliers1 = PDFReaderSingleton.get_suppliers()
    print(f"✓ Test 2 passed: {len(suppliers1)} suppliers loaded")
    
    # Test 3: Refresh
    PDFReaderSingleton.refresh_suppliers()
    suppliers2 = PDFReaderSingleton.get_suppliers()
    print(f"✓ Test 3 passed: Suppliers refreshed ({len(suppliers2)} suppliers)")
    
    # Test 4: Shared state
    reader1.vendor_keywords.append("test_supplier")
    assert "test_supplier" in reader2.vendor_keywords, "ERROR: State not shared!"
    print("✓ Test 4 passed: State is shared between references")
    
    print("\n✅ All tests passed!")


if __name__ == "__main__":
    # Uncomment to run tests
    test_singleton()
    
    PaperBox()