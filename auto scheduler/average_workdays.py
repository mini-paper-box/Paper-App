import pyodbc
import pandas as pd
from datetime import datetime
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.lib.units import inch
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT

server   = 'wbdbserver'
database = 'flute_data'

CONN_STRING = (
    'DRIVER={SQL Server};'
    f'SERVER={server};'
    f'DATABASE={database};'
    'Trusted_Connection=yes;'
)
# CONN_STRING = (
#     'DRIVER={ODBC Driver 18 for SQL Server};'
#     f'SERVER={server};'
#     f'DATABASE={database};'
#     'Trusted_Connection=yes;'
#     'Encrypt=no;'
# )

QUERY = """
SELECT
    c.short_name,
    CAST(oh.order_id AS varchar(25)) + '-' + CAST(od.order_line_nbr AS varchar(25)) AS order_id,
    od.docket_id,
    CASE
        WHEN d.docket_dsc LIKE '%Board and Print%' THEN 'Board and Print'
        WHEN pd.printing_dsc LIKE '%Nozomi%' THEN 'Digital'
        ELSE 'Brown Box'
    END AS printing_type,
    CAST(oh.order_dte AS DATE) AS order_dte,
    recv.mat_recv_dte,
    CAST(od.scheduled_dte AS DATE) AS ship_dte,
    (
        DATEDIFF(DAY, recv.mat_recv_dte, od.scheduled_dte)
        - (DATEDIFF(WEEK, recv.mat_recv_dte, od.scheduled_dte) * 2)
        - CASE WHEN DATEPART(WEEKDAY, recv.mat_recv_dte) = 1 THEN 1 ELSE 0 END
        - CASE WHEN DATEPART(WEEKDAY, od.scheduled_dte)  = 7 THEN 1 ELSE 0 END
    ) + 3 AS workdays

FROM order_header oh
LEFT JOIN order_details od
    ON oh.order_id = od.order_id
LEFT JOIN customer c
    ON oh.customer_id = c.customer_id
LEFT JOIN docket d
    ON od.docket_id = d.docket_id
LEFT JOIN printing_dsc pd
    ON d.printing_id = pd.printing_id
LEFT JOIN (
    SELECT
        order_id,
        order_line_nbr,
        purchase_id,
        purchase_line_nbr,
        ROW_NUMBER() OVER (
            PARTITION BY order_id, order_line_nbr
            ORDER BY purchase_id
        ) AS rn
    FROM purchase_details
) pod
    ON od.order_id = pod.order_id
    AND od.order_line_nbr = pod.order_line_nbr
    AND pod.rn = 1
LEFT JOIN (
    SELECT
        purchase_id,
        purchase_line_nbr,
        MIN(receipt_dte) AS receipt_dte
    FROM purchase_receipts
    GROUP BY purchase_id, purchase_line_nbr
) pr
    ON pod.purchase_id = pr.purchase_id
    AND pod.purchase_line_nbr = pr.purchase_line_nbr
CROSS APPLY (
    SELECT CAST(
        CASE
            WHEN pr.receipt_dte IS NOT NULL THEN pr.receipt_dte
            ELSE DATEADD(DAY,
                     3 + 2 * (((DATEPART(WEEKDAY, oh.order_dte) + @@DATEFIRST - 2) % 7 + 2) / 5),
                     CAST(oh.order_dte AS DATE))
        END
    AS DATE) AS mat_recv_dte
) recv

WHERE oh.status_id = 4
AND DATEPART(ISO_WEEK, od.scheduled_dte) = ?
AND YEAR(od.scheduled_dte) = ?
AND c.customer_id not in  (15562, 12853)
AND recv.mat_recv_dte IS NOT NULL
AND od.scheduled_dte IS NOT NULL
"""


# ── colour palette ────────────────────────────────────────────────────────────
DARK_BLUE  = colors.HexColor('#1B3A5C')
MID_BLUE   = colors.HexColor('#2E6DA4')
LIGHT_BLUE = colors.HexColor('#D6E8F7')
ALT_ROW    = colors.HexColor('#F4F8FC')
WHITE      = colors.white
DARK_GREY  = colors.HexColor('#444444')
MID_GREY   = colors.HexColor('#888888')


def fetch_data(week_num: int, year_num: int) -> pd.DataFrame:
    conn = pyodbc.connect(CONN_STRING)
    df = pd.read_sql(QUERY, conn, params=[week_num, year_num])
    conn.close()
    return df


def build_summary(df: pd.DataFrame) -> pd.DataFrame:
    df_clean = df[df['workdays'] <= 30]
    summary = (
        df_clean
        .groupby('printing_type')['workdays']
        .agg(count='count', avg='mean', median='median', std='std',
             min='min', max='max')
        .round(2)
        .reset_index()
    )
    return summary


def generate_pdf(week_num: int, year_num: int, output_path: str = None):
    if output_path is None:
        output_path = f'workdays_report_week{week_num}_{year_num}.pdf'

    print(f"Fetching data for week {week_num}, {year_num}...")
    df = fetch_data(week_num, year_num)

    if df.empty:
        print(f"No data found for week {week_num}, {year_num}.")
        return

    summary = build_summary(df)

    doc = SimpleDocTemplate(
        output_path,
        pagesize=letter,
        leftMargin=0.65*inch,
        rightMargin=0.65*inch,
        topMargin=0.65*inch,
        bottomMargin=0.65*inch,
    )

    styles = getSampleStyleSheet()

    style_title = ParagraphStyle(
        'ReportTitle',
        fontSize=18,
        fontName='Helvetica-Bold',
        textColor=DARK_BLUE,
        alignment=TA_LEFT,
        spaceAfter=4,
    )
    style_subtitle = ParagraphStyle(
        'Subtitle',
        fontSize=10,
        fontName='Helvetica',
        textColor=MID_GREY,
        alignment=TA_LEFT,
        spaceAfter=16,
    )
    style_section = ParagraphStyle(
        'Section',
        fontSize=12,
        fontName='Helvetica-Bold',
        textColor=DARK_BLUE,
        spaceBefore=16,
        spaceAfter=6,
    )

    story = []

    # ── header ────────────────────────────────────────────────────────────────
    story.append(Paragraph(f'Workdays Report — Week {week_num}', style_title))
    story.append(Paragraph(
        f'Year {year_num} &nbsp;|&nbsp; Generated {datetime.now().strftime("%B %d, %Y %H:%M")} &nbsp;|&nbsp; {len(df)} orders',
        style_subtitle
    ))

    # ── summary section ───────────────────────────────────────────────────────
    story.append(Paragraph('Average Workdays by Printing Type', style_section))
    story.append(Spacer(1, 4))

    sum_header = ['Printing Type', 'Orders', 'Avg Days', 'Median', 'Std Dev', 'Min', 'Max']
    sum_data = [sum_header]
    for _, row in summary.iterrows():
        sum_data.append([
            row['printing_type'],
            str(int(row['count'])),
            f"{row['avg']:.1f}",
            f"{row['median']:.1f}",
            f"{row['std']:.1f}",
            str(int(row['min'])),
            str(int(row['max'])),
        ])

    col_widths = [2.2*inch, 0.8*inch, 0.9*inch, 0.8*inch, 0.8*inch, 0.6*inch, 0.6*inch]
    sum_table = Table(sum_data, colWidths=col_widths, repeatRows=1)
    sum_table.setStyle(TableStyle([
        # header
        ('BACKGROUND',   (0, 0), (-1, 0), DARK_BLUE),
        ('TEXTCOLOR',    (0, 0), (-1, 0), WHITE),
        ('FONTNAME',     (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE',     (0, 0), (-1, 0), 9),
        ('ALIGN',        (0, 0), (-1, 0), 'CENTER'),
        ('BOTTOMPADDING',(0, 0), (-1, 0), 8),
        ('TOPPADDING',   (0, 0), (-1, 0), 8),
        # data rows
        ('FONTNAME',     (0, 1), (-1, -1), 'Helvetica'),
        ('FONTSIZE',     (0, 1), (-1, -1), 9),
        ('ALIGN',        (1, 1), (-1, -1), 'CENTER'),
        ('ALIGN',        (0, 1), (0, -1),  'LEFT'),
        ('TOPPADDING',   (0, 1), (-1, -1), 6),
        ('BOTTOMPADDING',(0, 1), (-1, -1), 6),
        ('ROWBACKGROUNDS',(0, 1), (-1, -1), [WHITE, ALT_ROW]),
        ('GRID',         (0, 0), (-1, -1), 0.4, colors.HexColor('#CCCCCC')),
        ('LINEBELOW',    (0, 0), (-1, 0),  1.2, DARK_BLUE),
    ]))
    story.append(sum_table)

    # ── detail section ────────────────────────────────────────────────────────
    story.append(Paragraph('Order Detail', style_section))
    story.append(Spacer(1, 4))

    det_header = ['Customer', 'Order ID', 'Docket', 'Printing Type',
                  'Order Date', 'Recv Date', 'Ship Date', 'Workdays']
    det_data = [det_header]

    df_sorted = df.sort_values(['printing_type', 'ship_dte'])
    for _, row in df_sorted.iterrows():
        wdays = int(row['workdays']) if row['workdays'] <= 30 else f"{int(row['workdays'])}*"
        det_data.append([
            str(row['short_name'])   if pd.notna(row['short_name'])   else '',
            str(row['order_id'])     if pd.notna(row['order_id'])     else '',
            str(row['docket_id'])    if pd.notna(row['docket_id'])    else '',
            str(row['printing_type']),
            str(row['order_dte'])    if pd.notna(row['order_dte'])    else '',
            str(row['mat_recv_dte']) if pd.notna(row['mat_recv_dte']) else '',
            str(row['ship_dte'])     if pd.notna(row['ship_dte'])     else '',
            str(wdays),
        ])

    det_col_widths = [1.1*inch, 1.0*inch, 0.8*inch, 1.3*inch,
                      0.85*inch, 0.85*inch, 0.85*inch, 0.75*inch]
    det_table = Table(det_data, colWidths=det_col_widths, repeatRows=1)
    det_table.setStyle(TableStyle([
        # header
        ('BACKGROUND',   (0, 0), (-1, 0), MID_BLUE),
        ('TEXTCOLOR',    (0, 0), (-1, 0), WHITE),
        ('FONTNAME',     (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE',     (0, 0), (-1, 0), 8),
        ('ALIGN',        (0, 0), (-1, 0), 'CENTER'),
        ('BOTTOMPADDING',(0, 0), (-1, 0), 7),
        ('TOPPADDING',   (0, 0), (-1, 0), 7),
        # data rows
        ('FONTNAME',     (0, 1), (-1, -1), 'Helvetica'),
        ('FONTSIZE',     (0, 1), (-1, -1), 8),
        ('ALIGN',        (4, 1), (-1, -1), 'CENTER'),
        ('ALIGN',        (7, 1), (7, -1),  'CENTER'),
        ('ALIGN',        (0, 1), (3, -1),  'LEFT'),
        ('TOPPADDING',   (0, 1), (-1, -1), 5),
        ('BOTTOMPADDING',(0, 1), (-1, -1), 5),
        ('ROWBACKGROUNDS',(0, 1), (-1, -1), [WHITE, ALT_ROW]),
        ('GRID',         (0, 0), (-1, -1), 0.4, colors.HexColor('#CCCCCC')),
        ('LINEBELOW',    (0, 0), (-1, 0),  1.2, MID_BLUE),
    ]))
    story.append(det_table)

    # ── footnote ──────────────────────────────────────────────────────────────
    story.append(Spacer(1, 10))
    story.append(Paragraph(
        '* Workdays marked with an asterisk exceed 30 days and will use the group average in scheduling.',
        ParagraphStyle('footnote', fontSize=7, textColor=MID_GREY)
    ))

    doc.build(story)
    print(f"Report saved to: {output_path}")


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Usage: python generate_report.py <week_number> [year]")
        sys.exit(1)

    try:
        week = int(sys.argv[1])
        year = int(sys.argv[2]) if len(sys.argv) == 3 else 2026
    except ValueError:
        print("Week number and year must be integers.")
        sys.exit(1)

    generate_pdf(week, year)