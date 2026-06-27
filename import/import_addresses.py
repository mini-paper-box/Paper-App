import sqlite3
import csv
from datetime import datetime

# Paths
db_path = "prod_db.db"
csv_path = "customers.csv"

# Connect
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

# Optional: Enforce foreign key constraints
cursor.execute("PRAGMA foreign_keys = OFF;")

# Clear table
# cursor.execute("DELETE FROM order_routing")
# conn.commit()

# Read & Insert
with open(csv_path, newline='', encoding='utf-8') as csvfile:
    reader = csv.DictReader(csvfile)
    columns = reader.fieldnames

    placeholders = ", ".join(["?"] * len(columns))
    insert_sql = f"""
    INSERT OR IGNORE INTO customers ({", ".join(columns)})
    VALUES ({placeholders})
    """

    for row in reader:
        values = []
        for col in columns:
            val = row[col].strip()
            if val == '':
                values.append(None)
            elif "date" in col.lower():  # attempt to parse date fields
                try:
                    parsed = datetime.strptime(val, "%Y-%m-%d")
                    values.append(parsed.date().isoformat())
                except Exception:
                    values.append(None)
            else:
                values.append(val)
        cursor.execute(insert_sql, values)

conn.commit()
conn.close()
print("✅ CSV data loaded into addresses successfully.")
