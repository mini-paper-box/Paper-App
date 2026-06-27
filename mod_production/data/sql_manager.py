import pyodbc
import sqlite3
import os
import pandas as pd
from ..config import CONFIG

class SQLManager:
    def __init__(self, test_mode = False):
        """Initializes connection settings using the central Config."""
        db = CONFIG["DATABASE"]
        # self.conn_str = (
        #     f"DRIVER={db['driver']};"
        #     f"SERVER={db['server']};"
        #     f"DATABASE={db['database']};"
        #     f"Trusted_Connection={db['trusted_connection']};"
        #     f"Encrypt={db['encrypt']};"
        #     f"TrustServerCertificate={db['trust_cert']};"
        # )

        self.conn_str = (
            'DRIVER={SQL Server};'
            f'SERVER={db['server']};'
            f'DATABASE={db['database']};'
            'Trusted_Connection=yes;'
        )

        #path to local db
        self.local_db_path = 'db/prod_db.db'
        self.test_mode = test_mode
        #create local db
        self._initialize_local_db()

    def _get_connection(self):
        """Internal helper to create a fresh connection."""
        try:
            return pyodbc.connect(self.conn_str)
        except Exception as e:
            print(f"Primary SQL connection failed: {e}")

    def _get_local_connection(self):
        """Creates a connection to the local SQLite fallback"""
        return sqlite3.connect(self.local_db_path)
    
    def _initialize_local_db(self):
        """Creates the SQLite file and schema if missing."""
        if not os.path.exists(self.local_db_path):
            print("Local database missing. Initializing new cache...")
            
        with self._get_local_connection() as conn:
            cursor = conn.cursor()
            
            # 1. Docket Table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS docket (
                    docket_id TEXT PRIMARY KEY,
                    style_id TEXT,
                    printing_id TEXT,
                    sqfpm REAL,
                    linked_docket_id TEXT,
                    order_qty REAL,
                    order_min REAL
                )
            """)

            # 2. Track Table (History for AI)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS track (
                    track_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    docket_id TEXT,
                    process_id TEXT,
                    process_nme TEXT,
                    process_qty REAL,
                    setup_min REAL,
                    run_min REAL,
                    start_date TEXT,
                    order_id TEXT,
                    order_line_nbr TEXT
                )
            """)

            # 3. Routing Table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS docket_routing (
                    docket_id TEXT,
                    sequence INTEGER,
                    process_id TEXT,
                    routing_dsc TEXT,
                    PRIMARY KEY (docket_id, sequence)
                )
            """)

            # 4. Holidays
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS company_holidays (
                    holiday_dte TEXT PRIMARY KEY
                )
            """)
            
            # 5. Schedule View (Snapshot of future jobs)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS schedule_view (
                    docket_id TEXT,
                    process_id TEXT,
                    schedule_dte TEXT,
                    order_id TEXT,
                    order_line_nbr TEXT,
                    PRIMARY KEY (docket_id, process_id, schedule_dte)
                )
            """)

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS process (
                    process_id TEXT PRIMARY KEY,
                    process_nme,
                    capacity_1,
                    capacity_2,
                    capacity_3,
                    capacity_4,
                    capacity_5,
                    capacity_6,
                    capacity_7
                )
            """)

            conn.commit()

    def insert_schedule(self,book_data: dict):
        """Saves a dataframe to the local SQLite cache."""
        try:
            df = pd.DataFrame([book_data])
            with self._get_local_connection() as conn:
                df.to_sql("schedule_view", conn, if_exists='append', index=False)
                print(f"Successfully inserted {len(df)} rows to local schedule_view.")
            return True
        except Exception as e:
            print(f"Insert failed: {e}")

    def update_local_cache(self, table_name, df):
        """Saves a dataframe to the local SQLite cache."""
        try:
            with self._get_local_connection() as conn:
                # 'replace' will overwrite the table with new live data
                # 'append' would keep adding history
                df.to_sql(table_name, conn, if_exists='replace', index=False)
                print(f"Successfully cached {len(df)} rows to local {table_name}.")
        except Exception as e:
            print(f"Cache update error: {e}")

    def perform_full_sync(self):
        """Fetches all primary data from SQL Server and refreshes the local SQLite cache."""
        print("Starting Full Cache Sync...")
        conn = self._get_connection()
        if not conn:
            print("Sync failed: No connection to live SQL Server.")
            return False

        try:
            # Table 1: Docket Metadata
            dockets = pd.read_sql("SELECT * FROM docket", conn)
            self.update_local_cache("docket", dockets)

            # Table 2: Recent History (last 4 years for AI)
            track_query = "SELECT * FROM track WHERE start_date > DATEADD(year, -4, GETDATE())"
            track = pd.read_sql(track_query, conn)
            self.update_local_cache("track", track)

            # Table 3: Routing
            routing = pd.read_sql("SELECT * FROM docket_routing", conn)
            self.update_local_cache("docket_routing", routing)

            # Table 4: Holidays
            holidays = pd.read_sql("SELECT * FROM company_holidays", conn)
            self.update_local_cache("company_holidays", holidays)

            # Table 5: Holidays
            schedule = pd.read_sql("SELECT * FROM schedule_view", conn)
            self.update_local_cache("schedule_view", schedule)
            
            # Table 6: Holidays
            process = pd.read_sql("SELECT * FROM process", conn)
            self.update_local_cache("process", process)
            
            print("Full Sync Complete!")
            return True
        except Exception as e:
            print(f"Sync Error: {e}")
            return False
        finally:
            conn.close()

    def safe_fetch(self, query, params=None):
        """
        The Master Fetcher: 
        Tries SQL Server first. If it fails, tries Local SQLite.
        """
        # 1. Try Primary (SQL Server)
        if not self.test_mode:
            conn = self._get_connection()
            if conn:
                try:
                    # print("Fetching from Live Production SQL...")
                    df = pd.read_sql(query, conn, params=params if params else [])
                    conn.close()
                    # OPTIONAL: Update local cache whenever a live fetch succeeds
                    # self.sync_to_local(df, "cache_table") 

                    return df
                except Exception as e:
                    print(f"SQL Execution Error: {e}")
        
        # 2. Fallback (SQLite)
        print("⚠️ NETWORK DOWN: Switching to Local SQLite Cache...")
        if not os.path.exists(self.local_db_path):
            print("No local cache found.")
            return pd.DataFrame()

        try:
            with self._get_local_connection() as local_conn:
                # SQLite uses '?' as placeholders, same as pyodbc, 
                # but syntax for some functions (like GETDATE()) differs.
                # We fix the query syntax for SQLite compatibility:
                local_query = self._convert_to_sqlite_syntax(query)
                return pd.read_sql(local_query, local_conn, params=params if params else [])
        except Exception as e:
            print(f"Local SQLite Error: {e}")
            return pd.DataFrame()
        
    def _convert_to_sqlite_syntax(self, query):
        """Translates SQL Server specific keywords to SQLite equivalents."""
        replacements = {
            "GETDATE()": "date('now')",
            "DATEADD(year, -4, GETDATE())": "date('now', '-4 years')",
            "DATEADD(YEAR, -1, GETDATE())": "date('now', '-1 year')",
            "ISNULL": "IFNULL",
            "STRING_AGG": "GROUP_CONCAT",
            "WITHIN GROUP (ORDER BY sequence)": "", # SQLite doesn't use this clause
            "WITHIN GROUP (ORDER BY dr.sequence)": "",
            "CAST(GETDATE() AS DATE)": "date('now')",
            "CAST(t.start_date AS DATE)": "date(t.start_date)",
            "CAST(s.schedule_dte AS DATE)": "date(s.schedule_dte)",
            "DECIMAL(18,1)": "REAL",
            "DECIMAL(18,2)": "REAL"
        }
        for sql_term, lite_term in replacements.items():
            query = query.replace(sql_term, lite_term)
        return query
    
    def fetch_ai_training_data(self):
        """Pulls dataset for AI Training. Links Style, Routing, and SQFPM."""
        query = """
            WITH RoutingPaths AS (
                SELECT 
                    docket_id, 
                    STRING_AGG(CAST(process_id AS VARCHAR), '->') 
                    WITHIN GROUP (ORDER BY sequence) as full_path
                FROM docket_routing
                GROUP BY docket_id
            ),
            StyleBaselines AS (
                -- Get the baseline SQFPM for each style
                SELECT 
                    style_id, 
                    AVG(CAST(sqfpm AS FLOAT)) as avg_style_sqfpm
                FROM docket
                GROUP BY style_id
            )
            SELECT 
                t.process_id,
                d.style_id,
                d.printing_id,
                rp.full_path, 
                t.process_qty as Qty,
                d.sqfpm,
                t.setup_min as Setup,
                t.run_min as Run
            FROM track t
            JOIN docket d ON d.docket_id = t.docket_id
            JOIN RoutingPaths rp ON rp.docket_id = d.docket_id
            JOIN StyleBaselines sb ON sb.style_id = d.style_id
            WHERE t.run_min > 0 
            AND d.sqfpm > 0 
            -- Similarity Logic: Filter for 80% to 110% of style average
            -- 0.7-0.85 (possible good version)
            AND d.sqfpm >= (sb.avg_style_sqfpm * 0.70)
            AND d.sqfpm <= (sb.avg_style_sqfpm * 0.85)
            AND t.start_date > DATEADD(year, -4, GETDATE());
        """
        try:
            with self._get_connection() as conn:
                # return pd.read_sql(query, conn)
                return self.safe_fetch(query)
        except Exception as e:
            print(f"AI Training Data Fetch Error: {e}")
            return pd.DataFrame()

    def fetch_docket_history_all(self, docket_id=None, style_id=None):
        """
        Fetches general performance history for UI display.
        (Renamed from fetch_docket_history to avoid name collision)
        """
        query = """
            SELECT 
                t.process_id,
                d.style_id,
                d.sqfpm,
                CAST(t.start_date AS DATE) as [Date],
                t.process_nme as Process,
                t.setup_min as [Setup],
                t.run_min as [Run],
                t.process_qty as [Qty],
                CAST(t.process_qty / NULLIF(t.run_min, 0) AS DECIMAL(18,1)) as [Speed],
                CAST(t.process_qty * (d.sqfpm / 1000.0) AS DECIMAL(18,2)) as [MSF]
            FROM track t
            JOIN docket d ON d.docket_id = t.docket_id
            WHERE t.run_min > 0
        """
        params = []
        if docket_id:
            query += " AND t.docket_id = ?"
            params.append(str(docket_id))
        elif style_id:
            query += " AND d.style_id = ?"
            params.append(str(style_id))
        else:
            return pd.DataFrame()
            
        query += " ORDER BY t.start_date DESC"

        try:
            # with self._get_connection() as conn:
                # return pd.read_sql(query, conn, params=tuple(params))
            return self.safe_fetch(query, params=tuple(params))
        except Exception as e:
            print(f"History Fetch Error: {e}")
            return pd.DataFrame()

    def get_docket_metadata(self, docket_id):
        """Retrieves metadata for the docket being currently scheduled."""
        query = "SELECT style_id, printing_id, sqfpm FROM docket WHERE docket_id = ?"
        try:
            # with self._get_connection() as conn:
            # res = pd.read_sql(query, conn, params=[str(docket_id)])
            res = self.safe_fetch(query, params=[str(docket_id)])
            if not res.empty:
                return res['style_id'].iloc[0],res['printing_id'].iloc[0], float(res['sqfpm'].iloc[0])
            return None,None, 1000.0
        except Exception as e:
            print(f"Style/Printing/SQFPM Fetch Error: {e}")
            return None,None, 1000.0

    def fetch_booked_and_holidays_and_process(self):
        """
        Fetches all future booked jobs with their correct routing paths and 
        remaining quantities to allow for one-time AI caching.
        """
        booked_query = """
            WITH LinkedRouting AS (
                SELECT DISTINCT
                    d.docket_id,
                    d.style_id,
                    d.printing_id,
                    d.sqfpm,
                    CASE 
                        WHEN d.linked_docket_id > 0 THEN d.linked_docket_id 
                        ELSE d.docket_id 
                    END AS routing_source_id
                FROM docket d
            ),
            PathAssembly AS (
                SELECT 
                    lr.docket_id,
                    STRING_AGG(CAST(dr.process_id AS VARCHAR), '->') 
                        WITHIN GROUP (ORDER BY dr.sequence) AS full_path
                FROM LinkedRouting lr
                JOIN docket_routing dr 
                    ON dr.docket_id = lr.routing_source_id
                GROUP BY lr.docket_id
            ),
            TrackSummary AS (
                SELECT
                    order_id,
                    order_line_nbr,
                    process_id,
                    SUM(process_qty) AS process_qty
                FROM track
                GROUP BY order_id, order_line_nbr, process_id
            )
            SELECT 
                s.process_id, 
                CAST(s.schedule_dte AS DATE) AS schedule_date,
                s.docket_id,
                lr.style_id,
                lr.printing_id,
                pa.full_path,
                ISNULL(t.process_qty, 0) AS process_qty,
                lr.sqfpm,

                /* Remaining quantity */
                CASE 
                    WHEN s.order_qty - ISNULL(t.process_qty,0) < 0 THEN 0
                    ELSE s.order_qty - ISNULL(t.process_qty,0)
                END AS job_qty,

                /* Total minutes = setup + run */
                s.setup_time 
                + (
                    CASE 
                        WHEN s.run_speed > 0 THEN
                            (
                                CASE 
                                    WHEN s.order_qty - ISNULL(t.process_qty,0) < 0 THEN 0
                                    ELSE s.order_qty - ISNULL(t.process_qty,0)
                                END
                            ) *1.0 / s.run_speed * 60
                        ELSE 0
                    END
                ) AS total_time,

                /* MSF */
                (
                    CASE 
                        WHEN s.order_qty - ISNULL(t.process_qty,0) < 0 THEN 0
                        ELSE s.order_qty - ISNULL(t.process_qty,0)
                    END
                ) * lr.sqfpm / 1000.0 AS msf

            FROM schedule_view s
            LEFT JOIN LinkedRouting lr 
                ON s.docket_id = lr.docket_id
            LEFT JOIN PathAssembly pa 
                ON s.docket_id = pa.docket_id
            LEFT JOIN TrackSummary t 
                ON s.order_id = t.order_id 
            AND s.order_line_nbr = t.order_line_nbr 
            AND s.process_id = t.process_id
            WHERE s.schedule_dte >= CAST(GETDATE() AS DATE)
            AND ISNULL(t.process_qty, 0) <= s.order_min
            ORDER BY s.schedule_dte ASC;
        """
        hol_query = "SELECT holiday_dte FROM company_holidays"

        process_query = """SELECT 
            process_id, process_nme, capacity_1,
            capacity_2, capacity_3, capacity_4, 
            capacity_5, capacity_6, capacity_7
            FROM process"""

        try:
            # with self._get_connection() as conn:
            # 1. Fetch raw jobs with routing strings and qty
            raw_booked = self.safe_fetch(booked_query)

            process_config = self.safe_fetch(process_query)
            
            # 2. Fetch Holidays
            holidays_df = self.safe_fetch(hol_query)
            hol_list = pd.to_datetime(holidays_df["holiday_dte"]).dt.date.tolist()
            
            # Ensure the date column is clean for Python comparisons
            raw_booked['schedule_date'] = pd.to_datetime(raw_booked['schedule_date']).dt.date
            
            return raw_booked, hol_list, process_config
                
        except Exception as e:
            print(f"Capacity Cache SQL Error: {e}")
            return pd.DataFrame(columns=[
                'process_id', 'schedule_date', 'docket_id', 'style_id', 'full_path', 'sqfpm', 'job_qty'
            ]), [], []
    
    def fetch_docket_history(self, docket_id):
        """Fetches performance history for a specific docket across all its processes."""
        query = """
            SELECT 
                CAST(t.start_date AS DATE) as [Date],
                t.process_nme as [Process], -- Added process name since one docket has many steps
                t.setup_min as [Setup],
                CAST(t.process_qty / NULLIF(t.run_min, 0) AS DECIMAL(18,1)) as [Speed],
                CAST(t.process_qty * (d.sqfpm / 1000.0) AS DECIMAL(18,2)) as [MSF]
            FROM track t
            JOIN docket d ON d.docket_id = t.docket_id
            WHERE t.docket_id = ? AND t.run_min > 0
            ORDER BY t.start_date DESC
        """
        try:
            # with self._get_connection() as conn:
                # Ensure docket_id is passed as a string to match SQL types if necessary
                # return pd.read_sql(query, conn, params=[str(docket_id)])
            return self.safe_fetch(query, params=[str(docket_id)])
        except Exception as e:
            print(f"History SQL Error for Docket {docket_id}: {e}")
            return pd.DataFrame(columns=['Date', 'Process', 'Setup', 'Speed', 'MSF'])
    
    def fetch_capacity(self):
        query = """
        
        """

    def fetch_on_time_report(self):
        query = """
            WITH FinishedTagCTE AS (
                SELECT
                    order_id,
                    order_line_nbr,
                    MAX(CAST(finish_dte AS DATE)) AS finished_date,
                    SUM(finish_qty) AS finished_qty
                FROM finished_goods
                GROUP BY order_id, order_line_nbr
            )

            SELECT
                c.customer_nme
                , oh.customer_id
                , od.order_id
                , od.order_line_nbr
                , od.docket_id
                , CASE  
                    WHEN p.printing_dsc LIKE '%Digital%' THEN 'Digital'
                    WHEN p.printing_dsc LIKE '%Flexo%' THEN 'Flexo'
                    ELSE 
                        'Plain'
                    END AS printing_style
                , CAST(oh.order_dte as date) AS order_date
                , CAST(s.ship_date AS DATE) AS ship_date
                , CAST(od.requested_dte AS DATE) AS requested_date
                , CASE
                    WHEN s.days_diff_workdays >= 2 THEN 'Early'

                    WHEN s.days_diff_workdays >= 0
                        AND dsd.delivery_status_dsc IN ('OT', 'CRB')
                        THEN 'On Time'

                    WHEN s.days_diff_workdays < 0  
                        THEN 
                            CASE  
                                WHEN dsd.delivery_status_dsc IN ('OT', 'CRB') THEN 'Late - Other'
                            ELSE dsd.delivery_status_dsc
                            END
                    ELSE ISNULL(dsd.delivery_status_dsc, 'Late - Other')
                END AS on_time_dsc
                ,CASE
                    WHEN s.days_diff_workdays >= 0 THEN 1
                    ELSE -1
                END AS on_time_code
                ,s.days_diff_workdays
                , CASE 
                    WHEN oh.order_dte IS NULL THEN 0
                    ELSE
                            DATEDIFF(day, CAST(pr.receipt_dte AS DATE), CAST(od.scheduled_dte AS DATE))
                        - (DATEDIFF(week, CAST(oh.order_dte AS DATE), CAST(od.scheduled_dte AS DATE)) * 2)
                        - CASE WHEN DATENAME(weekday, pr.receipt_dte) = 'Sunday' THEN 1 ELSE 0 END
                        - CASE WHEN DATENAME(weekday, od.scheduled_dte) = 'Saturday' THEN 1 ELSE 0 END
                END AS num_days
                ,oh.order_user_id
                ,CONCAT(RTRIM(u.user_first_name), ' ', RTRIM(u.user_last_name))
                ,oh.status_id
            FROM order_details od

            LEFT JOIN FinishedTagCTE ftc
                ON od.order_id = ftc.order_id
            AND od.order_line_nbr = ftc.order_line_nbr
            LEFT JOIN delivery_status_dsc dsd
                ON od.delivery_status_id = dsd.delivery_status_id
            LEFT JOIN order_header oh
                ON od.order_id = oh.order_id
            LEFT JOIN customer c
                ON oh.customer_id = c.customer_id
            LEFT JOIN users u  
                ON oh.order_user_id = u.[user_id]
            LEFT JOIN docket d  
                ON od.docket_id = d.docket_id
            LEFT JOIN printing_dsc p  
                ON d.printing_id = p.printing_id
            LEFT JOIN purchase_details pd    
                ON od.order_id = pd.order_id AND od.order_line_nbr = pd.order_line_nbr
            LEFT JOIN purchase_receipts pr  
                ON pd.purchase_id = pr.purchase_id AND pd.purchase_line_nbr = pr.purchase_line_nbr

            CROSS APPLY (
                SELECT
                    -- 1️⃣ Final ship date
                    CASE
                        WHEN ftc.finished_date IS NOT NULL THEN ftc.finished_date
                        WHEN oh.status_id = 3 THEN
                            CASE
                                WHEN DATENAME(weekday, od.scheduled_dte) = 'Friday' THEN DATEADD(day, 3, od.scheduled_dte)
                                WHEN DATENAME(weekday, od.scheduled_dte) = 'Saturday' THEN DATEADD(day, 2, od.scheduled_dte)
                                ELSE DATEADD(day, 1, od.scheduled_dte)
                            END
                        ELSE CAST(od.scheduled_dte AS DATE)
                    END AS ship_date,

                    -- 2️⃣ Working-day difference
                    CASE
                        WHEN ftc.finished_date IS NULL AND oh.status_id = 4 THEN
                            DATEDIFF(day, od.scheduled_dte, CAST(od.requested_dte AS DATE))
                        - (DATEDIFF(week, od.scheduled_dte, CAST(od.requested_dte AS DATE)) * 2)
                        - CASE WHEN DATENAME(weekday, od.scheduled_dte) = 'Sunday' THEN 1 ELSE 0 END
                        - CASE WHEN DATENAME(weekday, od.requested_dte) = 'Saturday' THEN 1 ELSE 0 END
                        ELSE
                            DATEDIFF(day,
                                CASE
                                    WHEN ftc.finished_date IS NOT NULL THEN ftc.finished_date
                                    WHEN oh.status_id = 3 THEN
                                        CASE
                                            WHEN DATENAME(weekday, od.scheduled_dte) = 'Friday' THEN DATEADD(day, 3, od.scheduled_dte)
                                            WHEN DATENAME(weekday, od.scheduled_dte) = 'Saturday' THEN DATEADD(day, 2, od.scheduled_dte)
                                            ELSE DATEADD(day, 1, od.scheduled_dte)
                                        END
                                    ELSE CAST(od.scheduled_dte AS DATE)
                                END,
                                CAST(od.requested_dte AS DATE)
                            )
                        - (DATEDIFF(week,
                                CASE
                                    WHEN ftc.finished_date IS NOT NULL THEN ftc.finished_date
                                    ELSE CAST(od.scheduled_dte AS DATE)
                                END,
                                CAST(od.requested_dte AS DATE)
                            ) * 2)
                        - CASE WHEN DATENAME(weekday,
                                CASE
                                    WHEN ftc.finished_date IS NOT NULL THEN ftc.finished_date
                                    ELSE CAST(od.scheduled_dte AS DATE)
                                END
                            ) = 'Sunday' THEN 1 ELSE 0 END
                        - CASE WHEN DATENAME(weekday, od.requested_dte) = 'Saturday' THEN 1 ELSE 0 END
                    END AS days_diff_workdays
            ) s


            WHERE
                (oh.status_id IN (3, 4))
                AND od.requested_dte >= DATEFROMPARTS(YEAR(GETDATE()), 1, 1)
                AND od.requested_dte <  DATEADD(week, DATEDIFF(week, 0, GETDATE()), 0);

        """
        try:
            return self.safe_fetch(query)
        except Exception as e:
            print(f"On Time delivery Query Error: {e}")
            return pd.DataFrame()

    def fetch_completed_orders(self):
        query ="""
        WITH FinishedTagCTE AS(   
                    SELECT
                        order_id,
                        order_line_nbr,
                        MAX(CAST(finish_dte AS DATE)) AS finished_date,
                        SUM(finish_qty) AS finished_qty
                    FROM finished_goods
                    GROUP BY order_id, order_line_nbr
                )
                SELECT od.order_id
                    ,od.order_line_nbr
                    ,od.docket_id
                    ,CAST(od.scheduled_dte AS DATE) AS ship_date
                    ,CAST(od.requested_dte AS DATE) AS requested_date
                    ,dsd.delivery_status_dsc AS on_time_code
                    -- Workday Logic
                    ,CASE 
                        WHEN ftc.finished_date IS NULL THEN NULL 
                        ELSE (DATEDIFF(dd, ftc.finished_date, CAST(od.requested_dte AS DATE)))
                                -(DATEDIFF(wk, ftc.finished_date, CAST(od.requested_dte AS DATE)) * 2)
                                -(CASE WHEN DATENAME(dw, ftc.finished_date) = 'Sunday' THEN 1 ELSE 0 END)
                                -(CASE WHEN DATENAME(dw, od.requested_dte) = 'Saturday' THEN 1 ELSE 0 END)
                    END AS days_diff_workdays
                FROM order_details od
                LEFT JOIN FinishedTagCTE ftc 
                    ON od.order_id = ftc.order_id AND od.order_line_nbr = ftc.order_line_nbr
                LEFT JOIN delivery_status_dsc dsd  
                    ON od.delivery_status_id = dsd.delivery_status_id
                LEFT JOIN order_header oh   
                    ON od.order_id = oh.order_id
                WHERE oh.status_id = 4
                -- DYNAMIC PREVIOUS WEEK FILTER
                AND od.requested_dte >= DATEADD(week, DATEDIFF(week, 0, GETDATE()) - 1, 0)
                AND od.requested_dte <  DATEADD(week, DATEDIFF(week, 0, GETDATE()), 0)
        """
        try:
            return self.safe_fetch(query)
        except Exception as e:
            print(f"On Time delivery Query Error: {e}")
            return pd.DataFrame()

    def fetch_raw_capacity(self):
        """Fetches the raw history needed for the CapacityEngine's P80 math."""
        query = """
        SELECT 
            t.process_id, 
            CAST(t.start_date AS DATE) as work_date,
            COUNT(DISTINCT t.docket_id) as job_count, -- Required for matrix grouping
            SUM(t.process_qty * (d.sqfpm / 1000.0)) as daily_msf -- The missing column
        FROM track t 
        JOIN docket d ON d.docket_id = t.docket_id
        WHERE t.run_min > 0 AND t.start_date >= DATEADD(YEAR, -1, GETDATE())
        GROUP BY t.process_id, CAST(t.start_date AS DATE)
        """
        try:
            # with self._get_connection() as conn:
                # df = pd.read_sql(query, conn)
            df = self.safe_fetch(query)
            if df.empty:
                # Return empty DF with required columns to prevent ValueError
                return pd.DataFrame(columns=['process_id', 'job_count', 'daily_msf'])
            return df
        except Exception as e:
            print(f"Capacity Query Error: {e}")
            return pd.DataFrame(columns=['process_id', 'job_count', 'daily_msf'])
        
    def fetch_docket_routing(self, docket_id, qty):
        """Fetches clean routing using CTE to prevent duplicates."""
        query = """
        WITH RankedRouting AS (
            SELECT 
                dr.sequence AS seq_order, 
                dr.process_id AS process_id, 
                dr.routing_dsc AS process_name,
                CAST(? AS FLOAT) * (d.sqfpm / 1000.0) AS run_sqft,
                d.sqfpm,
                ROW_NUMBER() OVER (PARTITION BY dr.sequence ORDER BY dr.process_id) as route_rank
            FROM docket d
            JOIN docket_routing dr ON dr.docket_id = CASE 
                WHEN d.linked_docket_id > 0 THEN d.linked_docket_id 
                ELSE d.docket_id 
            END
            WHERE d.docket_id = ?
        )
        SELECT 
            seq_order, 
            process_id, 
            process_name,
            sqfpm, 
            run_sqft
        FROM RankedRouting
        WHERE route_rank = 1
        ORDER BY seq_order;
        """
        try:
            # with self._get_connection() as conn:
            #     # Parameters: 1st is Qty, 2nd is Docket_ID
            #     # return pd.read_sql(sql, conn, params=(qty, str(docket_id)))
            return self.safe_fetch(query,params=(qty, str(docket_id)))
        except Exception as e:
            print(f"Routing Query Error: {e}")
            return pd.DataFrame(columns=['seq_order', 'process_id', 'process_name', 'run_sqft'])