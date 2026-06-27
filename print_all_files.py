import os
import subprocess

sumatra_path = r"C:\Users\sang.n\OneDrive - whitebird.ca\Paper App\SumatraPDF.exe"  # Adjust this path
root_folder = r"C:\Users\sang.n\OneDrive - whitebird.ca\Paper App\purchase order\FSC\2025"

for dirpath, _, filenames in os.walk(root_folder):
    for filename in filenames:
        if filename.lower().endswith('.pdf'):
            pdf_path = os.path.join(dirpath, filename)
            print(f"Printing: {pdf_path}")
            subprocess.run([
                sumatra_path,
                '-print-to-default',
                pdf_path
            ])