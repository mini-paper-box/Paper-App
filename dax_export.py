import os
import sys
import clr
import pandas as pd
import subprocess
import re
import time

adomd_dll = r"C:\Program Files\Microsoft.NET\ADOMD.NET\160\Microsoft.AnalysisServices.AdomdClient.dll"
sys.path.append(os.path.dirname(adomd_dll))

clr.AddReference("Microsoft.AnalysisServices.AdomdClient")
from pyadomd import Pyadomd

def find_powerbi_ports():
    """Find all Power BI Desktop ports using netstat"""
    try:
        result = subprocess.run(
            ['netstat', '-ano'],
            capture_output=True,
            text=True
        )
        
        ports = []
        lines = result.stdout.split('\n')
        
        for line in lines:
            if 'LISTENING' in line and '127.0.0.1:' in line:
                match = re.search(r'127\.0\.0\.1:(\d+)', line)
                if match:
                    port = match.group(1)
                    if 50000 <= int(port) <= 65000:
                        pid_match = re.search(r'\s+(\d+)\s*$', line)
                        if pid_match:
                            pid = pid_match.group(1)
                            
                            tasklist = subprocess.run(
                                ['tasklist', '/FI', f'PID eq {pid}', '/FO', 'CSV', '/NH'],
                                capture_output=True,
                                text=True
                            )
                            
                            if 'msmdsrv.exe' in tasklist.stdout:
                                ports.append(port)
        
        return list(set(ports))
    
    except Exception as e:
        print(f"⚠️  Could not auto-detect ports: {e}")
        return []

def test_connection(port):
    """Test if we can connect to a port"""
    try:
        conn_str = f"Provider=MSOLAP;Data Source=localhost:{port};"
        with Pyadomd(conn_str) as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT [CATALOG_NAME] FROM $SYSTEM.DBSCHEMA_CATALOGS")
                databases = [row[0] for row in cur.fetchall()]
                return databases
        return None
    except:
        return None

def clean_column_name(col_name):
    """Remove table prefix from column names like 'Query1[purchase_i]' -> 'purchase_i'"""
    if '[' in col_name and ']' in col_name:
        match = re.search(r'\[([^\]]+)\]', col_name)
        if match:
            return match.group(1)
    return col_name

def refresh_powerbi_table(port, database_name, table_name=None):
    """Refresh Power BI table or entire model using XMLA"""
    print("🔄 Refreshing Power BI data...")
    
    from Microsoft.AnalysisServices.AdomdClient import AdomdConnection, AdomdCommand
    
    conn_str = f"Data Source=localhost:{port};Initial Catalog={database_name}"
    
    try:
        conn = AdomdConnection(conn_str)
        conn.Open()
        
        if table_name:
            print(f"   Refreshing table: {table_name}")
            tmsl_command = f'''
            {{
              "refresh": {{
                "type": "full",
                "objects": [
                  {{
                    "database": "{database_name}",
                    "table": "{table_name}"
                  }}
                ]
              }}
            }}
            '''
        else:
            print(f"   Refreshing entire model")
            tmsl_command = f'''
            {{
              "refresh": {{
                "type": "full",
                "objects": [
                  {{
                    "database": "{database_name}"
                  }}
                ]
              }}
            }}
            '''
        
        cmd = AdomdCommand(tmsl_command, conn)
        cmd.ExecuteNonQuery()
        conn.Close()
        
        print("   ✅ Refresh initiated successfully!")
        return True
        
    except Exception as e:
        print(f"   ⚠️  Refresh failed: {e}")
        print("   Continuing with current data...")
        return False

# Auto-detect ports
print("🔍 Searching for Power BI Desktop instances...")
ports = find_powerbi_ports()

if not ports:
    print("❌ No Power BI Desktop instances found!")
    print("   Make sure Power BI Desktop is running with a file open.")
    sys.exit(1)

print(f"✅ Found {len(ports)} potential Power BI port(s): {', '.join(ports)}")

# Test each port and find databases
valid_connections = []

for port in ports:
    print(f"\n🔌 Testing port {port}...")
    databases = test_connection(port)
    if databases:
        print(f"   ✅ Connected! Found {len(databases)} database(s)")
        valid_connections.append((port, databases))
    else:
        print(f"   ❌ Could not connect")

if not valid_connections:
    print("\n❌ No valid connections found!")
    sys.exit(1)

# Use first valid connection
port, databases = valid_connections[0]
print(f"\n✅ Using port: {port}")

# Hardcoded database and query
# database_name = "763e1b6e-3bc6-4a89-8ca8-8ce13995e41a"
database_name = "763e1b6e-3bc6-4a89-8ca8-8ce13995e41a"
query_name = "schedule_listing"

# Automatic refresh - refresh just Query1 table
refresh_success = refresh_powerbi_table(port, database_name, query_name)

if refresh_success:
    # Wait for refresh to complete (10 seconds default)
    print("   ⏳ Waiting 10 seconds for refresh to complete...")
    time.sleep(10)

# Connect and export
conn_str_db = f"Provider=MSOLAP;Data Source=localhost:{port};Initial Catalog={database_name}"

print(f"\n📊 Exporting {query_name}...")

with Pyadomd(conn_str_db) as conn:
    with conn.cursor() as cur:
        dax_query = f"EVALUATE {query_name}"
        cur.execute(dax_query)
        
        # Get column names and clean them
        columns = [col[0] for col in cur.description]
        cleaned_columns = [clean_column_name(col) for col in columns]
        
        rows = cur.fetchall()

# Create DataFrame with cleaned column names
df = pd.DataFrame(rows, columns=cleaned_columns)

# Create filename with timestamp
from datetime import datetime
timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
output_file = f"schedule_listing.csv"

df.to_csv(output_file, index=False, encoding='utf-8-sig')

print(f"\n✅ Export completed!")
print(f"   Port: {port}")
print(f"   Database: {database_name}")
print(f"   Query: {query_name}")
print(f"   Rows: {len(df):,}")
print(f"   Columns: {len(df.columns)}")
print(f"   File: {output_file}")
print(f"\n📋 Columns exported:")
for col in cleaned_columns:
    print(f"   • {col}")