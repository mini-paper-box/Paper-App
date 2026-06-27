DECLARE @lookahead_days INT = 15;
DECLARE @run_qty INT = 1000;
DECLARE @docket INT = 170024;
DECLARE @lead_time INT = 4;

SET DATEFIRST 1; -- Monday = 1

---------------------------------------------------
-- Step 1: Docket routing
---------------------------------------------------
WITH docket_routing_cte AS (
    SELECT
        dr.docket_id,
        dr.sequence AS seq_order,
        dr.process_id,
        dr.routing_dsc AS process_name,
        @run_qty * (d.sqfpm / 1000.0) AS run_sqft
    FROM docket d
    JOIN docket_routing dr
        ON dr.docket_id = CASE WHEN d.linked_docket_id > 0 THEN d.linked_docket_id ELSE d.docket_id END
    WHERE d.docket_id = @docket
),
process_list AS (
    SELECT process_id 
    FROM docket_routing_cte
),

---------------------------------------------------
-- Step 2: Assign sequential row numbers for chaining
---------------------------------------------------
docket_routing_ordered AS (
    SELECT *,
        ROW_NUMBER() OVER (ORDER BY seq_order) AS chain_step
    FROM docket_routing_cte
),

---------------------------------------------------
-- Step 3: Future workdays
---------------------------------------------------
future_dates AS (
    SELECT CAST(GETDATE() AS DATE) AS d, 0 AS weekday_count
    UNION ALL
    SELECT DATEADD(DAY, 1, d),
           CASE WHEN DATEPART(WEEKDAY, DATEADD(DAY,1,d)) NOT IN (1,7)
                    AND NOT EXISTS (SELECT 1 FROM company_holidays h WHERE h.holiday_dte = DATEADD(DAY,1,d))
                THEN weekday_count + 1 ELSE weekday_count END
    FROM future_dates
    WHERE weekday_count < @lookahead_days
),

future_workdays AS (
    SELECT d
    FROM future_dates
    WHERE DATEPART(WEEKDAY,d) NOT IN (1,7)
      AND NOT EXISTS (SELECT 1 FROM company_holidays h WHERE h.holiday_dte = d)
),

---------------------------------------------------
-- Step 4: Historical process tracking
---------------------------------------------------
track_process AS (
    SELECT 
        t.docket_id,
        t.process_id,
        t.process_nme,
        CAST(t.start_date AS DATE) AS process_date,
        c.qty_per_min,
        t.setup_min,
        t.run_min,
        c.qty_per_min * (d.sqfpm / 1000.0) AS sqft_per_min,
        t.process_qty * (d.sqfpm / 1000.0) AS total_process_sqft
    FROM track t
    JOIN docket d ON d.docket_id = t.docket_id
    CROSS APPLY (SELECT CAST(t.process_qty AS DECIMAL(18,4)) / NULLIF(t.run_min,0)) c(qty_per_min)
    WHERE t.run_min > 0
),

process_data AS (
    SELECT 
        process_id,
        process_date,
        COUNT(*) AS job_process_per_day,
        SUM(run_min) AS total_run_time,
        SUM(setup_min) AS total_setup_time,
        SUM(total_process_sqft) AS total_msf
    FROM track_process
    GROUP BY process_id, process_date
),

process_capacity AS (
    SELECT 
        process_id,
        AVG(job_process_per_day*1.0) AS avg_job,
        AVG(total_msf) AS avg_sqft
    FROM process_data
    GROUP BY process_id
),

booked_per_day AS (
    SELECT
        sv.process_id,
        CAST(sv.schedule_dte AS DATE) AS schedule_date,
        SUM(sv.msf) AS booked_sqft,
        COUNT(*) AS booked_jobs
    FROM schedule_view sv
    GROUP BY sv.process_id, CAST(sv.schedule_dte AS DATE)
),

capacity_per_day AS (
    SELECT
        fd.d AS date,
        drc.chain_step,
        drc.process_id,
        drc.process_name,
        drc.run_sqft,
        ISNULL(b.booked_sqft,0) AS booked_sqft,
        ISNULL(b.booked_jobs,0) AS booked_jobs,
        pc.avg_job - ISNULL(b.booked_jobs,0) AS available_jobs,
        (pc.avg_sqft / NULLIF(pc.avg_job,0)) * (pc.avg_job - ISNULL(b.booked_jobs,0)) AS available_sqft
    FROM future_workdays fd
    CROSS JOIN process_list
    LEFT JOIN docket_routing_ordered drc
    LEFT JOIN process_capacity pc
        ON drc.process_id = pc.process_id
    LEFT JOIN booked_per_day b
        ON drc.process_id = pc.process_id
       AND b.schedule_date = fd.d
),

first_window_per_process AS (
    SELECT *,
           ROW_NUMBER() OVER (PARTITION BY chain_step ORDER BY date) AS rn
    FROM capacity_per_day
    WHERE available_sqft > 0 OR available_jobs > 0
),

---------------------------------------------------
-- Step 5: Sequential chaining using chain_step
---------------------------------------------------
process_chain AS (
    -- Anchor: first step
    SELECT
        f.chain_step,
        f.process_id,
        f.process_name,
        f.date AS start_date,
        f.date AS end_date,
        f.date AS chain_start,
        f.date AS chain_end
    FROM first_window_per_process f
    WHERE f.chain_step = 1
      AND f.rn = 1

    UNION ALL

    -- Recursive: next step by chain_step order
    SELECT
        f.chain_step,
        f.process_id,
        f.process_name,
        f.date AS start_date,
        f.date AS end_date,
        pc.chain_start,
        f.date AS chain_end
    FROM process_chain pc
    JOIN first_window_per_process f
        ON f.chain_step = pc.chain_step + 1
       AND f.date >= pc.chain_end
       AND f.rn = 1
)

SELECT * FROM capacity_per_day
---------------------------------------------------
-- Step 6: Output
---------------------------------------------------
-- SELECT
--     chain_step,
--     process_name,
--     start_date,
--     end_date,
--     chain_start AS job_start_date,
--     chain_end   AS job_completion_date
-- FROM process_chain
-- ORDER BY chain_step;
