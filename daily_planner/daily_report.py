import sqlite3
import pandas as pd
from datetime import datetime, timedelta
from reportlab.lib import colors
from reportlab.lib.colors import HexColor
from reportlab.lib.pagesizes import landscape, A4
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle

# === CONFIG ===
db_path = r"C:\Users\sang.n\OneDrive - whitebird.ca\Paper App\prod_db.db"
planned_date = "2025-10-17"
pdf_path = f"Daily_Planner_{planned_date}.pdf"

# === DATABASE CONNECTION ===
conn = sqlite3.connect(db_path)

# --- Get holiday dates ---
holiday_dates = set(pd.read_sql_query("SELECT date FROM holiday", conn)["date"].tolist())

# --- Compute next working day ---
def next_working_day(date_str):
    d = datetime.strptime(date_str, "%Y-%m-%d").date()
    next_day = d + timedelta(days=1)
    while next_day.weekday() >= 5 or next_day.strftime("%Y-%m-%d") in holiday_dates:
        next_day += timedelta(days=1)
    return next_day.strftime("%Y-%m-%d")

next_day = next_working_day(planned_date)

# === 1️⃣ SUMMARY TABLE (with total MSF formatted) ===
summary_query = f"""
SELECT 
    ws.process_nme AS "Process Name",
    COUNT(DISTINCT ws.order_id) AS "# of Orders Due",
    SUM(r.msf) AS "Total MSF",
    '' AS "Resource",
    '' AS "Material",
    '' AS "Shift"
FROM workback_schedule ws
LEFT JOIN order_routing r
    ON ws.order_id = r.order_id
   AND ws.order_line_nbr = r.order_line_nbr
WHERE date(substr(ws.planned_start,1,10)) = '{planned_date}'
GROUP BY ws.process_nme
ORDER BY ws.process_nme
"""
summary_df = pd.read_sql_query(summary_query, conn)
if not summary_df.empty:
    summary_df["Total MSF"] = summary_df["Total MSF"].fillna(0).astype(int).map("{:,}".format)

# --- Today's processes ---
today_processes = tuple(summary_df['Process Name'].tolist())
if not today_processes:
    today_processes = ("",)

# === 2️⃣ ORDER DETAILS TABLE ===
details_query = f"""
SELECT 
    r.order_id || '-' || r.order_line_nbr AS "Order #",
    r.short_name AS "Customer",
    r.all_routing AS "Processes",
    '' AS "Status",
    '' AS "Note",
    CASE WHEN r.quality_watch = 1 THEN 'YES' ELSE '' END AS "QW"
FROM order_routing r
WHERE date(substr(r.requested_dte,1,10)) = '{next_day}'
  AND r.process_id != 168
  AND r.process_nme IN {today_processes}
GROUP BY r.order_id, r.order_line_nbr
ORDER BY r.order_id, r.order_line_nbr
"""
details_df = pd.read_sql_query(details_query, conn)
conn.close()

# === 3️⃣ POTENTIAL PROBLEMS / RISKS TABLE ===
risks_df = pd.DataFrame({
    "Area": ["Equipment", "Staffing", "Materials", "Logistics"],
    "Risk Description": ["", "", "", ""],
    "Impact Level (circle one)": ["Low / Med / High"]*4,
    "Mitigation Plan": ["", "", "", ""]
})

# === PDF SETUP ===
doc = SimpleDocTemplate(
    pdf_path,
    pagesize=landscape(A4),
    rightMargin=30,
    leftMargin=30,
    topMargin=40,
    bottomMargin=30
)
styles = getSampleStyleSheet()
elements = []

# === TITLE / HEADINGS ===
title_style = ParagraphStyle(name="TitleStyle", parent=styles["Title"], fontSize=16)
heading_style = ParagraphStyle(name="HeadingStyle", parent=styles["Heading2"], fontSize=16)
elements.append(Paragraph(f"<b>Daily Planner – {planned_date}</b>", title_style))
elements.append(Spacer(1, 12))

# === Helper: Column widths ===
def calc_col_widths_summary(df, first_col_width=250, total_width=760):
    remaining_width = total_width - first_col_width
    other_cols = len(df.columns) - 1
    other_width = remaining_width / other_cols if other_cols > 0 else remaining_width
    return [first_col_width] + [other_width]*other_cols

def calc_col_widths_order_details(df, processes_col="Processes", processes_width=250, total_width=760):
    n_cols = len(df.columns)
    widths = []
    remaining_width = total_width - processes_width
    other_cols = n_cols - 1
    other_width = remaining_width / other_cols if other_cols > 0 else remaining_width
    for col in df.columns:
        widths.append(processes_width if col == processes_col else other_width)
    return widths

# === 1️⃣ SUMMARY TABLE ===
if not summary_df.empty:
    elements.append(Paragraph("Summary by Process", heading_style))
    data = [list(summary_df.columns)] + summary_df.values.tolist()
    summary_table = Table(data, colWidths=calc_col_widths_summary(summary_df))
    summary_table.setStyle(TableStyle([
        ("BACKGROUND", (0,0), (-1,0), HexColor("#FAFAFA")),
        ("TEXTCOLOR", (0,0), (-1,0), colors.black),
        ("ALIGN", (0,0), (-1,-1), "LEFT"),
        ("FONTNAME", (0,0), (-1,0), "Helvetica-Bold"),
        ("FONTSIZE", (0,0), (-1,-1), 12),
        ("BOTTOMPADDING", (0,0), (-1,0), 6),
        ("GRID", (0,0), (-1,-1), 0.25, colors.grey),
        ("ALIGN", (2,1), (2,-1), "RIGHT")  # Total MSF right-aligned
    ]))
    elements.append(summary_table)
else:
    elements.append(Paragraph("No summary data available for this date.", styles["Normal"]))
elements.append(Spacer(1, 18))

# === 2️⃣ ORDER DETAILS TABLE ===
if not details_df.empty:
    elements.append(Paragraph(f"Order Details (Due {next_day})", heading_style))
    data = [list(details_df.columns)] + details_df.values.tolist()
    details_table = Table(data, colWidths=calc_col_widths_order_details(details_df))
    details_table.setStyle(TableStyle([
        ("BACKGROUND", (0,0), (-1,0), HexColor("#FAFAFA")),
        ("TEXTCOLOR", (0,0), (-1,0), colors.black),
        ("ALIGN", (0,0), (-1,-1), "LEFT"),
        ("FONTNAME", (0,0), (-1,0), "Helvetica-Bold"),
        ("FONTSIZE", (0,0), (-1,-1), 12),
        ("BOTTOMPADDING", (0,0), (-1,0), 6),
        ("GRID", (0,0), (-1,-1), 0.25, colors.grey)
    ]))
    elements.append(details_table)
else:
    elements.append(Paragraph(f"No orders due for {next_day}.", styles["Normal"]))
elements.append(Spacer(1, 18))

# === 3️⃣ POTENTIAL PROBLEMS / RISKS TABLE ===
elements.append(Paragraph("Potential Problems / Risks", heading_style))
data = [list(risks_df.columns)] + risks_df.values.tolist()
risks_table = Table(data, colWidths=calc_col_widths_summary(risks_df))
risks_table.setStyle(TableStyle([
    ("BACKGROUND", (0,0), (-1,0), HexColor("#FAFAFA")),
    ("TEXTCOLOR", (0,0), (-1,0), colors.black),
    ("ALIGN", (0,0), (-1,-1), "LEFT"),
    ("FONTNAME", (0,0), (-1,0), "Helvetica-Bold"),
    ("FONTSIZE", (0,0), (-1,-1), 12),
    ("BOTTOMPADDING", (0,0), (-1,0), 6),
    ("GRID", (0,0), (-1,-1), 0.25, colors.grey),
    ("TEXTCOLOR", (2,1), (2,-1), HexColor("#BABABA"))  # Impact Level font color
]))
elements.append(risks_table)
elements.append(Spacer(1, 36))

# === FOOTER ===
footer_style = ParagraphStyle(name="Footer", parent=styles["Normal"], fontSize=14)
elements.append(Paragraph("Date: ____________________", footer_style))
elements.append(Spacer(1, 12))
elements.append(Paragraph("Plan approved by: ____________________", footer_style))

# === BUILD PDF ===
doc.build(elements)
print(f"✅ PDF generated: {pdf_path}")
print(f"Next working day (skipping weekends/holidays): {next_day}")
