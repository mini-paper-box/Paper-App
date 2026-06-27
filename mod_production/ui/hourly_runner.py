print("ALIVE", flush=True)
import sys
import os
import time
import traceback
import logging
from datetime import datetime, timedelta

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

# Explicitly build our own logger — bypasses root logger conflicts
LOG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "automation.log")

logger = logging.getLogger("hourly_runner")
logger.setLevel(logging.INFO)

file_handler = logging.FileHandler(LOG_PATH)
file_handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s", "%Y-%m-%d %H:%M:%S"))

stream_handler = logging.StreamHandler(sys.stdout)
stream_handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s", "%Y-%m-%d %H:%M:%S"))

logger.addHandler(file_handler)
logger.addHandler(stream_handler)

logger.info("🟢 Script starting...")

try:
    from mod_production.predict_daily_leadtime_v2 import SchedulerMailer, add_workdays, workdays_between
    logger.info("✅ Import successful")
except Exception as e:
    logger.error(f"❌ Import failed: {e}")
    logger.error(traceback.format_exc())
    sys.exit(1)

def run_my_pipeline():
    start = datetime.now()
    logger.info("🚀 Pipeline triggered")
    try:
        # ... your pipeline code, replacing all logging.info with logger.info ...
        pass
    except Exception as e:
        logger.error(f"❌ Pipeline error: {e}")
        logger.error(traceback.format_exc())

if __name__ == "__main__":
    logger.info("🧪 Running pipeline directly first...")
    run_my_pipeline()
    logger.info("🧪 Direct call done.")

    scheduler = BackgroundScheduler()
    scheduler.add_job(
        run_my_pipeline,
        CronTrigger(minute="*/10"),
        id="pipeline_trigger",
        max_instances=1,
        coalesce=True,
        misfire_grace_time=300,
    )

    logger.info("⏰ Scheduler started — every 10 minutes")
    scheduler.start()

    try:
        while True:
            time.sleep(2)
    except (KeyboardInterrupt, SystemExit):
        logger.info("Stopping scheduler...")
        scheduler.shutdown()
    except Exception as e:
        logger.error(f"❌ Loop crashed: {e}")
        logger.error(traceback.format_exc())
        scheduler.shutdown()