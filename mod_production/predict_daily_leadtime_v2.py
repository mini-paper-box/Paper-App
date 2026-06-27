import win32com.client as win32
from datetime import datetime, timedelta
import pandas as pd

from mod_production.services.schedule_service import ScheduleService


# ═════════════════════════════════════════════════════════════════════════════
# CONFIGURATION  — edit these, nothing else needs touching
# ═════════════════════════════════════════════════════════════════════════════

COLOUR_THEME = "navy_teal"   # "navy_teal"  |  "slate_amber"

THEMES = {
    "slate_amber": {
        "header_bg":     "#37474f",
        "header_text":   "#ffffff",
        "col_header_bg": "#eceff1",
        "ai_colour":     "#e65100",
        "ai_bg":         "#fff8e1",
        "ai_label":      "Leadtime",
        "tier_colour":   "#546e7a",
        "tier_bg":       "#eceff1",
        "tier_label":    "Tier Leadtime",
        "ship_colour":   "#4a235a",
        "ship_bg":       "#aeb4e0",
        "step_colour":   "#546e7a",
        "footer_bg":     "#eceff1",
        "footer_text":   "#777777",
        "row_odd":       "#ffffff",
        "row_even":      "#f9f9f9",
    },
    "navy_teal": {
        "header_bg":     "#0d2b4e",
        "header_text":   "#ffffff",
        "col_header_bg": "#e8f5f3",
        "ai_colour":     "#00796b",
        "ai_bg":         "#e0f2f1",
        "ai_label":      "Leadtime",
        "tier_colour":   "#1565c0",
        "tier_bg":       "#e3f2fd",
        "tier_label":    "Tier Leadtime",
        "ship_colour":   "#4a235a",
        "ship_bg":       "#aeb4e0",
        "step_colour":   "#004d61",
        "footer_bg":     "#0d2b4e",
        "footer_text":   "#a0bec8",
        "row_odd":       "#ffffff",
        "row_even":      "#f4fafa",
    },
}

SHOW_TIER_LEADTIME    = False
TEST_MODE             = False
TEST_RECIPIENT        = "sang.n@whitebird.ca"
TIER_START_OFFSET     = 8
DEFAULT_LEAD_DAYS     = 4
EXCLUDED_PROCESS_IDS: set = set()

PRODUCTION_RECIPIENTS = (
    "sang.n@whitebird.ca;allen.g@whitebird.ca;erin.l@moyydesign.com;"
    "catherine.s@moyydesign.com;john.t@whitebird.ca;tamminga@whitebird.ca;"
    "lon.s@moyydesign.com;michelle.d@moyydesign.com;becky.j@moyydesign.com;"
    "jason.w@moyydesign.com;jason.h@moyydesign.com;"
    "jeff.c@moyydesign.com;ray.j@moyydesign.com;megan.h@moyydesign.com;"
    "ryan.p@moyydesign.com;cameron.c@whitebird.ca;don.s@whitebird.ca;"
    "Kamaldeep.k@whitebird.ca;"
    "madison.s@whitebird.ca;luke.t@moyydesign.com;craig.a@whitebird.ca"
)

JOBS = {
    "Eterna":                    ("188989", 6000),
    "Langston":                  ("172368", 9000),
    "United":                    ("167174", 7500),
    "Eterna_Bobst":              ("178910", 20000),
    "United_Bobst":              ("170605", 4000),
    "Elitron_Strip":             ("172271", 220),
    "Elitron_Strip_Glue":        ("189542", 500),
    "Nozomi":                    ("190943", 2200),
    "Nozomi_Eterna":             ("185388", 3000),
    "Nozomi_United":             ("175175", 10000),
    "Nozomi_Langston":           ("169796", 5000),
    "Nozomi_Eterna_Bobst":       ("184263", 5000),
    "Nozomi_United_Bobst":       ("187010", 10000),
    "Nozomi_United_Boxer":       ("188351", 3000),
    "Nozomi_Elitron_Strip":      ("186831", 300),
    "Nozomi_Elitron_Strip_Glue": ("191031", 1000),
}


# ═════════════════════════════════════════════════════════════════════════════
# HELPERS
# ═════════════════════════════════════════════════════════════════════════════

def add_workdays(start_date, days, holidays):
    current = start_date
    while days > 0:
        current += timedelta(days=1)
        if current.weekday() < 5 and current not in holidays:
            days -= 1
    return current


def workdays_between(start_date, end_date, holidays):
    count, current = 0, start_date
    while current < end_date:
        if current.weekday() < 5 and current not in holidays:
            count += 1
        current += timedelta(days=1)
    return count


def subject_with_timestamp(base: str) -> str:
    now = datetime.now()
    return f"[{now.strftime('%H:%M')}] {base} {now.strftime('%Y-%m-%d')}"


def build_tier_starts(tier_start_date, num_steps, holidays) -> list:
    """Each process starts 1 workday after the previous, from tier_start_date."""
    starts = []
    current = tier_start_date
    for _ in range(num_steps):
        starts.append(current)
        current = add_workdays(current, 1, holidays)
    return starts


# ═════════════════════════════════════════════════════════════════════════════
# SCHEDULER MAILER
# ═════════════════════════════════════════════════════════════════════════════

class SchedulerMailer:

    def __init__(self):
        self.scheduler = ScheduleService()

    def run_schedule(self, docket_id, qty, lead_days=DEFAULT_LEAD_DAYS):
        return self.scheduler.build_schedule(
            docket_id=docket_id,
            qty=qty,
            lead_days=lead_days,
        )

    def send_email(self, to, subject, email_rows, cc=None):
        t     = THEMES[COLOUR_THEME]
        today = datetime.today().strftime("%Y-%m-%d")
        cols  = "4" if SHOW_TIER_LEADTIME else "3"

        # ── Responsive <style> block ──────────────────────────────────────
        style = """
        <style>
          @media only screen and (max-width: 600px) {
            .outer-table   { width: 100% !important; }
            .main-table    { width: 100% !important; }
            .col-route     { display: block !important; width: 100% !important;
                             box-sizing: border-box; }
            .col-ai        { display: block !important; width: 100% !important;
                             box-sizing: border-box; border-top: none !important; }
            .col-ship      { display: block !important; width: 100% !important;
                             box-sizing: border-box; border-top: none !important; }
            .col-tier      { display: block !important; width: 100% !important;
                             box-sizing: border-box; border-top: none !important; }
            .hide-mobile   { display: none !important; }
            .header-text   { font-size: 16px !important; }
            .days-text     { font-size: 18px !important; }
          }
        </style>
        """

        # ── Column headers ────────────────────────────────────────────────
        tier_th = (
            f"""<th class="col-tier"
                    style="padding:12px 14px; border:1px solid #ddd;
                           text-align:center; font-size:12px;
                           text-transform:uppercase; letter-spacing:0.5px;
                           background:{t['col_header_bg']}; color:{t['tier_colour']};">
                    {t['tier_label']}
                </th>"""
            if SHOW_TIER_LEADTIME else ""
        )

        # ── Data rows ─────────────────────────────────────────────────────
        body_html = ""
        for i, row in enumerate(email_rows):
            bg = t["row_odd"] if i % 2 == 0 else t["row_even"]

            # AI process sub-rows under the day count
            ai_steps_html = "".join(
                f"""<tr>
                      <td style="padding:2px 0; font-size:11px;
                                 color:{t['step_colour']};">
                          &#8627;&nbsp;
                          <span style="font-weight:600;">{s['process_name']}</span>
                          &nbsp;&#xb7;&nbsp;
                          <span style="color:#444;">{s['start_date']}</span>
                      </td>
                    </tr>"""
                for s in row["process_rows"]
            )

            # Tier process sub-rows — 1 workday apart
            tier_steps_html = ""
            tier_td = ""
            if SHOW_TIER_LEADTIME:
                tier_steps_html = "".join(
                    f"""<tr>
                          <td style="padding:2px 0; font-size:11px;
                                     color:{t['tier_colour']};">
                              &#8627;&nbsp;
                              <span style="font-weight:600;">{s['process_name']}</span>
                              &nbsp;&#xb7;&nbsp;
                              <span style="color:#444;">{s['tier_start']}</span>
                          </td>
                        </tr>"""
                    for s in row["process_rows"]
                )
                tier_td = f"""
                    <td class="col-tier"
                        style="border:1px solid #ddd; padding:14px 16px;
                               vertical-align:top; background:{t['tier_bg']};
                               min-width:150px;">
                        <div class="days-text"
                             style="font-size:20px; font-weight:700;
                                    color:{t['tier_colour']}; text-align:center;">
                            {row['tier_lead_days']}&nbsp;days
                        </div>
                        <table cellpadding="0" cellspacing="0"
                               style="border-collapse:collapse; margin-top:8px;
                                      width:100%;">
                            {tier_steps_html}
                        </table>
                    </td>"""

            body_html += f"""
                <tr style="background:{bg};">

                  <!-- Route name -->
                  <td class="col-route"
                      style="border:1px solid #ddd; padding:14px 18px;
                             vertical-align:middle; min-width:160px;">
                    <div style="font-size:14px; font-weight:700;
                                color:{t['header_bg']}; line-height:1.5;">
                        {row['route_label']}
                    </div>
                  </td>

                  <!-- AI Leadtime + process start dates -->
                  <td class="col-ai"
                      style="border:1px solid #ddd; padding:14px 16px;
                             vertical-align:top; background:{t['ai_bg']};
                             min-width:160px;">
                    <div class="days-text"
                         style="font-size:20px; font-weight:700;
                                color:{t['ai_colour']}; text-align:center;">
                        {row['lead_days_count']}&nbsp;days
                    </div>
                    <table cellpadding="0" cellspacing="0"
                           style="border-collapse:collapse; margin-top:8px;
                                  width:100%;">
                        {ai_steps_html}
                    </table>
                  </td>

                  <!-- Ship date -->
                  <td class="col-ship"
                      style="border:1px solid #ddd; padding:14px 16px;
                             vertical-align:middle; text-align:center;
                             background:{t['ship_bg']}; min-width:120px;">
                    <div style="font-size:11px; text-transform:uppercase;
                                letter-spacing:0.5px; color:#888;
                                margin-bottom:4px;">
                        Ships
                    </div>
                    <div style="font-size:16px; font-weight:700;
                                color:{t['ship_colour']};">
                        {row['ship_date']}
                    </div>
                  </td>

                  {tier_td}

                </tr>
            """

        # ── Tier column header ────────────────────────────────────────────
        tier_ship_th = (
            f"""<th class="col-tier"
                    style="padding:12px 14px; border:1px solid #ddd;
                           text-align:center; font-size:12px;
                           text-transform:uppercase; letter-spacing:0.5px;
                           background:{t['col_header_bg']}; color:{t['tier_colour']};">
                    Tier Ship Date
                </th>"""
            if SHOW_TIER_LEADTIME else ""
        )

        test_banner = (
            f"""<tr>
                  <td colspan="{cols}"
                      style="background:#fff3cd; color:#856404; padding:10px;
                             text-align:center; font-size:13px;
                             border-bottom:2px solid #ffc107;">
                      &#9888; TEST MODE — not sent to production recipients
                  </td>
                </tr>"""
            if TEST_MODE else ""
        )

        html = f"""
        <!DOCTYPE html>
        <html lang="en">
        <head>
          <meta charset="UTF-8"/>
          <meta name="viewport" content="width=device-width, initial-scale=1.0"/>
          {style}
        </head>
        <body style="margin:0; padding:0;
                     font-family:Arial,Helvetica,sans-serif;
                     background:#f0f4f8;">
          <table class="outer-table" width="100%" cellpadding="0" cellspacing="0"
                 style="background:#f0f4f8; padding:16px;">
            <tr><td align="center">
              <table class="main-table" width="860" cellpadding="0" cellspacing="0"
                     style="background:#fff; border-radius:10px; overflow:hidden;
                            box-shadow:0 2px 12px rgba(0,0,0,0.08);">

                <!-- Header -->
                <tr>
                  <td colspan="{cols}"
                      style="background:{t['header_bg']}; color:{t['header_text']};
                             padding:22px 24px; text-align:center;">
                    <div class="header-text"
                         style="font-size:20px; font-weight:700;
                                letter-spacing:0.5px;">
                        {subject}
                    </div>
                    <div style="font-size:11px; margin-top:5px; opacity:0.6;">
                        Generated {today}
                    </div>
                  </td>
                </tr>

                {test_banner}

                <!-- Intro -->
                <tr>
                  <td colspan="{cols}"
                      style="padding:14px 20px 10px 20px; font-size:13px;
                             line-height:1.7; color:#444;
                             border-bottom:1px solid #eee;">
                    This timeline standard reduces back-and-forth between Sales
                    and Order Management for quick, accurate due dates.<br/>
                    <strong style="color:{t['header_bg']};">
                        Large order thresholds — coordinate directly with
                        Order Management:
                    </strong>
                    <ul style="margin:4px 0 0 0; padding-left:18px;">
                      <li>3 processes and <strong>25,000+ sqft</strong></li>
                      <li>1 process and <strong>50,000+ sqft</strong></li>
                    </ul>
                  </td>
                </tr>

                <!-- Column headers -->
                <tr style="background:{t['col_header_bg']};">
                  <th class="col-route"
                      style="padding:12px 18px; border:1px solid #ddd;
                             text-align:left; font-size:12px;
                             text-transform:uppercase; letter-spacing:0.5px;
                             color:#555;">
                    Route
                  </th>
                  <th class="col-ai"
                      style="padding:12px 14px; border:1px solid #ddd;
                             text-align:center; font-size:12px;
                             text-transform:uppercase; letter-spacing:0.5px;
                             color:{t['ai_colour']};">
                    {t['ai_label']}
                  </th>
                  <th class="col-ship"
                      style="padding:12px 14px; border:1px solid #ddd;
                             text-align:center; font-size:12px;
                             text-transform:uppercase; letter-spacing:0.5px;
                             color:{t['ship_colour']};">
                    Ship Date
                  </th>
                  {tier_th}
                  {tier_ship_th}
                </tr>

                {body_html}

                <!-- Footer -->
                <tr>
                  <td colspan="{cols}"
                      style="background:{t['footer_bg']}; padding:14px 24px;
                             text-align:center; font-size:11px;
                             color:{t['footer_text']}; letter-spacing:0.3px;">
                    Best regards, Moyy Design &nbsp;&#xb7;&nbsp;
                    &#169; Moyy 2026 &nbsp;&#xb7;&nbsp;
                    Sent {today}
                  </td>
                </tr>

              </table>
            </td></tr>
          </table>
        </body>
        </html>
        """

        import pythoncom
        pythoncom.CoInitialize()

        try:
            outlook = win32.GetActiveObject("Outlook.Application")
        except Exception:
            try:
                outlook = win32.Dispatch("Outlook.Application")
            except Exception as e:
                raise RuntimeError(
                    "Cannot bind to Outlook — ensure it is running."
                ) from e

        mail          = outlook.CreateItem(0)
        mail.To       = to
        mail.Subject  = subject
        mail.HTMLBody = html
        if cc:
            mail.CC = cc
        mail.Send()


# ═════════════════════════════════════════════════════════════════════════════
# MAIN
# ═════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import traceback

    try:
        company_holidays = {
            datetime(2026, 1, 1).date(),
            datetime(2026, 12, 25).date(),
        }

        scheduler_mailer = SchedulerMailer()
        today            = datetime.today().date()
        tier_start_date  = add_workdays(today, TIER_START_OFFSET, company_holidays)

        print(f"Processing {len(JOBS)} jobs  |  theme={COLOUR_THEME}  |  test={TEST_MODE}")

        email_rows = []

        for job_key, (docket_id, qty) in JOBS.items():
            print(f"  {job_key} ({docket_id}) qty={qty:,} ...", end=" ", flush=True)

            try:
                steps = scheduler_mailer.run_schedule(docket_id, qty)
            except Exception as e:
                print(f"SKIP (schedule error: {e})")
                continue

            if not steps:
                print("SKIP (no routing)")
                continue

            # Route label from actual process names
            route_label = " \u2192 ".join(s["process_name"].split()[0] for s in steps)

            # Visible steps for display
            visible = [
                s for s in steps
                if s.get("process_id") not in EXCLUDED_PROCESS_IDS
            ]
            if not visible:
                print("SKIP (all steps excluded)")
                continue

            # Tier start dates — 1 workday apart per step
            tier_starts = build_tier_starts(tier_start_date, len(visible), company_holidays)

            process_rows = [
                {
                    "process_name": s["process_name"].split()[0],
                    "start_date":   (
                        s["start"].strftime("%Y-%m-%d") if s["start"] else "TBD"
                    ),
                    "tier_start": tier_starts[idx].strftime("%Y-%m-%d"),
                }
                for idx, s in enumerate(visible)
            ]

            # Date calcs on full unfiltered steps
            chain_end = steps[-1]["end"]
            if not chain_end:
                print("SKIP (no end date)")
                continue

            lead_days_count = workdays_between(today, chain_end, company_holidays)
            ship_date       = add_workdays(chain_end, 1, company_holidays)

            # Tier end = last tier start + 1 workday
            tier_end       = add_workdays(tier_starts[-1], 1, company_holidays)
            tier_lead_days = workdays_between(today, tier_end, company_holidays)
            tier_ship_date = add_workdays(tier_end, 1, company_holidays)

            email_rows.append({
                "route_label":     route_label,
                "process_rows":    process_rows,
                "lead_days_count": lead_days_count,
                "ship_date":       ship_date.strftime("%Y-%m-%d"),
                "tier_lead_days":  tier_lead_days,
                "tier_ship_date":  tier_ship_date.strftime("%Y-%m-%d"),
            })
            print("OK")

        if not email_rows:
            print("No rows to send — aborting.")
        else:
            recipient = TEST_RECIPIENT if TEST_MODE else PRODUCTION_RECIPIENTS
            subject   = subject_with_timestamp("Timeline Agreement")

            print(f"\nSending  \u2192 {'TEST' if TEST_MODE else 'PRODUCTION'}")
            print(f"Subject  \u2192 {subject}")

            scheduler_mailer.send_email(
                to         = recipient,
                subject    = subject,
                email_rows = email_rows,
            )
            print("Email sent successfully.")

    except Exception as e:
        print(f"Fatal: {e}")
        traceback.print_exc()