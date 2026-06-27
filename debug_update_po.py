"""
Database Importer Classes
Place this file in the same directory as your main script
or adjust the import path accordingly
"""

import sqlite3
import csv
from datetime import datetime
from typing import Optional


class ImportOrder:
    """Import orders from CSV into the orders table"""
    
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
                    update_rows.append(("Active", order_id))

        # Do inserts and updates in bulk
        if new_rows:
            cursor.executemany(insert_sql, new_rows)
        if update_rows:
            cursor.executemany(update_sql, update_rows)

        conn.commit()
        conn.close()
        print(f"✅ Inserted {len(new_rows)} new orders, updated {len(update_rows)} existing ones.")


class OrderRoutingImporter:
    """Import CSV data into the order_routing table"""
    
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


class AddOrdersToPurchaseOrder:
    """Update purchase orders with order information from CSV"""
    
    def __init__(self, db_path="prod_db.db", csv_path="po_manager.csv"):
        self.db_path = db_path
        self.csv_path = csv_path
        self.target_columns = ["orderid", "line", "ponum", "poline"]  # CSV column headers
        self.columns_name = ["order_id", "order_line"]                # DB column names

    def run(self):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("PRAGMA foreign_keys = ON;")

        # Check if purchase_order table exists
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='purchase_order'")
        if not cursor.fetchone():
            print("❌ Error: 'purchase_order' table does not exist in database!")
            conn.close()
            return

        with open(self.csv_path, newline='', encoding='utf-8') as csvfile:
            reader = csv.DictReader(csvfile)

            # SQL for updating with or without po_line
            update_sql_with_line = """
                UPDATE purchase_order
                SET order_id = ?, order_line = ?
                WHERE po_number = ? AND po_line = ?
            """
            update_sql_no_line = """
                UPDATE purchase_order
                SET order_id = ?, order_line = ?
                WHERE po_number = ? AND (po_line IS NULL OR po_line = '')
            """
            
            insert_sql = """
                INSERT OR IGNORE INTO purchase_order (order_id, order_line, po_number, po_line, requested_date)
                VALUES (?,?,?,?,?)
            """
            
            update_count = 0
            new_record = 0
            skipped_count = 0
            rows_processed = 0
            
            for row in reader:
                rows_processed += 1
                try:
                    # Extract values in correct order
                    order_id = row.get("orderid", "").strip() or None
                    order_line = row.get("line", "").strip() or None
                    po_number = row.get("ponum", "").strip()
                    po_line = row.get("poline", "").strip() or None  # Allow None
                    supplier = row.get("supplier", "").strip()
                    po_due_date = row.get("podue", "").strip()
                    
                    if po_due_date and len(po_due_date) >= 10:
                        requested_date = po_due_date[:10]  # Keep only 'YYYY-MM-DD'
                    else:
                        requested_date = datetime.now().date().isoformat()

                    if not po_number:
                        skipped_count += 1
                        continue  # skip if no PO number

                    # Check existence in DB - handle NULL po_line
                    if po_line:
                        cursor.execute(
                            "SELECT 1 FROM purchase_order WHERE po_number = ? AND po_line = ?;",
                            (po_number, po_line)
                        )
                    else:
                        cursor.execute(
                            "SELECT 1 FROM purchase_order WHERE po_number = ? AND (po_line IS NULL OR po_line = '');",
                            (po_number,)
                        )

                    if cursor.fetchone():
                        # PO exists - update it
                        if po_line:
                            cursor.execute(update_sql_with_line, [order_id, order_line, po_number, po_line])
                        else:
                            cursor.execute(update_sql_no_line, [order_id, order_line, po_number])
                        
                        if cursor.rowcount > 0:
                            update_count += 1
                    else:
                        # PO doesn't exist - try to insert
                        if supplier:
                            cursor.execute(
                                "SELECT 1 FROM supplier WHERE supplier_code = ?;",
                                (supplier,)
                            )
                            if cursor.fetchone():
                                values = [order_id, order_line, po_number, po_line, requested_date]
                                cursor.execute(insert_sql, values)
                                if cursor.rowcount > 0:
                                    new_record += 1
                            else:
                                skipped_count += 1
                                if rows_processed <= 5:  # Show first few errors
                                    print(f"      ⚠️ Skipped PO {po_number}: supplier '{supplier}' not found")
                        else:
                            # No supplier provided, can't insert
                            skipped_count += 1

                except Exception as e:
                    skipped_count += 1
                    if rows_processed <= 5:  # Show first few errors
                        print(f"      ⚠️ Skipped row {rows_processed} due to error: {e}")

        conn.commit()
        conn.close()
        
        print(f"✅ Processed {rows_processed} rows: {update_count} updated, {new_record} inserted, {skipped_count} skipped.")
        
        if update_count == 0 and new_record == 0 and rows_processed > 0:
            print(f"⚠️  WARNING: No records were updated or inserted!")
            print(f"   Possible issues:")
            print(f"   • PO numbers in CSV ({rows_processed} records) don't match database PO numbers")
            print(f"   • Database has different PO numbers - check with: SELECT DISTINCT po_number FROM purchase_order LIMIT 10")
            print(f"   • For inserts: supplier codes in CSV don't exist in supplier table")


class ImportOrderDetails:
    """Import order details/line items from CSV"""
    
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

            insert_count = 0
            skip_count = 0
            
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

                cursor.execute("SELECT 1 FROM order_details WHERE order_id = ? AND order_line = ?", (order_id, order_line))
                if cursor.fetchone() is None:
                    cursor.execute(insert_sql, values)
                    insert_count += 1
                else:
                    skip_count += 1

        conn.commit()
        conn.close()
        print(f"✅ Inserted {insert_count} order details, skipped {skip_count} existing records.")


class ImportCustomer:
    """Import customer information from CSV"""
    
    def __init__(self, db_path="prod_db.db", csv_path="customers.csv"):
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

            insert_count = 0
            update_count = 0
            
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
                        except:
                            values.append(None)
                    else:
                        values.append(val)

                customer_id, short_name, legal_name, sales_rep, customer_code = values
                cursor.execute("SELECT 1 FROM customers WHERE customer_id = ?", (customer_id,))
                if cursor.fetchone() is None:
                    cursor.execute(insert_sql, values)
                    insert_count += 1
                else:
                    values.append(values.pop(0)) #move first to last
                    cursor.execute(update_sql, values)
                    update_count += 1

        conn.commit()
        conn.close()
        print(f"✅ Inserted {insert_count} new customers, updated {update_count} existing customers.")


# Test each class individually
if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1:
        test_class = sys.argv[1]
        
        if test_class == "import_order":
            importer = ImportOrder()
            importer.run()
        elif test_class == "order_routing":
            importer = OrderRoutingImporter()
            importer.run()
        elif test_class == "update_order":
            importer = AddOrdersToPurchaseOrder()
            importer.run()
        elif test_class == "order_details":
            importer = ImportOrderDetails()
            importer.run()
        elif test_class == "import_customer":
            importer = ImportCustomer()
            importer.run()
        else:
            print(f"Unknown class: {test_class}")
            print("Usage: python importers.py [import_order|order_routing|update_order|order_details|import_customer]")
    else:
        print("Usage: python importers.py [import_order|order_routing|update_order|order_details|import_customer]")