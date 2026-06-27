import sqlite3
import tkinter as tk
from typing import Optional
from tkinter import ttk

class MakeSimpleSql():
    def reject_window(self):
        rw = tk.Toplevel()
        rw.title('Rejected Purchase Order')
        rw.geometry('400x600')

    def init_connection(self):
        """
        Connect to database
        :return: Database connection
        """
        path = 'C:/Users/sang.n/OneDrive - whitebird.ca/Paper App/prod_db.db'
        return sqlite3.connect(path)

    def create_tables(self) -> None:
        """
        Create table
        """
        connection: sqlite3.Connection = self.init_connection()
        cursor = connection.cursor()
        #supplier
        cursor.execute("""CREATE TABLE IF NOT EXISTS supplier
        (supplier TEXT, address TEXT, phone_number TEXT, email TEXT)""")
        #price list
        cursor.execute("""CREATE TABLE IF NOT EXISTS supplier_price_list
                       (supplier TEXT, charge_type TEXT, min int, max int, price REAL)""")
        
        #"Supplier", "Purchase Order Number", "Material", "Price", "Width", "Length",  "Ordered Quanty", "Shipped Quantity",  "Purchase Date", "Requested Date", "Status"), show='headings')
        cursor.execute("""CREATE TABLE IF NOT EXISTS purchase_order
                       (supplier TEXT, 
                       purchase_order_number TEXT PRIMARY KEY,
                       material TEXT, price REAL,
                       width REAL,
                       length REAL,
                       ordered_quantity int,
                       shipped_quantity int,
                       purchase_date TEXT,
                       requested_date TEXT,
                       status Text )""")
        #purchase order
        # cursor.execute("""CREATE TABLE IF NOT EXISTS purchase_order
        # (supplier TEXT, order_num int, order_num_line int, po_num int, po_num_line int, purchase date, due date, line_up TEXT, scheduled date, status TEXT)""")
        #Commit command
        connection.commit()
        #Close connection
        connection.close()

    def execute(self, query: str, params: tuple = ()):
        try:
            connection: sqlite3.Connection = self.init_connection()
            cursor = connection.cursor()
            cursor.execute(query, params)

            # SELECT query → return results
            if query.strip().lower().startswith("select"):
                rows = cursor.fetchall()
                connection.close()
                return rows

            # Non-SELECT → commit and return affected rows
            connection.commit()
            affected = cursor.rowcount
            connection.close()
            return affected

        except sqlite3.Error as e:
            print(f"❌ Database error: {e}")
            print(f"SQL: {query}")
            print(f"Params: {params}")
            raise
        
    #Insert single record to table    
    def insert_single(self, supplier:str, charge_type: str, min: int, max: int, price: float) -> None:
        connection: sqlite3.Connection = self.init_connection()

        cursor = connection.cursor()
        
        cursor.execute(f"""INSERT INTO supplier_price_list VALUES ('{supplier}', '{charge_type}', '{min}', '{max}', {price})
        """)

        connection.commit()
        #Close connection
        connection.close()

    def insert_material(self, material:str) -> None:
        connection: sqlite3.Connection = self.init_connection()

        cursor = connection.cursor()
        
        cursor.execute(f"""INSERT OR IGNORE INTO material (material_name) VALUES ('{material}')
        """)

        connection.commit()
        #Close connection
        connection.close()


    def insert_multi_material(self, list_material) -> None:
        connection: sqlite3.Connection = self.init_connection()
        
        cursor = connection.cursor()

        #Insert place holder ?,?,?,?
        cursor.executemany('INSERT INTO material (material_name) VALUES (?)', list_material)

        connection.commit()
        #Close connection
        connection.close()

    def delete_record(self, purchase_order:str) -> None:
        connection: sqlite3.Connection = self.init_connection()

        cursor = connection.cursor()
        
        cursor.execute(f"""DELETE FROM purchase_order WHERE purchase_order_number = '{purchase_order}'
        """)

        connection.commit()
        #Close connection
        connection.close()

    def insert_purchase_order(self, supplier:str, charge_type: str, min: int, max: int, price: float) -> None:
        connection: sqlite3.Connection = self.init_connection()

        cursor = connection.cursor()
        
        cursor.execute(f"""INSERT INTO purchase_order VALUES ('{supplier}', '{charge_type}', '{min}', '{max}', {price})
        """)

        connection.commit()
        #Close connection
        connection.close()

    def insert_record(self) -> None:
        connection: sqlite3.Connection = self.init_connection()
        
        cursor = connection.cursor()

        many_suppliers = [
                        ('Coastal', '123 address', '999-999-9999', 'sheets@coastal.com'),
                        ('Green Meadows', '123 address', '999-999-9999', 'sheets@coastal.com'),
                        ('Independent', '123 address', '999-999-9999', 'sheets@coastal.com'),
                        ('Tencorr', '123 address', '999-999-9999', 'sheets@coastal.com')
        ]
        
        #Insert place holder ?,?,?,?
        cursor.executemany('INSERT INTO supplier VALUES (?,?,?,?)', many_suppliers)

        connection.commit()
        #Close connection
        connection.close()

    #Insert multip record 
    def insert_multiple(self) -> None:
        connection: sqlite3.Connection = self.init_connection()
        
        cursor = connection.cursor()

        many_suppliers = [
                        ('Coastal', '123 address', '999-999-9999', 'sheets@coastal.com'),
                        ('Green Meadows', '123 address', '999-999-9999', 'sheets@coastal.com'),
                        ('Independent', '123 address', '999-999-9999', 'sheets@coastal.com'),
                        ('Tencorr', '123 address', '999-999-9999', 'sheets@coastal.com')
        ]
        
        #Insert place holder ?,?,?,?
        cursor.executemany('INSERT INTO supplier VALUES (?,?,?,?)', many_suppliers)

        connection.commit()
        #Close connection
        connection.close()

    def insert_multiple_purchase_order(self, list_purchase_order) -> None:
        connection: sqlite3.Connection = self.init_connection()
        
        cursor = connection.cursor()

        num_columns = len(list_purchase_order[0]) if list_purchase_order else 0
        placeholders = ", ".join(["?"] * num_columns)

        pos = list_purchase_order

        insert_sql = f"""INSERT OR IGNORE INTO purchase_order (supplier_id, po_number, po_line, suffix, material, price, uom, 
                           width, length, ordered_quantity, purchase_date, 
                           requested_date, file_name
                           ) VALUES ({placeholders})"""
        
        #Insert place holder ?,?,?,?
        #"Supplier", "Purchase Order Number", "Material", "Price", "Width", "Length",  "Ordered Quanty", "Shipped Quantity",  "Purchase Date", "Requested Date", "Status")
        cursor.executemany(insert_sql, pos)

        connection.commit()
        #Close connection
        connection.close()

    def in_or_up_purchase_order(self, list_purchase_order) -> None:
        """
        Insert or update purchase orders in SQLite.
        If (po_number, po_line) exists, update the row instead of inserting a duplicate.
        """

        if not list_purchase_order:
            return

        connection: sqlite3.Connection = self.init_connection()
        cursor = connection.cursor()

        upsert_sql = """
            INSERT INTO purchase_order (
                supplier_id, po_number, po_line, suffix, material, price, uom,
                width, length, ordered_quantity, purchase_date,
                requested_date, file_name
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(po_number, po_line) DO UPDATE SET
                supplier_id      = excluded.supplier_id,
                suffix           = excluded.suffix,
                material         = excluded.material,
                price            = excluded.price,
                uom              = excluded.uom,
                width            = excluded.width,
                length           = excluded.length,
                ordered_quantity = excluded.ordered_quantity,
                purchase_date    = excluded.purchase_date,
                requested_date   = excluded.requested_date,
                file_name        = excluded.file_name
        """

        try:
            cursor.executemany(upsert_sql, list_purchase_order)
            connection.commit()
        except sqlite3.Error as e:
            print(f"❌ Database error: {e}")
            connection.rollback()
        finally:
            connection.close()

    
    def insert_multiple_price(self, list_price) -> None:
        if not list_price:
            return
        connection: sqlite3.Connection = self.init_connection()
        cursor = connection.cursor()
        #Insert place holder ?,?,?,?material (material_name) VALUES ('{material}')
        cursor.executemany('INSERT OR IGNORE INTO price_list (supplier_id, material_id,alter_name, charge_type, min, max, price) VALUES (?,?,?,?,?,?,?)', list_price)
        connection.commit()
        #Close connection
        connection.close()
    
    def split_po_number(self, po_string):
            if '-' not in str(po_string):
                return po_string, 1, None

            base, rest = po_string.split('-', 1)

            # Separate digits and letters after the dash
            num_part = ''.join(filter(str.isdigit, rest))
            suffix = ''.join(filter(str.isalpha, rest))

            return base, num_part, suffix
    
    def insert_delivery_docket(self, docket_number, shipped_date, delivery_date, dict_data, status):
        connection: sqlite3.Connection = self.init_connection()
        connection.row_factory = sqlite3.Row
        cursor = connection.cursor()

        try:
            # Insert only if docket doesn't exist
            cursor.execute("""
                INSERT OR IGNORE INTO delivery_docket (delivery_docket_id, shipped_date, delivery_date) 
                SELECT ?, ?, ?
                WHERE NOT EXISTS (
                    SELECT 1 FROM delivery_docket WHERE delivery_docket_id = ?
                )
            """, (docket_number, shipped_date, delivery_date, docket_number))

            # Fetch the docket ID
            cursor.execute("SELECT * FROM delivery_docket WHERE delivery_docket_id = ?", (docket_number,))
            docket_row = cursor.fetchone()

            if docket_row:
                docket_id = docket_row['id']
                for data in dict_data:
                    po_number, po_line, suffix = self.split_po_number(data["purchase_order_number"])
                    cursor.execute("""
                        INSERT OR IGNORE INTO purchase_order_delivery_docket 
                        (shipped_quantity, purchase_order_number, delivery_docket_id, po_number, po_line, suffix)
                        VALUES (?, ?, ?, ?, ?, ?)
                    """, (data["shipped_quantity"], data["purchase_order_number"], docket_id, po_number, po_line, suffix))

                    cursor.execute("""
                        UPDATE purchase_order 
                        SET status = ?
                        WHERE po_number = ? AND po_line = ?
                    """, (status, po_number, po_line))

                connection.commit()
                return docket_id
            else:
                print("Docket not inserted or found.")
                return None
        except Exception as e:
            print("Insert failed:", e)
            connection.rollback()
        finally:
            connection.close()


    def update_multiple_delivery_docket(self, list_po) -> None:
        if not list_po:
            return
        connection: sqlite3.Connection = self.init_connection()
        cursor = connection.cursor()
        #Insert place holder ?,?,?,?material (material_name) VALUES ('{material}')
        cursor.executemany('UPDATE purchase_order SET shipped_quantity=? WHERE purchase_order_number= ?', list_po)
        connection.commit()
        #Close connection
        connection.close()

    def update_po_fields(self, po_data: dict):
        def split_po_number(po_string):
            if '-' not in po_string:
                return po_string, None, None

            base, rest = po_string.split('-', 1)

            # Separate digits and letters after the dash
            num_part = ''.join(filter(str.isdigit, rest))
            suffix = ''.join(filter(str.isalpha, rest))

            return base, num_part, suffix
        connection: sqlite3.Connection = self.init_connection()
        
        update_fields = ["material", "width", "length", "ordered_quantity", "price", "status", "requested_date"]
        set_clause = ", ".join(f"{field} = ?" for field in update_fields)
        po, line, suffix = split_po_number(po_data["purchase_order_number"])
        values = [po_data[field] for field in update_fields] + [po,line]
        cursor = connection.cursor()
        cursor.execute(f"""
            UPDATE purchase_order SET {set_clause}
            WHERE po_number = ? and po_line = ?
        """, values)

        connection.commit()
        #Close connection
        connection.close()

    def update_order_status(self, data: dict):
        connection: sqlite3.Connection = self.init_connection()
        
        update_fields = ["status"]
        set_clause = ", ".join(f"{field} = ?" for field in update_fields)
        values = [data[field] for field in update_fields] + [data["order_id"]]
        cursor = connection.cursor()
        cursor.execute(f"""
            UPDATE orders SET {set_clause}
            WHERE order_id = ?
        """, values)

        connection.commit()
        #Close connection
        connection.close()

    def update_order(self, data: dict):
        """
        Update order status, ship_id, and/or billing_id in the orders table.

        Expects `data` to contain:
            - order_id (required)
            - status (optional)
            - ship_id (optional)
            - bill_id (optional)
        """
        connection: sqlite3.Connection = self.init_connection()
        try:
            cursor = connection.cursor()

            update_fields = []
            values = []

            if "status" in data:
                update_fields.append("status = ?")
                values.append(data["status"])

            if "ship_id" in data:
                update_fields.append("ship_id = ?")
                values.append(data["ship_id"])

            if "bill_id" in data:  # ✅ Add billing update support
                update_fields.append("billing_id = ?")
                values.append(data["bill_id"])

            if not update_fields:
                return  # Nothing to update

            values.append(data["order_id"])
            sql = f"UPDATE orders SET {', '.join(update_fields)} WHERE order_id = ?"

            cursor.execute(sql, tuple(values))  # ✅ Always pass tuple
            connection.commit()
        finally:
            connection.close()


        

    def update_status(self, po, status) -> None:
        if not po or not status:
            return
        connection: sqlite3.Connection = self.init_connection()
        cursor = connection.cursor()
        #Insert place holder ?,?,?,?material (material_name) VALUES ('{material}')
        cursor.execute(f"UPDATE purchase_order SET status='{status}' WHERE purchase_order_number='{po}'")
        connection.commit()
        #Close connection
        connection.close()

    def update_multi_po(self, list_purchase_order) -> None:
        connection: sqlite3.Connection = self.init_connection()
        
        cursor = connection.cursor()
        update_list = list_purchase_order
        for i in update_list:
            cursor.execute("""UPDATE purchase_order SET
                material = :material,
                price = :price,
                width = :width,
                length = :length,
                ordered_quantity = :ordered_quantity,
                shipped_quantity = :shipped_quantity,
                purchase_date = :purchase_date,
                requested_date = :requested_date,
                status = :status
                            
            WHERE purchase_order_number = :pon""",
            {
                'pon':i[1],
                'material': i[2],
                'price' :i[3],
                'width' :i[4],
                'length' :i[5],
                'ordered_quantity' :i[6],
                'shipped_quantity' :i[7],
                'purchase_date' :i[8],
                'requested_date' :i[9],
                'status' :i[10],
            })

        connection.commit()
        #Close connection
        connection.close()
    

    #Insert place holder ?,?,?,?
    #cursor.executemany('INSERT INTO supplier VALUES (?,?,?,?)', many_suppliers)

    #Return all record
    def fetch_all(self) -> None:
        connection: sqlite3.Connection = self.init_connection()
        connection.row_factory = sqlite3.Row #allow access column header row['status']

        cursor = connection.cursor()

        cursor.execute('SELECT * FROM purchase_order')
        queryData: list[tuple]
        queryData = (cursor.fetchall())

        #Commit command
        connection.commit()

        #Close connection
        connection.close()
        return queryData
    
    def get_purchase_order_with_query(self, query, params) -> None:
        connection: sqlite3.Connection = self.init_connection()
        connection.row_factory = sqlite3.Row #allow access column header row['status']

        cursor = connection.cursor()
        cursor.execute(query, params)
        queryData: list[tuple]
        queryData = (cursor.fetchall())     

        #Commit command
        connection.commit()

        #Close connection
        connection.close()
        return queryData
    
    def get_supplier_id(self, supplier_name) -> None:
        connection: sqlite3.Connection = self.init_connection()
        connection.row_factory = sqlite3.Row #allow access column header row['status']

        cursor = connection.cursor()

        cursor.execute(f'SELECT sid FROM supplier where supplier_name LIKE "{supplier_name}%"')
        queryData = (cursor.fetchone())

        #Commit command
        connection.commit()

        #Close connection
        connection.close()
        if queryData:
            return queryData[0]
        return None
    
    def get_supplier(self) -> None:
        connection: sqlite3.Connection = self.init_connection()
        connection.row_factory = sqlite3.Row #allow access column header row['status']

        cursor = connection.cursor()

        cursor.execute(f'SELECT supplier_name FROM supplier')
        queryData = (cursor.fetchone())

        #Close connection
        connection.close()
        if queryData:
            return queryData[0]
        return None
    
    def get_supplier_name_by_po(self, po) -> None:
        connection: sqlite3.Connection = self.init_connection()
        connection.row_factory = sqlite3.Row #allow access column header row['status']

        po_number, po_line, suffix = self.split_po_number(po)
        cursor = connection.cursor()

        supplier_id_data  = cursor.execute(f'SELECT supplier_id FROM purchase_order where po_number = ? AND po_line = ?', (po_number,po_line)).fetchone()
        supplier_id = supplier_id_data['supplier_id'] if supplier_id_data else None
        if supplier_id:
            supplier_name_data = cursor.execute(f'SELECT supplier_name FROM supplier where sid =?', (supplier_id,)).fetchone()

        #Close connection
        connection.close()

        return supplier_name_data['supplier_name'] if supplier_id_data else None
    
    def get_supplier_name(self, sid: int) -> Optional[str]:
        """Fetch supplier_name by supplier ID (sid)."""
        connection: sqlite3.Connection = self.init_connection()
        cursor = connection.cursor()

        cursor.execute("SELECT supplier_name FROM supplier WHERE sid = ?", (sid,))
        row = cursor.fetchone()

        connection.close()

        return row[0] if row else None
    
    def get_suppliers(self) -> list[str]:
        """Return a list of all supplier names."""
        with self.init_connection() as connection:
            cursor = connection.cursor()
            cursor.execute("SELECT supplier_name FROM supplier")
            return [row[0] for row in cursor.fetchall()]
    
    def get_supplier_emails(self, supplier_name: str) -> str | None:
        connection: sqlite3.Connection = self.init_connection()
        connection.row_factory = sqlite3.Row

        try:
            cursor = connection.cursor()
            cursor.execute(f'SELECT email FROM supplier WHERE supplier_name LIKE "{supplier_name}%";')
            row = cursor.fetchone()
            return row['email'] if row else None
        finally:
            connection.close()
    
    def get_material(self, material_name) -> None:
        connection: sqlite3.Connection = self.init_connection()
        connection.row_factory = sqlite3.Row #allow access column header row['status']

        cursor = connection.cursor()

        cursor.execute(f'SELECT id FROM material where material_name LIKE "{material_name}%"')
        query = cursor.fetchone()

        #Commit command
        connection.commit()

        #Close connection
        connection.close()
        if query:
            return query[0]
        return None
    
    def get_material_with_supplier(self, supplier_id, material_id) -> None:
        connection: sqlite3.Connection = self.init_connection()
        connection.row_factory = sqlite3.Row #allow access column header row['status']

        cursor = connection.cursor()

        cursor.execute(f'SELECT alter_name FROM price_list where supplier_id = "{supplier_id}" AND material_id = "{material_id}"')
        query = cursor.fetchone()

        #Commit command
        connection.commit()

        #Close connection
        connection.close()
        if query:
            return query[0]
        return None

    def get_purchase_order(self) -> list[tuple]:
        connection: sqlite3.Connection = self.init_connection()
        connection.row_factory = sqlite3.Row #allow access column header row['status']

        cursor = connection.cursor()
        cursor.execute('''SELECT * FROM purchase_order_view
                        WHERE strftime('%Y-%m', requested_date) = strftime('%Y-%m', 'now')
                        ORDER BY requested_date;''')
        #Declare variable
        queryData: list[tuple]
        queryData = (cursor.fetchall())
  
        #Commit command
        connection.commit()
        #Close connection
        connection.close()
        return queryData
    
    def get_orders(self) -> list[dict]:
        """Fetch all orders from orders_view and return as a list of dicts."""
        try:
            connection: sqlite3.Connection = self.init_connection()
            connection.row_factory = sqlite3.Row  # allows row['status'] access
            cursor = connection.cursor()
            cursor.execute("SELECT * FROM orders_view;")
            return self.row_to_dict(cursor.fetchall())
        finally:
            connection.close()

    def get_customer_addresses(self, query, customer_id):
        connection: sqlite3.Connection = self.init_connection()
        connection.row_factory = sqlite3.Row  # Access by column name
        cursor = connection.cursor()
        cursor.execute(query,customer_id)
        
        rows = cursor.fetchall()
        if rows:
            result = []
            for row in rows:
                result.append(self.row_to_dict(row))
        
        connection.close()
        return result
    
    def get_order_details(self, order_id, order_line=None) -> list[dict]:
        """Fetch order details from the view with optional order line filter."""
        connection: sqlite3.Connection = self.init_connection()
        connection.row_factory = sqlite3.Row
        cursor = connection.cursor()

        sql = "SELECT * FROM order_details_view WHERE order_id = ?"
        params = [order_id]

        if order_line is not None:
            sql += " AND order_line_nbr = ?"
            params.append(order_line)

        cursor.execute(sql, params)
        rows = cursor.fetchall()

        result = [self.row_to_dict(row) for row in rows] if rows else []

        print(f"✅ Retrieved {len(result)} row(s) for order_id={order_id}, line={order_line}")

        connection.close()

        return result
    
    def get_pending_purchase_order(self) -> list[dict]:
        """Fetch order details from the view with optional order line filter."""
        connection: sqlite3.Connection = self.init_connection()
        connection.row_factory = sqlite3.Row
        cursor = connection.cursor()

        sql = "SELECT * FROM purchase_order_receipt_view"

        cursor.execute(sql)
        rows = cursor.fetchall()

        result = [self.row_to_dict(row) for row in rows] if rows else []

        connection.close()

        return result

    
    def get_all_addresses(self, customer_id):
        query = """
        SELECT name_1, address_1, city, province, postal_code
        FROM addresses WHERE customer_id = {customer_id}
        """
        return [dict(zip(("name","street","city","province","postal"), row)) for row in self.fetchall(query)]


    def get_order_addresses(self, order_id: int) -> dict[str, dict | None]:
        """
        Fetch both billing and shipping addresses for a given order.
        Returns dict with plain dictionaries (not sqlite3.Row).
        Example:
            {
                "billing": {"name": "...", "street": "...", ...},
                "shipping": {"name": "...", "street": "...", ...}
            }
        """
        connection: sqlite3.Connection = self.init_connection()
        connection.row_factory = sqlite3.Row
        cursor = connection.cursor()

        # Fetch order row first
        cursor.execute(
            "SELECT billing_id, ship_id, customer_id FROM orders WHERE order_id = ?;",
            (order_id,),
        )
        order_row = cursor.fetchone()

        def row_to_dict(row):
            return dict(row) if row else None

        result = {"billing": None, "shipping": None}

        if not order_row:
            # No order found, return empty
            connection.close()
            return result

        customer_id = order_row["customer_id"]

        # --- Billing address ---
        if order_row["billing_id"]:
            cursor.execute(
                """
                SELECT a.*, c.customer_name AS name, bh.*
                FROM addresses a
                LEFT JOIN customers c ON a.customer_id = c.customer_id
                LEFT JOIN business_hours bh ON a.business_hours_id = bh.id
                WHERE a.address_id = ?;
                """,
                (order_row["billing_id"],),
            )
        else:
            cursor.execute(
                """
                SELECT a.*, c.customer_name AS name, bh.*
                FROM addresses a
                LEFT JOIN customers c ON a.customer_id = c.customer_id
                LEFT JOIN business_hours bh ON a.business_hours_id = bh.id
                WHERE a.customer_id = ?;
                """,
                (customer_id,),
            )
        result["billing"] = row_to_dict(cursor.fetchone())

        # --- Shipping address ---
        if order_row["ship_id"]:
            cursor.execute(
                """
                SELECT a.*, c.customer_name AS name, bh.*
                FROM addresses a
                LEFT JOIN customers c ON a.customer_id = c.customer_id
                LEFT JOIN business_hours bh ON a.business_hours_id = bh.id
                WHERE a.address_id = ?;
                """,
                (order_row["ship_id"],),
            )
        else:
            cursor.execute(
                """
                SELECT a.*, c.customer_name AS name, bh.*
                FROM addresses a
                LEFT JOIN customers c ON a.customer_id = c.customer_id
                LEFT JOIN business_hours bh ON a.business_hours_id = bh.id
                WHERE a.customer_id = ?;
                """,
                (customer_id,),
            )
        result["shipping"] = row_to_dict(cursor.fetchone())

        connection.close()
        return result


    def row_to_dict(self, rows):
        """
        Convert sqlite3.Row or tuple rows to list of dictionaries.
        If rows is a single row, returns a dict.
        """
        if rows is None:
            return None
        if isinstance(rows, list):  # multiple rows
            return [dict(r) for r in rows]
        return dict(rows)  # single row


    def pdf_reader(self, str:str)-> dict:
        """
        Read Pdf file
        :return:dict of purchase order details
        """
        pass

def main() -> None:
    data = (make_simple().fetch_all())
    print(data[1]['status'])
        
if __name__ == '__main__':
    main()
