import tkinter as tk
import ttkbootstrap as ttk
from ttkbootstrap.constants import *
from settings import *
from main import *
from pdf_reader_singleton import get_pdf_reader, PDFReaderSingleton
from plyer import notification
import os, shutil, time, logging

try:
    import win32clipboard
    import win32con
except:
    pass

logger = logging.getLogger(__name__)


class Toolbar(tk.Frame):
    def __init__(self, parent):
        super().__init__(parent)
        self.columnconfigure(0, weight=0)
        self.rowconfigure(0, weight=0)
        self.grid(row=0, column=0, sticky="nesw")

        # Use singleton PDFReader instance
        self.reader = get_pdf_reader()
        self.last_supplier_refresh = time.time()
        self.supplier_refresh_interval = 3600  # Refresh every hour
        
        self.auto_refresh_clipboard()

        # Load icons
        new_icon = tk.PhotoImage(file="icons/new.png")
        purchase_icon = tk.PhotoImage(file="icons/complex-pie.png", height=32, width=32)
        save_icon = tk.PhotoImage(file="icons/exit.png")
        lookup_icon = tk.PhotoImage(file="icons/arrow-up-and-three-steps-18200.png")

        # Add buttons to toolbar
        ttk.Button(self, image=new_icon, command=self.open_order).grid(row=0, column=0, padx=5)
        ttk.Button(self, image=purchase_icon, command=self.open_purchasing).grid(row=0, column=1, padx=5)
        ttk.Button(self, image=save_icon, command=self.open_delivery_docket).grid(row=0, column=2, padx=5)
        ttk.Button(self, image=lookup_icon, command=self.open_scheduler_chain).grid(row=0, column=3, padx=5)
        ttk.Button(self, image=lookup_icon, command=self.open_auto_unitize).grid(row=0, column=4, padx=5)
        
        # Optional: Add refresh button
        # refresh_icon = tk.PhotoImage(file="icons/refresh.png")
        # ttk.Button(self, image=refresh_icon, command=self.refresh_suppliers, 
        #           bootstyle="info-outline").grid(row=0, column=4, padx=5)

        # Keep references to icons
        self.new_icon = new_icon
        self.purchase_icon = purchase_icon
        self.save_icon = save_icon
        self.lookup_icon = lookup_icon
        
        # Create context menu
        self.create_context_menu()
        self.bind("<Button-3>", self.show_context_menu)

    def create_context_menu(self):
        """Create right-click context menu."""
        self.context_menu = tk.Menu(self, tearoff=0)
        self.context_menu.add_command(
            label="🔄 Refresh Suppliers", 
            command=self.refresh_suppliers
        )
        self.context_menu.add_command(
            label="📋 Process Clipboard Now", 
            command=self.manual_process_clipboard
        )
        self.context_menu.add_separator()
        self.context_menu.add_command(
            label="ℹ️ Show Supplier List", 
            command=self.show_supplier_info
        )

    def show_context_menu(self, event):
        """Show context menu at mouse position."""
        try:
            self.context_menu.tk_popup(event.x_root, event.y_root)
        finally:
            self.context_menu.grab_release()

    def refresh_suppliers(self):
        """Manually refresh supplier list from database."""
        try:
            PDFReaderSingleton.refresh_suppliers()
            supplier_count = len(PDFReaderSingleton.get_suppliers())
            
            notification.notify(
                title="Suppliers Refreshed",
                message=f"Loaded {supplier_count} suppliers from database",
                timeout=3
            )
            logger.info(f"Supplier list refreshed: {supplier_count} suppliers")
        except Exception as e:
            logger.error(f"Error refreshing suppliers: {e}")
            notification.notify(
                title="Refresh Failed",
                message="Could not refresh supplier list",
                timeout=3
            )

    def show_supplier_info(self):
        """Show dialog with current supplier list."""
        suppliers = PDFReaderSingleton.get_suppliers()
        
        info_window = tk.Toplevel(self)
        info_window.title("Current Suppliers")
        info_window.geometry("400x500")
        
        # Header
        header = ttk.Label(
            info_window, 
            text=f"Loaded Suppliers ({len(suppliers)})",
            font=("Segoe UI", 12, "bold")
        )
        header.pack(pady=10)
        
        # Text widget with scrollbar
        text_frame = ttk.Frame(info_window)
        text_frame.pack(fill="both", expand=True, padx=10, pady=10)
        
        scrollbar = ttk.Scrollbar(text_frame)
        scrollbar.pack(side="right", fill="y")
        
        text_widget = tk.Text(
            text_frame, 
            yscrollcommand=scrollbar.set, 
            wrap="word",
            font=("Consolas", 10)
        )
        text_widget.pack(side="left", fill="both", expand=True)
        scrollbar.config(command=text_widget.yview)
        
        # Insert supplier list
        for i, supplier in enumerate(sorted(suppliers), 1):
            text_widget.insert("end", f"{i}. {supplier.title()}\n")
        
        text_widget.config(state="disabled")
        
        # Close button
        ttk.Button(
            info_window, 
            text="Close", 
            command=info_window.destroy,
            bootstyle="secondary"
        ).pack(pady=10)

    def check_supplier_refresh(self):
        """Automatically refresh suppliers periodically."""
        current_time = time.time()
        if current_time - self.last_supplier_refresh > self.supplier_refresh_interval:
            logger.info("Auto-refreshing supplier list")
            self.refresh_suppliers()
            self.last_supplier_refresh = current_time

    def manual_process_clipboard(self):
        """Manually trigger clipboard processing immediately."""
        # Cancel existing scheduled callback and process now
        self.after_cancel(getattr(self, '_clipboard_job', None))
        self.auto_refresh_clipboard(interval=100)

    def open_scheduler(self):
        from main import Scheduler
        Scheduler(self)

    def open_order(self):
        from main import MainOrders
        MainOrders(self)

    def open_purchasing(self):
        from main import Purchasing
        Purchasing(self)

    def open_delivery_docket(self):
        from main import DeliveryDocket, screen_size
        DeliveryDocket(self, screen_size())

    def open_scheduler_chain(self):
        from main import SchedulerChain
        SchedulerChain(self)

    def open_auto_unitize(self):
        Unitize(self)

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
        """Monitor clipboard for PDF files and process them."""
        try:
            # Check if suppliers need periodic refresh
            self.check_supplier_refresh()
            
            files = self.get_clipboard_files()
            if files:
                processed_count = 0
                failed_count = 0
                failed_files = []
                
                for file_path in files:
                    try:
                        # Only process PDF files
                        if not file_path.lower().endswith('.pdf'):
                            continue
                        
                        # Extract information from the PDF
                        extracted_data = self.reader.extract_files_info(file_path)
                        if extracted_data:
                            if os.path.isfile(file_path):
                                # Copy file to destination
                                dest_path = os.path.join(CPO_PATH, os.path.basename(file_path))
                                shutil.copy(file_path, dest_path)
                                processed_count += 1
                                logger.info(f"✓ Processed: {os.path.basename(file_path)}")
                            elif os.path.isdir(file_path):
                                folder_name = os.path.basename(file_path)
                                shutil.copytree(file_path, os.path.join(CPO_PATH, folder_name))
                                processed_count += 1
                            else:
                                logger.warning(f"Unknown file type: {file_path}")
                                failed_count += 1
                        else:
                            logger.warning(f"✗ No data extracted: {os.path.basename(file_path)}")
                            failed_files.append(os.path.basename(file_path))
                            failed_count += 1
                            
                    except Exception as e:
                        logger.error(f"Error processing {file_path}: {e}")
                        failed_files.append(os.path.basename(file_path))
                        failed_count += 1
                
                # Show notification with results
                if processed_count > 0:
                    message = f"✓ Processed {processed_count} PDF(s)"
                    if failed_count > 0:
                        message += f"\n✗ Failed: {failed_count}"
                        if len(failed_files) <= 3:
                            message += f"\n({', '.join(failed_files)})"
                    
                    notification.notify(
                        title="PDF Processing Complete",
                        message=message,
                        timeout=5
                    )
                    
                    # Clear clipboard after successful processing
                    self.clear_clipboard()
                    
                elif failed_count > 0:
                    notification.notify(
                        title="PDF Processing Failed",
                        message=f"Could not process {failed_count} file(s)",
                        timeout=5
                    )
                    
        except Exception as e:
            logger.error(f"Clipboard check failed: {e}", exc_info=True)

        # Schedule next check
        self._clipboard_job = self.after(interval, self.auto_refresh_clipboard, interval)

# Alternative: Context menu for manual operations
class ToolbarWithMenu(Toolbar):
    """Extended toolbar with right-click context menu."""
    
    def __init__(self, parent):
        super().__init__(parent)
        
        # Create context menu
        self.context_menu = tk.Menu(self, tearoff=0)
        self.context_menu.add_command(label="Refresh Suppliers", command=self.refresh_suppliers)
        self.context_menu.add_command(label="Process Clipboard PDFs", command=self.manual_process_clipboard)
        self.context_menu.add_separator()
        self.context_menu.add_command(label="View Processing Log", command=self.show_processing_log)
        
        # Bind right-click to show menu
        self.bind("<Button-3>", self.show_context_menu)
    
    def show_context_menu(self, event):
        """Show context menu at mouse position."""
        try:
            self.context_menu.tk_popup(event.x_root, event.y_root)
        finally:
            self.context_menu.grab_release()
    
    def manual_process_clipboard(self):
        """Manually trigger clipboard processing."""
        self.auto_refresh_clipboard(interval=100)  # Process immediately
    
    def show_processing_log(self):
        """Show a window with recent processing logs."""
        log_window = tk.Toplevel(self)
        log_window.title("PDF Processing Log")
        log_window.geometry("600x400")
        
        # Add text widget with scrollbar
        text_frame = ttk.Frame(log_window)
        text_frame.pack(fill="both", expand=True, padx=10, pady=10)
        
        scrollbar = ttk.Scrollbar(text_frame)
        scrollbar.pack(side="right", fill="y")
        
        log_text = tk.Text(text_frame, yscrollcommand=scrollbar.set, wrap="word")
        log_text.pack(side="left", fill="both", expand=True)
        scrollbar.config(command=log_text.yview)
        
        # Read log file if it exists
        try:
            # You would need to implement a log file or keep recent logs in memory
            log_text.insert("1.0", "Processing log would appear here...\n")
            log_text.insert("end", f"Suppliers loaded: {len(self.reader.vendor_keywords)}\n")
            log_text.insert("end", f"Supplier keywords: {', '.join(self.reader.vendor_keywords)}\n")
        except Exception as e:
            log_text.insert("1.0", f"Error loading log: {e}\n")
        
        log_text.config(state="disabled")  # Make read-only