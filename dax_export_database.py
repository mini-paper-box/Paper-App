import os
import sys
import clr

adomd_dll = r"C:\Program Files\Microsoft.NET\ADOMD.NET\160\Microsoft.AnalysisServices.AdomdClient.dll"
sys.path.append(os.path.dirname(adomd_dll))

clr.AddReference("Microsoft.AnalysisServices.AdomdClient")
from pyadomd import Pyadomd

port = input("Enter your PBIX port: ").strip()

# Connect without specifying a database
conn_str = f"Provider=MSOLAP;Data Source=localhost:{port};"

try:
    with Pyadomd(conn_str) as conn:
        with conn.cursor() as cur:
            # Get all databases
            cur.execute("SELECT [CATALOG_NAME] FROM $SYSTEM.DBSCHEMA_CATALOGS")
            databases = [row[0] for row in cur.fetchall()]
            
    print("\n" + "="*70)
    print("📊 POWER BI DATABASES AND MODELS")
    print("="*70)
    
    # For each database, show its contents
    for db_name in databases:
        print(f"\n🗄️  DATABASE: {db_name}")
        print("-"*70)
        
        # Connect to this specific database
        conn_str_db = f"Provider=MSOLAP;Data Source=localhost:{port};Initial Catalog={db_name}"
        
        try:
            with Pyadomd(conn_str_db) as conn_db:
                # Query 1: Get all tables
                with conn_db.cursor() as cur_db:
                    cur_db.execute("""
                        SELECT [TABLE_NAME], [TABLE_TYPE]
                        FROM $SYSTEM.DBSCHEMA_TABLES
                    """)
                    tables = cur_db.fetchall()
                
                # Query 2: Get all measures
                with conn_db.cursor() as cur_db:
                    cur_db.execute("""
                        SELECT [MEASURE_NAME], [MEASUREGROUP_NAME]
                        FROM $SYSTEM.MDSCHEMA_MEASURES
                    """)
                    measures = cur_db.fetchall()
                
                # Query 3: Get all columns
                with conn_db.cursor() as cur_db:
                    cur_db.execute("""
                        SELECT [TABLE_NAME], [COLUMN_NAME], [DATA_TYPE]
                        FROM $SYSTEM.DBSCHEMA_COLUMNS
                    """)
                    columns = cur_db.fetchall()
                
                # Now display the results (sort in Python)
                if tables:
                    print("\n  📋 TABLES:")
                    tables_sorted = sorted(tables, key=lambda x: x[0])
                    for table_name, table_type in tables_sorted:
                        if table_type == "TABLE":
                            print(f"    • {table_name}")
                
                if measures:
                    print("\n  📊 MEASURES:")
                    measures_sorted = sorted(measures, key=lambda x: (x[1], x[0]))
                    current_group = None
                    for measure_name, group_name in measures_sorted:
                        if group_name != current_group:
                            current_group = group_name
                            print(f"    [{group_name}]")
                        print(f"      • {measure_name}")
                
                if columns:
                    print("\n  🔤 COLUMNS BY TABLE:")
                    columns_sorted = sorted(columns, key=lambda x: x[0])
                    current_table = None
                    column_count = 0
                    for table_name, column_name, data_type in columns_sorted:
                        # Skip RowNumber system tables
                        if "RowNumber" in table_name:
                            continue
                            
                        if table_name != current_table:
                            if current_table:
                                print(f"        ({column_count} columns)")
                            current_table = table_name
                            column_count = 0
                            print(f"\n    📁 {table_name}:")
                        
                        column_count += 1
                        print(f"      • {column_name} ({data_type})")
                    
                    if current_table:
                        print(f"        ({column_count} columns)")
        
        except Exception as e:
            print(f"    ⚠️  Could not access database details: {e}")
    
    print("\n" + "="*70)
    print("✅ Discovery complete!")
    print("="*70 + "\n")
    
except Exception as e:
    print(f"\n❌ Error: {e}")