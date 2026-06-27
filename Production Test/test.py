import pytds
import pytds.login

class AutoScheduler:
    def __init__(self, server, database):
        self.server = server
        self.database = database
        self.conn = None

    def connect(self):
        if self.conn is None:
            self.conn = pytds.connect(
                server=self.server,
                database=self.database,
                auth=pytds.login.SspiAuth()
            )
        return self.conn

    def test_select(self):
        """Runs a simple SELECT to verify connection."""
        # Note: Added '*' to the SELECT statement
        sql = "SELECT TOP 10 * FROM track"
        
        try:
            # We use a context manager for the cursor to ensure it closes
            with self.connect().cursor() as cursor:
                cursor.execute(sql)
                rows = cursor.fetchall()
                for row in rows:
                    print(row)
                return rows
        except Exception as e:
            print(f"Query failed: {e}")

    def close(self):
        if self.conn:
            self.conn.close()
            self.conn = None

# --- Execution ---
scheduler = AutoScheduler("YOUR_SERVER", "YOUR_DATABASE")
scheduler.test_select()
scheduler.close()