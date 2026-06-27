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
SELECT TOP 5 *
FROM schedule_view
"""

df = pd.read_sql(query, conn)
print(df)

conn.close()
