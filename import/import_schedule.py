import sqlite3
import csv
from datetime import datetime

# Paths
db_path = "prod_db.db"
csv_path = "schedule_listing.csv"

def parse_date(value):
    """Try to parse date from multiple formats."""
    for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%d-%m-%Y"):
        try:
            return datetime.strptime(value, fmt).date().isoformat()
        except ValueError:
            continue
    return None

# Connect to DB
conn = sqlite3.connect(db_path)
cursor = conn.cursor()
cursor.execute("PRAGMA foreign_keys = ON;")

# Count existing rows before clearing
cursor.execute("SELECT COUNT(*) FROM order_routing")
existing_count = cursor.fetchone()[0]
print(f"⚠️  Deleting {existing_count} existing rows from order_routing...")
cursor.execute("DELETE FROM order_routing")
conn.commit()

# Read CSV
with open(csv_path, newline='', encoding='utf-8') as csvfile:
    reader = csv.DictReader(csvfile)
    columns = reader.fieldnames
    placeholders = ", ".join(["?"] * len(columns))
    insert_sql = f"INSERT INTO order_routing ({', '.join(columns)}) VALUES ({placeholders})"

    rows_to_insert = []
    bad_rows = []

    for i, row in enumerate(reader, start=1):
        values = []
        for col in columns:
            val = row[col].strip()
            if val == '':
                values.append(None)
            elif "date" in col.lower():
                values.append(parse_date(val))
            else:
                values.append(val)
        rows_to_insert.append(values)

    try:
        cursor.executemany(insert_sql, rows_to_insert)
        conn.commit()
        print(f"✅ Successfully inserted {len(rows_to_insert)} rows into order_routing.")
    except sqlite3.IntegrityError as e:
        conn.rollback()
        print(f"❌ Import failed due to constraint error: {e}")
    except Exception as e:
        conn.rollback()
        print(f"❌ Unexpected error: {e}")
    finally:
        conn.close()
