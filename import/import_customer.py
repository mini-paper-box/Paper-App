import sqlite3
import csv
from settings import *
from datetime import datetime

class ImportCustomer:
    def __init__(self, db_path="prod_db.db", csv_path=CUSTOMER_PATH):
        self.db_path = db_path
        self.csv_path = csv_path
        self.target_columns = ["customer_id", "short_name", "customer_nme","salesrep_nme", "old_cust_code"]  # from CSV
        self.columns_name = ["customer_id", "customer_name", "legal_name", "sales_rep", "customer_code"]         # DB table columns
        self.update_columns_name = ["customer_name", "legal_name", "sales_rep", "customer_code"] 

    def run(self):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("PRAGMA foreign_keys = ON;")

        with open(self.csv_path, newline='', encoding='cp1252') as csvfile:
            reader = csv.DictReader(csvfile)
            
            #build sql clause
            set_clause = ", ".join([f"{col}=?" for col in self.update_columns_name])

            update_sql = f"""
                UPDATE customers SET {set_clause}
                WHERE customer_id = ?
                """
            
            insert_sql = f"""
                INSERT INTO customers ({", ".join(self.columns_name)})
                VALUES ({", ".join(["?"] * len(self.columns_name))})
            """

            counter = 0
            for row in reader:
                print(repr(row.get("customer_id", "")))  # see exactly what's there
                values = []
                for col in self.target_columns:
                    val = row.get(col, "").strip()
                    if col in "customer_id":
                        print(val)
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

                customer_id, short_name, legal_name, sales_rep, customer_code = values
                cursor.execute("SELECT 1 FROM customers WHERE customer_id = ?", (customer_id,))
                if cursor.fetchone() is None:
                    cursor.execute(insert_sql, values)
                    counter += 1
                else:
                    values.append(values.pop(0)) #move first to last
                    cursor.execute(update_sql, values)

        conn.commit()
        conn.close()
        print(f"✅ Inserted {counter} new customer(s) into customers table.")

def main() -> None:
    importer = ImportCustomer()
    importer.run()

if __name__ == "__main__":
    main()
