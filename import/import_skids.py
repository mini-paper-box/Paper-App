import sqlite3
import csv
from datetime import datetime

# --- CONFIG ---
db_path = "prod_db.db"
csv_path = "skids.csv"
table_name = "skids"  

# Connect
conn = sqlite3.connect(db_path)
cursor = conn.cursor()
cursor.execute("PRAGMA foreign_keys = ON;")

# --- Read CSV into memory ---
with open(csv_path, newline='', encoding='utf-8') as csvfile:
    reader = csv.DictReader(csvfile)
    columns = [col.strip().replace(" ", "_") for col in reader.fieldnames]  # clean column names
    rows = list(reader)

# --- Smart Type Detection ---
def detect_type(values, col_name):
    if any(k in col_name.lower() for k in ["date", "dte", "dt"]):
        return "TEXT"

    all_int, all_num = True, True
    for v in values:
        if v == '' or v is None:
            continue
        try:
            int(v)
        except ValueError:
            all_int = False
        try:
            float(v)
        except ValueError:
            all_num = False

    if all_int and len(values) > 0:
        return "INTEGER"
    elif all_num and len(values) > 0:
        return "REAL"
    else:
        return "TEXT"

# --- Build CREATE TABLE dynamically ---
col_defs = []
for col in columns:
    values = [row[col].strip() for row in rows if row[col].strip() != '']
    inferred_type = detect_type(values, col)
    col_defs.append(f"{col} {inferred_type}")

create_sql = f"""
CREATE TABLE IF NOT EXISTS {table_name} (
    {", ".join(col_defs)}
);
"""
cursor.execute(create_sql)

# ✅ Print inferred schema for verification
print(f"📋 Table `{table_name}` schema:")
for col_def in col_defs:
    print(f"  - {col_def}")

# --- Prepare INSERT SQL ---
placeholders = ", ".join(["?"] * len(columns))
insert_sql = f"""
INSERT OR IGNORE INTO {table_name} ({", ".join(columns)})
VALUES ({placeholders})
"""

# --- Insert Rows ---
for row in rows:
    values = []
    for col in columns:
        val = row[col].strip()
        if val == '':
            values.append(None)
        elif any(k in col.lower() for k in ["date", "dte", "dt"]):
            try:
                parsed = datetime.strptime(val, "%Y-%m-%d")
                values.append(parsed.date().isoformat())
            except Exception:
                values.append(val)
        else:
            values.append(val)
    cursor.execute(insert_sql, values)

conn.commit()
conn.close()

print(f"✅ CSV data loaded into `{table_name}` with smart schema inference.")
