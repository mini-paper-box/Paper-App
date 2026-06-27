import sqlite3
import csv
from datetime import datetime

class ImportOrder:
    def __init__(self, db_path="prod_db.db", csv_path="schedule_listing.csv", close_existing=True):
        self.db_path = db_path
        self.csv_path = csv_path
        self.target_columns = ["order_id", "customer_id"]  # CSV headers
        self.columns_name = ["order_id", "customer_id"]    # DB columns
        self.close_existing = close_existing

    def parse_date(self, value):
        """Try to parse date from multiple formats."""
        for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%d-%m-%Y"):
            try:
                return datetime.strptime(value, fmt).date().isoformat()
            except ValueError:
                continue
        return None

    def run(self):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("PRAGMA foreign_keys = ON;")

        insert_sql = f"""
        INSERT OR IGNORE INTO orders ({", ".join(self.columns_name)})
        VALUES ({", ".join(["?"] * len(self.columns_name))})
        """
        update_sql = """
        UPDATE orders
        SET status = ?
        WHERE order_id = ?
        """

        new_rows = []
        update_rows = []

        with open(self.csv_path, newline='', encoding='utf-8') as csvfile:
            reader = csv.DictReader(csvfile)
            for row in reader:
                values = []
                for col in self.target_columns:
                    val = row.get(col, "").strip()
                    if not val:
                        values.append(None)
                    elif "date" in col.lower():
                        values.append(self.parse_date(val))
                    else:
                        values.append(val)

                order_id, customer_id = values

                cursor.execute("SELECT 1 FROM orders WHERE order_id = ?", (order_id,))
                if cursor.fetchone() is None:
                    new_rows.append(values)
                elif self.close_existing:
                    update_rows.append(( "Active", order_id ))

        # Do inserts and updates in bulk
        if new_rows:
            cursor.executemany(insert_sql, new_rows)
        if update_rows:
            cursor.executemany(update_sql, update_rows)

        conn.commit()
        conn.close()
        print(f"✅ Inserted {len(new_rows)} new orders, updated {len(update_rows)} existing ones.")

def main():
    importer = ImportOrder()
    importer.run()

if __name__ == "__main__":
    main()
