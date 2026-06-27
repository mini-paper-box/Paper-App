import sqlite3
import csv
from datetime import datetime
from typing import Optional

class OrderRoutingImporter:
    """
    Class to import CSV data into the 'order_routing' table.
    Includes:
    - Auto column detection from CSV headers
    - Optional date parsing
    - Bulk insert with executemany()
    - Transaction rollback on failure
    - Row counting before clearing table
    """

    def __init__(self, db_path: str = "prod_db.db", csv_path: str = "schedule_listing.csv"):
        self.db_path = db_path
        self.csv_path = csv_path

    def _parse_date(self, value: str) -> Optional[str]:
        """Try to parse date using multiple common formats."""
        for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%d-%m-%Y"):
            try:
                return datetime.strptime(value, fmt).date().isoformat()
            except ValueError:
                continue
        return None

    def run(self, dry_run: bool = False):
        """Import CSV data into order_routing table."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("PRAGMA foreign_keys = ON;")

        # Count existing rows
        cursor.execute("SELECT COUNT(*) FROM order_routing")
        existing_count = cursor.fetchone()[0]
        print(f"⚠️ Found {existing_count} existing rows in 'order_routing' table.")

        if dry_run:
            print("🔎 Dry run: No changes will be made.")
            conn.close()
            return

        # Clear table
        print("🗑️ Deleting existing rows...")
        cursor.execute("DELETE FROM order_routing")
        conn.commit()

        # Read CSV & prepare rows
        with open(self.csv_path, newline='', encoding='utf-8') as csvfile:
            reader = csv.DictReader(csvfile)
            columns = reader.fieldnames
            if not columns:
                print("❌ CSV file has no headers. Aborting.")
                conn.close()
                return

            placeholders = ", ".join(["?"] * len(columns))
            insert_sql = f"INSERT INTO order_routing ({', '.join(columns)}) VALUES ({placeholders})"

            rows_to_insert = []
            for i, row in enumerate(reader, start=1):
                values = []
                for col in columns:
                    val = row[col].strip()
                    if val == '':
                        values.append(None)
                    elif "date" in col.lower():
                        values.append(self._parse_date(val))
                    else:
                        values.append(val)
                rows_to_insert.append(values)

        # Bulk insert inside transaction
        try:
            cursor.executemany(insert_sql, rows_to_insert)
            conn.commit()
            print(f"✅ Successfully inserted {len(rows_to_insert)} rows into order_routing.")
        except sqlite3.IntegrityError as e:
            conn.rollback()
            print(f"❌ Import failed due to UNIQUE/constraint error: {e}")
        except Exception as e:
            conn.rollback()
            print(f"❌ Unexpected error: {e}")
        finally:
            conn.close()


# Usage Example:
if __name__ == "__main__":
    importer = OrderRoutingImporter(db_path="prod_db.db", csv_path="schedule_listing.csv")
    importer.run(dry_run=False)  # Set dry_run=True to preview without changing DB
