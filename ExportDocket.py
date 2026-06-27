import urllib.request
import zipfile
import os
import glob
import clr
import System
import pandas as pd

pkg_name = "Microsoft.AnalysisServices.AdomdClient.retail.amd64"
pkg_version = "19.64.0"
nupkg_url = f"https://www.nuget.org/api/v2/package/{pkg_name}/{pkg_version}"
pkg_file = f"{pkg_name}.{pkg_version}.nupkg"
extract_dir = "adomd"

# Step 1: Download + extract if DLL not already present
if not os.path.exists("AdomdClient.dll"):
    print("📦 Downloading ADOMD client...")
    urllib.request.urlretrieve(nupkg_url, pkg_file)

    # Extract the nupkg (zip)
    with zipfile.ZipFile(pkg_file, "r") as zip_ref:
        zip_ref.extractall(extract_dir)

    # Step 2: Find DLL anywhere under extracted folder
    dll_candidates = glob.glob(os.path.join(extract_dir, "**", "Microsoft.AnalysisServices.AdomdClient.dll"), recursive=True)
    if not dll_candidates:
        raise FileNotFoundError("❌ Could not find ADOMD Client DLL in NuGet package.")
    
    dll_path = dll_candidates[0]  # pick first found
    print(f"✅ Found DLL: {dll_path}")

    # Copy to working dir for easier loading
    os.rename(dll_path, "AdomdClient.dll")

# Step 3: Load the DLL
clr.AddReference("AdomdClient.dll")
from Microsoft.AnalysisServices.AdomdClient import AdomdConnection, AdomdCommand, AdomdDataAdapter

# Step 4: Connect to Power BI (replace with detected port)
port = "59667"  # TODO: auto-detect like in PowerShell
cn = AdomdConnection(f"Data Source=localhost:{port}")
cn.Open()

# Step 5: Run DAX query
cmd = cn.CreateCommand()
cmd.CommandText = """
EVALUATE
SELECTCOLUMNS (
    'docket',
    "OrderID", 'docket'[order_id],
    "ShipDate", 'docket'[ship_date],
    "Status", 'docket'[status]
)
"""

da = AdomdDataAdapter(cmd)
dt = System.Data.DataTable()
da.Fill(dt)

# Step 6: Export to CSV
df = pd.DataFrame([list(r) for r in dt.Rows], columns=[c.ColumnName for c in dt.Columns])
df.to_csv("docket_export.csv", index=False, encoding="utf-8")

print("✅ Export complete: docket_export.csv")

cn.Close()
