import os
import sys
import pandas as pd
import subprocess
import re
import time
import json
from datetime import datetime
from pathlib import Path
from pythonnet import load

# --- 1️⃣ Load the .NET runtime ---
# Use "netfx" if you have .NET Framework-based ADOMD.NET
# Use "coreclr" if you have .NET Core-based ADOMD.NET
load("netfx")

import clr

adomd_dll = r"C:\Program Files\Microsoft.NET\ADOMD.NET\160\Microsoft.AnalysisServices.AdomdClient.dll"
sys.path.append(os.path.dirname(adomd_dll))

clr.AddReference("Microsoft.AnalysisServices.AdomdClient")
from pyadomd import Pyadomd
from Microsoft.AnalysisServices.AdomdClient import AdomdConnection, AdomdCommand

# ==============================================================================
# POST-EXPORT OPERATIONS
# ==============================================================================

def run_post_export_operations(config, exported_files):
    """
    Execute post-export Python operations using the exported CSV files
    
    Args:
        config: Configuration dictionary
        exported_files: Dictionary mapping table names to their CSV file paths
                       e.g., {'schedule_listing': 'exports/schedule_listing_20241028.csv',
                              'po_manager': 'exports/po_manager_20241028.csv'}
    """
    try:
        # Import your classes from importers.py
        # Make sure importers.py is in the same directory or adjust the path
        from importers import ImportOrder, OrderRoutingImporter, ImportOrderDetails, AddOrdersToPurchaseOrder, CustomerImporter, AddressImporter, OrderRevisionEventsImporter        
        operations = []
        db_path = config.get('post_export_operations', {}).get('db_path', 'prod_db.db')
        
        # Get the specific CSV files we need
        schedule_csv = exported_files.get('schedule_listing')
        po_manager_csv = exported_files.get('po_manager')
        customers_csv = exported_files.get('customers')
        
        print(f"\n   📁 CSV files available:")
        for table_name, file_path in exported_files.items():
            print(f"      • {table_name}: {file_path}")
        print(f"   🗄️  Database: {db_path}")
        
        # Import Order (uses schedule_listing)
        print("\n   🔄 Running: import_order")
        try:
            if schedule_csv:
                import_order = ImportOrder(db_path=db_path, csv_path=schedule_csv)
                import_order.run()
                operations.append({'name': 'import_order', 'success': True})
            else:
                print("      ⚠️  Skipped: schedule_listing.csv not found")
                operations.append({'name': 'import_order', 'success': False, 'error': 'CSV not found'})
        except Exception as e:
            print(f"      ❌ import_order failed: {e}")
            operations.append({'name': 'import_order', 'success': False, 'error': str(e)})
        
        # Import Order Routing (uses schedule_listing)
        print("\n   🔄 Running: import_order_routing")
        try:
            if schedule_csv:
                import_order_routing = OrderRoutingImporter(db_path=db_path, csv_path=schedule_csv)
                import_order_routing.run()
                operations.append({'name': 'import_order_routing', 'success': True})
            else:
                print("      ⚠️  Skipped: schedule_listing.csv not found")
                operations.append({'name': 'import_order_routing', 'success': False, 'error': 'CSV not found'})
        except Exception as e:
            print(f"      ❌ import_order_routing failed: {e}")
            operations.append({'name': 'import_order_routing', 'success': False, 'error': str(e)})
        
        # Update Order (uses po_manager)
        print("\n   🔄 Running: update_order")
        try:
            if po_manager_csv:
                update_order = AddOrdersToPurchaseOrder(db_path=db_path, csv_path=po_manager_csv)
                update_order.run()
                operations.append({'name': 'update_order', 'success': True})
            else:
                print("      ⚠️  Skipped: po_manager.csv not found")
                operations.append({'name': 'update_order', 'success': False, 'error': 'CSV not found'})
        except Exception as e:
            print(f"      ❌ update_order failed: {e}")
            operations.append({'name': 'update_order', 'success': False, 'error': str(e)})
        
        # Import Order Details (uses schedule_listing)
        print("\n   🔄 Running: import_order_details")
        try:
            if schedule_csv:
                order_details = ImportOrderDetails(db_path=db_path, csv_path=schedule_csv)
                order_details.run()
                operations.append({'name': 'import_order_details', 'success': True})
            else:
                print("      ⚠️  Skipped: schedule_listing.csv not found")
                operations.append({'name': 'import_order_details', 'success': False, 'error': 'CSV not found'})
        except Exception as e:
            print(f"      ❌ import_order_details failed: {e}")
            operations.append({'name': 'import_order_details', 'success': False, 'error': str(e)})
        
        # Import Customers (uses customers)
        print("\n   🔄 Running: import_customers")
        try:
            if customers_csv:
                customer = CustomerImporter(db_path=db_path, csv_path=customers_csv)
                customer.run()
                operations.append({'name': 'import_customers', 'success': True})
            else:
                print("      ⚠️  Skipped: schedule_listing.csv not found")
                operations.append({'name': 'import_customers', 'success': False, 'error': 'CSV not found'})
        except Exception as e:
            print(f"      ❌ import_customers failed: {e}")
            operations.append({'name': 'import_customers', 'success': False, 'error': str(e)})
        
        return operations
        
    except ImportError as e:
        print(f"\n   ❌ Could not import importer classes: {e}")
        print(f"   💡 Make sure 'importers.py' is in the same directory as this script")
        return []
    except Exception as e:
        print(f"\n   ❌ Post-export operations failed: {e}")
        return []

# ==============================================================================
# CONFIGURATION MANAGEMENT
# ==============================================================================

DEFAULT_CONFIG = {
    "database_name": "763e1b6e-3bc6-4a89-8ca8-8ce13995e41a",
    "tables": [
        "schedule_listing"
    ],
    "post_export_operations": {
        "enabled": True,
        "db_path": "prod_db.db",
        "operations": [
            "import_order",
            "import_order_routing",
            "update_order",
            "import_order_details"
        ]
    },
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
        
        # Query for active sessions with status 2 (busy/executing)
        query = """
        SELECT 
            [SESSION_ID],
            [SESSION_STATUS],
            [SESSION_COMMAND_COUNT]
        FROM $SYSTEM.DISCOVER_SESSIONS
        WHERE [SESSION_STATUS] = 2
        """
        
        cmd = AdomdCommand(query, conn)
        reader = cmd.ExecuteReader()
        
        active_sessions = 0
        while reader.Read():
            active_sessions += 1
        
        reader.Close()
        
        # Also check for active commands
        cmd_query = """
        SELECT [COMMAND_ID]
        FROM $SYSTEM.DISCOVER_COMMANDS
        WHERE [COMMAND_END_TIME] IS NULL
        """
        
        cmd2 = AdomdCommand(cmd_query, conn)
        reader2 = cmd2.ExecuteReader()
        
        active_commands = 0
        while reader2.Read():
            active_commands += 1
        
        reader2.Close()
        conn.Close()
        
        # Refresh is complete when no active sessions AND no active commands
        is_complete = (active_sessions == 0 and active_commands == 0)
        
        if not is_complete:
            print(f" [{active_sessions} sessions, {active_commands} commands]", end='', flush=True)
        
        return is_complete
        
    except Exception as e:
        # Silently fail during status checks - don't spam the output
        return True  # Assume complete if we can't check

def refresh_powerbi_tables(port, database_name, table_names):
    """Refresh multiple Power BI tables using XMLA"""
    conn_str = f"Data Source=localhost:{port};Initial Catalog={database_name}"
    
    try:
        conn = AdomdConnection(conn_str)
        conn.Open()
        
        # Build objects array for all tables
        objects = ',\n'.join([
            f'''          {{
            "database": "{database_name}",
            "table": "{table}"
          }}''' for table in table_names
        ])
        
        print(f"   Refreshing {len(table_names)} table(s): {', '.join(table_names)}")
        tmsl_command = f'''
        {{
          "refresh": {{
            "type": "full",
            "objects": [
{objects}
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
    
    # Initial delay to let refresh start
    time.sleep(2)
    
    start_time = time.time()
    dots = 0
    last_check_incomplete = False
    consecutive_complete_checks = 0
    
    while time.time() - start_time < max_wait_seconds:
        is_complete = check_refresh_status(port, database_name)
        
        if is_complete:
            consecutive_complete_checks += 1
            # Require 2 consecutive "complete" checks to be sure
            if consecutive_complete_checks >= 2:
                elapsed = time.time() - start_time
                print(f"\n   ✅ Refresh completed in {elapsed:.1f} seconds")
                # Add extra buffer time to ensure data is fully available
                print(f"   ⏳ Waiting additional 3 seconds for data availability...")
                time.sleep(3)
                return True
        else:
            consecutive_complete_checks = 0
            last_check_incomplete = True
        
        # Show progress indicator
        dots = (dots + 1) % 4
        elapsed = time.time() - start_time
        print(f"\r   ⏳ Refresh in progress ({elapsed:.0f}s){'.' * dots}   ", end='', flush=True)
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

def export_table(port, database_name, table_name, output_dir, include_timestamp=True, encoding='utf-8-sig'):
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
    print("Power BI Data Exporter with Post-Processing")
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
    if(databases):
        config['database_name'] = databases[0]
    print(f"\n✅ Using port: {port}")
    print(f"📊 Database: {config['database_name']}")
    
    # Handle refresh for main export tables
    refresh_settings = config.get('refresh_settings', {})
    if refresh_settings.get('enabled', True):
        print("\n🔄 Phase 1: Initial data refresh...")
        
        refresh_success = refresh_powerbi_tables(
            port, 
            config['database_name'], 
            config['tables']
        )
        
        if refresh_success:
            wait_for_refresh_completion(
                port, 
                config['database_name'],
                max_wait_seconds=refresh_settings.get('max_wait_seconds', 300),
                check_interval=refresh_settings.get('check_interval_seconds', 5)
            )
    else:
        print("\n⏭️  Refresh disabled in configuration")
    
    # Export main tables
    print("\n" + "=" * 70)
    print(f"📤 Phase 2: Exporting {len(config['tables'])} table(s)")
    print("=" * 70)
    
    export_settings = config.get('export_settings', {})
    export_results = []
    exported_files = {}  # Track all exported files by table name
    
    for table_name in config['tables']:
        result = export_table(
            port,
            config['database_name'],
            table_name,
            config.get('output_directory', 'exports'),
            include_timestamp=export_settings.get('include_timestamp', True),
            encoding=export_settings.get('encoding', 'utf-8-sig')
        )
        export_results.append(result)
        
        # Keep track of all successful exports
        if result['success']:
            exported_files[table_name] = result['file']
    
    # Run post-export operations
    post_export_config = config.get('post_export_operations', {})
    operation_results = []
    
    if post_export_config.get('enabled', True) and exported_files:
        print("\n" + "=" * 70)
        print(f"🔄 Phase 3: Post-Export Operations")
        print("=" * 70)
        
        operation_results = run_post_export_operations(config, exported_files)
    elif not exported_files:
        print("\n⚠️  No export files available for post-processing")
    else:
        print("\n⏭️  Post-export operations disabled in configuration")
    
    # Summary
    print("\n" + "=" * 70)
    print("📋 Summary")
    print("=" * 70)
    
    # Export summary
    print(f"\n📊 Data Export:")
    export_success = [r for r in export_results if r['success']]
    export_failed = [r for r in export_results if not r['success']]
    print(f"   ✅ Successful: {len(export_success)}/{len(export_results)}")
    print(f"   ❌ Failed: {len(export_failed)}/{len(export_results)}")
    
    if export_success:
        print(f"\n   📁 Exported files:")
        for result in export_success:
            print(f"      • {result['table']}: {result['rows']:,} rows → {result['file']}")
    
    if export_failed:
        print(f"\n   ❌ Failed exports:")
        for result in export_failed:
            print(f"      • {result['table']}: {result['error']}")
    
    # Operations summary
    if operation_results:
        print(f"\n🔄 Post-Export Operations:")
        ops_success = [r for r in operation_results if r['success']]
        ops_failed = [r for r in operation_results if not r['success']]
        print(f"   ✅ Successful: {len(ops_success)}/{len(operation_results)}")
        print(f"   ❌ Failed: {len(ops_failed)}/{len(operation_results)}")
        
        if ops_success:
            print(f"\n   ✅ Completed operations:")
            for result in ops_success:
                print(f"      • {result['name']}")
        
        if ops_failed:
            print(f"\n   ❌ Failed operations:")
            for result in ops_failed:
                print(f"      • {result['name']}: {result.get('error', 'Unknown error')}")
    
    print("\n" + "=" * 70)
    print("✅ Process completed!")
    print("=" * 70)

if __name__ == "__main__":
    main()