import sqlite3
import win32com.client as win32
from datetime import datetime, timedelta

class SchedulerMailer:
    def __init__(self, db_path=r"C:\Users\sang.n\OneDrive - whitebird.ca\Paper App\prod_db.db"):
        """Initialize SchedulerMailer with database path."""
        self.db_path = db_path

    def run_schedule(self, job_size, process_ids, max_consec_days=15, skip_weekdays=8, num_jobs=1):
        """Execute scheduling query for given job size and process IDs.
        
        Args:
            job_size: Required square footage
            process_ids: List of process IDs to route through
            max_consec_days: Maximum consecutive days per window
            skip_weekdays: Workdays to skip before scheduling
            num_jobs: Number of jobs (for capacity check)
        
        Returns:
            List of schedule result tuples
        """
        values = ",\n        ".join(f"({i+1}, {pid})" for i, pid in enumerate(process_ids))
        lookahead_days = skip_weekdays + 60

        sql = f"""
        WITH process_sequence(seq_order, pid) AS (
            VALUES {values}
        ),
        process_list AS (
            SELECT p.id, p.process_name, s.seq_order
            FROM process_sequence s
            JOIN process p ON p.id = s.pid
            ORDER BY s.seq_order
        ),
        process_count AS (
            SELECT COUNT(*) AS n FROM process_list
        ),
        future_dates AS (
            SELECT date('now') AS d, 0 AS weekday_count
            UNION ALL
            SELECT date(d, '+1 day'),
                CASE 
                    WHEN strftime('%w', date(d, '+1 day')) NOT IN ('0','6')
                        AND NOT EXISTS (SELECT 1 FROM holiday h WHERE h.date = date(d, '+1 day'))
                    THEN weekday_count + 1
                    ELSE weekday_count
                END
            FROM future_dates
            WHERE weekday_count < {lookahead_days}
        ),
        future_workdays AS (
            SELECT d
            FROM future_dates
            WHERE weekday_count >= {skip_weekdays}
            AND strftime('%w', d) NOT IN ('0','6')
            AND NOT EXISTS (SELECT 1 FROM holiday h WHERE h.date = d)
        ),
        capacity_per_day AS (
            SELECT 
                fd.d AS date,
                p.seq_order,
                p.process_name,
                -- Get max_sqft: try date-specific first, then fall back to default (NULL date)
                (SELECT COALESCE(
                    (SELECT max_sqft FROM process_capacity 
                     WHERE process_name = p.process_name AND date = fd.d LIMIT 1),
                    (SELECT max_sqft FROM process_capacity 
                     WHERE process_name = p.process_name AND date IS NULL LIMIT 1)
                ))
                - COALESCE((SELECT SUM(CAST(o.msf AS REAL))
                            FROM order_routing o
                            WHERE o.process_nme = p.process_name
                            AND substr(o.schedule_dte,1,10) = fd.d),0) AS available_sqft,
                -- Get max_jobs: try date-specific first, then fall back to default (NULL date)
                (SELECT COALESCE(
                    (SELECT max_jobs FROM process_capacity 
                     WHERE process_name = p.process_name AND date = fd.d LIMIT 1),
                    (SELECT max_jobs FROM process_capacity 
                     WHERE process_name = p.process_name AND date IS NULL LIMIT 1)
                ))
                - COALESCE((SELECT COUNT(*) AS num_jobs
                            FROM order_routing o
                            WHERE o.process_nme = p.process_name
                            AND substr(o.schedule_dte,1,10) = fd.d),0) AS available_jobs
            FROM future_workdays fd
            CROSS JOIN process_list p
        ),
        windows AS (
            SELECT 
                seq_order,
                process_name,
                date AS start_date,
                date AS end_date,
                available_sqft,
                available_sqft AS total_available_sqft,
                available_jobs AS total_available_jobs,
                1 AS days_used,
                date || ':' || available_sqft || 'sqft/' || available_jobs || 'jobs' AS breakdown
            FROM capacity_per_day
            WHERE available_sqft > 0 OR available_jobs > 0

            UNION ALL

            SELECT
                w.seq_order,
                w.process_name,
                w.start_date,
                c.date AS end_date,
                c.available_sqft,
                w.total_available_sqft + c.available_sqft AS total_available_sqft,
                w.total_available_jobs + c.available_jobs AS total_available_jobs,
                w.days_used + 1 AS days_used,
                w.breakdown || ' | ' || c.date || ':' || c.available_sqft || 'sqft/' || c.available_jobs || 'jobs' AS breakdown
            FROM windows w
            JOIN capacity_per_day c
            ON c.process_name = w.process_name
            AND c.date = (
                SELECT MIN(fd2.date)
                FROM capacity_per_day fd2
                WHERE fd2.process_name = w.process_name
                    AND fd2.date > w.end_date
                    AND (fd2.available_sqft > 0 OR fd2.available_jobs > 0)
            )
            WHERE (w.total_available_sqft < {job_size} AND w.total_available_jobs < {num_jobs})
            AND w.days_used < {max_consec_days}
        ),
        feasible_windows AS (
            SELECT *
            FROM windows
            WHERE total_available_sqft >= {job_size} OR total_available_jobs >= {num_jobs}
        ),
        chain AS (
            SELECT
                f.seq_order,
                f.process_name,
                f.start_date,
                f.end_date,
                f.total_available_sqft,
                f.total_available_jobs,
                f.breakdown,
                f.start_date AS chain_start,
                f.end_date AS chain_end
            FROM feasible_windows f
            WHERE f.seq_order = 1
            AND f.start_date = (SELECT MIN(start_date) FROM feasible_windows WHERE seq_order = 1)
            AND f.end_date = (
                SELECT MIN(end_date)
                FROM feasible_windows
                WHERE seq_order = 1
                    AND start_date = (SELECT MIN(start_date) FROM feasible_windows WHERE seq_order = 1)
            )

            UNION ALL

            SELECT
                n.seq_order,
                n.process_name,
                n.start_date,
                n.end_date,
                n.total_available_sqft,
                n.total_available_jobs,
                n.breakdown,
                ch.chain_start,
                n.end_date AS chain_end
            FROM chain ch
            JOIN feasible_windows n
            ON n.seq_order = ch.seq_order + 1
            AND n.start_date >= date(ch.end_date, '+1 day')
            WHERE n.start_date = (
                SELECT MIN(start_date)
                FROM feasible_windows x
                WHERE x.seq_order = ch.seq_order + 1
                    AND x.start_date >= date(ch.end_date, '+1 day')
            )
            AND n.end_date = (
                SELECT MIN(end_date)
                FROM feasible_windows x
                WHERE x.seq_order = ch.seq_order + 1
                    AND x.start_date = (
                        SELECT MIN(start_date)
                        FROM feasible_windows y
                        WHERE y.seq_order = ch.seq_order + 1
                        AND y.start_date >= date(ch.end_date, '+1 day')
                    )
            )
        ),
        earliest_complete_chain AS (
            SELECT MIN(chain_start) AS chain_start
            FROM chain
            WHERE seq_order = (SELECT n FROM process_count)
        )
        SELECT
            ch.seq_order,
            ch.process_name,
            ch.start_date,
            ch.end_date,
            ch.total_available_sqft,
            ch.total_available_jobs,
            ch.breakdown,
            ec.chain_start AS chain_start_date,
            (SELECT MAX(end_date) 
            FROM chain 
            WHERE chain_start = ec.chain_start) AS chain_end_date
        FROM chain ch
        CROSS JOIN earliest_complete_chain ec
        WHERE ch.chain_start = ec.chain_start
        ORDER BY ch.seq_order;
        """

        conn = sqlite3.connect(self.db_path)
        cur = conn.cursor()
        cur.execute(sql)
        results = cur.fetchall()
        conn.close()
        return results

    def send_email(self, to, subject, data_rows, cc=None, attachments=None):
        """Send HTML email via Outlook with alternating colors and tier columns."""
        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
        </head>
        <body style="margin:0; padding:0; font-family: Arial, Helvetica, sans-serif; background-color:#f4f4f4;">
            <table width="100%" cellpadding="0" cellspacing="0" border="0" style="background-color:#f4f4f4; padding:20px;">
                <tr>
                    <td align="center">
                        <table width="1000" cellpadding="0" cellspacing="0" border="0" style="background-color:#ffffff; border-radius:8px; overflow:hidden;">
                            <tr>
                                <td style="background-color:#4CAF50; color:#ffffff; padding:20px; text-align:center; font-size:24px;">
                                    {subject}
                                </td>
                            </tr>
                            <tr>
                                <td style="padding:20px;">
                                    <p style="margin:0 0 20px 0; font-size:15px; line-height:1.6;">The purpose of this timeline standard is to eliminate back and forth between sales and order management, allowing order management to respond quickly with order due dates.</p>
                                    <table width="100%" cellpadding="12" cellspacing="0" border="0" style="border-collapse:collapse; font-size:14px;">
                                        <tr>
                                            <th style="background-color:#f0f0f0; border:1px solid #ddd; text-align:left; padding:12px; text-transform:uppercase; font-size:12px; letter-spacing:0.5px;">Process</th>
                                            <th style="background-color:#f0f0f0; border:1px solid #ddd; text-align:left; padding:12px; text-transform:uppercase; font-size:12px; letter-spacing:0.5px;">Tier 1 & 2 Leadtime</th>
                                            <th style="background-color:#f0f0f0; border:1px solid #ddd; text-align:left; padding:12px; text-transform:uppercase; font-size:12px; letter-spacing:0.5px;">Tier 1 & 2 Ship Date</th>
                                            <th style="background-color:#f0f0f0; border:1px solid #ddd; text-align:left; padding:12px; text-transform:uppercase; font-size:12px; letter-spacing:0.5px;">Tier 3 Leadtime</th>
                                            <th style="background-color:#f0f0f0; border:1px solid #ddd; text-align:left; padding:12px; text-transform:uppercase; font-size:12px; letter-spacing:0.5px;">Tier 3 Ship Date</th>
                                        </tr>
        """

        for i, row in enumerate(data_rows):
            bg_color = "#ffffff" if i % 2 == 0 else "#f9f9f9"
            process_name, leadtime, ship_date, chain_start, chain_end, tier_leadtime, tier_ship_date, tier_chain_start, tier_chain_end = row
            html += f"""
                <tr>
                    <td style="border:1px solid #ddd; background-color:{bg_color}; padding:12px; line-height:1.6;">{process_name}</td>
                    <td style="border:1px solid #ddd; background-color:{bg_color}; padding:12px; line-height:1.6;">
                        {tier_leadtime}<br/><small style="font-size:11px; color:#666;">({tier_chain_start} → {tier_chain_end})</small>
                    </td>
                    <td style="border:1px solid #ddd; background-color:{bg_color}; padding:12px; line-height:1.6;">{tier_ship_date}</td>
                    <td style="border:1px solid #ddd; background-color:{bg_color}; padding:12px; line-height:1.6;">
                        {leadtime}<br/><small style="font-size:11px; color:#666;">({chain_start} → {chain_end})</small>
                    </td>
                    <td style="border:1px solid #ddd; background-color:{bg_color}; padding:12px; line-height:1.6;">{ship_date}</td>
                </tr>
            """

        html += """
                                    </table>
                                    <p style="margin:20px 0 0 0; font-size:15px; line-height:1.6;">Best regards,<br>Moyy Design</p>
                                </td>
                            </tr>
                            <tr>
                                <td style="background-color:#f0f0f0; padding:10px; text-align:center; font-size:12px; color:#666;">
                                    © Moyy 2025. All rights reserved.
                                </td>
                            </tr>
                        </table>
                    </td>
                </tr>
            </table>
        </body>
        </html>
        """

        outlook = win32.Dispatch('Outlook.Application')
        mail = outlook.CreateItem(0)
        mail.To = to
        if cc:
            mail.CC = cc
        mail.Subject = subject
        mail.HTMLBody = html
        if attachments:
            for path in attachments:
                mail.Attachments.Add(path)
        mail.Display()

    def get_holidays(self):
        """Retrieve holiday dates from database."""
        with sqlite3.connect(self.db_path) as conn:
            cur = conn.cursor()
            cur.execute("SELECT date FROM holiday")
            rows = cur.fetchall()
            return {datetime.strptime(r[0], "%Y-%m-%d").date() for r in rows}

# ================= Helper Functions =================

def add_workdays(start_date, days, holidays):
    """Add 'days' workdays to start_date, skipping weekends and holidays."""
    if holidays is None:
        holidays = set()
    current_date = start_date
    while days > 0:
        current_date += timedelta(days=1)
        if current_date.weekday() < 5 and current_date not in holidays:
            days -= 1
    return current_date

def workdays_between(start_date, end_date, holidays):
    """Count workdays between start_date (inclusive) and end_date (exclusive)."""
    if holidays is None:
        holidays = set()
    day_count = 0
    current_date = start_date
    while current_date < end_date:
        current_date += timedelta(days=1)
        if current_date.weekday() < 5 and current_date not in holidays:
            day_count += 1
    return day_count

# ================= Main =================
if __name__ == "__main__":
    scheduler = SchedulerMailer()

    # CONFIGURABLE: Set the tier start offset (workdays from today)
    TIER_START_OFFSET = 5  # Change this value to adjust tier calculation start

    # Define schedules to run: (job_size, process_ids, max_days, skip_weekdays, num_jobs)
    msf = 10000
    max_days = 15
    lead = 10
    lead2 = 13
    lead3 = 13
    schedules_to_run = {
        "Eterna": (msf*2, [3], max_days, lead, 1),
        "Langston": (msf*4, [1], max_days, lead, 1),
        "United": (msf*4, [2], max_days, lead, 1),
        "Eterna_Langston": (msf*3, [3,1], max_days, lead, 1),
        "United_Langston": (msf*4, [2,1], lead, lead, 1),
        "Elitron_Strip": (msf, [13,9], max_days, lead+1, 1),
        "Elitron_Strip_Glue": (msf, [13,9,15], max_days, lead2+2, 1),
        "Nozomi": (msf*4, [6], max_days, lead3, 1),
        "Nozomi_Eterna": (msf*2, [6,3], max_days, lead3, 1),
        "Nozomi_United": (msf*5, [6,2], max_days, lead3, 1),
        "Nozomi_Langston": (msf*5, [6,1], max_days, lead3, 1),
        "Nozomi_Eterna_Langston": (msf*2, [6,3,1], max_days, lead3, 1),
        "Nozomi_United_Langston": (msf*5, [6,2,1], max_days, lead3, 1),
        "Nozomi_Elitron_Strip": (msf, [6,13,9], max_days, lead3+1, 1),
        "Nozomi_Elitron_Strip_Glue": (msf, [6,13,9,15], max_days, lead3+1, 1)
    }

    results = {}
    for name, (size, pids, consecutive_days, weekdays_lead, jobs) in schedules_to_run.items():
        results[name] = scheduler.run_schedule(size, pids, consecutive_days, weekdays_lead, jobs)

    # Build email rows dynamically
    today = datetime.today().date()
    holidays = scheduler.get_holidays()
    
    # Calculate tier start date (configurable offset from today)
    tier_start_date = add_workdays(today, TIER_START_OFFSET, holidays)
    
    email_rows = []
    for sch_name, sch in results.items():
        if not sch:
            continue
        process_names = " → ".join([row[1].split()[0] for row in sch])
        chain_start = sch[0][7]  # chain_start_date
        chain_end = sch[0][8]    # chain_end_date
        end_date = datetime.strptime(sch[-1][3], "%Y-%m-%d").date()
        
        # Regular leadtime and ship date (Tier 3)
        lead_days = workdays_between(today, end_date, holidays)
        ship_date = add_workdays(end_date, 1, holidays)
        
        # Tier 1/2 calculations: Start from tier_start_date and add 1 day per process
        num_processes = len(sch)
        tier_end_date = add_workdays(tier_start_date, num_processes, holidays)
        tier_lead_days = workdays_between(today, tier_end_date, holidays)
        tier_ship_date = add_workdays(tier_end_date, 1, holidays)
        
        email_rows.append((
            process_names, 
            f"{lead_days} workdays", 
            ship_date.strftime("%Y-%m-%d"), 
            chain_start, 
            chain_end,
            f"{tier_lead_days} workdays",
            tier_ship_date.strftime("%Y-%m-%d"),
            tier_start_date.strftime("%Y-%m-%d"), 
            tier_end_date.strftime("%Y-%m-%d")
        ))

    # Send email
    scheduler.send_email(
        to="sang.n@whitebird.ca;allen.g@whitebird.ca;erin.l@moyydesign.com;catherine.s@moyydesign.com;" \
        "john.t@whitebird.ca;tamminga@whitebird.ca;lon.s@moyydesign.com;michelle.d@moyydesign.com;becky.j@moyydesign.com;" \
        "jason.w@moyydesign.com;jason.h@moyydesign.com;hendrik@moyydesign.com;" \
        "jeff.c@moyydesign.com;ray.j@moyydesign.com;megan.h@moyydesign.com;" \
        "ryan.p@moyydesign.com;cameron.c@whitebird.ca;don.s@whitebird.ca;" \
        "caitlin@whitebird.ca;Kamaldeep.k@whitebird.ca",
        subject=f"Timeline Agreement {today}",
        data_rows=email_rows
    )