import email, smtplib, ssl, os, shutil, datetime, csv, pathlib, re

from pypdf import PdfReader
from datetime import datetime
from email import encoders
from email.mime.base import MIMEBase
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

isEmailNotSuccess = True
class Emaily():
    def __init__(self, master):
        self.path = r"C:\Users\sang.n\OneDrive - whitebird.ca\POs\To Be Process"
        pass

    def move_files(self, vendor):
        pathlib.Path(f'{self.path}\\{vendor}').mkdir(exist_ok=True)
        # List all files in the folder and subdirectories
        files = [f for f in os.listdir(self.path)] 
        for file_name in files:
            file_path = os.path.join(self.path, file_name)
            dest_path = os.path.join(f"{self.path}\\{vendor}", file_name)
            if "pdf" in file_path.lower() and vendor.lower() in file_path.lower():
                shutil.move(file_path, dest_path)

    def get_part_of_day(self, h):
        return (
            "Good morning"
            if 5 <= h <= 11
            else "Good afternoon"
            if 12 <= h <= 17
            else "Good evening"
        )
        
    def send_email(self, vendor):
        #get current folder
        folder_path = r"C:\Users\sang.n\OneDrive - whitebird.ca\POs\To Be Process"
        pdf_files = []
        po = []
        # List all files in the folder and subdirectories
        files = [f for f in os.listdir(folder_path)] 
        for file_name in files:
            file_path = os.path.join(folder_path, file_name)
            if "pdf" in file_path.lower() and vendor.lower() in file_path.lower():
                po.append(file_name[file_name.find("_")+1:file_name.find("_")+8])
                pdf_files.append(file_path)
                print(file_path)  # Print or process the file path
                        
        if len(pdf_files) < 1:
            return
        #getting greeting 
        greeting = self.get_part_of_day(datetime.now().hour)
        order = "New order"
        if len(po) > 1:
            order = "New orders"
        subject = f"{order} - {vendor.title()} PO# {", ".join(po)}"
        text_body = f"""{greeting},

        Please process attached and confirm receipt
        
        
        Thank You,
        Sang Nguyen
        """
        html_body = f"""
        <html>
            <body>
                <p>{greeting},<br/><br/>
                Please process attached and confirm receipt<br/><br/>
                Thank you,<br/>
                Sang Nguyen
                </p>
            </body>
        </html>
        """
        sender_email = "homtu.sys@gmail.com"
        receiver_email = "sang.n@whitebird.ca"
        password = "zzfp ezir omhl giid"

        # Create a multipart message and set headers
        message = MIMEMultipart("alternative")
        message["From"] = sender_email
        message["To"] = receiver_email
        message["Subject"] = subject
        message["Bcc"] = receiver_email  # Recommended for mass emails

        # Add body to email
        message.attach(MIMEText(text_body, "plain"))
        message.attach(MIMEText(html_body, "html"))


        for file_path in pdf_files:
            try:
                # Check if the file exists before attaching
                if os.path.isfile(file_path):
                    with open(file_path, 'rb') as file:
                        # Create a MIMEBase object
                        part = MIMEBase('application', 'octet-stream')
                        part.set_payload(file.read())
                        encoders.encode_base64(part)  # Encode the file in base64
                        part.add_header('Content-Disposition', f'attachment; filename={os.path.basename(file_path)}')
                        #part.add_header('Content-Disposition', f'attachment; filename={file_path}')
                        message.attach(part)
                        print(f"Attached: {file_path}")
                else:
                    print(f"File not found: {file_path}")
            except Exception as e:
                print(f"Could not attach {file_path}: {e}")

            # Add attachment to message and convert message to string

        text = message.as_string()

        # Log in to server using secure context and send email
        try:
            context = ssl.create_default_context()
            with smtplib.SMTP_SSL("smtp.gmail.com", 465, context=context) as server:
                server.login(sender_email, password)
                server.sendmail(sender_email, receiver_email, text)
                isEmailNotSuccess = False
        except Exception as e:
            isEmailNotSuccess = True
            print(f"Could not send {e}")
        finally:
            if not isEmailNotSuccess:
                pass
              
if __name__ == '__main__':
    pass
        
    