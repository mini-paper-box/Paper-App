import clr
import sys
import os
import subprocess
import re
from datetime import datetime

print("=" * 70)
print("Power BI Desktop Model Inspector")
print("=" * 70)

# ----------------------------
# Step 1: Load ADOMD.NET Library
# ----------------------------
print("\n[Step 1] Loading ADOMD.NET library...")

adomd_dll = r"C:\Program Files\Microsoft.NET\ADOMD.NET\160\Microsoft.AnalysisServices.AdomdClient.dll"

if not os.path.exists(adomd_dll):
    print("❌ ERROR: ADOMD.NET library not found!")
    print(f"   Expected location: {adomd_dll}")
    print("   Download from: https://aka.ms/downloadadomd")
    sys.exit(1)

sys.path.append(os.path.dirname(adomd_dll))
clr.AddReference(adomd_dll)

from Microsoft.AnalysisServices.AdomdClient import AdomdConnection, AdomdCommand

print("✅ Library loaded successfully")

# ----------------------------
# Step 2: Detect Power BI Desktop Instance
# ----------------------------
print("\n[Step 2] Searching for Power BI Desktop...")

def find_powerbi_port():
    result = subprocess.run(['netstat', '-ano'], capture_output=True, text=True)
    for line in result.stdout.splitlines():
        if "LISTENING" in line and "127.0.0.1:" in line:
            match = re.search(r'127\.0\.0\.1:(\d+)', line)
            if match:
                port = match.group(1)
                pid_match = re.search(r'\s+(\d+)$', line)
                if pid_match:
                    pid = pid_match.group(1)
                    tasklist = subprocess.run(
                        ['tasklist', '/FI', f'PID eq {pid}', '/FO', 'CSV', '/NH'],
                        capture_output=True, text=True
                    )
                    if 'msmdsrv.exe' in tasklist.stdout:
                        return port
    return None

port = find_powerbi_port()

if not port:
    print("❌ ERROR: Power BI Desktop not found!")
    print("   Make sure a PBIX file is open in Power BI Desktop.")
    sys.exit(1)

print(f"✅ Found Power BI Desktop on port: {port}")

# ----------------------------
# Step 3: Connect to Analysis Services
# ----------------------------
print("\n[Step 3] Connecting to Power BI Analysis Services...")

conn_str = f"Provider=MSOLAP;Data Source=localhost:{port};"
connection = AdomdConnection(conn_str)

try:
    connection.Open()
    print("✅ Successfully connected!")
except Exception as e:
    print(f"❌ ERROR: Could not connect - {e}")
    sys.exit(1)

# ----------------------------
# Helper: Execute Query
# ----------------------------
def execute_query(connection, query):
    try:
        cmd = AdomdCommand(query, connection)
        reader = cmd.ExecuteReader()
        results = []
        while reader.Read():
            row = {}
            for i in range(reader.FieldCount):
                name = reader.GetName(i)
                try:
                    row[name] = reader.GetValue(i)
                except:
                    row[name] = None
            results.append(row)
        reader.Close()
        return results
    except Exception as e:
        print(f"⚠️ Query failed: {e}")
        return []

# ----------------------------
# Step 4: Detect Active Model
# ----------------------------
print("\n[Step 4] Detecting active Power BI model...")

catalog_query = "SELECT [CATALOG_NAME] FROM $SYSTEM.DBSCHEMA_CATALOGS"
catalogs = execute_query(connection, catalog_query)

model_query = "SELECT [Name] FROM $SYSTEM.TMSCHEMA_MODEL"
models = execute_query(connection, model_query)

if not catalogs:
    print("❌ No model found — open a PBIX file first.")
    sys.exit(1)

catalog_name = catalogs[0]['CATALOG_NAME']
model_name = models[0]['Name'] if models else catalog_name

print(f"✅ Model detected:")
print(f"   • Internal ID: {catalog_name}")
print(f"   • Friendly name: {model_name}")

try:
    connection.ChangeDatabase(catalog_name)
    print(f"✅ Switched to model context '{model_name}'")
except Exception as e:
    print(f"⚠️ Could not switch catalog context: {e}")

# ----------------------------
# Step 5: Inspect Model Metadata
# ----------------------------
print(f"\n[Step 5] Inspecting model '{model_name}'...")

# Tables
tables = execute_query(connection, """
SELECT [Name], [Description]
FROM $SYSTEM.TMSCHEMA_TABLES
WHERE [Type] = 'Table'
ORDER BY [Name]
""")

# Measures
measures = execute_query(connection, """
SELECT [Name], [TableName], [Description]
FROM $SYSTEM.TMSCHEMA_MEASURES
ORDER BY [TableName], [Name]
""")

# Columns
columns = execute_query(connection, """
SELECT [TableName], [Name], [DataType]
FROM $SYSTEM.TMSCHEMA_COLUMNS
ORDER BY [TableName], [Name]
""")

# Relationships
relationships = execute_query(connection, """
SELECT [Name], [FromTableName], [FromColumnName],
       [ToTableName], [ToColumnName]
FROM $SYSTEM.TMSCHEMA_RELATIONSHIPS
""")

# ----------------------------
# Step 6: Display Summary
# ----------------------------
print("\n" + "=" * 70)
print(f"Model Summary – {model_name}")
print("=" * 70)
print(f"📊 Tables: {len(tables)}")
print(f"📐 Measures: {len(measures)}")
print(f"📋 Columns: {len(columns)}")
print(f"🔗 Relationships: {len(relationships)}")

# Display table names
if tables:
    print("\nTables:")
    for i, t in enumerate(tables, 1):
        desc = f" - {t['Description']}" if t.get('Description') else ""
        print(f"  {i:2}. {t['Name']}{desc}")

# Display relationships
if relationships:
    print("\nRelationships:")
    for i, r in enumerate(relationships, 1):
        print(f"  {i:2}. {r['FromTableName']}[{r['FromColumnName']}] → {r['ToTableName']}[{r['ToColumnName']}]")

connection.Close()
print("\n✅ Connection closed successfully.")
print("=" * 70)
