import sqlite3
from datetime import datetime, timedelta
from collections import defaultdict

# --- CONFIG ---
db_path = r"C:\Users\sang.n\OneDrive - whitebird.ca\Paper App\prod_db.db"

# --- Connect to DB ---
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

# --- Load holidays safely ---
try:
    cursor.execute("SELECT date FROM holiday")
    holidays = set(row[0] for row in cursor.fetchall())
except sqlite3.OperationalError:
    holidays = set()

# --- Load order routing (excluding unwanted process IDs) ---
cursor.execute("""
SELECT order_id, order_line_nbr, process_id, process_nme, order_seq, requested_dte
FROM order_routing
WHERE process_id NOT IN (234, 168)
ORDER BY order_id, order_line_nbr, order_seq DESC
""")
orders = cursor.fetchall()

# --- Helper: move date back skipping weekends/holidays ---
def prev_working_day(d):
    while d.weekday() >= 5 or d.strftime("%Y-%m-%d") in holidays:
        d -= timedelta(days=1)
    return d

# --- Clear existing schedule ---
cursor.execute("DELETE FROM workback_schedule")

# --- Build workback schedule ---
schedule = []
grouped = defaultdict(list)

# Group by order/line
for row in orders:
    grouped[(row[0], row[1])].append(row)

for (order_id, line_nbr), procs in grouped.items():
    # Start from the latest process (highest sequence)
    last_proc = procs[0]
    requested_date = datetime.strptime(last_proc[5][:10], "%Y-%m-%d")

    # 🔹 Start FROM the requested date (not one day before)
    planned_end = prev_working_day(requested_date)

    for proc in procs:
        planned_start = prev_working_day(planned_end - timedelta(days=1))

        schedule.append((
            proc[0],  # order_id
            proc[1],  # order_line_nbr
            proc[2],  # process_id
            proc[3],  # process_nme
            proc[4],  # order_seq
            planned_start.strftime("%Y-%m-%d"),
            planned_end.strftime("%Y-%m-%d")
        ))

        # Next process ends when this one starts
        planned_end = planned_start  

# --- Insert results ---
cursor.executemany("""
INSERT INTO workback_schedule 
(order_id, order_line_nbr, process_id, process_nme, order_seq, planned_start, planned_end)
VALUES (?, ?, ?, ?, ?, ?, ?)
""", schedule)

conn.commit()
conn.close()

print(f"✅ Workback schedule populated for {len(schedule)} process entries (starting from requested date)")
