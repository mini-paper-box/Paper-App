import sqlite3
import csv
from datetime import datetime

class AddOrdersToPurchaseOrder:
    def __init__(self, db_path="prod_db.db", csv_path="po_manager.csv"):
        self.db_path = db_path
        self.csv_path = csv_path
        self.target_columns = ["orderid", "line", "ponum", "poline"]  # CSV column headers
        self.columns_name = ["order_id", "order_line"]                # DB column names

    def run(self):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("PRAGMA foreign_keys = ON;")

        with open(self.csv_path, newline='', encoding='utf-8') as csvfile:
            reader = csv.DictReader(csvfile)

            # SQL clause: UPDATE col1=?, col2=? WHERE po_number=? AND po_line=?
            set_clause = ", ".join([f"{col}=?" for col in self.columns_name])
            update_sql = f"""
                UPDATE purchase_order
                SET {set_clause}
                WHERE po_number = ? AND po_line = ?
            """
            insert_sql = f"""INSERT OR IGNORE INTO purchase_order ( order_id, order_line, po_number, po_line, requested_date
                           ) VALUES (?,?,?,?,?)"""
            
            update_count = 0
            new_record = 0
            for row in reader:
                try:
                    # Extract values in correct order
                    order_id = row.get("orderid", "").strip() or None
                    order_line = row.get("line", "").strip() or None
                    po_number = row.get("ponum", "").strip()
                    po_line = row.get("poline", "").strip()
                    supplier = row.get("supplier", "").strip()
                    po_due_date = row.get("podue", "").strip()
                    if po_due_date and len(po_due_date) >= 10:
                        requested_date = po_due_date[:10]  # Keep only 'YYYY-MM-DD'
                    else:
                        requested_date = datetime.now().isoformat()

                    if not po_number or not po_line:
                        continue  # skip invalid row

                    # Check existence in DB
                    cursor.execute(
                        "SELECT 1 FROM purchase_order WHERE po_number = ? AND po_line = ?;",
                        (po_number, po_line)
                    )

                    if cursor.fetchone():
                        values = [order_id, order_line, po_number, po_line]
                        cursor.execute(update_sql, values)
                        update_count += 1
                    else:
                        cursor.execute(
                        "SELECT 1 FROM supplier WHERE supplier_code = ?;",
                        (supplier,)
                        )
                        if cursor.fetchone():
                            values = [order_id, order_line, po_number, po_line, requested_date]
                            cursor.execute(insert_sql, values)
                            new_record += 1

                except Exception as e:
                    print(f"⚠️ Skipped row due to error: {e}")

        conn.commit()
        conn.close()
        print(f"✅ Updated {update_count} purchase_order rows successfully.")
        print(f"✅ New Record {new_record} purchase_order rows successfully.")

def main():
    updater = AddOrdersToPurchaseOrder()
    updater.run()

if __name__ == "__main__":
    main()
