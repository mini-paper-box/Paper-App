import os
import sys
import clr
import pandas as pd
import subprocess
import re
import time
import json
from datetime import datetime
from pathlib import Path

adomd_dll = r"C:\Program Files\Microsoft.NET\ADOMD.NET\160\Microsoft.AnalysisServices.AdomdClient.dll"
sys.path.append(os.path.dirname(adomd_dll))

clr.AddReference("Microsoft.AnalysisServices.AdomdClient")
from pyadomd import Pyadomd
from Microsoft.AnalysisServices.AdomdClient import AdomdConnection, AdomdCommand

# ==============================================================================
# CONFIGURATION MANAGEMENT
# ==============================================================================

DEFAULT_CONFIG = {
    "database_name": "763e1b6e-3bc6-4a89-8ca8-8ce13995e41a",
    "tables": [
        "schedule_listing"
    ],
    "output_directory": "exports",
    "refresh_settings": {
        "enabled": True,
        "refresh_entire_model": False,
        "max_wait_seconds": 300,
        "check_interval_seconds": 5
    },
    "export_settings": {
        "include_timestamp": True,
        "encoding": "utf-8-sig"
    }
}

def load_config(config_path="powerbi_export_config.json"):
    """Load configuration from JSON file, create default if not exists"""
    if not os.path.exists(config_path):
        print(f"⚙️  Config file not found. Creating default: {config_path}")
        with open(config_path, 'w') as f:
            json.dump(DEFAULT_CONFIG, f, indent=2)
        print(f"   ✅ Default config created. Please review and update as needed.")
        return DEFAULT_CONFIG
    
    try:
        with open(config_path, 'r') as f:
            config = json.load(f)
        print(f"✅ Loaded config from: {config_path}")
        return config
    except Exception as e:
        print(f"⚠️  Error loading config: {e}")
        print(f"   Using default configuration")
        return DEFAULT_CONFIG

# ==============================================================================
# PORT DISCOVERY & CONNECTION
# ==============================================================================

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

# ==============================================================================
# REFRESH OPERATIONS
# ==============================================================================

def check_refresh_status(port, database_name):
    """Check if any refresh operations are in progress"""
    try:
        conn_str = f"Data Source=localhost:{port};Initial Catalog={database_name}"
        conn = AdomdConnection(conn_str)
        conn.Open()
        
        # Query for active refresh operations
        query = """
        SELECT 
            [SESSION_ID],
            [SESSION_STATUS],
            [SESSION_ELAPSED_TIME_MS]
        FROM $SYSTEM.DISCOVER_SESSIONS
        WHERE [SESSION_STATUS] = 2
        """
        
        cmd = AdomdCommand(query, conn)
        reader = cmd.ExecuteReader()
        
        active_sessions = 0
        while reader.Read():
            active_sessions += 1
        
        reader.Close()
        conn.Close()
        
        return active_sessions == 0  # True if no active sessions (refresh complete)
        
    except Exception as e:
        print(f"   ⚠️  Could not check refresh status: {e}")
        return True  # Assume complete if we can't check

def refresh_powerbi_table(port, database_name, table_name=None):
    """Refresh Power BI table or entire model using XMLA"""
    print("🔄 Initiating data refresh...")
    
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
        
        print("   ✅ Refresh command sent successfully!")
        return True
        
    except Exception as e:
        print(f"   ⚠️  Refresh failed: {e}")
        print("   Continuing with current data...")
        return False

def wait_for_refresh_completion(port, database_name, max_wait_seconds=300, check_interval=5):
    """Poll refresh status until complete or timeout"""
    print(f"   ⏳ Waiting for refresh to complete (max {max_wait_seconds}s)...")
    
    start_time = time.time()
    dots = 0
    
    while time.time() - start_time < max_wait_seconds:
        if check_refresh_status(port, database_name):
            elapsed = time.time() - start_time
            print(f"\n   ✅ Refresh completed in {elapsed:.1f} seconds")
            return True
        
        # Show progress indicator
        dots = (dots + 1) % 4
        print(f"\r   ⏳ Checking refresh status{'.' * dots}   ", end='', flush=True)
        time.sleep(check_interval)
    
    print(f"\n   ⚠️  Refresh timeout after {max_wait_seconds}s. Proceeding anyway...")
    return False

# ==============================================================================
# DATA EXPORT
# ==============================================================================

def clean_column_name(col_name):
    """Remove table prefix from column names like 'Query1[purchase_i]' -> 'purchase_i'"""
    if '[' in col_name and ']' in col_name:
        match = re.search(r'\[([^\]]+)\]', col_name)
        if match:
            return match.group(1)
    return col_name

def export_table(port, database_name, table_name, output_dir, include_timestamp=False, encoding='utf-8-sig'):
    """Export a single table to CSV"""
    print(f"\n📊 Exporting table: {table_name}")
    
    conn_str = f"Provider=MSOLAP;Data Source=localhost:{port};Initial Catalog={database_name}"
    
    try:
        with Pyadomd(conn_str) as conn:
            with conn.cursor() as cur:
                dax_query = f"EVALUATE {table_name}"
                cur.execute(dax_query)
                
                # Get column names and clean them
                columns = [col[0] for col in cur.description]
                cleaned_columns = [clean_column_name(col) for col in columns]
                
                rows = cur.fetchall()
        
        # Create DataFrame with cleaned column names
        df = pd.DataFrame(rows, columns=cleaned_columns)
        
        # Create output directory if it doesn't exist
        Path(output_dir).mkdir(parents=True, exist_ok=True)
        
        # Generate filename
        if include_timestamp:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_file = os.path.join(output_dir, f"{table_name}_{timestamp}.csv")
        else:
            output_file = os.path.join(output_dir, f"{table_name}.csv")
        
        # Export to CSV
        df.to_csv(output_file, index=False, encoding=encoding)
        
        print(f"   ✅ Exported {len(df):,} rows × {len(df.columns)} columns")
        print(f"   📁 File: {output_file}")
        
        return {
            'success': True,
            'table': table_name,
            'rows': len(df),
            'columns': len(df.columns),
            'file': output_file
        }
        
    except Exception as e:
        print(f"   ❌ Export failed: {e}")
        return {
            'success': False,
            'table': table_name,
            'error': str(e)
        }

# ==============================================================================
# MAIN EXECUTION
# ==============================================================================

def main():
    print("=" * 70)
    print("Power BI Data Exporter")
    print("=" * 70)
    
    # Load configuration
    config = load_config()
    
    # Auto-detect ports
    print("\n🔍 Searching for Power BI Desktop instances...")
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
    print(f"📊 Database: {config['database_name']}")
    
    # Handle refresh
    refresh_settings = config.get('refresh_settings', {})
    if refresh_settings.get('enabled', True):
        if refresh_settings.get('refresh_entire_model', False):
            refresh_success = refresh_powerbi_table(port, config['database_name'])
        else:
            # Refresh only the tables we're exporting
            for table_name in config['tables']:
                refresh_success = refresh_powerbi_table(port, config['database_name'], table_name)
                if not refresh_success:
                    break
        
        if refresh_success:
            wait_for_refresh_completion(
                port, 
                config['database_name'],
                max_wait_seconds=refresh_settings.get('max_wait_seconds', 300),
                check_interval=refresh_settings.get('check_interval_seconds', 5)
            )
    else:
        print("\n⏭️  Refresh disabled in configuration")
    
    # Export all tables
    print("\n" + "=" * 70)
    print(f"📤 Exporting {len(config['tables'])} table(s)")
    print("=" * 70)
    
    export_settings = config.get('export_settings', {})
    results = []
    
    for table_name in config['tables']:
        result = export_table(
            port,
            config['database_name'],
            table_name,
            config.get('output_directory', 'exports'),
            include_timestamp=export_settings.get('include_timestamp', True),
            encoding=export_settings.get('encoding', 'utf-8-sig')
        )
        results.append(result)
    
    # Summary
    print("\n" + "=" * 70)
    print("📋 Export Summary")
    print("=" * 70)
    
    successful = [r for r in results if r['success']]
    failed = [r for r in results if not r['success']]
    
    print(f"✅ Successful: {len(successful)}/{len(results)}")
    print(f"❌ Failed: {len(failed)}/{len(results)}")
    
    if successful:
        print(f"\n📁 Exported files:")
        for result in successful:
            print(f"   • {result['table']}: {result['rows']:,} rows → {result['file']}")
    
    if failed:
        print(f"\n❌ Failed exports:")
        for result in failed:
            print(f"   • {result['table']}: {result['error']}")

if __name__ == "__main__":
    main()