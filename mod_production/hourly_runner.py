import sys
import os
import time
import logging
import traceback
from datetime import datetime

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

# ── Logging ────────────────────────────────────────────────────────────────
LOG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "automation.log")
fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s", "%Y-%m-%d %H:%M:%S")

file_handler = logging.FileHandler(LOG_PATH, encoding="utf-8")
file_handler.setFormatter(fmt)

stream_handler = logging.StreamHandler(
    open(sys.stdout.fileno(), mode="w", encoding="utf-8", buffering=1, closefd=False)
)
stream_handler.setFormatter(fmt)

logger = logging.getLogger("hourly_runner")
logger.setLevel(logging.INFO)
logger.addHandler(file_handler)
logger.addHandler(stream_handler)
logger.propagate = False

logger.info("hourly_runner.py starting...")

# ── Import pipeline ────────────────────────────────────────────────────────
try:
    from mod_production.predict_daily_leadtime_v2 import (
        SchedulerMailer,
        add_workdays,
        workdays_between,
        build_tier_starts,
        subject_with_timestamp,
        JOBS,
        PRODUCTION_RECIPIENTS,
        TEST_MODE,
        TEST_RECIPIENT,
        TIER_START_OFFSET,
        DEFAULT_LEAD_DAYS,
        EXCLUDED_PROCESS_IDS,
    )
    from mod_production.shipment_report import (
        ShipmentMailer,
        SHIPMENT_TEST_MODE,
        SHIPMENT_TEST_RECIPIENT,
        SHIPMENT_PRODUCTION_RECIPIENTS)
    logger.info("Import successful")
except Exception as e:
    logger.error(f"Import failed: {e}")
    logger.error(traceback.format_exc())
    sys.exit(1)


# ── Pipeline ───────────────────────────────────────────────────────────────
def run_my_pipeline():
    start = datetime.now()
    logger.info("Pipeline triggered")

    try:
        company_holidays = {
            datetime(2026, 1, 1).date(),
            datetime(2026, 12, 25).date(),
        }

        scheduler_mailer = SchedulerMailer()
        today            = datetime.today().date()
        tier_start_date  = add_workdays(today, TIER_START_OFFSET, company_holidays)

        logger.info(f"Processing {len(JOBS)} jobs...")
        email_rows = []

        for job_key, (docket_id, qty) in JOBS.items():
            logger.info(f"  {job_key} ({docket_id}) qty={qty:,}")

            try:
                steps = scheduler_mailer.run_schedule(docket_id, qty)
            except Exception as e:
                logger.warning(f"  SKIP {job_key} — schedule error: {e}")
                continue

            if not steps:
                logger.warning(f"  SKIP {job_key} — no routing returned")
                continue

            # Route label from actual process names
            route_label = " \u2192 ".join(s["process_name"].split()[0] for s in steps)

            # Filter visible steps
            visible = [
                s for s in steps
                if s.get("process_id") not in EXCLUDED_PROCESS_IDS
            ]
            if not visible:
                logger.warning(f"  SKIP {job_key} — all steps excluded")
                continue

            # Tier start dates — 1 workday apart
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

            chain_end = steps[-1]["end"]
            if not chain_end:
                logger.warning(f"  SKIP {job_key} — no end date")
                continue

            ship_date       = add_workdays(chain_end, 1, company_holidays)
            lead_days_count = workdays_between(today, ship_date, company_holidays)
            # lead_days_count = workdays_between(today, chain_end, company_holidays)

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

        if not email_rows:
            logger.warning("No rows to send — aborting email")
            return

        recipient = TEST_RECIPIENT if TEST_MODE else PRODUCTION_RECIPIENTS #PRODUCTION_RECIPIENTS
        subject   = subject_with_timestamp("Timeline Agreement")

        logger.info(f"Sending to {'TEST' if TEST_MODE else 'PRODUCTION'}")
        logger.info(f"Subject: {subject}")

        scheduler_mailer.send_email(
            to         = recipient,
            subject    = subject,
            email_rows = email_rows,
        )

        duration = (datetime.now() - start).total_seconds()
        logger.info(f"Pipeline finished ({duration:.1f}s)")

    except Exception as e:
        logger.error(f"Pipeline error: {e}")
        logger.error(traceback.format_exc())

# ── Shipment Report Pipeline ────────────────────────────────────────────────
def run_shipment_report():
    """
    Send the daily shipment report.

    EDIT NOTE:
    This job is scheduled separately from the Timeline Agreement job.
    Current schedule: Monday-Friday at 4:30 PM.
    """

    start = datetime.now()

    logger.info("=" * 70)
    logger.info("Shipment Report triggered")
    logger.info("=" * 70)

    try:

        shipment_mailer = ShipmentMailer()

        logger.info("Fetching shipment report...")

        df = shipment_mailer.fetch_report()

        if df is None or df.empty:

            logger.warning(
                "Shipment Report — no shipments found, email not sent."
            )

            return

        logger.info(
            f"Shipment Report — found {len(df):,} shipment order lines."
        )

        # ─────────────────────────────────────────────────────────────────
        # Recipient
        #
        # EDIT NOTE:
        # TEST_MODE comes from your shipment_mailer.py.
        #
        # True  = TEST_RECIPIENT
        # False = PRODUCTION_RECIPIENTS
        # ─────────────────────────────────────────────────────────────────

        recipient = (
            SHIPMENT_TEST_RECIPIENT
            if SHIPMENT_TEST_MODE
            else SHIPMENT_PRODUCTION_RECIPIENTS
        )

        subject = subject_with_timestamp(
            "Daily Shipment Report"
        )

        logger.info(
            f"Shipment Report sending to "
            f"{'TEST' if SHIPMENT_TEST_MODE else 'PRODUCTION'}"
        )

        logger.info(
            f"Recipient: {recipient}"
        )

        logger.info(
            f"Subject: {subject}"
        )

        # ─────────────────────────────────────────────────────────────────
        # Send email
        # ─────────────────────────────────────────────────────────────────

        shipment_mailer.send_email(
            to=recipient,
            subject=subject,
            df=df,
        )

        duration = (
            datetime.now() - start
        ).total_seconds()

        logger.info(
            f"Shipment Report finished successfully "
            f"({duration:.1f}s)"
        )

        logger.info("=" * 70)

    except Exception as e:

        logger.error(
            f"Shipment Report error: {e}"
        )

        logger.error(
            traceback.format_exc()
        )

# ── Entry point ────────────────────────────────────────────────────────────
if __name__ == "__main__":

    # Uncomment to fire once immediately on startup for testing
    # logger.info("Running pipeline once immediately...")
    run_shipment_report()
    # logger.info("Done. Starting scheduler...")

    scheduler = BackgroundScheduler()
    scheduler.add_job(
        run_my_pipeline,
        CronTrigger(
            hour="6-15",
            day_of_week="mon-fri",
            minute="0"
        ),
        id="pipeline_trigger",
        max_instances=1,
        coalesce=True,
        misfire_grace_time=300,
    )

    # ── Shipment Report — 4:30 PM Mon-Fri ───────────────────────────────────────
    scheduler.add_job(
        run_shipment_report,
        CronTrigger(
            hour=16,
            minute=30,
            day_of_week="mon-fri"
        ),
        id="shipment_report_trigger",
        max_instances=1,
        coalesce=True,
        misfire_grace_time=300,
    )

    scheduler.start()
    logger.info(
        "Shipment Report scheduled — Monday-Friday at 4:30 PM"
    )
    logger.info("Scheduler running — hourly Mon-Fri 6 AM to 3 PM")

    try:
        while True:
            time.sleep(2)
    except (KeyboardInterrupt, SystemExit):
        logger.info("Stopping scheduler...")
        scheduler.shutdown()
    except Exception as e:
        logger.error(f"Loop crashed: {e}")
        logger.error(traceback.format_exc())
        scheduler.shutdown()