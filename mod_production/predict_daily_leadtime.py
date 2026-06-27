import win32com.client as win32
from datetime import datetime, timedelta
import pandas as pd

# Import the architectural scheduling engine we built
from mod_production.services.schedule_service import ScheduleService


class SchedulerMailer:

    def __init__(self, holidays=None, process_df=None, booked_mins_lookup=None):
        """
        Initialize SchedulerMailer with required scheduling metadata data frames.
        
        :param holidays: Set/List of datetime.date objects.
        :param process_df: Pandas DataFrame containing process capacity limits.
        :param booked_mins_lookup: Dict tracking pre-existing job allocations.
        """
        self.holidays = holidays or []
        # Instantiate the internal AI allocation scheduler
        self.scheduler = ScheduleService(
            holidays=holidays,
            process_df=process_df,
            booked_mins_lookup=booked_mins_lookup
        )

    def run_schedule(self, docket_id, qty, lead_days):
        """
        Execute prediction timeline planning via the AI capacity engine.
        
        Returns:
            List of dictionaries containing process step allocations.
        """
        # Execute production allocation directly via AI batch prediction steps
        return self.scheduler.build_schedule(
            docket_id=docket_id,
            qty=qty,
            lead_days=lead_days
        )

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
                                    <p style="margin:0 0 20px 0; font-size:15px; line-height:1.6;"> The goal of this timeline standard is to reduce back-and-forth between Sales and Order Management, enabling Order Management to provide due dates quickly and accurately. </p> <strong>Booking Large Orders</strong><ul><li>For orders above the following thresholds, do <strong>NOT</strong> use the standard timeline guidelines:</li> <ul> <li>3 processes and <strong> 25,000 </strong> sqft or more</li> <li>1 process and <strong> 50,000</strong> sqft or more</li> </ul> <li>These orders require direct coordination with Order Management for precise delivery dates.</li> </ul>
                                    <table width="100%" cellpadding="12" cellspacing="0" border="0" style="border-collapse:collapse; font-size:14px;">
                                        <tr>
                                            <th style="background-color:#f0f0f0; border:1px solid #ddd; text-align:left; padding:12px; text-transform:uppercase; font-size:12px; letter-spacing:0.5px;">Process</th>
                                            <th style="background-color:#f0f0f0; border:1px solid #ddd; text-align:left; padding:12px; text-transform:uppercase; font-size:12px; letter-spacing:0.5px;">Leadtime</th>
                                            <th style="background-color:#f0f0f0; border:1px solid #ddd; text-align:left; padding:12px; text-transform:uppercase; font-size:12px; letter-spacing:0.5px;">Ship Date</th>
                                        </tr>
        """

        for i, row in enumerate(data_rows):
            bg_color = "#ffffff" if i % 2 == 0 else "#f9f9f9"
            process_name, leadtime, ship_date, chain_start, chain_end, tier_leadtime, tier_ship_date, tier_chain_start, tier_chain_end = row
            html += f"""
                <tr>
                    <td style="border:1px solid #ddd; background-color:{bg_color}; padding:12px; line-height:1.6;">{process_name}</td>
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
                                    © Moyy 2026. All rights reserved.
                                </td>
                            </tr>
                        </table>
                    </td>
                </tr>
            </table>
        </body>
        </html>
        """

        # Defensive COM initialization to handle privilege disparities and active processes
        try:
            # First, attempt to bind directly to a running desktop window of Outlook
            outlook = win32.GetActiveObject('Outlook.Application')
        except Exception:
            try:
                # If no open instance exists, fall back to initializing a clean background process
                outlook = win32.Dispatch('Outlook.Application')
            except Exception as e:
                raise RuntimeError(
                    "COM tracking failed: Unable to bind or dispatch Outlook. Application. "
                    "Ensure Microsoft Outlook is open and accessible within your active user context."
                ) from e

        mail = outlook.CreateItem(0)
        mail.To = to
        if cc:
            mail.CC = cc
        mail.Subject = subject
        mail.HTMLBody = html
        if attachments:
            for path in attachments:
                mail.Attachments.Add(path)
        mail.Send()


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
        if current_date.weekday() < 5 and current_date not in holidays:
            day_count += 1
        current_date += timedelta(days=1)
    return day_count


# ================= Main Execution =================
if __name__ == "__main__":
    
    # 1. Provide Context variables required for Scheduling
    company_holidays = [
        datetime(2026, 1, 1).date(),
        datetime(2026, 12, 25).date()
    ]
    
    # Mocking standard operational shifts capacity configurations
    capacity_matrix = {
        'process_id': [1, 2, 3, 6, 9, 13, 15], 
        'capacity_1': [0.0]*7, 'capacity_2': [8.0]*7, 'capacity_3': [8.0]*7,
        'capacity_4': [8.0]*7, 'capacity_5': [8.0]*7, 'capacity_6': [8.0]*7, 'capacity_7': [0.0]*7
    }
    process_capacity_df = pd.DataFrame(capacity_matrix)
    active_bookings = {}

    # Initialize mailer wrapper with configuration models
    scheduler_mailer = SchedulerMailer()

    TIER_START_OFFSET = 8  # Lead days boundary parameter
    
    # Configuration profiles (Map profile identifier name directly to target docket ID metrics)
    lead_days = 4
    jobs_to_run = {
        "Eterna": ("188989", 6000, lead_days),
        "Langston": ("172368", 10000, lead_days),
        "United": ("186655", 26600, lead_days),
        "Eterna_Bobst": ("178910", 20000, lead_days),
        "United_Bbost": ("184830", 16000, lead_days),
        "Elitron_Strip": ("172271", 220, lead_days),
        "Elitron_Strip_Glue": ("189542", 500, lead_days),
        "Nozomi": ("190943", 2200, lead_days),
        "Nozomi_Eterna": ("185388", 3000, lead_days),
        "Nozomi_United": ("175175", 10000, lead_days),
        "Nozomi_Langston": ("169796", 5000, lead_days),
        "Nozomi_Eterna_Bobst": ("184263", 5000, lead_days),
        "Nozomi_United_Bobst": ("187010", 10000, lead_days),
        "Nozomi_United_Boxer": ("188351", 3000, lead_days),
        "Nozomi_Elitron_Strip": ("186831", 300, lead_days),
        "Nozomi_Elitron_Strip_Glue": ("191031", 1000, lead_days)
    }

    results = {}
    for name, (docket_id, qty, lead_days) in jobs_to_run.items():
        results[name] = scheduler_mailer.run_schedule(docket_id, qty, lead_days)

    today = datetime.today().date()
    holidays_set = set(company_holidays)
    
    tier_start_date = add_workdays(today, TIER_START_OFFSET, holidays_set)
    
    email_rows = []
    for sch_name, schedule_steps in results.items():
        if not schedule_steps:
            continue
            
        # Parse process names from the sequential steps returned by AI schedule data
        process_names = " → ".join([step['process_name'].split()[0] for step in schedule_steps])
        
        # Pull allocation details returned directly from ScheduleService output payload
        chain_start_dt = schedule_steps[0]['start']
        chain_end_dt = schedule_steps[-1]['end']
        
        if not chain_start_dt or not chain_end_dt:
            continue

        # Regular leadtime and ship date calculations (Tier 3)
        lead_days_count = workdays_between(today, chain_end_dt, holidays_set)
        ship_date = add_workdays(chain_end_dt, 1, holidays_set)
        
        # Tier 1/2 calculations: Fixed progression based on process depth path
        num_processes = len(schedule_steps)
        tier_end_date = add_workdays(tier_start_date, num_processes, holidays_set)
        tier_lead_days = workdays_between(today, tier_end_date, holidays_set)
        tier_ship_date = add_workdays(tier_end_date, 1, holidays_set)
        
        email_rows.append((
            process_names, 
            f"{lead_days_count} workdays", 
            ship_date.strftime("%Y-%m-%d"), 
            chain_start_dt.strftime("%Y-%m-%d"), 
            chain_end_dt.strftime("%Y-%m-%d"),
            f"{tier_lead_days} workdays",
            tier_ship_date.strftime("%Y-%m-%d"),
            tier_start_date.strftime("%Y-%m-%d"), 
            tier_end_date.strftime("%Y-%m-%d")
        ))

    # Dispatch complete compiled payload through Outlook
    scheduler_mailer.send_email(
        # to="sang.n@whitebird.ca",
        to="sang.n@whitebird.ca;allen.g@whitebird.ca;erin.l@moyydesign.com;catherine.s@moyydesign.com;" \
        "john.t@whitebird.ca;tamminga@whitebird.ca;lon.s@moyydesign.com;michelle.d@moyydesign.com;becky.j@moyydesign.com;" \
        "jason.w@moyydesign.com;jason.h@moyydesign.com;hendrik@moyydesign.com;" \
        "jeff.c@moyydesign.com;ray.j@moyydesign.com;megan.h@moyydesign.com;" \
        "ryan.p@moyydesign.com;cameron.c@whitebird.ca;don.s@whitebird.ca;" \
        "caitlin@whitebird.ca;Kamaldeep.k@whitebird.ca;william@whitebird.ca;luke.t@moyydesign.com;craig.a@whitebird.ca",
        subject=f"Timeline Agreement {today}",
        data_rows=email_rows
    )