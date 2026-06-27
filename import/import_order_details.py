import sqlite3
import csv
from datetime import datetime

class ImportOrderDetails:
    def __init__(self, db_path="prod_db.db", csv_path="schedule_listing.csv"):
        self.db_path = db_path
        self.csv_path = csv_path
        self.target_columns = ["order_id", "order_line_nbr", 'docket_id', 'order_qty', 'requested_dte', 'active_dte', 'order_dte',
                             'order_min', 'order_max', 'docket_dsc', 'style_dsc', 'closure_dsc',
                               'ink_dsc', 'tooling_dsc']   # CSV column headers
        self.columns_name = ['order_id', 'order_line', 'docket_id', 'order_quantity', 'requested_date', 'active_date', 'order_date', 
                             'order_min', 'order_max', 'docket_description', 'style_description', 'closure_description',
                               'ink_description', 'tooling_description']    # DB column names

    def run(self):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("PRAGMA foreign_keys = ON;")

        with open(self.csv_path, newline='', encoding='utf-8') as csvfile:
            reader = csv.DictReader(csvfile)

            insert_sql = f"""
            INSERT INTO order_details ({", ".join(self.columns_name)})
            VALUES ({", ".join(["?"] * len(self.columns_name))})
            """

            for row in reader:
                values = []
                for col in self.target_columns:
                    val = row.get(col, "").strip()
                    if val == "":
                        values.append(None)
                    elif "date" in col.lower():
                        try:
                            parsed = datetime.strptime(val, "%Y-%m-%d")
                            values.append(parsed.date().isoformat())
                        except ValueError:
                            values.append(None)
                    else:
                        values.append(val)

                order_id, order_line = values[0:2]

                cursor.execute("SELECT 1 FROM order_details WHERE order_id = ? AND order_line = ?", (order_id,order_line))
                if cursor.fetchone() is None:
                    cursor.execute(insert_sql, values)

        conn.commit()
        conn.close()
        print("✅ Order details imported successfully.")

def main():
    importer = ImportOrderDetails()
    importer.run()

if __name__ == "__main__":
    main()
