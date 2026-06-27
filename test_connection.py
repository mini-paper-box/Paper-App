import pyodbc
import pandas as pd

# --- CONFIG ---
server = 'wbdbserver'      
database = 'flute_data'  

# --- CONNECT ---
conn_str = (
    'DRIVER={ODBC Driver 18 for SQL Server};'
    f'SERVER={server};'
    f'DATABASE={database};'
    'Trusted_Connection=yes;'
    'Encrypt=no;'
)

conn = pyodbc.connect(conn_str)

# --- TEST QUERY ---
query = """
SELECT
      r.order_revision_id,
      LTRIM(RTRIM(u.user_first_name)) 
        + ' ' 
        + LEFT(LTRIM(RTRIM(u.user_last_name)), 1) + '.' AS full_name,
      c.short_name AS customer_name,
      r.order_id,
      od.order_line_nbr,
      od.scheduled_dte AS shipped_date,
      od.requested_dte,
      r.user_id,
      r.revision_date,
      od.delivery_status_txt,
      r.revision_num,
      r.revision_dsc,
      r.status_id, 
      0 AS emailed
FROM [flute_data].[dbo].[order_revisions] r
JOIN [flute_data].[dbo].[order_details] od
    ON r.order_id = od.order_id
JOIN users u
    ON r.user_id = u.[user_id]
JOIN order_header oh
    ON r.order_id = oh.order_id
JOIN customer c
    ON oh.customer_id = c.customer_id
WHERE r.revision_date >= CAST(DATEADD(DAY, -1, GETDATE()) AS DATE)
  AND r.revision_dsc NOT IN ('Order Processed', 'Printed (New)', 'Order sent to Pronto')
  AND od.scheduled_dte > od.requested_dte
  AND r.status_id = 3;
"""

df = pd.read_sql(query, conn)
print(df)

conn.close()
