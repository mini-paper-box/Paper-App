import logging
import logging.handlers
import os
from datetime import datetime, date, timedelta
import pandas as pd
from mod_production.data.sql_manager import SQLManager
from mod_production.core.predictor2 import ProductionAI

logger = logging.getLogger(__name__)
sched_logger = logging.getLogger(f"{__name__}.schedule_trace")

FARMOUT_PROCESS_IDS = frozenset({236, 257, 168})
FARMOUT_BUFFER_DAYS = 5
PLANNING_HORIZON = 90
BATCH_HORIZON = 120
MIN_START_AVAIL_MINS = 60
MIN_BLOCK_AVAIL_MINS = 60
FALLBACK_BASE_MINS = 15.0
FALLBACK_PER_UNIT = 0.01


def _configure_schedule_log(log_dir="logs", max_bytes=10 * 1024 * 1024, backup_count=7):
    if any(isinstance(h, logging.handlers.RotatingFileHandler) for h in sched_logger.handlers):
        return
    os.makedirs(log_dir, exist_ok=True)
    handler = logging.handlers.RotatingFileHandler(
        os.path.join(log_dir, "schedule_trace.log"),
        maxBytes=max_bytes,
        backupCount=backup_count,
        encoding="utf-8",
    )
    handler.setLevel(logging.DEBUG)
    handler.setFormatter(logging.Formatter(
        "%(asctime)s  %(levelname)-8s  %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    ))
    sched_logger.setLevel(logging.DEBUG)
    sched_logger.propagate = False
    sched_logger.addHandler(handler)


class SchedulingError(Exception):
    """Raised when a process cannot be placed within the planning horizon."""


def _normalize_date(d):
    return d.date() if isinstance(d, datetime) else d


def _add_workdays(start, n, holidays):
    current = start
    added = 0
    while added < n:
        current += timedelta(days=1)
        if current.weekday() < 5 and current not in holidays:
            added += 1
    return current


def _first_workday_after_lead(lead_days, holidays):
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


def _build_workdays(start, n, holidays):
    days = []
    current = start
    while len(days) < n:
        if current.weekday() < 5 and current not in holidays:
            days.append(current)
        current += timedelta(days=1)
    return days


def _build_capacity_lookup(process_df):
    return {
        r.process_id: {
            1: r.capacity_2,
            2: r.capacity_3,
            3: r.capacity_4,
            4: r.capacity_5,
            5: r.capacity_6,
            6: r.capacity_7,
            7: r.capacity_1,
        }
        for r in process_df.itertuples()
    }


class ScheduleService:
    def __init__(self, holidays=None, process_df=None, booked_mins_lookup=None, log_dir="logs"):
        _configure_schedule_log(log_dir=log_dir)
        self.db = SQLManager()
        self.ai_engine = ProductionAI()
        today = date.today()

        def weekday_range(start, end):
            return {
                start + timedelta(days=i)
                for i in range((end - start).days + 1)
                if (start + timedelta(days=i)).weekday() < 5
            }

        self.by_pass_dates = {
            69: weekday_range(today, today + timedelta(days=1)),
            189: weekday_range(date(2026, 7, 10), date(2026, 7, 23)),
            166: weekday_range(date(2026, 7, 10), date(2026, 7, 24)),
        }

        self.booked_mins_lookup = {}
        self.booked_jobs_lookup = {}
        self.booked_sqft_lookup = {}

        if holidays is None or process_df is None:
            self.initialize_capacity_cache()
        else:
            self.raw_jobs = None
            self.holidays = holidays
            self.process_df = process_df

    def initialize_capacity_cache(self):
        try:
            self.raw_jobs, self.holidays, self.process_df = (
                self.db.fetch_booked_and_holidays_and_process()
            )

            if self.raw_jobs is None or self.raw_jobs.empty:
                self._initialize_empty_cache()
                return

            if not self.ai_engine.is_trained:
                self._build_cache_with_fallback(self.raw_jobs)
                return

            processed_df = self._predict_for_cache(self.raw_jobs)

            processed_df["booked_sqft"] = (
                processed_df["job_qty"] * processed_df["sqfpm"] / 1000
            )

            grouped = (
                processed_df.groupby(["process_id", "schedule_date"])
                .agg(
                    mins_booked=("total_m", "sum"),
                    booked_sqft=("booked_sqft", "sum"),
                    booked_jobs=("process_id", "count"),
                )
                .reset_index()
            )

            self.booked_mins_lookup = {
                (r.process_id, _normalize_date(r.schedule_date)): float(r.mins_booked)
                for r in grouped.itertuples()
            }
            self.booked_sqft_lookup = {
                (r.process_id, _normalize_date(r.schedule_date)): float(r.booked_sqft)
                for r in grouped.itertuples()
            }
            self.booked_jobs_lookup = {
                (r.process_id, _normalize_date(r.schedule_date)): int(r.booked_jobs)
                for r in grouped.itertuples()
            }

            sched_logger.info(
                "Capacity cache loaded: %s rows",
                len(processed_df),
            )

        except Exception:
            sched_logger.exception("Failed to initialize capacity cache")
            self._initialize_empty_cache()

    def _build_cache_with_fallback(self, raw_jobs):
        processed = raw_jobs.copy()

        if "job_qty" not in processed.columns:
            processed["job_qty"] = 0

        processed["total_m"] = (
            FALLBACK_BASE_MINS +
            processed["job_qty"].fillna(0).astype(float) * FALLBACK_PER_UNIT
        )
        processed["setup_m"] = 0.0
        processed["run_m"] = processed["total_m"]
        processed["confidence"] = 0.0

        if "schedule_date" not in processed.columns:
            processed["schedule_date"] = date.today()

        processed["schedule_date"] = processed["schedule_date"].apply(_normalize_date)
        processed["booked_sqft"] = 0.0

        grouped = (
            processed.groupby(["process_id", "schedule_date"])
            .agg(
                mins_booked=("total_m", "sum"),
                booked_sqft=("booked_sqft", "sum"),
                booked_jobs=("process_id", "count"),
            )
            .reset_index()
        )

        self.booked_mins_lookup = {
            (r.process_id, r.schedule_date): float(r.mins_booked)
            for r in grouped.itertuples()
        }
        self.booked_sqft_lookup = {
            (r.process_id, r.schedule_date): float(r.booked_sqft)
            for r in grouped.itertuples()
        }
        self.booked_jobs_lookup = {
            (r.process_id, r.schedule_date): int(r.booked_jobs)
            for r in grouped.itertuples()
        }

    def _predict_for_cache(self, raw_jobs):
        df = raw_jobs.copy()

        defaults = {
            "style_id": "UNKNOWN",
            "printing_id": "UNKNOWN",
            "full_path": "",
            "sqfpm": 1000.0,
        }

        for col, value in defaults.items():
            if col not in df.columns:
                df[col] = value
            else:
                df[col] = df[col].fillna(value)

        if hasattr(self.ai_engine, "predict_batch"):
            batch = pd.DataFrame({
                "process_id": df["process_id"],
                "style_id": df["style_id"],
                "printing_id": df["printing_id"],
                "full_path": df["full_path"],
                "qty": df["job_qty"],
                "sqfpm": df["sqfpm"],
            })

            try:
                predictions = self.ai_engine.predict_batch(batch, buffer=True)
                return pd.concat(
                    [df.reset_index(drop=True), predictions.reset_index(drop=True)],
                    axis=1,
                )
            except Exception:
                sched_logger.exception("Batch AI prediction failed; using fallback")

        results = []
        for row in df.itertuples():
            try:
                pred = self.ai_engine.predict_ai(
                    process_id=row.process_id,
                    style_id=row.style_id,
                    printing_id=row.printing_id,
                    full_path=row.full_path,
                    qty=row.job_qty,
                    sqfpm=row.sqfpm,
                    buffer=True,
                )
            except Exception:
                pred = {
                    "total_m": FALLBACK_BASE_MINS + float(row.job_qty or 0) * FALLBACK_PER_UNIT,
                    "setup_m": 0.0,
                    "run_m": 0.0,
                    "confidence": 0.0,
                }

            results.append(pred)

        return pd.concat(
            [df.reset_index(drop=True), pd.DataFrame(results)],
            axis=1,
        )

    def _initialize_empty_cache(self):
        self.booked_mins_lookup = {}
        self.booked_jobs_lookup = {}
        self.booked_sqft_lookup = {}
        self.raw_jobs = pd.DataFrame()
        self.process_df = pd.DataFrame(
            columns=[
                "process_id",
                "capacity_1",
                "capacity_2",
                "capacity_3",
                "capacity_4",
                "capacity_5",
                "capacity_6",
                "capacity_7",
            ]
        )

    def _slot_process(
        self,
        pid,
        pname,
        docket_id,
        total_m,
        workdays,
        earliest,
        farmout,
        capacity_lookup,
        session_booked,
        use_existing_bookings=False,
        holidays=None,
    ):
        holidays = holidays or set()
        bypass_dates = self.by_pass_dates.get(pid, set())

        for candidate in workdays:
            if candidate < earliest:
                continue

            remaining = float(total_m)
            temp_alloc = {}

            for day in workdays:
                if day < candidate:
                    continue

                capacity_hrs = (
                    0.0
                    if day in bypass_dates
                    else float(capacity_lookup.get(pid, {}).get(day.isoweekday(), 8.0) or 0)
                )

                existing = (
                    float(self.booked_mins_lookup.get((pid, day), 0))
                    if use_existing_bookings
                    else 0.0
                )

                session = float(session_booked.get((pid, day), 0))
                available = max(0.0, capacity_hrs * 60.0 - existing - session)

                sched_logger.debug(
                    "docket=%s pid=%s day=%s capacity=%.1f existing=%.1f session=%.1f available=%.1f remaining=%.1f",
                    docket_id,
                    pid,
                    day,
                    capacity_hrs * 60.0,
                    existing,
                    session,
                    available,
                    remaining,
                )

                if available < MIN_BLOCK_AVAIL_MINS:
                    break

                if available >= MIN_BLOCK_AVAIL_MINS or (
                    available > 0 and available >= remaining
                ):
                    allocated = min(available, remaining)
                    temp_alloc[day] = allocated
                    remaining -= allocated

                if remaining <= 0:
                    for alloc_day, mins in temp_alloc.items():
                        session_booked[(pid, alloc_day)] = (
                            session_booked.get((pid, alloc_day), 0) + mins
                        )

                    end = max(temp_alloc)

                    if farmout:
                        end = _add_workdays(
                            end,
                            FARMOUT_BUFFER_DAYS,
                            holidays,
                        )

                    return candidate, end, temp_alloc

        sched_logger.warning(
            "docket=%s pid=%s (%s) could not be scheduled",
            docket_id,
            pid,
            pname,
        )
        return None, None, {}

    def _prepare_predictions(self, routing_data, qty):
        routing_data = routing_data.copy()

        style_id = routing_data.get("style_id", pd.Series(["UNKNOWN"] * len(routing_data)))
        printing_id = routing_data.get("printing_id", pd.Series(["UNKNOWN"] * len(routing_data)))
        sqfpm = routing_data.get("sqfpm", pd.Series([1000.0] * len(routing_data)))

        routing_data["style_id"] = style_id.fillna("UNKNOWN")
        routing_data["printing_id"] = printing_id.fillna("UNKNOWN")
        routing_data["sqfpm"] = pd.to_numeric(sqfpm, errors="coerce").fillna(1000.0)
        routing_data["full_path"] = "->".join(
            routing_data["process_id"].astype(str)
        )
        routing_data["qty"] = qty

        batch_df = routing_data[
            ["process_id", "style_id", "printing_id", "full_path", "qty", "sqfpm"]
        ].copy()

        pred_df = self.ai_engine.predict_batch(
            batch_df,
            buffer=True,
        ).reset_index(drop=True)

        routing_data = routing_data.reset_index(drop=True)

        if len(pred_df) != len(routing_data):
            raise SchedulingError(
                f"Prediction count {len(pred_df)} does not match routing count {len(routing_data)}"
            )

        for col in ["total_m", "setup_m", "run_m", "confidence"]:
            routing_data[col] = pd.to_numeric(
                pred_df[col],
                errors="coerce",
            ).fillna(0.0)

        return routing_data

    def _build_schedule(
        self,
        docket_id,
        qty,
        lead_days,
        routing_data,
        session_booked=None,
    ):
        if routing_data is None or routing_data.empty:
            return []

        session_booked = session_booked if session_booked is not None else {}

        h_set = set(self.holidays or [])

        if self.process_df is None or self.process_df.empty:
            sched_logger.warning(
                "docket=%s — process capacity data unavailable",
                docket_id,
            )
            return []

        capacity_lookup = _build_capacity_lookup(self.process_df)

        try:
            routing_data = self._prepare_predictions(routing_data, qty)
        except Exception:
            sched_logger.exception(
                "docket=%s — prediction failed",
                docket_id,
            )
            return []

        process_schedule = []
        prev_end_date = None

        for idx, row in routing_data.iterrows():
            pid = int(row["process_id"])
            pname = row.get("process_name", f"Process {pid}")
            total_m = float(row["total_m"])
            setup_m = float(row["setup_m"])
            run_m = float(row["run_m"])
            confidence = float(row["confidence"])
            sqfpm = float(row.get("sqfpm", 1000.0) or 1000.0)
            seq_order = int(row.get("seq_order", idx + 1))

            if prev_end_date is None:
                first_day = _first_workday_after_lead(
                    lead_days,
                    h_set,
                )
            else:
                first_day = prev_end_date + timedelta(days=1)
                while (
                    first_day.weekday() >= 5
                    or first_day in h_set
                ):
                    first_day += timedelta(days=1)

            workdays = _build_workdays(
                first_day,
                PLANNING_HORIZON,
                h_set,
            )

            farmout = pid in FARMOUT_PROCESS_IDS

            start, end, allocation_map = self._slot_process(
                pid=pid,
                pname=pname,
                docket_id=docket_id,
                total_m=total_m,
                workdays=workdays,
                earliest=first_day,
                farmout=farmout,
                capacity_lookup=capacity_lookup,
                session_booked=session_booked,
                use_existing_bookings=True,
                holidays=h_set,
            )

            if start is None:
                sched_logger.warning(
                    "docket=%s process=%s could not be scheduled",
                    docket_id,
                    pid,
                )

            blank_per_hour = (
                int(qty / (run_m / 60))
                if run_m > 0
                else 0
            )

            process_schedule.append({
                "docket_id": docket_id,
                "process_id": pid,
                "process_name": pname,
                "seq_order": seq_order,
                "start": start,
                "end": end,
                "total_m": total_m,
                "setup_m": setup_m,
                "run_m": run_m,
                "required_sqft": (sqfpm / 1000.0) * qty,
                "predicted_mins": total_m,
                "blank_per_hour": blank_per_hour,
                "confidence": confidence,
                "allocation_map": allocation_map,
            })

            if end is not None:
                prev_end_date = end

        return process_schedule

    def build_schedule(self, docket_id, qty, lead_days):
        sched_logger.info(
            "Building schedule for docket=%s qty=%s lead_days=%s",
            docket_id,
            qty,
            lead_days,
        )

        routing_data = self.db.fetch_docket_routing(
            docket_id,
            qty,
        )

        if routing_data is None or routing_data.empty:
            sched_logger.warning(
                "docket=%s — no routing data found",
                docket_id,
            )
            return []

        return self._build_schedule(
            docket_id=docket_id,
            qty=qty,
            lead_days=lead_days,
            routing_data=routing_data,
        )

    def build_schedule_with_order_id(self, order_id, qty, lead_days):
        sched_logger.info(
            "Building schedule for order=%s qty=%s lead_days=%s",
            order_id,
            qty,
            lead_days,
        )

        routing_data = self.db.fetch_order_routing(
            order_id,
            qty,
        )

        if routing_data is None or routing_data.empty:
            sched_logger.warning(
                "order=%s — no routing data found",
                order_id,
            )
            return []

        if "docket_id" not in routing_data.columns:
            sched_logger.error(
                "order=%s — routing data does not contain docket_id. columns=%s",
                order_id,
                routing_data.columns.tolist(),
            )
            return []

        routing_data = routing_data.dropna(subset=["docket_id"])

        if routing_data.empty:
            sched_logger.warning(
                "order=%s — no dockets found",
                order_id,
            )
            return []

        all_schedules = []
        session_booked = {}

        for docket_id, docket_routing in routing_data.groupby(
            "docket_id",
            sort=False,
        ):
            docket_id = int(docket_id)

            sched_logger.info(
                "order=%s docket=%s — scheduling %s routing steps",
                order_id,
                docket_id,
                len(docket_routing),
            )

            schedule = self._build_schedule(
                docket_id=docket_id,
                qty=qty,
                lead_days=lead_days,
                routing_data=docket_routing,
                session_booked=session_booked,
            )

            all_schedules.extend(schedule)

        return all_schedules

    def build_schedule_from_df(self, jobs_df):
        if jobs_df is None or jobs_df.empty:
            return []

        h_set = set(self.holidays or [])

        if self.process_df is None or self.process_df.empty:
            return []

        capacity_lookup = _build_capacity_lookup(self.process_df)

        distinct_dockets = (
            jobs_df["docket_id"]
            .dropna()
            .unique()
            .tolist()
        )

        routing_frames = []

        if hasattr(self.db, "fetch_docket_routing_bulk"):
            bulk_data = self.db.fetch_docket_routing_bulk(
                distinct_dockets
            )
            if bulk_data is not None and not bulk_data.empty:
                routing_frames.append(bulk_data)
        else:
            for docket_id in distinct_dockets:
                routing = self.db.fetch_docket_routing(
                    docket_id,
                    1,
                )
                if routing is not None and not routing.empty:
                    routing = routing.copy()
                    routing["docket_id"] = docket_id
                    routing_frames.append(routing)

        if not routing_frames:
            return []

        master_df = pd.concat(
            routing_frames,
            ignore_index=True,
        )

        job_meta = jobs_df.set_index("docket_id").to_dict("index")

        records = []

        for row in master_df.itertuples():
            meta = job_meta.get(row.docket_id, {})
            qty = meta.get("qty", 1)
            style_id = meta.get("style_id", "UNKNOWN")
            printing_id = meta.get("printing_id", "UNKNOWN")
            sqfpm = meta.get("sqfpm", 1000.0)
            lead_days = meta.get("lead_days", 0)

            records.append({
                "docket_id": row.docket_id,
                "process_id": row.process_id,
                "process_name": getattr(
                    row,
                    "process_name",
                    getattr(row, "process_nme", f"Process {row.process_id}"),
                ),
                "seq_order": getattr(
                    row,
                    "seq_order",
                    getattr(row, "order_seq", 0),
                ),
                "style_id": style_id,
                "printing_id": printing_id,
                "full_path": "",
                "qty": qty,
                "sqfpm": sqfpm,
                "lead_days": lead_days,
            })

        master_df = pd.DataFrame(records)

        if master_df.empty:
            return []

        predictions = self.ai_engine.predict_batch(
            master_df[
                [
                    "process_id",
                    "style_id",
                    "printing_id",
                    "full_path",
                    "qty",
                    "sqfpm",
                ]
            ],
            buffer=True,
        ).reset_index(drop=True)

        if len(predictions) != len(master_df):
            raise SchedulingError(
                "Prediction count does not match routing count"
            )

        master_df = pd.concat(
            [master_df.reset_index(drop=True), predictions],
            axis=1,
        )

        session_booked = {}
        all_steps = []

        for _, job in jobs_df.iterrows():
            docket_id = job["docket_id"]
            qty = job.get("qty", 1)
            lead_days = job.get("lead_days", 0)

            job_steps = master_df[
                master_df["docket_id"] == docket_id
            ].copy()

            if job_steps.empty:
                continue

            sort_col = (
                "seq_order"
                if "seq_order" in job_steps.columns
                else "process_id"
            )
            job_steps = job_steps.sort_values(sort_col)

            first_day = _first_workday_after_lead(
                lead_days,
                h_set,
            )
            workdays = _build_workdays(
                first_day,
                BATCH_HORIZON,
                h_set,
            )

            prev_end = None

            for idx, row in job_steps.iterrows():
                pid = int(row["process_id"])
                pname = row.get(
                    "process_name",
                    f"Process {pid}",
                )
                total_m = float(row["total_m"])
                setup_m = float(row["setup_m"])
                run_m = float(row["run_m"])
                confidence = float(row["confidence"])
                sqfpm = float(row.get("sqfpm", 1000.0) or 1000.0)
                seq_order = int(row.get("seq_order", idx + 1))

                earliest = (
                    first_day
                    if prev_end is None
                    else prev_end + timedelta(days=1)
                )

                while (
                    earliest.weekday() >= 5
                    or earliest in h_set
                ):
                    earliest += timedelta(days=1)

                start, end, allocation_map = self._slot_process(
                    pid=pid,
                    pname=pname,
                    docket_id=docket_id,
                    total_m=total_m,
                    workdays=workdays,
                    earliest=earliest,
                    farmout=pid in FARMOUT_PROCESS_IDS,
                    capacity_lookup=capacity_lookup,
                    session_booked=session_booked,
                    use_existing_bookings=False,
                    holidays=h_set,
                )

                blank_per_hour = (
                    int(qty / (run_m / 60))
                    if run_m > 0
                    else 0
                )

                all_steps.append({
                    "docket_id": docket_id,
                    "process_id": pid,
                    "process_name": pname,
                    "seq_order": seq_order,
                    "start": start,
                    "end": end,
                    "total_m": total_m,
                    "setup_m": setup_m,
                    "run_m": run_m,
                    "required_sqft": (sqfpm / 1000.0) * qty,
                    "predicted_mins": total_m,
                    "blank_per_hour": blank_per_hour,
                    "confidence": confidence,
                    "allocation_map": allocation_map,
                })

                if end is not None:
                    prev_end = end

        return all_steps


if __name__ == "__main__":
    service = ScheduleService()

    docket_result = service.build_schedule(
        docket_id=182882,
        qty=1000,
        lead_days=4,
    )

    order_result = service.build_schedule_with_order_id(
        order_id=5035563,
        qty=1000,
        lead_days=4,
    )

    print("\n--- DOCKET ---")
    for step in docket_result:
        print(step)

    print("\n--- ORDER ---")
    for step in order_result:
        print(step)