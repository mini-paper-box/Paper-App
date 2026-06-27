import os
import pathlib
import shutil
from datetime import datetime
import win32com.client as win32
from settings import *
from tkinter import messagebox
from database import MakeSimpleSql

class Emaily():
    def __init__(self, master):
        self.master = master
        self.path = PO_PATH
        pass
    
    def move_files(self, vendor):
        vendor_path = os.path.join(self.path, vendor)
        pathlib.Path(vendor_path).mkdir(exist_ok=True)
        for file_name in os.listdir(self.path):
            file_path = os.path.join(self.path, file_name)
            dest_path = os.path.join(vendor_path, file_name)
            if os.path.isfile(file_path) and "pdf" in file_path.lower() and vendor.lower() in file_path.lower():
                shutil.move(file_path, dest_path)
                print(f"Moved: {file_name} -> {dest_path}")
    
    def move_delivery_docket(self, file_path, vendor):
        cwd = os.getcwd()
        filepath = file_path
        supplier_name = vendor
        vendor_path = os.path.join(cwd, "suppliers", supplier_name)
        pathlib.Path(vendor_path).mkdir(exist_ok=True)

        if filepath:
            file_name = os.path.basename(file_path)

        try:
            dest_path = os.path.join(vendor_path, file_name)
            if os.path.isfile(filepath) and "pdf" in file_path.lower() and supplier_name.lower() in dest_path.lower():
                shutil.move(filepath, dest_path)
                print(f"Moved: {file_name} -> {dest_path}")
        except Exception as e:
            pass

    def get_part_of_day(self, hour):
        if 5 <= hour <= 11:
            return "Good morning"
        elif 12 <= hour <= 17:
            return "Good afternoon"
        else:
            return "Good evening"

    def send_email(self, vendor):
        pdf_files = []
        po_numbers = []
        receiver = MakeSimpleSql().get_supplier_emails(vendor)
        for file_name in os.listdir(self.path):
            file_path = os.path.join(self.path, file_name)
            if os.path.isfile(file_path) and file_name.lower().endswith(".pdf") and vendor.lower() in file_name.lower():
                po_number = file_name[file_name.find("_")+1:file_name.find("_")+8]
                po_numbers.append(po_number)
                pdf_files.append(file_path)

        if not pdf_files:
            print("No files to attach.")
            if self.master:
                messagebox.showinfo("Email", "No matching PDF files to attach.")
            return

        greeting = self.get_part_of_day(datetime.now().hour)
        order_type = "New orders" if len(po_numbers) > 1 else "New order"
        subject = f"{order_type} - {vendor.title()} PO# {', '.join(po_numbers)}"

        body = f"""{greeting},<br><br>
        Please process attached and confirm receipt.<br><br>
        Thank you,<br>
        Sang Nguyen"""

        try:
            outlook = win32.Dispatch('Outlook.Application')
            mail = outlook.CreateItem(0)
            mail.To = receiver or "sang.n@whitebird.ca"
            mail.CC = "catherine.s@moyydesign.com;Kamaldeep.k@whitebird.ca"
            mail.Subject = subject
            mail.HTMLBody = body

            for file_path in pdf_files:
                if os.path.exists(file_path):
                    mail.Attachments.Add(Source=file_path)
                    print(f"Attached: {file_path}")
                else:
                    print(f"Missing: {file_path}")

            # mail.Display()  # Only open draft window
            mail.Send()  # Only open draft window
            print("Email draft opened in Outlook.")
            if self.master:
                pass
                # messagebox.showinfo("Email", "Email draft opened in Outlook.")

        except Exception as e:
            print(f"Failed to compose email: {e}")
            if self.master:
                messagebox.showerror("Email Error", f"Failed to open email draft:\n{e}")
