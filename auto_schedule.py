import sqlite3
from datetime import datetime, timedelta

def skip_weekends(date):
    while date.weekday() >= 5:
        date += timedelta(days=1)
    return date

def safe_parse_iso(dt_str):
    if dt_str is None:
        return None
    try:
        return datetime.fromisoformat(dt_str)
    except ValueError:
        parts = dt_str.split(" ")
        if len(parts) == 2:
            date_part, time_part = parts
            hour_min = time_part.split(":")
            if len(hour_min[0]) == 1:
                hour_min[0] = "0" + hour_min[0]
            fixed_time = ":".join(hour_min)
            fixed_str = f"{date_part} {fixed_time}"
            return datetime.fromisoformat(fixed_str)
        raise

def get_average_capacity(process_name):
    db_path = "prod_db.db"
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT MAX(max_sqft), MAX(max_jobs)
        FROM process_capacity
        WHERE process_name = ?
    """, (process_name,))
    avg_sqft, avg_jobs = cursor.fetchone()
    conn.close()
    return int(avg_sqft or 200000), int(avg_jobs or 5)

def find_slots_for_sqft_with_spillover(process_name, total_sqft, earliest_date=None, requested_date=None, max_lookahead=10, force=False):
    db_path = "prod_db.db"
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    today = skip_weekends(datetime.today().date())
    requested = safe_parse_iso(str(requested_date)).date() if requested_date else today
    min_date = skip_weekends(requested - timedelta(days=5))
    base_date = max(today, min_date)

    avg_sqft, avg_jobs = get_average_capacity(process_name)
    oversized = total_sqft > avg_sqft

    allocations = []
    remaining_sqft = total_sqft
    day_offsets_checked = 0

    while remaining_sqft > 0 and day_offsets_checked < max_lookahead:
        current_date = skip_weekends(base_date + timedelta(days=day_offsets_checked))

        # Ensure process_capacity exists
        cursor.execute("""
            SELECT max_sqft, max_jobs
            FROM process_capacity
            WHERE process_name = ? AND date = ?
        """, (process_name, current_date))
        row = cursor.fetchone()

        if row:
            max_sqft, max_jobs = row
            if oversized and max_sqft < int(avg_sqft * 1.3):
                max_sqft = int(avg_sqft * 1.3)
                cursor.execute("""
                    UPDATE process_capacity SET max_sqft = ?
                    WHERE process_name = ? AND date = ?
                """, (max_sqft, process_name, current_date))
                conn.commit()
        else:
            max_sqft = int(avg_sqft * 1.3) if oversized else avg_sqft
            max_jobs = avg_jobs
            cursor.execute("""
                INSERT INTO process_capacity(process_name, date, max_sqft, max_jobs)
                VALUES (?, ?, ?, ?)
            """, (process_name, current_date, max_sqft, max_jobs))
            conn.commit()

        # Capacity already used
        cursor.execute("""
            SELECT COALESCE(SUM(msf), 0), COUNT(*)
            FROM order_routing
            WHERE process_nme = ? AND substr(schedule_dte, 1, 10) = ?
        """, (process_name, current_date))
        used_sqft, used_jobs = cursor.fetchone()
        available_sqft = max_sqft - used_sqft
        available_jobs = max_jobs - used_jobs

        if not force and (available_sqft <= 0 or available_jobs <= 0):
            day_offsets_checked += 1
            continue

        alloc = min(remaining_sqft, available_sqft if not force else remaining_sqft)
        allocations.append((current_date, alloc))
        remaining_sqft -= alloc
        day_offsets_checked += 1

    conn.close()

    if remaining_sqft > 0 and not force:
        print(f"❌ Unable to schedule {process_name} ({total_sqft} sqft). Remaining: {remaining_sqft}")
        return None

    if force and remaining_sqft > 0:
        print(f"⚠️ Forced scheduling: Job {process_name} exceeds capacity. Force-allocated full sqft.")

    return allocations

def auto_schedule_process(order_routing_id, process_name, sqft_needed, earliest_date=None, requested_date=None, max_lookahead=10, force=False):
    allocations = find_slots_for_sqft_with_spillover(
        process_name, sqft_needed, earliest_date, requested_date, max_lookahead, force=force
    )
    if not allocations:
        return None

    db_path = "prod_db.db"
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    try:
        cursor.execute("UPDATE order_routing SET schedule_dte = NULL WHERE order_routing_id = ?", (order_routing_id,))

        for date, sqft in allocations:
            if not force:
                cursor.execute("""
                    UPDATE process_capacity
                    SET max_sqft = max_sqft - ?
                    WHERE date = ? AND process_name = ?
                """, (sqft, date, process_name))

        first_date = allocations[0][0]
        total_sqft = sum(sqft for _, sqft in allocations)
        note = ""
        if sqft_needed > get_average_capacity(process_name)[0]:
            note += "Oversized"
        if force:
            note += " [FORCED]"

        cursor.execute("""
            UPDATE order_routing
            SET schedule_dte = ?, msf = ?, remove_schedule_factor = ?
            WHERE order_routing_id = ?
        """, (first_date, total_sqft, note, order_routing_id))

        conn.commit()
    except Exception as e:
        conn.rollback()
        print("❌ Error during scheduling:", e)
        return None
    finally:
        conn.close()

    return [date for date, _ in allocations]

def schedule_job(order_id, line_number, force=False):
    db_path = "prod_db.db"
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    cursor.execute("""
        SELECT order_routing_id, process_nme, msf, schedule_dte, requested_dte
        FROM order_routing
        WHERE order_id = ? AND order_line_nbr = ?
        ORDER BY order_seq, requested_dte
    """, (order_id, line_number))
    process_steps = cursor.fetchall()
    conn.close()

    earliest_date = skip_weekends(datetime.today().date())

    for track_id, process_name, msf, schedule_dte, requested_dte in process_steps:
        requested_date = safe_parse_iso(str(requested_dte)).date() if requested_dte else None
        scheduled_dates = auto_schedule_process(
            track_id, process_name, msf,
            earliest_date.isoformat(), requested_date,
            max_lookahead=10, force=force
        )
        if scheduled_dates:
            earliest_date = skip_weekends(max(scheduled_dates) + timedelta(days=1))

def reschedule_all_jobs(force=False):
    db_path = "prod_db.db"
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    cursor.execute("UPDATE order_routing SET schedule_dte = NULL, remove_schedule_factor = NULL;")
    cursor.execute("DELETE FROM process_capacity WHERE date >= datetime('now');")
    conn.commit()

    cursor.execute("""
        SELECT order_id, order_line_nbr, MIN(requested_dte), COUNT(*)
        FROM order_routing
        GROUP BY order_id, order_line_nbr
        ORDER BY MIN(requested_dte)
    """)
    groups = cursor.fetchall()
    conn.close()

    for o_id, line_nbr, requested_dte, count in groups:
        schedule_job(o_id, line_nbr, force=force)

if __name__ == "__main__":
    # Run with forced scheduling enabled
    reschedule_all_jobs(force=True)
