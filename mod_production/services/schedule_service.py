import logging
import logging.handlers
import os
from datetime import datetime, date, timedelta

import pandas as pd

from mod_production.data.sql_manager import SQLManager
from mod_production.core.predictor2 import ProductionAI


# ---------------------------------------------------------------------------
# Logging setup
# ---------------------------------------------------------------------------
# Main application logger (INFO and above)
logger = logging.getLogger(__name__)

# Dedicated per-day scheduling trace logger (DEBUG — writes to rotating file)
sched_logger = logging.getLogger(f"{__name__}.schedule_trace")


def _configure_schedule_log(log_dir: str = "logs", max_bytes: int = 10 * 1024 * 1024, backup_count: int = 7) -> None:
    """
    Attach a rotating file handler to the schedule_trace logger.
    Call once at application startup (or let ScheduleService.__init__ call it).
    Safe to call multiple times — skips setup if a file handler already exists.
    """
    if any(isinstance(h, logging.handlers.RotatingFileHandler) for h in sched_logger.handlers):
        return

    os.makedirs(log_dir, exist_ok=True)
    log_path = os.path.join(log_dir, "schedule_trace.log")

    handler = logging.handlers.RotatingFileHandler(
        log_path, maxBytes=max_bytes, backupCount=backup_count, encoding="utf-8"
    )
    handler.setLevel(logging.DEBUG)
    handler.setFormatter(logging.Formatter(
        "%(asctime)s  %(levelname)-8s  %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    ))

    sched_logger.setLevel(logging.DEBUG)
    sched_logger.propagate = False   # don't flood the root logger with trace lines
    sched_logger.addHandler(handler)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

FARMOUT_PROCESS_IDS  = frozenset({236, 257})
FARMOUT_BUFFER_DAYS  = 5
PLANNING_HORIZON     = 90          # workdays for build_schedule
BATCH_HORIZON        = 120         # workdays for build_schedule_from_df
MIN_START_AVAIL_MINS = 60          # candidate day must have at least this free
MIN_BLOCK_AVAIL_MINS = 60          # skip days below this (unless job finishes)
FALLBACK_BASE_MINS   = 15.0
FALLBACK_PER_UNIT    = 0.01


class SchedulingError(Exception):
    """Raised when a process cannot be placed within the planning horizon."""


# ---------------------------------------------------------------------------
# Module-level calendar helpers
# ---------------------------------------------------------------------------

def _normalize_date(d) -> date:
    return d.date() if isinstance(d, datetime) else d


def _add_workdays(start: date, n: int, holidays: set) -> date:
    """Advance n working days forward, skipping weekends and holidays."""
    current = start
    added = 0
    while added < n:
        current += timedelta(days=1)
        if current.weekday() < 5 and current not in holidays:
            added += 1
    return current


def _first_workday_after_lead(lead_days: int, holidays: set) -> date:
    """Return the first working date strictly after lead_days working days from today."""
    current = date.today()
    counted = 0
    while counted < lead_days:
        current += timedelta(days=1)
        if current.weekday() < 5 and current not in holidays:
            counted += 1
    current += timedelta(days=1)
    while current.weekday() >= 5 or current in holidays:
        current += timedelta(days=1)
    return current


def _build_workdays(start: date, n: int, holidays: set) -> list[date]:
    """Return a list of n working dates beginning on or after start."""
    days: list[date] = []
    current = start
    while len(days) < n:
        if current.weekday() < 5 and current not in holidays:
            days.append(current)
        current += timedelta(days=1)
    return days


def _build_capacity_lookup(process_df: pd.DataFrame) -> dict[int, dict[int, float]]:
    """
    Build {process_id: {isoweekday: capacity_hours}}.
    isoweekday() 1=Mon … 7=Sun matches capacity_1 … capacity_7 columns directly.
    """
    return {
        r.process_id: {
            1: r.capacity_1, 2: r.capacity_2, 3: r.capacity_3,
            4: r.capacity_4, 5: r.capacity_5, 6: r.capacity_6,
            7: r.capacity_7,
        }
        for r in process_df.itertuples()
    }


# ---------------------------------------------------------------------------
# ScheduleService
# ---------------------------------------------------------------------------

class ScheduleService:

    def __init__(self, holidays=None, process_df=None, booked_mins_lookup=None,
                 log_dir: str = "logs"):
        """
        Initialize scheduling engine and preload finite-capacity datasets.
        Pass holidays and process_df to skip the DB fetch (useful in tests).
        log_dir controls where schedule_trace.log is written.
        """
        _configure_schedule_log(log_dir=log_dir)

        self.db        = SQLManager()
        self.ai_engine = ProductionAI()

        self.by_pass_dates: dict[int, set[date]] = {
            69:  {date(2026, 5, 29)},
            166: {date(2026, 6, 17)},
            189: {date(2026, 6, 15), date(2026, 6, 16), date(2026, 6, 17),
                  date(2026, 6, 18), date(2026, 6, 19), date(2026, 6, 22)},
        }

        self.booked_mins_lookup: dict[tuple, float] = {}
        self.booked_jobs_lookup: dict[tuple, int]   = {}
        self.booked_sqft_lookup: dict[tuple, float] = {}

        if holidays is None or process_df is None:
            self.initialize_capacity_cache()
        else:
            self.raw_jobs   = None
            self.holidays   = holidays
            self.process_df = process_df

    # ------------------------------------------------------------------ #
    #  Cache initialisation                                                #
    # ------------------------------------------------------------------ #

    def initialize_capacity_cache(self) -> None:
        """
        Load booked jobs and build fast in-memory lookup dicts.
        Falls back gracefully on any error.
        """
        try:
            start_time = datetime.now()

            raw_jobs, self.holidays, self.process_df = (
                self.db.fetch_booked_and_holidays_and_process()
            )

            if raw_jobs is None or raw_jobs.empty:
                self._initialize_empty_cache()
                return

            if not self.ai_engine.is_trained:
                self._build_cache_with_fallback(raw_jobs)
                return

            processed_df = self._predict_for_cache(raw_jobs)

            processed_df['booked_sqft'] = (
                processed_df['job_qty'] * processed_df['sqfpm'] / 1000
            )

            self.booked_df = processed_df.groupby(
                ['process_id', 'schedule_date'], as_index=False
            ).agg(
                mins_booked=('total_m',     'sum'),
                booked_sqft=('booked_sqft', 'sum'),
                booked_jobs=('process_id',  'count'),
            )

            self.booked_mins_lookup = {
                (r.process_id, r.schedule_date): r.mins_booked
                for r in self.booked_df.itertuples()
            }
            self.booked_sqft_lookup = {
                (r.process_id, r.schedule_date): r.booked_sqft
                for r in self.booked_df.itertuples()
            }
            self.booked_jobs_lookup = {
                (r.process_id, r.schedule_date): r.booked_jobs
                for r in self.booked_df.itertuples()
            }

            self.cache_load_seconds = (datetime.now() - start_time).total_seconds()
            logger.info("Capacity cache loaded in %.2fs", self.cache_load_seconds)

        except Exception:
            logger.exception("initialize_capacity_cache failed — using empty cache")
            self._initialize_empty_cache()

    def _predict_for_cache(self, raw_jobs: pd.DataFrame) -> pd.DataFrame:
        """Run AI prediction for cache build; falls back to a linear formula on failure."""

        def _fallback(df):
            return [FALLBACK_BASE_MINS + r.job_qty * FALLBACK_PER_UNIT
                    for r in df.itertuples()]

        for col, default in [('style_id', 'UNKNOWN'), ('printing_id', 'UNKNOWN'),
                              ('full_path', ''), ('sqfpm', 1000)]:
            raw_jobs[col] = raw_jobs.get(col, default)
            if hasattr(raw_jobs[col], 'fillna'):
                raw_jobs[col] = raw_jobs[col].fillna(default)

        try:
            if hasattr(self.ai_engine, 'predict_batch'):
                batch_df = pd.DataFrame({
                    'process_id':  raw_jobs['process_id'],
                    'style_id':    raw_jobs['style_id'],
                    'printing_id': raw_jobs['printing_id'],
                    'full_path':   raw_jobs['full_path'],
                    'qty':         raw_jobs['job_qty'],
                    'sqfpm':       raw_jobs['sqfpm'],
                })
                predictions  = self.ai_engine.predict_batch(batch_df)
                processed_df = pd.concat(
                    [raw_jobs.reset_index(drop=True),
                     predictions.reset_index(drop=True)],
                    axis=1,
                )
            else:
                total_mins: list[float] = []
                for _, job in raw_jobs.iterrows():
                    try:
                        t, *_ = self.ai_engine.predict_ai(
                            job['process_id'], job['style_id'], job['printing_id'],
                            job['full_path'], job['job_qty'], job['sqfpm'], buffer=True,
                        )
                        total_mins.append(float(t))
                    except Exception:
                        total_mins.append(FALLBACK_BASE_MINS + job['job_qty'] * FALLBACK_PER_UNIT)

                processed_df = raw_jobs.copy()
                processed_df['total_m'] = total_mins

        except Exception:
            logger.exception("AI prediction failed in cache build — using linear fallback")
            processed_df = raw_jobs.copy()
            processed_df['total_m'] = _fallback(raw_jobs)

        return processed_df

    def _initialize_empty_cache(self) -> None:
        """Set up empty scheduling structures when no historical bookings exist."""
        self.booked_df = pd.DataFrame(
            columns=['process_id', 'schedule_date', 'mins_booked', 'booked_sqft', 'booked_jobs']
        )
        self.booked_mins_lookup = {}
        self.booked_jobs_lookup = {}
        self.booked_sqft_lookup = {}

    # ------------------------------------------------------------------ #
    #  Core allocation primitive                                           #
    # ------------------------------------------------------------------ #

    def _slot_process(
        self,
        pid:             int,
        pname:           str,
        docket_id,
        total_m:         float,
        workdays:        list[date],
        earliest:        date,
        farmout:         bool,
        capacity_lookup: dict[int, dict[int, float]],
        session_booked:  dict[tuple, float],
        *,
        use_existing_bookings: bool = False,
        holidays:        set | None = None,
    ) -> tuple[date | None, date | None, dict[date, float]]:
        """
        Find the earliest start where total_m minutes can be allocated
        across consecutive workdays, respecting capacity and bookings.

        Emits a per-day trace line to schedule_trace.log for every day
        evaluated, with the reason it was skipped or how many minutes
        were allocated.

        Mutates session_booked in-place on success.
        Returns (start_date, end_date, allocation_map).
        """
        bypass_dates  = self.by_pass_dates.get(pid, set())
        tag           = f"[docket={docket_id} | pid={pid} | {pname}]"
        need          = total_m

        sched_logger.debug("%s  START SEARCH  need=%.0f min  earliest=%s", tag, need, earliest)

        for cand_idx, candidate in enumerate(workdays):
            if candidate < earliest:
                sched_logger.debug(
                    "%s  %s  SKIPPED — before earliest (%s)", tag, candidate, earliest
                )
                continue

            sched_logger.debug("%s  Trying candidate start: %s", tag, candidate)

            remaining:  float             = total_m
            temp_alloc: dict[date, float] = {}
            wd_idx = cand_idx

            while remaining > 0 and wd_idx < len(workdays):
                day = workdays[wd_idx]

                # ── Determine raw capacity ───────────────────────────────────
                if day in bypass_dates:
                    capacity_hrs = 0.0
                    cap_reason   = "bypass date"
                else:
                    capacity_hrs = float(
                        capacity_lookup.get(pid, {}).get(day.isoweekday(), 8.0)
                    )
                    cap_reason = f"capacity={capacity_hrs:.1f}h"

                booked_existing = (
                    float(self.booked_mins_lookup.get((pid, day), 0))
                    if use_existing_bookings else 0.0
                )
                booked_session = session_booked.get((pid, day), 0.0)
                capacity_mins  = capacity_hrs * 60
                available      = max(0.0, capacity_mins - booked_existing - booked_session)

                # ── Start-day gate ───────────────────────────────────────────
                if day == candidate and available < MIN_START_AVAIL_MINS:
                    sched_logger.debug(
                        "%s    %s  [candidate]  SKIPPED START — avail=%.0f min < %d min  "
                        "(%s  booked_existing=%.0f  booked_session=%.0f)",
                        tag, day, available, MIN_START_AVAIL_MINS,
                        cap_reason, booked_existing, booked_session,
                    )
                    break   # try next candidate

                # ── Allocation decision ──────────────────────────────────────
                if available >= MIN_BLOCK_AVAIL_MINS or (available > 0 and available >= remaining):
                    alloc = min(available, remaining)
                    temp_alloc[day] = alloc
                    remaining -= alloc
                    sched_logger.debug(
                        "%s    %s  ALLOCATED %.0f min  "
                        "(avail=%.0f  booked_existing=%.0f  booked_session=%.0f  %s)  "
                        "remaining=%.0f",
                        tag, day, alloc,
                        available, booked_existing, booked_session, cap_reason,
                        remaining,
                    )
                else:
                    sched_logger.debug(
                        "%s    %s  SKIPPED — avail=%.0f min too low  "
                        "(%s  booked_existing=%.0f  booked_session=%.0f)",
                        tag, day, available,
                        cap_reason, booked_existing, booked_session,
                    )

                wd_idx += 1

            # ── Did this candidate succeed? ──────────────────────────────────
            if remaining <= 0:
                end_date = max(temp_alloc.keys())

                # Commit to session slate
                for d, m in temp_alloc.items():
                    key = (pid, d)
                    session_booked[key] = session_booked.get(key, 0.0) + m

                if farmout:
                    h = holidays if holidays is not None else set(self.holidays)
                    original_end = end_date
                    end_date = _add_workdays(end_date, FARMOUT_BUFFER_DAYS, h)
                    sched_logger.debug(
                        "%s  FARMOUT  end extended %s → %s (+%d workdays)",
                        tag, original_end, end_date, FARMOUT_BUFFER_DAYS,
                    )

                sched_logger.debug(
                    "%s  SCHEDULED  start=%s  end=%s  days_used=%d",
                    tag, candidate, end_date, len(temp_alloc),
                )
                return candidate, end_date, temp_alloc

            else:
                sched_logger.debug(
                    "%s  Candidate %s FAILED — %.0f min still unallocated, trying next",
                    tag, candidate, remaining,
                )

        sched_logger.warning(
            "%s  EXHAUSTED %d-day horizon — could not allocate %.0f min",
            tag, len(workdays), total_m,
        )
        return None, None, {}

    # ------------------------------------------------------------------ #
    #  build_schedule  (single docket, respects existing bookings)        #
    # ------------------------------------------------------------------ #

    def build_schedule(self, docket_id, qty, lead_days) -> list[dict]:
        """
        Generate a finite-capacity production schedule for a single docket
        using AI-predicted process durations.
        """
        sched_logger.info(
            "=== build_schedule  docket=%s  qty=%s  lead_days=%s ===",
            docket_id, qty, lead_days,
        )

        routing_data = self.db.fetch_docket_routing(docket_id, qty)
        if routing_data is None or routing_data.empty:
            sched_logger.warning("docket=%s — no routing data found, returning []", docket_id)
            return []

        style_id, printing_id, sqfpm = self.db.get_docket_metadata(docket_id)
        style_id    = style_id    or "UNKNOWN"
        printing_id = printing_id or "UNKNOWN"
        sqfpm       = float(sqfpm or 1000.0)

        path_str = "->".join(routing_data['process_id'].astype(str))
        h_set    = set(self.holidays)

        first_day = _first_workday_after_lead(lead_days, h_set)
        workdays  = _build_workdays(first_day, PLANNING_HORIZON, h_set)

        sched_logger.info(
            "docket=%s  path=%s  calendar_start=%s  horizon=%d days",
            docket_id, path_str, first_day, PLANNING_HORIZON,
        )

        batch_df = routing_data.copy().assign(
            style_id=style_id, printing_id=printing_id,
            full_path=path_str, qty=qty, sqfpm=sqfpm,
        )
        pred_df      = self.ai_engine.predict_batch(batch_df, buffer=True)
        routing_data = routing_data.reset_index(drop=True)
        pred_df      = pred_df.reset_index(drop=True)

        if len(pred_df) != len(routing_data):
            raise SchedulingError(
                f"AI returned {len(pred_df)} predictions for "
                f"{len(routing_data)} routing steps on docket {docket_id}."
            )

        for col in ('total_m', 'setup_m', 'run_m', 'confidence'):
            routing_data[col] = pd.to_numeric(pred_df[col], errors='coerce').fillna(0.0)

        if self.process_df.empty or 'process_id' not in self.process_df.columns:
            raise ValueError("process_df is missing required 'process_id' column.")

        capacity_lookup = _build_capacity_lookup(self.process_df)
        session_booked: dict[tuple, float] = {}
        process_schedule: list[dict]       = []
        prev_end_date: date | None         = None

        for step_idx, (_, proc) in enumerate(routing_data.iterrows(), 1):
            pid     = int(proc['process_id'])
            pname   = proc.get('process_name') or f"Process {pid}"
            total_m = float(proc['total_m'])

            earliest = (
                _add_workdays(prev_end_date, 1, h_set)
                if prev_end_date else workdays[0]
            )

            sched_logger.info(
                "── Step %d/%d  pid=%s (%s)  need=%.0f min  earliest=%s",
                step_idx, len(routing_data), pid, pname, total_m, earliest,
            )

            start_date, end_date, allocation_map = self._slot_process(
                pid, pname, docket_id,
                total_m, workdays, earliest,
                farmout=pid in FARMOUT_PROCESS_IDS,
                capacity_lookup=capacity_lookup,
                session_booked=session_booked,
                use_existing_bookings=True,
                holidays=h_set,
            )

            if start_date is None:
                logger.warning(
                    "Could not schedule process %s (%s) for docket %s within %d-day horizon.",
                    pid, pname, docket_id, PLANNING_HORIZON,
                )
                sched_logger.warning(
                    "Step %d UNSCHEDULED  pid=%s (%s)  docket=%s",
                    step_idx, pid, pname, docket_id,
                )
            else:
                sched_logger.info(
                    "Step %d DONE  pid=%s (%s)  start=%s  end=%s  days_used=%d",
                    step_idx, pid, pname, start_date, end_date, len(allocation_map),
                )

            prev_end_date = end_date

            blank_per_hour = (
                int(qty / (proc['run_m'] / 60)) if proc['run_m'] > 0 else 0
            )

            process_schedule.append({
                'process_id':     pid,
                'process_name':   pname,
                'seq_order':      step_idx,
                'start':          start_date,
                'end':            end_date,
                'total_m':        total_m,
                'setup_m':        float(proc['setup_m']),
                'run_m':          float(proc['run_m']),
                'required_sqft':  (sqfpm / 1000) * qty,
                'predicted_mins': total_m,
                'blank_per_hour': blank_per_hour,
                'confidence':     float(proc['confidence']),
                'allocation_map': allocation_map,
            })

        sched_logger.info("=== build_schedule COMPLETE  docket=%s  steps=%d ===\n", docket_id, len(process_schedule))
        return process_schedule

    # ------------------------------------------------------------------ #
    #  build_schedule_from_df  (batch, empty slate)                       #
    # ------------------------------------------------------------------ #

    def build_schedule_from_df(
        self, jobs_df: pd.DataFrame, lead_days: int = 0
    ) -> list[dict]:
        """
        Batch-schedule a DataFrame of jobs against a FRESH capacity slate.
        All routing fetches and AI predictions are batched upfront.
        """
        if jobs_df is None or jobs_df.empty:
            return []

        sched_logger.info(
            "=== build_schedule_from_df  jobs=%d  lead_days=%d ===",
            len(jobs_df), lead_days,
        )

        h_set = set(self.holidays)

        if self.process_df.empty or "process_id" not in self.process_df.columns:
            raise ValueError("process_df is missing required 'process_id' column.")

        capacity_lookup = _build_capacity_lookup(self.process_df)

        # ── 1. Bulk-fetch all routing ─────────────────────────────────────────
        distinct_dockets: list = jobs_df["docket_id"].unique().tolist()

        if hasattr(self.db, "fetch_docket_routing_batch"):
            all_routings: pd.DataFrame = self.db.fetch_docket_routing_batch(distinct_dockets)
        else:
            parts = []
            for d_id in distinct_dockets:
                r_df = self.db.fetch_docket_routing(d_id, 1)
                if r_df is not None and not r_df.empty:
                    r_df = r_df.copy()
                    r_df["docket_id"] = d_id
                    parts.append(r_df)
            all_routings = pd.concat(parts, ignore_index=True) if parts else pd.DataFrame()

        if all_routings.empty:
            sched_logger.warning("build_schedule_from_df — no routing data found for any docket")
            return []

        # ── 2. Per-docket metadata map ────────────────────────────────────────
        job_meta: dict[str, dict] = {
            row["docket_id"]: {
                "qty":         float(row.get("qty", 1)),
                "style_id":    str(row.get("style_id",    "UNKNOWN") or "UNKNOWN"),
                "printing_id": str(row.get("printing_id", "UNKNOWN") or "UNKNOWN"),
                "sqfpm":       float(row.get("sqfpm", 1000.0) or 1000.0),
                "lead_days":   int(row.get("lead_days", lead_days)),
            }
            for _, row in jobs_df.iterrows()
        }

        # ── 3. Unified prediction matrix (single batch call) ──────────────────
        sort_col = next(
            (c for c in ("seq_order", "process_id") if c in all_routings.columns), None
        )

        records: list[dict] = []
        for d_id, group in all_routings.groupby("docket_id"):
            meta = job_meta.get(d_id)
            if meta is None:
                continue
            if sort_col:
                group = group.sort_values(sort_col)
            path_str = "->".join(group["process_id"].astype(str))
            for _, proc_row in group.iterrows():
                records.append({
                    "docket_id":    d_id,
                    "process_id":   int(proc_row["process_id"]),
                    "process_name": proc_row.get("process_name", f"Process {proc_row['process_id']}"),
                    "style_id":     meta["style_id"],
                    "printing_id":  meta["printing_id"],
                    "full_path":    path_str,
                    "qty":          meta["qty"],
                    "sqfpm":        meta["sqfpm"],
                })

        if not records:
            return []

        master_df = pd.DataFrame(records)
        pred_df   = self.ai_engine.predict_batch(master_df, buffer=True)

        if len(pred_df) != len(master_df):
            raise SchedulingError(
                f"AI prediction row count mismatch: expected {len(master_df)}, "
                f"got {len(pred_df)}."
            )

        master_df = master_df.reset_index(drop=True)
        pred_df   = pred_df.reset_index(drop=True)

        for col in ('total_m', 'setup_m', 'run_m', 'confidence'):
            master_df[col] = pd.to_numeric(pred_df[col], errors='coerce').fillna(0.0)

        # ── 4. Allocate in job-priority order ─────────────────────────────────
        session_booked: dict[tuple, float] = {}
        all_steps:      list[dict]         = []

        for _, job_row in jobs_df.iterrows():
            d_id = job_row["docket_id"]
            meta = job_meta.get(d_id)
            if meta is None:
                continue

            job_steps = master_df[master_df["docket_id"] == d_id]
            if job_steps.empty:
                continue

            first_day = _first_workday_after_lead(meta["lead_days"], h_set)
            workdays  = _build_workdays(first_day, BATCH_HORIZON, h_set)
            prev_end: date | None = None

            sched_logger.info(
                "── Docket %s  qty=%.0f  lead=%d  calendar_start=%s",
                d_id, meta["qty"], meta["lead_days"], first_day,
            )

            for step_idx, (_, proc) in enumerate(job_steps.iterrows(), 1):
                pid     = int(proc["process_id"])
                pname   = str(proc["process_name"])
                total_m = float(proc["total_m"])

                earliest = (
                    _add_workdays(prev_end, 1, h_set) if prev_end else workdays[0]
                )

                sched_logger.info(
                    "  Step %d  pid=%s (%s)  need=%.0f min  earliest=%s",
                    step_idx, pid, pname, total_m, earliest,
                )

                start, end, alloc = self._slot_process(
                    pid, pname, d_id,
                    total_m, workdays, earliest,
                    farmout=pid in FARMOUT_PROCESS_IDS,
                    capacity_lookup=capacity_lookup,
                    session_booked=session_booked,
                    use_existing_bookings=False,
                    holidays=h_set,
                )

                if start is None:
                    logger.warning(
                        "Could not schedule process %s for docket %s within %d-day horizon.",
                        pid, d_id, BATCH_HORIZON,
                    )
                    sched_logger.warning(
                        "  Step %d UNSCHEDULED  pid=%s (%s)  docket=%s",
                        step_idx, pid, pname, d_id,
                    )
                else:
                    sched_logger.info(
                        "  Step %d DONE  pid=%s (%s)  start=%s  end=%s  days_used=%d",
                        step_idx, pid, pname, start, end, len(alloc),
                    )

                blank_per_hour = (
                    int(meta["qty"] / (proc["run_m"] / 60))
                    if proc["run_m"] > 0 else 0
                )

                all_steps.append({
                    "docket_id":      d_id,
                    "process_id":     pid,
                    "process_name":   pname,
                    "seq_order":      step_idx,
                    "start":          start,
                    "end":            end,
                    "total_m":        total_m,
                    "setup_m":        float(proc["setup_m"]),
                    "run_m":          float(proc["run_m"]),
                    "required_sqft":  (meta["sqfpm"] / 1000) * meta["qty"],
                    "predicted_mins": total_m,
                    "blank_per_hour": blank_per_hour,
                    "confidence":     float(proc["confidence"]),
                    "allocation_map": alloc,
                })

                prev_end = end

        sched_logger.info(
            "=== build_schedule_from_df COMPLETE  total_steps=%d ===\n", len(all_steps)
        )
        return all_steps


# ─────────────────────────────────────────────────────────────────────────────
# USAGE EXAMPLE
# ─────────────────────────────────────────────────────────────────────────────
#
# from mod_production.services.schedule_service import ScheduleService
# import pandas as pd
#
# jobs = pd.DataFrame([
#     {"docket_id": "188989", "qty": 6000,  "lead_days": 4},
#     {"docket_id": "172368", "qty": 10000, "lead_days": 4},
#     {"docket_id": "186655", "qty": 26600, "lead_days": 4},
# ])
#
# svc      = ScheduleService()                       # logs go to logs/schedule_trace.log
# svc      = ScheduleService(log_dir="/var/log/moyy") # custom path
# schedule = svc.build_schedule_from_df(jobs, lead_days=4)
#
# df = pd.DataFrame(schedule)
# print(df[["docket_id", "process_name", "start", "end", "total_m", "confidence"]])