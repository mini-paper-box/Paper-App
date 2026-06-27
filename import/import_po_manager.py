import sqlite3
import csv
from datetime import datetime

db_path = "prod_db.db"
csv_path = "po_manager.csv"
target_columns = ["orderid", "line","ponum", "poline"] #column name on csv file
columns_name = ["order_id", "order_line"] #column name on table

conn = sqlite3.connect(db_path)
cursor = conn.cursor()
cursor.execute("PRAGMA foreign_keys = ON;")

with open(csv_path, newline='', encoding='utf-8') as csvfile:
    reader = csv.DictReader(csvfile)

    #build sql clause
    set_clause = ", ".join([f"{col}=?" for col in columns_name])

    update_sql = f"""
    UPDATE purchase_order SET {set_clause}
    WHERE po_number = ? and po_line = ?
    """

    insert_sql = f"""INSERT OR IGNORE INTO purchase_order ( order_id, order_line, po_number, po_line
                           ) VALUES (?,?,?,?)"""

    for row in reader:
        # Prepare values
        values = []
        for col in target_columns:
            val = row.get(col, "").strip()
            if val == "":
                values.append(None)
            elif "date" in col.lower():
                try:
                    parsed = datetime.strptime(val, "%Y-%m-%d")
                    values.append(parsed.date().isoformat())
                except:
                    values.append(None)
            else:
                values.append(val)
        order_id, order_line, po_number, po_line = values
        # Check if exists
        cursor.execute("""
            SELECT 1 FROM purchase_order
            WHERE po_number = ? AND po_line =?;
        """, (po_number,po_line))
        if cursor.fetchone() is not None:
            cursor.execute(update_sql, values)
        else:
            print(values)
            cursor.execute(insert_sql, values)

conn.commit()
conn.close()
print("✅ Inserted non-duplicate rows into order_routing.")
