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
    
    def __init__(self, db_path="prod_db.db", csv_path="exports/schedule_listing.csv", close_existing=True):
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
    
    def __init__(self, db_path: str = "prod_db.db", csv_path: str = "exports/schedule_listing.csv"):
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
            insert_sql = f"INSERT OR IGNORE INTO order_routing ({', '.join(columns)}) VALUES ({placeholders})"

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

class CustomerImporter:
    """Import CSV data into the order_routing table"""
    
    def __init__(self, db_path: str = "prod_db.db", csv_path: str = "exports/customers.csv"):
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
        """Import CSV data into customers table."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("PRAGMA foreign_keys = ON;")
 
        if dry_run:
            print("🔎 Dry run: No changes will be made.")
            conn.close()
            return

        # Read CSV & prepare rows
        with open(self.csv_path, newline='', encoding='utf-8') as csvfile:
            reader = csv.DictReader(csvfile)
            columns = reader.fieldnames
            if not columns:
                print("❌ CSV file has no headers. Aborting.")
                conn.close()
                return

            placeholders = ", ".join(["?"] * len(columns))
            insert_sql = f"INSERT OR IGNORE INTO customers ({', '.join(columns)}) VALUES ({placeholders})"

            rows_to_insert = []
            for i, row in enumerate(reader, start=1):
                values = []
                for col in columns:
                    val = row[col].strip()
                    if val == '':
                        values.append(None)
                    else:
                        values.append(val)
                rows_to_insert.append(values)

        # Bulk insert inside transaction
        try:
            cursor.executemany(insert_sql, rows_to_insert)
            conn.commit()
            print(f"✅ Successfully inserted {len(rows_to_insert)} rows into customers.")
        except sqlite3.IntegrityError as e:
            conn.rollback()
            print(f"❌ Import failed due to UNIQUE/constraint error: {e}")
        except Exception as e:
            conn.rollback()
            print(f"❌ Unexpected error: {e}")
        finally:
            conn.close()

class DocketImporter:
    def __init__(self, db_path: str = "prod_db.db", csv_path: str = "exports/docket.csv"):
        self.db_path = db_path
        self.csv_path = csv_path

    def run(self, dry_run: bool = False):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("PRAGMA foreign_keys = ON;")

        if dry_run:
            print("🔎 Dry run: No changes will be made.")
            conn.close()
            return

        # Read CSV & format rows
        with open(self.csv_path, newline='', encoding='utf-8') as csvfile:
            reader = csv.DictReader(csvfile)
            columns = reader.fieldnames

            if not columns:
                print("⚠️ CSV is empty or missing headers.")
                conn.close()
                return

            # Build UPSERT Statement
            pk = "docket_id"   

            placeholders = ", ".join("?" for _ in columns)
            col_list = ", ".join(columns)

            # Build update list: col = excluded.col
            update_list = ", ".join(
                f"{col} = excluded.{col}"
                for col in columns
                if col != pk
            )

            insert_sql = f"""
                INSERT INTO docket ({col_list})
                VALUES ({placeholders})
                ON CONFLICT({pk}) DO UPDATE SET
                {update_list};
            """

            rows = []
            for row in reader:
                formatted = []
                for col in columns:
                    val = row[col].strip()
                    formatted.append(None if val == "" else val)
                rows.append(formatted)

        # Execute UPSERT
        try:
            cursor.executemany(insert_sql, rows)
            conn.commit()
            print(f"✅ Inserted/Updated {cursor.rowcount} rows into docket.")
        except Exception as e:
            conn.rollback()
            print("❌ Error during import:", e)
        finally:
            conn.close()


class AddressImporter:
    """Import CSV data into the addresses table"""
    
    def __init__(self, db_path: str = "prod_db.db", csv_path: str = "exports/addresses.csv"):
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
        """Import CSV data into addresses table."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("PRAGMA foreign_keys = ON;")
 
        if dry_run:
            print("🔎 Dry run: No changes will be made.")
            conn.close()
            return

        # Read CSV & prepare rows
        with open(self.csv_path, newline='', encoding='utf-8') as csvfile:
            reader = csv.DictReader(csvfile)
            columns = reader.fieldnames
            if not columns:
                print("❌ CSV file has no headers. Aborting.")
                conn.close()
                return

            placeholders = ", ".join(["?"] * len(columns))
            insert_sql = f"INSERT OR IGNORE INTO addresses ({', '.join(columns)}) SELECT {placeholders} WHERE EXISTS (SELECT 1 FROM customers WHERE customer_id = ?)"

            rows_to_insert = []
            for i, row in enumerate(reader, start=1):
                values = []
                customer_id = 0
                for col in columns:
                    val = row[col].strip()
                    if col == 'customer_id':
                        try:
                            val = int(val)
                            if val > 1000000000:
                                val -= 1000000000
                            customer_id = val
                        except ValueError:
                            print(val)
                            val = None
                    if val == '':
                        values.append(None)
                    else:
                        values.append(val)

                rows_to_insert.append(values + [customer_id])


        # Bulk insert inside transaction
        try:
            cursor.executemany(insert_sql, rows_to_insert)
            conn.commit()
            print(f"✅ Successfully inserted {len(rows_to_insert)} rows into addresses.")
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
    
    def __init__(self, db_path="prod_db.db", csv_path="exports/po_manager.csv"):
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
        print(f"✅ Updated {update_count} purchase orders, inserted {new_record} new records.")


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
    
    def __init__(self, db_path="prod_db.db", csv_path="exports/customers.csv"):
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


class OrderRevisionEventsImporter:
    """Import CSV into order_revision_events, creating table dynamically from CSV header."""

    def __init__(self, db_path="prod_db.db", csv_path="exports/order_revision_events.csv"):
        self.db_path = db_path
        self.csv_path = csv_path

    # ----------------------------
    #   DATE PARSING
    # ----------------------------
    def _parse_date(self, value: str) -> Optional[str]:
        if not value:
            return None
        for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%d-%m-%Y", "%Y/%m/%d"):
            try:
                return datetime.strptime(value, fmt).date().isoformat()
            except ValueError:
                continue
        return value  # leave unchanged if unknown format

    # ----------------------------
    #   NUMERIC TYPE DETECTION
    # ----------------------------
    def _is_integer(self, value: str) -> bool:
        try:
            int(value)
            return True
        except:
            return False

    def _is_float(self, value: str) -> bool:
        try:
            float(value)
            return True
        except:
            return False

    def _detect_column_types(self, rows, columns):
        types = {col: "TEXT" for col in columns}

        for col in columns:
            vals = [row[col] for row in rows if row[col] not in ("", None)]

            is_all_int = all(self._is_integer(v) for v in vals)
            is_all_float = all(self._is_float(v) for v in vals)

            if is_all_int:
                types[col] = "INTEGER"
            elif is_all_float:
                types[col] = "REAL"
            else:
                types[col] = "TEXT"

        return types

    # ----------------------------
    #   CREATE TABLE
    # ----------------------------
    def _ensure_table(self, cursor, columns, col_types):
        col_defs = ", ".join([f'"{c}" {col_types[c]}' for c in columns])

        # Required keys
        keys = ["order_revision_id", "order_id", "order_line_nbr"]
        has_keys = all(k in columns for k in keys)

        unique_clause = ""
        if has_keys:
            unique_clause = (
                ", UNIQUE(order_revision_id, order_id, order_line_nbr) "
                "ON CONFLICT REPLACE"
            )
            print("✔ UNIQUE(order_revision_id, order_id, order_line_nbr) — REPLACE")
        else:
            print("⚠ UNIQUE constraint skipped — missing key column(s).")

        cursor.execute(f"""
            CREATE TABLE IF NOT EXISTS order_revision_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                {col_defs}
                {unique_clause}
            );
        """)

    # ----------------------------
    #   CREATE INDEXES
    # ----------------------------
    def _create_indexes(self, cursor, columns):
        index_fields = [
            "order_revision_id",
            "order_id",
            "order_line_nbr",
            "revision_date",
            "requested_dte",
            "scheduled_dte",
            "user_id",
            "status_id"
        ]

        for col in index_fields:
            if col in columns:
                cursor.execute(f"""
                    CREATE INDEX IF NOT EXISTS idx_orev_{col}
                    ON order_revision_events ("{col}");
                """)

    # ----------------------------
    #   MAIN IMPORT
    # ----------------------------
    def run(self, dry_run=False):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("PRAGMA foreign_keys = ON;")

        # Load CSV
        with open(self.csv_path, newline='', encoding="utf-8") as f:
            reader = csv.DictReader(f)
            columns = reader.fieldnames

            if not columns:
                print("❌ CSV header missing.")
                conn.close()
                return

            rows = list(reader)

        # Detect types
        col_types = self._detect_column_types(rows, columns)

        # Create table
        self._ensure_table(cursor, columns, col_types)

        if dry_run:
            print("\n🔎 Dry Run — Detected Column Types:")
            for c in columns:
                print(f"  {c}: {col_types[c]}")
            conn.close()
            return

        # Prepare insert
        placeholders = ", ".join(["?"] * len(columns))
        insert_sql = f"""
            INSERT INTO order_revision_events
            ({", ".join(columns)})
            VALUES ({placeholders})
        """

        # Build rows
        insert_rows = []
        for row in rows:
            values = []
            for col in columns:
                raw = row[col].strip()

                # Auto date detection
                if any(x in col.lower() for x in ["date", "dte"]):
                    values.append(self._parse_date(raw))
                    continue

                if col_types[col] == "INTEGER":
                    values.append(int(raw) if raw else None)
                elif col_types[col] == "REAL":
                    values.append(float(raw) if raw else None)
                else:
                    values.append(raw if raw else None)

            insert_rows.append(values)

        # Insert
        try:
            cursor.executemany(insert_sql, insert_rows)
            conn.commit()

            self._create_indexes(cursor, columns)
            conn.commit()

            print(f"✅ Imported {len(insert_rows)} rows into order_revision_events.")

        except Exception as e:
            conn.rollback()
            print(f"❌ Import failed: {e}")

        finally:
            conn.close()


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
            importer = CustomerImporter()
            importer.run()
        elif test_class == "import_addresses":
            importer = AddressImporter()
            importer.run()
        elif test_class == "import_docket":
            importer = DocketImporter()
            importer.run()
        elif test_class == "import_order_revision":
            importer = OrderRevisionEventsImporter()
            importer.run()
        else:
            print(f"Unknown class: {test_class}")
            print("Usage: python importers.py [import_order|order_routing|update_order|order_details|import_customer]")
    else:
        print("Usage: python importers.py [import_order|order_routing|update_order|order_details|import_customer]")