import win32com.client as win32
import pythoncom

from datetime import datetime, date, timedelta

import pandas as pd

from mod_production.services.schedule_service import ScheduleService


# ╔═══════════════════════════════════════════════════════════════════════════╗
# ║ CONFIGURATION — EDIT THESE SETTINGS                                      ║
# ╚═══════════════════════════════════════════════════════════════════════════╝

# ---------------------------------------------------------------------------
# EDIT: Color theme
# ---------------------------------------------------------------------------
COLOUR_THEME = "navy_teal"


THEMES = {
    "navy_teal": {

        # Main header
        "header_bg":       "#0d2b4e",
        "header_text":     "#ffffff",

        # Shipping day header
        "day_bg":          "#e8f5f3",
        "day_text":        "#0d2b4e",

        # City header
        "city_bg":         "#d9eaf7",
        "city_text":       "#0d2b4e",

        # Customer header
        "customer_bg":     "#f4f8fa",
        "customer_text":   "#1565c0",

        # Borders
        "border":          "#d9e1e5",

        # Alternating order rows
        "row_odd":         "#ffffff",
        "row_even":        "#f8fbfc",

        # Footer
        "footer_bg":       "#0d2b4e",
        "footer_text":     "#a0bec8",

        # Shipment status colours
        "ready_bg":        "#e8f5e9",
        "ready_text":      "#2e7d32",

        "partial_bg":      "#fff8e1",
        "partial_text":    "#f57f17",

        "production_bg":   "#e3f2fd",
        "production_text": "#1565c0",

        "not_ready_bg":    "#ffebee",
        "not_ready_text": "#c62828",
    }
}


# ╔═══════════════════════════════════════════════════════════════════════════╗
# ║ EMAIL SETTINGS — EDIT HERE                                               ║
# ╚═══════════════════════════════════════════════════════════════════════════╝

# ---------------------------------------------------------------------------
# EDIT: Set to True while testing.
#
# True  = email goes ONLY to TEST_RECIPIENT
# False = email goes to PRODUCTION_RECIPIENTS
# ---------------------------------------------------------------------------
SHIPMENT_TEST_MODE = False


# ---------------------------------------------------------------------------
# EDIT: Test email recipient
# ---------------------------------------------------------------------------
SHIPMENT_TEST_RECIPIENT = "sang.n@whitebird.ca"


# ---------------------------------------------------------------------------
# EDIT: Production recipients
#
# Separate multiple addresses with semicolons.
# ---------------------------------------------------------------------------
SHIPMENT_PRODUCTION_RECIPIENTS = (
    # "sang.n@whitebird.ca;"
    "sang.n@whitebird.ca;"
    "shipping@whitebird.ca;"
    "craig.a@whitebird.ca;"
    "william@whitebird.ca;"
    "allen.g@whitebird.ca;"
    "erin.l@moyydesign.com;"
    "catherine.s@moyydesign.com;"
)


# ╔═══════════════════════════════════════════════════════════════════════════╗
# ║ REPORT SETTINGS — EDIT HERE                                              ║
# ╚═══════════════════════════════════════════════════════════════════════════╝

# ---------------------------------------------------------------------------
# EDIT:
#
# Number of SHIPPING DAYS to display.
#
# Example:
#     4 = Today + next 3 business days
#     5 = Today + next 4 business days
# ---------------------------------------------------------------------------
NUMBER_OF_SHIPPING_DAYS = 4


# ╔═══════════════════════════════════════════════════════════════════════════╗
# ║ HELPER FUNCTIONS                                                          ║
# ╚═══════════════════════════════════════════════════════════════════════════╝


def subject_with_timestamp(base: str) -> str:
    """
    Create the email subject.

    Example:
        [14:32] Daily Shipment Report 2026-08-23

    EDIT:
        Change the text passed into this function in MAIN if you want
        a different report name.
    """

    now = datetime.now()

    return (
        f"[{now.strftime('%H:%M')}] "
        f"{base} "
        f"{now.strftime('%Y-%m-%d')}"
    )


def get_shipping_dates(
    start_date: date,
    count: int = NUMBER_OF_SHIPPING_DAYS,
) -> list[date]:
    """
    Return today's date plus the next business/shipping days.

    Weekends are skipped.

    Example if today is Friday:

        Friday
        Monday
        Tuesday
        Wednesday

    EDIT:
        If weekends should be included, remove the weekday check.
    """

    dates = []

    current = start_date

    while len(dates) < count:

        # Monday = 0
        # Tuesday = 1
        # ...
        # Friday = 4
        # Saturday = 5
        # Sunday = 6

        if current.weekday() < 5:
            dates.append(current)

        current += timedelta(days=1)

    return dates


def status_style(
    status: str,
    theme: dict,
) -> tuple[str, str]:
    """
    Return:

        background colour
        text colour

    based on shipment status.

    EDIT:
        Add/change status colours here.
    """

    status = str(status).strip().upper()

    styles = {

        "READY": (
            theme["ready_bg"],
            theme["ready_text"],
        ),

        "PARTIAL": (
            theme["partial_bg"],
            theme["partial_text"],
        ),

        "IN PRODUCTION": (
            theme["production_bg"],
            theme["production_text"],
        ),

        "NOT READY": (
            theme["not_ready_bg"],
            theme["not_ready_text"],
        ),
    }

    return styles.get(
        status,
        ("#f5f5f5", "#555555"),
    )


def fmt_num(value) -> str:
    """
    Format numeric values for the email.

    Example:

        1000      -> 1,000
        12500.5   -> 12,501
        NaN       -> 0

    EDIT:
        Change :.0f if you want decimal places.

        :.0f = 1,000
        :.1f = 1,000.0
        :.2f = 1,000.00
    """

    if pd.isna(value):
        return "0"

    try:

        return f"{float(value):,.0f}"

    except (ValueError, TypeError):

        return str(value)


def fmt_delivery_note(value) -> str:
    """
    Format the delivery note.

    Empty values return "".

    This prevents:

        nan
        None
        NaN
        empty strings

    from appearing in the email.
    """

    if value is None:
        return ""

    try:

        if pd.isna(value):
            return ""

    except (TypeError, ValueError):

        pass

    value = str(value).strip()

    if not value:
        return ""

    return value


def normalize_dataframe(
    df: pd.DataFrame,
) -> pd.DataFrame:
    """
    Clean and normalize the shipment report DataFrame.

    EDIT:
        Add any additional column cleanup here.
    """

    df = df.copy()

    # ═══════════════════════════════════════════════════════════════════════
    # DATES
    # ═══════════════════════════════════════════════════════════════════════

    df["ship date"] = pd.to_datetime(
        df["ship date"],
        errors="coerce",
    ).dt.date


    # ═══════════════════════════════════════════════════════════════════════
    # CITY
    # ═══════════════════════════════════════════════════════════════════════

    df["ship_city"] = (
        df["ship_city"]
        .fillna("UNKNOWN")
        .astype(str)
        .str.strip()
    )

    df.loc[
        df["ship_city"].eq(""),
        "ship_city",
    ] = "UNKNOWN"


    # ═══════════════════════════════════════════════════════════════════════
    # CUSTOMER
    # ═══════════════════════════════════════════════════════════════════════

    df["short_name"] = (
        df["short_name"]
        .fillna("UNKNOWN CUSTOMER")
        .astype(str)
        .str.strip()
    )

    df.loc[
        df["short_name"].eq(""),
        "short_name",
    ] = "UNKNOWN CUSTOMER"


    # ═══════════════════════════════════════════════════════════════════════
    # DELIVERY NOTE
    #
    # This is NOT converted to a numeric value.
    #
    # It will be displayed on the CUSTOMER row.
    # ═══════════════════════════════════════════════════════════════════════

    if "delivery note" not in df.columns:

        # If SQL does not return the column, create it.
        df["delivery note"] = ""

    else:

        df["delivery note"] = (
            df["delivery note"]
            .fillna("")
            .astype(str)
            .str.strip()
        )


    # ═══════════════════════════════════════════════════════════════════════
    # NUMERIC COLUMNS
    # ═══════════════════════════════════════════════════════════════════════

    numeric_columns = [
        "order_qty",
        "est num_skid",
        "actual_unit_available",
        "actual_qty_available",
        "total weight",
    ]

    for column in numeric_columns:

        if column in df.columns:

            df[column] = pd.to_numeric(
                df[column],
                errors="coerce",
            ).fillna(0)


    # ═══════════════════════════════════════════════════════════════════════
    # STATUS
    # ═══════════════════════════════════════════════════════════════════════

    if "shipment readiness" in df.columns:

        df["shipment readiness"] = (
            df["shipment readiness"]
            .fillna("NOT READY")
            .astype(str)
            .str.strip()
            .str.upper()
        )

    else:

        df["shipment readiness"] = "NOT READY"


    # ═══════════════════════════════════════════════════════════════════════
    # PRIORITY
    # ═══════════════════════════════════════════════════════════════════════

    if "priority" not in df.columns:

        df["priority"] = "REGULAR"

    else:

        df["priority"] = (
            df["priority"]
            .fillna("REGULAR")
            .astype(str)
            .str.strip()
        )

        df.loc[
            df["priority"].eq(""),
            "priority",
        ] = "REGULAR"


    return df


# ╔═══════════════════════════════════════════════════════════════════════════╗
# ║ SHIPMENT MAILER                                                           ║
# ╚═══════════════════════════════════════════════════════════════════════════╝


class ShipmentMailer:

    def __init__(self):

        self.scheduler = ScheduleService()


    # ═══════════════════════════════════════════════════════════════════════
    # FETCH REPORT
    # ═══════════════════════════════════════════════════════════════════════

    def fetch_report(self) -> pd.DataFrame:
        """
        Fetch shipment report from ScheduleService.

        EDIT:
            If your data source changes, modify this method.
        """

        return self.scheduler.fetch_shipment_report()


    # ═══════════════════════════════════════════════════════════════════════
    # BUILD HTML
    # ═══════════════════════════════════════════════════════════════════════

    def build_html(
        self,
        df: pd.DataFrame,
        subject: str,
    ) -> str:

        theme = THEMES[COLOUR_THEME]

        today = date.today()


        # ═══════════════════════════════════════════════════════════════════
        # NORMALIZE DATA
        # ═══════════════════════════════════════════════════════════════════

        df = normalize_dataframe(df)


        # ═══════════════════════════════════════════════════════════════════
        # REPORTING DATES
        # ═══════════════════════════════════════════════════════════════════

        report_dates = get_shipping_dates(
            today,
            NUMBER_OF_SHIPPING_DAYS,
        )


        # ═══════════════════════════════════════════════════════════════════
        # FILTER TO REPORTING WINDOW
        # ═══════════════════════════════════════════════════════════════════

        df = df[
            df["ship date"].isin(report_dates)
        ].copy()


        # ═══════════════════════════════════════════════════════════════════
        # SORT
        #
        # Date
        #   City
        #       Customer
        #           Order
        # ═══════════════════════════════════════════════════════════════════

        df = df.sort_values(
            [
                "ship date",
                "ship_city",
                "short_name",
                "order number",
            ],
            kind="stable",
        )


        # ╔══════════════════════════════════════════════════════════════════╗
        # ║ RESPONSIVE CSS                                                   ║
        # ╚══════════════════════════════════════════════════════════════════╝

        style = f"""
        <style>

            @media only screen and (max-width: 700px) {{

                .outer-table {{
                    width: 100% !important;
                }}

                .main-table {{
                    width: 100% !important;
                }}

                .order-table {{
                    width: 100% !important;
                }}

                .mobile-small {{
                    font-size: 10px !important;
                }}

                .city-title {{
                    font-size: 16px !important;
                }}

                .day-title {{
                    font-size: 18px !important;
                }}

                .customer-title {{
                    font-size: 12px !important;
                }}

                .delivery-note {{
                    display:block !important;
                    margin-top:5px !important;
                    margin-left:0 !important;
                }}

            }}

        </style>
        """


        # ╔══════════════════════════════════════════════════════════════════╗
        # ║ BUILD REPORT BODY                                                ║
        # ╚══════════════════════════════════════════════════════════════════╝

        body_html = ""


        # ═══════════════════════════════════════════════════════════════════
        # LOOP THROUGH SHIPPING DAYS
        # ═══════════════════════════════════════════════════════════════════

        for report_date in report_dates:

            day_df = df[
                df["ship date"] == report_date
            ]


            # Skip days with no shipments
            if day_df.empty:
                continue


            # ═══════════════════════════════════════════════════════════════
            # DAY LABEL
            # ═══════════════════════════════════════════════════════════════

            if report_date == today:

                day_label = (
                    f"TODAY — "
                    f"{report_date.strftime('%b %d')}"
                )

            elif report_date == today + timedelta(days=1):

                day_label = (
                    f"TOMORROW — "
                    f"{report_date.strftime('%b %d')}"
                )

            else:

                day_label = report_date.strftime(
                    "%A — %b %d"
                )


            # ═══════════════════════════════════════════════════════════════
            # DAY HEADER
            #
            # IMPORTANT:
            # There are 9 columns in the order table.
            # ═══════════════════════════════════════════════════════════════

            body_html += f"""
            <tr>

                <td colspan="9"
                    style="
                        background:{theme['day_bg']};
                        color:{theme['day_text']};
                        padding:16px 20px;
                        border-top:3px solid {theme['header_bg']};
                    ">

                    <div class="day-title"
                         style="
                            font-size:20px;
                            font-weight:700;
                            letter-spacing:0.4px;
                         ">

                        {day_label}

                    </div>

                </td>

            </tr>
            """


            # ╔══════════════════════════════════════════════════════════════╗
            # ║ CITY GROUP                                                   ║
            # ╚══════════════════════════════════════════════════════════════╝

            for city, city_df in day_df.groupby(
                "ship_city",
                sort=True,
                dropna=False,
            ):

                city = (
                    city
                    if pd.notna(city)
                    else "UNKNOWN"
                )


                # ═══════════════════════════════════════════════════════════
                # CITY HEADER
                # ═══════════════════════════════════════════════════════════

                body_html += f"""
                <tr>

                    <td colspan="9"
                        style="
                            background:{theme['city_bg']};
                            color:{theme['city_text']};
                            padding:12px 20px;
                            border-bottom:1px solid
                                {theme['border']};
                        ">

                        <div class="city-title"
                             style="
                                font-size:18px;
                                font-weight:700;
                                text-transform:uppercase;
                                letter-spacing:0.5px;
                             ">

                            {city}

                        </div>

                    </td>

                </tr>
                """


                # ╔══════════════════════════════════════════════════════════╗
                # ║ CUSTOMER GROUP                                            ║
                # ╚══════════════════════════════════════════════════════════╝

                for customer, customer_df in city_df.groupby(
                    "short_name",
                    sort=True,
                    dropna=False,
                ):

                    customer = (
                        customer
                        if pd.notna(customer)
                        else "UNKNOWN CUSTOMER"
                    )


                    # ═══════════════════════════════════════════════════════
                    # DELIVERY NOTE
                    #
                    # IMPORTANT:
                    #
                    # Delivery note is CUSTOMER-level information.
                    #
                    # We therefore get it once from customer_df instead
                    # of getting it inside every order row.
                    #
                    # If multiple different delivery notes exist for the
                    # same customer, they are joined with " | ".
                    # ═══════════════════════════════════════════════════════

                    delivery_note = ""

                    if "delivery note" in customer_df.columns:

                        notes = (
                            customer_df["delivery note"]
                            .dropna()
                            .astype(str)
                            .str.strip()
                        )

                        # Remove blank notes
                        notes = notes[
                            notes != ""
                        ]

                        # Remove duplicates
                        notes = notes.drop_duplicates()

                        if not notes.empty:

                            delivery_note = " | ".join(
                                notes.tolist()
                            )


                    # ═══════════════════════════════════════════════════════
                    # BUILD DELIVERY NOTE HTML
                    #
                    # Only show the note if one exists.
                    # ═══════════════════════════════════════════════════════

                    delivery_note_html = ""

                    if delivery_note:

                        delivery_note_html = f"""
                        <span class="delivery-note"
                              style="
                                margin-left:12px;
                                padding:4px 9px;
                                background:#fff3cd;
                                color:#856404;
                                border-radius:10px;
                                font-size:11px;
                                font-weight:600;
                                display:inline-block;
                              ">

                            Delivery: {delivery_note}

                        </span>
                        """


                    # ═══════════════════════════════════════════════════════
                    # CUSTOMER HEADER
                    # ═══════════════════════════════════════════════════════

                    body_html += f"""
                    <tr>

                        <td colspan="9"
                            style="
                                background:{theme['customer_bg']};
                                color:{theme['customer_text']};
                                padding:9px 25px;
                                border-bottom:1px solid
                                    {theme['border']};
                            ">

                            <div class="customer-title"
                                 style="
                                    font-size:13px;
                                    font-weight:700;
                                 ">

                                Customer: {customer}

                                {delivery_note_html}

                            </div>

                        </td>

                    </tr>
                    """


                    # ╔══════════════════════════════════════════════════════╗
                    # ║ COLUMN HEADERS                                        ║
                    # ╚══════════════════════════════════════════════════════╝

                    body_html += f"""
                    <tr style="background:#ffffff;">

                        <!-- ORDER -->

                        <td style="
                            padding:8px 10px 8px 25px;
                            border-bottom:1px solid
                                {theme['border']};
                            font-size:10px;
                            font-weight:700;
                            color:#666;
                            text-transform:uppercase;
                        ">
                            Order
                        </td>


                        <!-- DOCKET -->

                        <td style="
                            padding:8px;
                            border-bottom:1px solid
                                {theme['border']};
                            font-size:10px;
                            font-weight:700;
                            color:#666;
                            text-transform:uppercase;
                        ">
                            Docket
                        </td>


                        <!-- PRIORITY -->

                        <td style="
                            padding:8px;
                            border-bottom:1px solid
                                {theme['border']};
                            font-size:10px;
                            font-weight:700;
                            color:#666;
                            text-transform:uppercase;
                        ">
                            Priority
                        </td>


                        <!-- ORDER QTY -->

                        <td style="
                            padding:8px;
                            border-bottom:1px solid
                                {theme['border']};
                            font-size:10px;
                            font-weight:700;
                            color:#666;
                            text-align:right;
                        ">
                            Order Qty
                        </td>


                        <!-- EST SKIDS -->

                        <td style="
                            padding:8px;
                            border-bottom:1px solid
                                {theme['border']};
                            font-size:10px;
                            font-weight:700;
                            color:#666;
                            text-align:right;
                        ">
                            Est. Skids
                        </td>


                        <!-- UNITS -->

                        <td style="
                            padding:8px;
                            border-bottom:1px solid
                                {theme['border']};
                            font-size:10px;
                            font-weight:700;
                            color:#666;
                            text-align:right;
                        ">
                            Units
                        </td>


                        <!-- AVAILABLE QTY -->

                        <td style="
                            padding:8px;
                            border-bottom:1px solid
                                {theme['border']};
                            font-size:10px;
                            font-weight:700;
                            color:#666;
                            text-align:right;
                        ">
                            Qty Available
                        </td>


                        <!-- WEIGHT -->

                        <td style="
                            padding:8px;
                            border-bottom:1px solid
                                {theme['border']};
                            font-size:10px;
                            font-weight:700;
                            color:#666;
                            text-align:right;
                        ">
                            Weight
                        </td>


                        <!-- STATUS -->

                        <td style="
                            padding:8px 20px 8px 8px;
                            border-bottom:1px solid
                                {theme['border']};
                            font-size:10px;
                            font-weight:700;
                            color:#666;
                            text-align:center;
                        ">
                            Status
                        </td>

                    </tr>
                    """


                    # ╔══════════════════════════════════════════════════════╗
                    # ║ ORDER ROWS                                            ║
                    # ╚══════════════════════════════════════════════════════╝

                    for row_index, (_, row) in enumerate(
                        customer_df.iterrows()
                    ):

                        # ---------------------------------------------------
                        # Alternating row background
                        # ---------------------------------------------------

                        bg = (
                            theme["row_odd"]
                            if row_index % 2 == 0
                            else theme["row_even"]
                        )


                        # ---------------------------------------------------
                        # Status
                        # ---------------------------------------------------

                        status = str(
                            row.get(
                                "shipment readiness",
                                "NOT READY",
                            )
                        ).strip().upper()


                        status_bg, status_text = status_style(
                            status,
                            theme,
                        )


                        # ---------------------------------------------------
                        # Values
                        #
                        # EDIT:
                        # Add/remove fields here if you add columns.
                        # ---------------------------------------------------

                        order_number = row.get(
                            "order number",
                            "",
                        )

                        docket_id = row.get(
                            "docket_id",
                            "",
                        )

                        priority = row.get(
                            "priority",
                            "REGULAR",
                        )

                        order_qty = row.get(
                            "order_qty",
                            0,
                        )

                        est_skids = row.get(
                            "est num_skid",
                            0,
                        )

                        units = row.get(
                            "actual_unit_available",
                            0,
                        )

                        qty_available = row.get(
                            "actual_qty_available",
                            0,
                        )

                        weight = row.get(
                            "total weight",
                            0,
                        )


                        # ═══════════════════════════════════════════════════
                        # ORDER ROW
                        #
                        # DELIVERY NOTE IS INTENTIONALLY NOT HERE.
                        #
                        # It is displayed once on the customer row above.
                        # ═══════════════════════════════════════════════════

                        body_html += f"""
                        <tr style="background:{bg};">

                            <!-- ORDER -->

                            <td style="
                                padding:9px 10px 9px 25px;
                                border-bottom:1px solid
                                    {theme['border']};
                                font-size:12px;
                                font-weight:600;
                                color:{theme['header_bg']};
                                white-space:nowrap;
                            ">

                                {order_number}

                            </td>


                            <!-- DOCKET -->

                            <td style="
                                padding:9px 8px;
                                border-bottom:1px solid
                                    {theme['border']};
                                font-size:12px;
                                color:#555;
                                white-space:nowrap;
                            ">

                                {docket_id}

                            </td>


                            <!-- PRIORITY -->

                            <td style="
                                padding:9px 8px;
                                border-bottom:1px solid
                                    {theme['border']};
                                font-size:12px;
                                color:#555;
                                white-space:nowrap;
                            ">

                                {priority}

                            </td>


                            <!-- ORDER QTY -->

                            <td style="
                                padding:9px 8px;
                                border-bottom:1px solid
                                    {theme['border']};
                                font-size:12px;
                                text-align:right;
                                white-space:nowrap;
                            ">

                                {fmt_num(order_qty)}

                            </td>


                            <!-- EST SKIDS -->

                            <td style="
                                padding:9px 8px;
                                border-bottom:1px solid
                                    {theme['border']};
                                font-size:12px;
                                text-align:right;
                                white-space:nowrap;
                            ">

                                {fmt_num(est_skids)}

                            </td>


                            <!-- UNITS -->

                            <td style="
                                padding:9px 8px;
                                border-bottom:1px solid
                                    {theme['border']};
                                font-size:12px;
                                text-align:right;
                                white-space:nowrap;
                            ">

                                {fmt_num(units)}

                            </td>


                            <!-- AVAILABLE QTY -->

                            <td style="
                                padding:9px 8px;
                                border-bottom:1px solid
                                    {theme['border']};
                                font-size:12px;
                                text-align:right;
                                white-space:nowrap;
                            ">

                                {fmt_num(qty_available)}

                            </td>


                            <!-- WEIGHT -->

                            <td style="
                                padding:9px 8px;
                                border-bottom:1px solid
                                    {theme['border']};
                                font-size:12px;
                                text-align:right;
                                white-space:nowrap;
                            ">

                                {fmt_num(weight)}

                            </td>


                            <!-- STATUS -->

                            <td style="
                                padding:6px 20px 6px 8px;
                                border-bottom:1px solid
                                    {theme['border']};
                                text-align:center;
                            ">

                                <span style="
                                    display:inline-block;
                                    background:{status_bg};
                                    color:{status_text};
                                    padding:5px 9px;
                                    border-radius:12px;
                                    font-size:10px;
                                    font-weight:700;
                                    white-space:nowrap;
                                ">

                                    {status}

                                </span>

                            </td>

                        </tr>
                        """


        # ╔══════════════════════════════════════════════════════════════════╗
        # ║ NO RECORDS                                                       ║
        # ╚══════════════════════════════════════════════════════════════════╝

        if not body_html:

            body_html = f"""
            <tr>

                <td colspan="9"
                    style="
                        padding:35px 20px;
                        text-align:center;
                        color:#777;
                        font-size:13px;
                    ">

                    No shipments scheduled for the
                    next {NUMBER_OF_SHIPPING_DAYS}
                    shipping days.

                </td>

            </tr>
            """


        # ╔══════════════════════════════════════════════════════════════════╗
        # ║ FINAL HTML                                                       ║
        # ╚══════════════════════════════════════════════════════════════════╝

        today_text = today.strftime("%Y-%m-%d")


        html = f"""
        <!DOCTYPE html>

        <html lang="en">

        <head>

            <meta charset="UTF-8"/>

            <meta name="viewport"
                  content="width=device-width,
                           initial-scale=1.0"/>

            {style}

        </head>


        <body style="
            margin:0;
            padding:0;
            font-family:Arial,Helvetica,sans-serif;
            background:#f0f4f8;
        ">


        <!-- ═══════════════════════════════════════════════════════════════ -->
        <!-- OUTER TABLE                                                     -->
        <!-- ═══════════════════════════════════════════════════════════════ -->

        <table class="outer-table"
               width="100%"
               cellpadding="0"
               cellspacing="0"
               style="
                    background:#f0f4f8;
                    padding:16px;
               ">

            <tr>

                <td align="center">


                    <!-- ════════════════════════════════════════════════ -->
                    <!-- MAIN REPORT                                      -->
                    <!-- ════════════════════════════════════════════════ -->

                    <table class="main-table"
                           width="1000"
                           cellpadding="0"
                           cellspacing="0"
                           style="
                                max-width:1000px;
                                background:#ffffff;
                                border-radius:10px;
                                overflow:hidden;
                                box-shadow:
                                    0 2px 12px
                                    rgba(0,0,0,0.08);
                           ">


                        <!-- ═══════════════════════════════════════════ -->
                        <!-- HEADER                                      -->
                        <!-- ═══════════════════════════════════════════ -->

                        <tr>

                            <td colspan="9"
                                style="
                                    background:{theme['header_bg']};
                                    color:{theme['header_text']};
                                    padding:22px 24px;
                                    text-align:center;
                                ">

                                <div style="
                                    font-size:21px;
                                    font-weight:700;
                                    letter-spacing:0.5px;
                                ">

                                    {subject}

                                </div>


                                <div style="
                                    font-size:11px;
                                    margin-top:5px;
                                    opacity:0.65;
                                ">

                                    Generated {today_text}

                                </div>

                            </td>

                        </tr>


                        <!-- ═══════════════════════════════════════════ -->
                        <!-- TEST MODE BANNER                             -->
                        <!-- ═══════════════════════════════════════════ -->

                        {
                            f'''
                            <tr>

                                <td colspan="9"
                                    style="
                                        background:#fff3cd;
                                        color:#856404;
                                        padding:10px;
                                        text-align:center;
                                        font-size:12px;
                                        border-bottom:
                                            2px solid #ffc107;
                                    ">

                                    &#9888;
                                    TEST MODE —
                                    email sent only to
                                    {SHIPMENT_TEST_RECIPIENT}

                                </td>

                            </tr>
                            '''
                            if SHIPMENT_TEST_MODE
                            else ""
                        }


                        <!-- ═══════════════════════════════════════════ -->
                        <!-- INTRO                                        -->
                        <!-- ═══════════════════════════════════════════ -->

                        <tr>

                            <td colspan="9"
                                style="
                                    padding:14px 22px;
                                    font-size:13px;
                                    line-height:1.6;
                                    color:#444;
                                    border-bottom:1px solid #eee;
                                ">

                                <strong>
                                    Shipment Schedule
                                </strong>

                                <br/>

                                Showing today's shipments and
                                the next 3 shipping days.

                                <br/>

                            </td>

                        </tr>


                        <!-- ═══════════════════════════════════════════ -->
                        <!-- REPORT BODY                                  -->
                        <!-- ═══════════════════════════════════════════ -->

                        {body_html}


                        <!-- ═══════════════════════════════════════════ -->
                        <!-- FOOTER                                       -->
                        <!-- ═══════════════════════════════════════════ -->

                        <tr>

                            <td colspan="9"
                                style="
                                    background:{theme['footer_bg']};
                                    padding:14px 24px;
                                    text-align:center;
                                    font-size:11px;
                                    color:{theme['footer_text']};
                                    letter-spacing:0.3px;
                                ">

                                Moyy Design
                                &nbsp;&#xb7;&nbsp;
                                Shipment Report
                                &nbsp;&#xb7;&nbsp;
                                Sent {today_text}

                            </td>

                        </tr>


                    </table>

                </td>

            </tr>

        </table>

        </body>

        </html>
        """


        return html


    # ╔══════════════════════════════════════════════════════════════════════╗
    # ║ SEND EMAIL                                                           ║
    # ╚══════════════════════════════════════════════════════════════════════╝

    def send_email(
        self,
        to: str,
        subject: str,
        df: pd.DataFrame,
        cc: str | None = None,
    ):
        """
        Send the shipment report through Outlook.

        EDIT:
            This method is normally not something you need to change.
        """

        # Build HTML
        html = self.build_html(
            df=df,
            subject=subject,
        )


        # Initialize COM
        pythoncom.CoInitialize()

        try:

            # ═══════════════════════════════════════════════════════════════
            # CONNECT TO OUTLOOK
            # ═══════════════════════════════════════════════════════════════

            try:

                outlook = win32.GetActiveObject(
                    "Outlook.Application"
                )

            except Exception:

                try:

                    outlook = win32.Dispatch(
                        "Outlook.Application"
                    )

                except Exception as e:

                    raise RuntimeError(
                        "Cannot bind to Outlook — "
                        "ensure Outlook is running."
                    ) from e


            # ═══════════════════════════════════════════════════════════════
            # CREATE EMAIL
            # ═══════════════════════════════════════════════════════════════

            mail = outlook.CreateItem(0)


            # EDIT:
            # Recipient is passed into this function from MAIN.
            mail.To = to


            # Subject
            mail.Subject = subject


            # HTML body
            mail.HTMLBody = html


            # Optional CC
            if cc:

                mail.CC = cc


            # ═══════════════════════════════════════════════════════════════
            # SEND
            # ═══════════════════════════════════════════════════════════════

            mail.Send()

        finally:

            # Always release COM
            pythoncom.CoUninitialize()


# ╔═══════════════════════════════════════════════════════════════════════════╗
# ║ MAIN                                                                      ║
# ╚═══════════════════════════════════════════════════════════════════════════╝


if __name__ == "__main__":

    import traceback


    try:

        print("=" * 70)
        print("DAILY SHIPMENT REPORT")
        print("=" * 70)


        # ═══════════════════════════════════════════════════════════════════
        # INITIALIZE
        # ═══════════════════════════════════════════════════════════════════

        mailer = ShipmentMailer()


        # ═══════════════════════════════════════════════════════════════════
        # REPORTING DATES
        # ═══════════════════════════════════════════════════════════════════

        today = date.today()

        shipping_dates = get_shipping_dates(
            today,
            NUMBER_OF_SHIPPING_DAYS,
        )


        print()
        print("Reporting dates:")

        for report_date in shipping_dates:

            print(
                f"  - {report_date.strftime('%A %Y-%m-%d')}"
            )


        # ═══════════════════════════════════════════════════════════════════
        # FETCH REPORT
        # ═══════════════════════════════════════════════════════════════════

        print()
        print("Fetching shipment report...")


        df = mailer.fetch_report()


        # ═══════════════════════════════════════════════════════════════════
        # CHECK FOR EMPTY REPORT
        # ═══════════════════════════════════════════════════════════════════

        if df is None or df.empty:

            print(
                "No shipments found — aborting."
            )


        else:

            print(
                f"Found {len(df):,} shipment order lines."
            )


            # ═══════════════════════════════════════════════════════════════
            # NORMALIZE DATA
            # ═══════════════════════════════════════════════════════════════

            normalized_df = normalize_dataframe(df)


            # ═══════════════════════════════════════════════════════════════
            # FILTER REPORTING WINDOW
            # ═══════════════════════════════════════════════════════════════

            report_df = normalized_df[
                normalized_df["ship date"].isin(
                    shipping_dates
                )
            ]


            print(
                f"Shipments in reporting window: "
                f"{len(report_df):,}"
            )


            # ╔══════════════════════════════════════════════════════════════╗
            # ║ CONSOLE GROUPING                                              ║
            # ╚══════════════════════════════════════════════════════════════╝

            if not report_df.empty:

                print()
                print("Shipment grouping:")


                for report_date in shipping_dates:

                    day_df = report_df[
                        report_df["ship date"] == report_date
                    ]


                    if day_df.empty:
                        continue


                    print(
                        f"\n{report_date.strftime('%A %Y-%m-%d')}"
                    )


                    for city, city_df in day_df.groupby(
                        "ship_city",
                        sort=True,
                    ):

                        customer_count = (
                            city_df["short_name"]
                            .nunique()
                        )

                        order_count = len(city_df)


                        print(
                            f"  {city}: "
                            f"{customer_count} customers, "
                            f"{order_count} order lines"
                        )


            # ╔══════════════════════════════════════════════════════════════╗
            # ║ RECIPIENT                                                     ║
            # ╚══════════════════════════════════════════════════════════════╝

            # EDIT:
            # TEST_MODE controls which recipient is used.

            recipient = (
                SHIPMENT_TEST_RECIPIENT
                if SHIPMENT_TEST_MODE
                else SHIPMENT_PRODUCTION_RECIPIENTS
            )


            # ╔══════════════════════════════════════════════════════════════╗
            # ║ SUBJECT                                                        ║
            # ╚══════════════════════════════════════════════════════════════╝

            # EDIT:
            # Change "Daily Shipment Report" here if desired.

            subject = subject_with_timestamp(
                "Daily Shipment Report"
            )


            print()

            print(
                f"Sending → "
                f"{'TEST' if SHIPMENT_TEST_MODE else 'PRODUCTION'}"
            )

            print(
                f"Recipient → {recipient}"
            )

            print(
                f"Subject → {subject}"
            )


            # ╔══════════════════════════════════════════════════════════════╗
            # ║ SEND EMAIL                                                    ║
            # ╚══════════════════════════════════════════════════════════════╝

            mailer.send_email(
                to=recipient,
                subject=subject,
                df=df,
            )


            print()

            print(
                "Shipment email sent successfully."
            )


        print("=" * 70)


    except Exception as e:

        print()

        print(
            f"Fatal: {e}"
        )

        traceback.print_exc()