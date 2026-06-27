import sqlite3

def schedule_job(job_msf, process_sequence_ids, db_path, max_consec_days=15,
                 start_offset_days=4, lookahead_days=60):
    """
    Schedule a job across a sequence of processes using SQLite recursive logic.

    Args:
        job_msf (int): Job size in MSF.
        process_sequence_ids (list[int]): Ordered list of process IDs.
        db_path (str): Path to SQLite database.
        max_consec_days (int): Maximum consecutive days for a process.
        start_offset_days (int): Days ahead to start looking for schedule.
        lookahead_days (int): Number of future days to consider for scheduling.

    Returns:
        list[dict]: Scheduled steps with start/end dates, breakdown, total available, etc.
    """
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Create temporary table for the process sequence
    cursor.execute("DROP TABLE IF EXISTS temp_process_sequence;")
    cursor.execute("""
    CREATE TEMP TABLE temp_process_sequence(
        sequence_order INTEGER,
        process_id INTEGER
    );
    """)
    for i, pid in enumerate(process_sequence_ids, start=1):
        cursor.execute(
            "INSERT INTO temp_process_sequence(sequence_order, process_id) VALUES (?, ?);",
            (i, pid)
        )
    conn.commit()

    # Recursive scheduling SQL with dynamic start offset and lookahead
    SQL = f"""
    WITH input_params AS (
        SELECT ? AS job_msf, ? AS max_consec_days
    ),
    process_list AS (
        SELECT t.sequence_order, p.id, p.process_name
        FROM temp_process_sequence t
        JOIN process p ON p.id = t.process_id
    ),
    future_dates AS (
        SELECT date('now', '+{start_offset_days} day') AS d
        UNION ALL
        SELECT date(d, '+1 day')
        FROM future_dates
        WHERE d < date('now', '+{lookahead_days} day')
    ),
    capacity_per_day AS (
        SELECT 
            fd.d AS date,
            p.sequence_order,
            p.process_name,
            COALESCE(pc.max_sqft,
                     (SELECT max_sqft FROM process_capacity
                      WHERE process_name = p.process_name AND date IS NULL)
            )
            - COALESCE((SELECT SUM(CAST(o.msf AS REAL))
                        FROM order_routing o
                        WHERE o.process_nme = p.process_name
                          AND substr(o.scheduled_dte,1,10) = fd.d),0) AS available_sqft
        FROM future_dates fd
        JOIN process_list p
        LEFT JOIN process_capacity pc
               ON pc.date = fd.d AND pc.process_name = p.process_name
        WHERE strftime('%w', fd.d) NOT IN ('0','6')
    ),
    windows AS (
        SELECT 
            sequence_order,
            process_name,
            date AS start_date,
            date AS end_date,
            available_sqft,
            available_sqft AS total_available,
            1 AS days_used,
            date || ':' || available_sqft AS breakdown
        FROM capacity_per_day
        WHERE available_sqft > 0

        UNION ALL

        SELECT
            w.sequence_order,
            w.process_name,
            w.start_date,
            c.date AS end_date,
            c.available_sqft,
            w.total_available + c.available_sqft AS total_available,
            w.days_used + 1 AS days_used,
            w.breakdown || ' | ' || c.date || ':' || c.available_sqft AS breakdown
        FROM windows w
        JOIN capacity_per_day c
          ON c.process_name = w.process_name
         AND c.date = (
               SELECT MIN(fd2.date)
               FROM capacity_per_day fd2
               WHERE fd2.process_name = w.process_name
                 AND fd2.date > w.end_date
                 AND fd2.available_sqft > 0
           )
        JOIN input_params p
          ON w.total_available < p.job_msf
         AND w.days_used < p.max_consec_days
    ),
    feasible_windows AS (
        SELECT w.*
        FROM windows w, input_params p
        WHERE w.total_available >= p.job_msf
    ),
    chain AS (
        SELECT
            f.sequence_order,
            f.process_name,
            f.start_date,
            f.end_date,
            f.total_available,
            f.breakdown,
            f.start_date AS chain_start,
            f.end_date   AS chain_end
        FROM feasible_windows f
        WHERE f.sequence_order = 1
          AND f.start_date = (
                SELECT MIN(start_date)
                FROM feasible_windows
                WHERE sequence_order = 1
            )
          AND f.end_date = (
                SELECT MIN(end_date)
                FROM feasible_windows
                WHERE sequence_order = 1
                  AND start_date = (
                        SELECT MIN(start_date)
                        FROM feasible_windows
                        WHERE sequence_order = 1
                  )
            )

        UNION ALL

        SELECT
            n.sequence_order,
            n.process_name,
            n.start_date,
            n.end_date,
            n.total_available,
            n.breakdown,
            ch.chain_start,
            n.end_date AS chain_end
        FROM chain ch
        JOIN feasible_windows n
          ON n.sequence_order = ch.sequence_order + 1
         AND n.start_date >= date(ch.end_date, '+1 day')
        WHERE n.start_date = (
                SELECT MIN(start_date)
                FROM feasible_windows x
                WHERE x.sequence_order = ch.sequence_order + 1
                  AND x.start_date >= date(ch.end_date, '+1 day')
            )
          AND n.end_date = (
                SELECT MIN(end_date)
                FROM feasible_windows x
                WHERE x.sequence_order = ch.sequence_order + 1
                  AND x.start_date = (
                        SELECT MIN(start_date)
                        FROM feasible_windows y
                        WHERE y.sequence_order = ch.sequence_order + 1
                          AND y.start_date >= date(ch.end_date, '+1 day')
                  )
            )
    ),
    earliest_complete_chain AS (
        SELECT MIN(chain_start) AS chain_start
        FROM chain
        WHERE sequence_order = (SELECT COUNT(*) FROM process_list)
    )
    SELECT
        ch.sequence_order,
        ch.process_name,
        ch.start_date,
        ch.end_date,
        ch.total_available,
        ch.breakdown,
        ec.chain_start AS chain_start_date,
        (SELECT MAX(end_date) FROM chain WHERE chain_start = ec.chain_start) AS chain_end_date
    FROM chain ch
    CROSS JOIN earliest_complete_chain ec
    WHERE ch.chain_start = ec.chain_start
    ORDER BY ch.sequence_order;
    """

    cursor.execute(SQL, (job_msf, max_consec_days))
    rows = cursor.fetchall()
    conn.close()

    schedule = []
    for row in rows:
        schedule.append({
            'sequence_order': row[0],
            'process_name': row[1],
            'start_date': row[2],
            'end_date': row[3],
            'total_available': row[4],
            'breakdown': row[5],
            'chain_start_date': row[6],
            'chain_end_date': row[7]
        })
    return schedule

db_path = "prod_db.db"
job_msf = 150000
process_sequence = [1, 2, 6]

schedule = schedule_job(job_msf, process_sequence, db_path,
                        max_consec_days=15, start_offset_days=3, lookahead_days=90)

for step in schedule:
    print(f"{step['process_name']} - {step['start_date']} : {step['breakdown']}")
