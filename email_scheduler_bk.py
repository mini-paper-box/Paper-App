import sqlite3
import win32com.client as win32
from datetime import datetime, timedelta

class SchedulerMailer:
    def __init__(self, db_path=r"C:\Users\sang.n\OneDrive - whitebird.ca\Paper App\prod_db.db"):
        """
        Initialize SchedulerMailer with database path.
        """
        self.db_path = db_path

    def run_schedule(self, job_size, process_ids, max_consec_days=15, skip_weekdays=7):
        """
        Execute the scheduling query for a given job size and ordered process IDs.
        Returns list of tuples with schedule results.
        """
        # Build process sequence
        values = ",\n        ".join(f"({i+1}, {pid})" for i, pid in enumerate(process_ids))

        # Precompute lookahead days for future_dates
        lookahead_days = skip_weekdays + 60  # matches previous logic

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
                COALESCE(pc.max_sqft,
                        (SELECT max_sqft FROM process_capacity
                        WHERE process_name = p.process_name AND date IS NULL)
                )
                - COALESCE((
                    SELECT SUM(CAST(o.msf AS REAL))
                    FROM order_routing o
                    WHERE o.process_nme = p.process_name
                    AND substr(o.scheduled_dte,1,10) = fd.d
                ),0) AS available_sqft
            FROM future_workdays fd
            JOIN process_list p
            LEFT JOIN process_capacity pc
                ON pc.date = fd.d AND pc.process_name = p.process_name
        ),
        windows AS (
            SELECT 
                seq_order,
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
                w.seq_order,
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
            WHERE w.total_available < {job_size}
            AND w.days_used < {max_consec_days}
        ),
        feasible_windows AS (
            SELECT *
            FROM windows
            WHERE total_available >= {job_size}
        ),
        chain AS (
            SELECT
                f.seq_order,
                f.process_name,
                f.start_date,
                f.end_date,
                f.total_available,
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
                n.total_available,
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
            ch.total_available,
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
        """
        Send a modern HTML table email via Outlook.

        :param to: Recipient email(s), comma-separated
        :param subject: Email subject
        :param data_rows: List of tuples/lists, each row must have 3 columns
        :param cc: CC email(s), optional
        :param attachments: List of file paths, optional
        """
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
                        <table width="800" cellpadding="0" cellspacing="0" border="0" style="background-color:#ffffff; border-radius:8px; overflow:hidden;">
                            <tr>
                                <td style="background-color:#4CAF50; color:#ffffff; padding:20px; text-align:center; font-size:24px;">
                                    {subject}
                                </td>
                            </tr>
                            <tr>
                                <td style="padding:20px;">
                                    <p style="margin:0 0 20px 0;">The purpose of this timeline standard is to eliminate the back and forth between sales and order management and allow order management to respond quickly with order due dates.</p>
                                    <table width="100%" cellpadding="8" cellspacing="0" border="0" style="border-collapse:collapse;">
                                        <tr>
                                            <th style="background-color:#f0f0f0; border:1px solid #ddd; text-align:left;">Process</th>
                                            <th style="background-color:#f0f0f0; border:1px solid #ddd; text-align:left;">Leadtime</th>
                                            <th style="background-color:#f0f0f0; border:1px solid #ddd; text-align:left;">Ship Date</th>
                                        </tr>
        """
        for i, row in enumerate(data_rows):
            bg_color = "#ffffff" if i % 2 == 0 else "#f9f9f9"
            html += f"""
                <tr>
                    <td style="border:1px solid #ddd; background-color:{bg_color};">{row[0]}</td>
                    <td style="border:1px solid #ddd; background-color:{bg_color};">{row[1]}</td>
                    <td style="border:1px solid #ddd; background-color:{bg_color};">{row[2]}</td>
                </tr>
            """

        html += """
                                    </table>
                                    <p style="margin:20px 0 0 0;">Best regards,<br>Moyy Design</p>
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
        print("Email prepared successfully via Outlook!")

# ================= Example usage =================

def add_workdays(start_date, days):
    """Add 'days' workdays to start_date, skipping weekends."""
    current = start_date
    added = 0
    while added < days:
        current += timedelta(days=1)
        if current.weekday() < 5:  # 0=Monday, 6=Sunday
            added += 1
    return current

def workdays_between(start_date, end_date):
    """Count number of workdays between two dates, inclusive of start_date, exclusive of end_date."""
    current = start_date
    workdays = 0
    while current < end_date:
        if current.weekday() < 5:
            workdays += 1
        current += timedelta(days=1)
    return workdays

if __name__ == "__main__":
    scheduler = SchedulerMailer(db_path=r"C:\Users\sang.n\OneDrive - whitebird.ca\Paper App\prod_db.db")

    # Run multiple schedules
    elitron = scheduler.run_schedule(10000, [231])
    eterna = scheduler.run_schedule(30000, [3])
    langston = scheduler.run_schedule(100000, [1])
    united = scheduler.run_schedule(100000, [2])
    elitron_glue = scheduler.run_schedule(10000, [231,45])
    eterna_langston = scheduler.run_schedule(30000, [3, 1])
    united_langston = scheduler.run_schedule(60000, [2, 1])


    nozomi = scheduler.run_schedule(40000, [6])
    nozomi_elitron = scheduler.run_schedule(10000, [6, 13])
    nozomi_eterna = scheduler.run_schedule(30000, [6, 3])
    nozomi_united = scheduler.run_schedule(50000, [6, 2])
    nozomi_eterna_langston = scheduler.run_schedule(30000, [6, 3,1])
    nozomi_united_langston = scheduler.run_schedule(60000, [6,2, 1])

    nozomi,nozomi_elitron,nozomi_eterna,nozomi_united,nozomi_eterna_langston,nozomi_united_langston

    email_rows = []
    today = datetime.today().date()

    for sch in [eterna, langston, united,eterna_langston, united_langston,nozomi,nozomi_elitron,nozomi_eterna,nozomi_united,nozomi_eterna_langston,nozomi_united_langston]:
        if len(sch) == 2:
            # Concatenate first word of process names
            process_name = f"{sch[0][1].split()[0]} → {sch[1][1].split()[0]}"
            end_date = datetime.strptime(sch[1][3], "%Y-%m-%d").date()
            lead_days = workdays_between(today, end_date)
            ship_date = add_workdays(end_date, 1)
            email_rows.append((process_name, f"{lead_days} workdays", ship_date.strftime("%Y-%m-%d")))
        elif len(sch) == 3:
            # Concatenate first word of process names
            process_name = f"{sch[0][1].split()[0]} → {sch[1][1].split()[0]} → {sch[2][1].split()[0]} "
            end_date = datetime.strptime(sch[2][3], "%Y-%m-%d").date()
            lead_days = workdays_between(today, end_date)
            ship_date = add_workdays(end_date, 1)
            email_rows.append((process_name, f"{lead_days} workdays", ship_date.strftime("%Y-%m-%d")))
        else:
            for row in sch:
                process_name = row[1].split()[0]  # first word only
                end_date = datetime.strptime(row[3], "%Y-%m-%d").date()
                lead_days = workdays_between(today, end_date)
                ship_date = add_workdays(end_date, 1)
                email_rows.append((process_name, f"{lead_days} workdays", ship_date.strftime("%Y-%m-%d")))

        # Optional separator
        email_rows.append(("---", "---", "---"))


    # Send email
    scheduler.send_email(
        to="sang.n@whitebird.ca;allen.g@whitebird.ca;erin.l@moyydesign.com;catherine.s@moyydesign.com",
        subject=f"TIMELINE AGREEMENT {today}",
        data_rows=email_rows
    )