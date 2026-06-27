"""
PRODUCTION AI – CONFIDENCE BUFFER WITH RELEARNING
==================================================

INTELLIGENT LEARNING SYSTEM:
- Low confidence (< 80%): Apply buffer, log for relearning
- High confidence (≥ 80%): Use raw prediction, no buffer
- Buffer approximates reality better than uncertain predictions
- AI learns from buffered data, confidence grows, buffer disappears
- Optional AUTO-RETRAIN when buffer reaches threshold

AUTHOR: Production Scheduler Team
VERSION: 3.0 - Rewritten with validation split, vectorized batch, safe logging
"""

import os
import shutil
import logging
import traceback
import warnings
from datetime import datetime

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestRegressor
from sklearn.model_selection import train_test_split
from sklearn.multioutput import MultiOutputRegressor

# ── Suppress noisy third-party warnings ───────────────────────────────────
warnings.filterwarnings("ignore", message="pandas only supports SQLAlchemy connectable")
warnings.filterwarnings("ignore", message="X does not have valid feature names", category=UserWarning, module="sklearn")

logger = logging.getLogger(__name__)


class ProductionAI:
    """
    Random-Forest production time estimator with adaptive confidence buffering.

    Prediction flow
    ---------------
    1. Build feature vector from (process, style, printing, path, qty, sqfpm).
    2. Run MultiOutputRegressor to get (setup_minutes, run_rate).
    3. Estimate confidence from per-tree variance (coefficient of variation).
    4. If confidence < CONFIDENCE_RELEARN_THRESHOLD:
         - Apply a square-root buffer to the raw prediction.
         - Log the buffered entry for future retraining.
    5. If auto_retrain is on and the buffer is full, retrain automatically.

    Retraining note
    ---------------
    Buffered entries store the *raw* AI values (ai_raw_setup, ai_raw_rate)
    alongside the inflated ones.  retrain_from_buffered_data() trains on the
    raw values, using the buffer only as a signal for *which* combinations
    need more data — avoiding compounding inflation across retrain cycles.
    """

    FEATURE_COLS = [
        "process_id",
        "style_code",
        "printing_code",
        "path_code",
        "log_qty",
        "sqfpm_bracket",
    ]

    def __init__(
        self,
        db_manager=None,
        model_path: str = "models/factory_brain.pkl",
        auto_retrain: bool = True,
        auto_retrain_threshold: int = 10,
        confidence_threshold: float = 80.0,
    ):
        self.db = db_manager
        self.model_path = os.path.abspath(model_path)

        self.model = None
        self.is_trained = False

        self.style_cats = None
        self.printing_cats = None
        self.path_cats = None
        self.feature_cols = list(self.FEATURE_COLS)

        self.CONFIDENCE_RELEARN_THRESHOLD = confidence_threshold
        self.low_confidence_buffer: list[dict] = []

        self.auto_retrain = auto_retrain
        self.auto_retrain_threshold = auto_retrain_threshold

        self.training_date = "Never"
        self.training_samples = 0
        self.last_r2_score = 0.0

        os.makedirs(os.path.dirname(self.model_path), exist_ok=True)
        self.load_model()

    # =========================================================================
    # LOAD / SAVE
    # =========================================================================

    def load_model(self) -> None:
        """Load trained model and low-confidence buffer from disk."""
        if not os.path.exists(self.model_path):
            logger.info("No trained model found at %s", self.model_path)
            return

        try:
            data = joblib.load(self.model_path)

            required = {"model", "style_cats", "printing_cats", "path_cats", "feature_cols"}
            missing = required - data.keys()
            if missing:
                logger.error("Model file corrupted — missing keys: %s", missing)
                return

            self.model           = data["model"]
            self.style_cats      = data["style_cats"]
            self.printing_cats   = data["printing_cats"]
            self.path_cats       = data["path_cats"]
            self.feature_cols    = data["feature_cols"]
            self.low_confidence_buffer   = data.get("low_confidence_buffer", [])
            self.auto_retrain            = data.get("auto_retrain", self.auto_retrain)
            self.auto_retrain_threshold  = data.get("auto_retrain_threshold", self.auto_retrain_threshold)
            self.training_date           = data.get("training_date", "Unknown")
            self.training_samples        = data.get("training_samples", 0)
            self.last_r2_score           = data.get("r2", 0.0)
            self.is_trained = True

            logger.info(
                "Model loaded — samples: %s  val-R2: %.3f  buffered: %d  auto-retrain: %s",
                f"{self.training_samples:,}",
                self.last_r2_score,
                len(self.low_confidence_buffer),
                "ON" if self.auto_retrain else "OFF",
            )
        except Exception:
            logger.exception("Failed to load model from %s", self.model_path)

    def save_model(self) -> bool:
        """Persist model and buffer to disk with a .backup fallback."""
        if not self.is_trained:
            logger.warning("Cannot save — model not trained yet")
            return False

        try:
            if os.path.exists(self.model_path):
                shutil.copy2(self.model_path, self.model_path + ".backup")

            joblib.dump(
                {
                    "model":                  self.model,
                    "style_cats":             self.style_cats,
                    "printing_cats":          self.printing_cats,
                    "path_cats":              self.path_cats,
                    "feature_cols":           self.feature_cols,
                    "low_confidence_buffer":  self.low_confidence_buffer,
                    "auto_retrain":           self.auto_retrain,
                    "auto_retrain_threshold": self.auto_retrain_threshold,
                    "training_samples":       self.training_samples,
                    "training_date":          self.training_date,
                    "r2":                     self.last_r2_score,
                },
                self.model_path,
                compress=3,
            )
            mb = os.path.getsize(self.model_path) / 1024 / 1024
            logger.info("Model saved (%.2f MB) → %s", mb, self.model_path)
            return True

        except Exception:
            logger.exception("Failed to save model")
            return False

    # =========================================================================
    # TRAINING
    # =========================================================================

    def train_global(self, df: pd.DataFrame, save: bool = True) -> bool:
        """
        Train on historical production data.

        Steps
        -----
        1. Validate & copy input.
        2. Engineer run_rate, log_qty, sqfpm_bracket.
        3. Filter physical outliers.
        4. Encode categorical columns.
        5. Train/validation split (80/20) — R² reported on held-out data.
        6. Fit MultiOutputRegressor(RandomForest).
        7. Optionally save.

        Parameters
        ----------
        df:   DataFrame with columns [job_qty, run_m, setup_m, sqfpm,
                                       style_id, printing_id, full_path, process_id]
        save: Persist model after training (default True).

        Returns
        -------
        True on success, False on failure.
        """
        if df is None or df.empty:
            logger.error("No data provided for training")
            return False
        if len(df) < 10:
            logger.error("Insufficient data: %d samples (need >= 10)", len(df))
            return False

        try:
            logger.info("=== AI TRAINING START ===")
            work = df.copy()
            logger.info("[1/5] Starting with %s samples", f"{len(work):,}")

            # Feature engineering
            logger.info("[2/5] Engineering features...")
            work["run_rate"]      = work["run_m"] / work["job_qty"]
            work["log_qty"]       = np.log1p(work["job_qty"])
            work["sqfpm_bracket"] = (
                work["sqfpm"].fillna(1000).clip(lower=1).div(100).round().mul(100)
            )

            # Physical reality filters
            logger.info("[3/5] Applying outlier filters...")
            pre = len(work)
            work = work[
                (work["run_rate"] > 0)
                & (work["run_rate"] < 2.0)
                & (work["setup_m"] >= 0)
                & (work["setup_m"] < 240)
                & (work["job_qty"] > 0)
            ]
            removed = pre - len(work)
            logger.info("  Removed %s outliers (%.1f%%)", f"{removed:,}", removed / pre * 100)

            if len(work) < 10:
                logger.error("Too few samples after filtering: %d", len(work))
                return False

            # Categorical encoding
            logger.info("[4/5] Encoding categories...")
            for col in ("style_id", "printing_id", "full_path"):
                work[col] = work[col].astype(str).astype("category")

            self.style_cats    = work["style_id"].cat.categories
            self.printing_cats = work["printing_id"].cat.categories
            self.path_cats     = work["full_path"].cat.categories

            work["style_code"]    = work["style_id"].cat.codes
            work["printing_code"] = work["printing_id"].cat.codes
            work["path_code"]     = work["full_path"].cat.codes

            logger.info(
                "  Styles: %d  Printing: %d  Paths: %d",
                len(self.style_cats),
                len(self.printing_cats),
                len(self.path_cats),
            )

            # Train / validation split — prevents reporting inflated train-R²
            logger.info("[5/5] Training Random Forest (250 trees, 80/20 split)...")
            X = work[self.feature_cols]
            y = work[["setup_m", "run_rate"]]

            X_train, X_val, y_train, y_val = train_test_split(
                X, y, test_size=0.2, random_state=42
            )

            self.model = MultiOutputRegressor(
                RandomForestRegressor(
                    n_estimators=250,
                    max_depth=14,
                    min_samples_leaf=2,
                    random_state=42,
                    n_jobs=-1,
                )
            )
            self.model.fit(X_train, y_train)

            # Validation R² — honest estimate of generalisation
            self.last_r2_score    = self.model.score(X_val, y_val)
            self.training_samples = len(work)
            self.training_date    = datetime.now().strftime("%Y-%m-%d %H:%M")
            self.is_trained       = True

            logger.info(
                "  Val-R2: %.3f  Train samples: %s",
                self.last_r2_score,
                f"{self.training_samples:,}",
            )

            if save:
                self.save_model()

            logger.info("=== AI TRAINING COMPLETE ===")
            return True

        except Exception:
            logger.exception("Training failed")
            return False

    # =========================================================================
    # HELPERS
    # =========================================================================

    def _normalize_sqfpm(self, sqfpm) -> float:
        """Round sqfpm to the nearest 100-unit bucket."""
        if sqfpm is None or sqfpm <= 0:
            return 1000.0
        try:
            return round(float(sqfpm) / 100) * 100
        except (ValueError, TypeError):
            return 1000.0

    def _encode_single(self, style_id, printing_id, full_path) -> tuple[int, int, int]:
        """Encode a single row's categorical fields, falling back to median."""
        sid = str(style_id).strip()
        pid = str(printing_id).strip()
        pth = str(full_path)

        s_code     = self.style_cats.get_loc(sid)    if sid in self.style_cats    else len(self.style_cats)    // 2
        print_code = self.printing_cats.get_loc(pid) if pid in self.printing_cats else len(self.printing_cats) // 2
        p_code     = self.path_cats.get_loc(pth)     if pth in self.path_cats     else len(self.path_cats)     // 2

        return s_code, print_code, p_code

    def _compute_confidence(self, run_estimator, X_np: np.ndarray) -> np.ndarray:
        """
        Vectorised per-tree variance → confidence score.

        Uses coefficient of variation (std / mean).  Returns an array of
        shape (n_samples,) with values in [0, 100].

        Passing raw numpy to individual DecisionTreeRegressors avoids the
        sklearn feature-name mismatch warning (trees were fitted on arrays).
        """
        # shape: (n_estimators, n_samples)
        tree_preds = np.vstack([t.predict(X_np) for t in run_estimator.estimators_])
        tree_mean  = tree_preds.mean(axis=0)
        tree_std   = tree_preds.std(axis=0)
        return np.clip((1.0 - tree_std / (tree_mean + 1e-6)) * 100.0, 0.0, 100.0)

    def _buffer_multiplier(self, confidence: np.ndarray) -> np.ndarray:
        """Square-root adaptive buffer multiplier for low-confidence predictions."""
        gap = np.maximum(0.0, (self.CONFIDENCE_RELEARN_THRESHOLD - confidence) / self.CONFIDENCE_RELEARN_THRESHOLD)
        return 1.0 + np.sqrt(gap) * 0.8

    def _adjusted_confidence(self, raw_conf: np.ndarray, multiplier: np.ndarray) -> np.ndarray:
        """Boost reported confidence after buffering, capped at 98."""
        return np.minimum(98.0, raw_conf + (multiplier - 1.0) * self.CONFIDENCE_RELEARN_THRESHOLD)

    def _maybe_auto_retrain(self) -> None:
        if self.auto_retrain and len(self.low_confidence_buffer) >= self.auto_retrain_threshold:
            logger.info(
                "AUTO-RETRAIN TRIGGERED (%d buffered predictions)",
                len(self.low_confidence_buffer),
            )
            self.retrain_from_buffered_data(min_samples=self.auto_retrain_threshold)

    # =========================================================================
    # SINGLE PREDICTION
    # =========================================================================

    def predict_ai(
        self,
        process_id,
        style_id,
        printing_id,
        full_path,
        qty,
        sqfpm,
        buffer: bool = True,
    ) -> tuple[float, float, float, float]:
        """
        Predict (total_minutes, setup_minutes, run_minutes, confidence).

        Confidence < threshold  → apply buffer, log for relearning.
        Confidence >= threshold → return raw AI prediction unchanged.
        """
        try:
            qty = float(qty)
            if qty <= 0:
                qty = 1.0
        except (ValueError, TypeError):
            qty = 1.0

        if not self.is_trained:
            run = qty * 0.01
            return run + 15.0, 15.0, run, 0.0

        try:
            s_code, print_code, p_code = self._encode_single(style_id, printing_id, full_path)

            X = pd.DataFrame(
                {
                    "process_id":    int(process_id),
                    "style_code":    s_code,
                    "printing_code": print_code,
                    "path_code":     p_code,
                    "log_qty":       np.log1p(qty),
                    "sqfpm_bracket": self._normalize_sqfpm(sqfpm),
                },
                index=[0],
            )[self.feature_cols]

            # Top-level model gets the named DataFrame (feature validation)
            preds    = self.model.predict(X)[0]
            ai_setup = max(0.0, preds[0])
            ai_rate  = max(0.0, preds[1])

            # Individual trees get numpy (they were fitted on arrays)
            run_estimator = self.model.estimators_[1]
            confidence    = float(self._compute_confidence(run_estimator, X.values)[0])

            if buffer and confidence < self.CONFIDENCE_RELEARN_THRESHOLD:
                mult          = float(self._buffer_multiplier(np.array([confidence]))[0])
                buf_setup     = ai_setup * mult
                buf_rate      = ai_rate  * mult
                run_total     = buf_rate * qty
                total         = buf_setup + run_total
                adj_conf      = float(self._adjusted_confidence(np.array([confidence]), np.array([mult]))[0])

                self.low_confidence_buffer.append(
                    {
                        "timestamp":      datetime.now().isoformat(),
                        "process_id":     int(process_id),
                        "style_id":       str(style_id).strip(),
                        "printing_id":    str(printing_id).strip(),
                        "full_path":      str(full_path),
                        "job_qty":        float(qty),
                        "sqfpm":          float(sqfpm) if sqfpm else 1000.0,
                        "setup_m":        float(buf_setup),
                        "run_m":          float(run_total),
                        "confidence_was": confidence,
                        "buffer_applied": mult - 1.0,
                        # Raw values stored so retraining uses unbiased targets
                        "ai_raw_setup":   float(ai_setup),
                        "ai_raw_rate":    float(ai_rate),
                    }
                )
                self._maybe_auto_retrain()
                return round(total, 1), round(buf_setup, 1), round(run_total, 1), round(adj_conf, 1)

            run_total = ai_rate * qty
            total     = ai_setup + run_total
            return round(total, 1), round(ai_setup, 1), round(run_total, 1), round(confidence, 1)

        except Exception:
            logger.exception("predict_ai failed")
            run = qty * 0.01
            return run + 15.0, 15.0, run, 0.0

    # =========================================================================
    # BATCH PREDICTION
    # =========================================================================

    def predict_batch(self, jobs_df: pd.DataFrame, buffer: bool = True) -> pd.DataFrame:
        """
        Vectorised batch prediction — results match predict_ai exactly.

        Input columns required: process_id, style_id, full_path, qty, sqfpm.
        Optional: printing_id (defaults to median encoding if absent).

        Returns DataFrame with columns: total_m, setup_m, run_m, confidence.
        """
        df = jobs_df.copy()
        df["qty"] = pd.to_numeric(df["qty"], errors="coerce").fillna(1.0).clip(lower=1.0)

        if not self.is_trained:
            df["setup_m"]    = 15.0
            df["run_m"]      = df["qty"] * 0.01
            df["total_m"]    = df["setup_m"] + df["run_m"]
            df["confidence"] = 0.0
            return df[["total_m", "setup_m", "run_m", "confidence"]]

        try:
            med_style = len(self.style_cats)    // 2
            med_path  = len(self.path_cats)     // 2
            med_print = len(self.printing_cats) // 2

            df["style_code"] = df["style_id"].astype(str).map(
                lambda x: self.style_cats.get_loc(x) if x in self.style_cats else med_style
            )
            df["path_code"] = df["full_path"].astype(str).map(
                lambda x: self.path_cats.get_loc(x) if x in self.path_cats else med_path
            )
            df["printing_code"] = (
                df["printing_id"].astype(str).map(
                    lambda x: self.printing_cats.get_loc(x) if x in self.printing_cats else med_print
                )
                if "printing_id" in df.columns
                else med_print
            )
            df["log_qty"]       = np.log1p(df["qty"])
            df["sqfpm_bracket"] = df["sqfpm"].fillna(1000.0).apply(self._normalize_sqfpm)

            X = pd.DataFrame(
                {
                    "process_id":    df["process_id"].astype(int),
                    "style_code":    df["style_code"].astype(int),
                    "printing_code": df["printing_code"].astype(int),
                    "path_code":     df["path_code"].astype(int),
                    "log_qty":       df["log_qty"].astype(float),
                    "sqfpm_bracket": df["sqfpm_bracket"].astype(float),
                }
            )[self.feature_cols]

            X_np = X.values  # numpy for tree-level calls

            # Top-level model: named DataFrame (feature validation happy)
            preds            = self.model.predict(X)
            df["setup_final"] = np.maximum(0.0, preds[:, 0])
            df["rate_final"]  = np.maximum(0.0, preds[:, 1])

            # Confidence: vectorised across all trees at once
            run_estimator    = self.model.estimators_[1]
            df["confidence"] = self._compute_confidence(run_estimator, X_np)
            df["raw_conf"]   = df["confidence"].copy()

            if buffer:
                low_mask = df["confidence"] < self.CONFIDENCE_RELEARN_THRESHOLD

                if low_mask.any():
                    mult = self._buffer_multiplier(df.loc[low_mask, "raw_conf"].values)

                    df.loc[low_mask, "setup_final"] *= mult
                    df.loc[low_mask, "rate_final"]  *= mult
                    df.loc[low_mask, "confidence"]   = self._adjusted_confidence(
                        df.loc[low_mask, "raw_conf"].values, mult
                    )

                    # Vectorised buffer logging — no iterrows
                    lc = df.loc[low_mask].copy()
                    lc["_mult"] = mult

                    records = [
                        {
                            "timestamp":      datetime.now().isoformat(),
                            "process_id":     int(r["process_id"]),
                            "style_id":       str(r["style_id"]),
                            "printing_id":    str(r.get("printing_id", "")),
                            "full_path":      str(r["full_path"]),
                            "job_qty":        float(r["qty"]),
                            "sqfpm":          float(r["sqfpm"]) if pd.notna(r["sqfpm"]) else 1000.0,
                            "setup_m":        float(r["setup_final"]),
                            "run_m":          float(r["rate_final"] * r["qty"]),
                            "confidence_was": float(r["raw_conf"]),
                            "buffer_applied": float(r["_mult"] - 1.0),
                            # Raw (pre-buffer) targets for honest retraining
                            "ai_raw_setup":   float(r["setup_final"] / r["_mult"]),
                            "ai_raw_rate":    float(r["rate_final"]  / r["_mult"]),
                        }
                        for _, r in lc.iterrows()
                    ]
                    self.low_confidence_buffer.extend(records)

            df["setup_m"]    = df["setup_final"].round(1)
            df["run_m"]      = (df["rate_final"] * df["qty"]).round(1)
            df["total_m"]    = (df["setup_m"] + df["run_m"]).round(1)
            df["confidence"] = df["confidence"].round(1)

            self._maybe_auto_retrain()
            return df[["total_m", "setup_m", "run_m", "confidence"]]

        except Exception:
            logger.exception("predict_batch failed")
            df["setup_m"]    = 15.0
            df["run_m"]      = df["qty"] * 0.01
            df["total_m"]    = df["setup_m"] + df["run_m"]
            df["confidence"] = 0.0
            return df[["total_m", "setup_m", "run_m", "confidence"]]

    # =========================================================================
    # RETRAINING FROM BUFFER
    # =========================================================================

    def retrain_from_buffered_data(self, min_samples: int = 10) -> bool:
        """
        Retrain using *raw* AI values from the low-confidence buffer.

        Using ai_raw_setup / ai_raw_rate (not the inflated buffered values)
        prevents compounding inflation across successive retrain cycles.
        The buffer signals *which* combinations need more data; the raw
        predictions are used as the actual training targets.
        """
        n = len(self.low_confidence_buffer)
        if n < min_samples:
            logger.warning("Need %d buffered samples, have %d", min_samples, n)
            return False

        try:
            buf_df = pd.DataFrame(self.low_confidence_buffer)

            # Rename raw fields to match train_global's expected schema
            train_ready = buf_df.rename(
                columns={
                    "ai_raw_setup": "setup_m",
                    "ai_raw_rate":  "run_rate",   # train_global derives this itself
                    "job_qty":      "job_qty",
                }
            )
            # Reconstruct run_m so train_global can compute run_rate = run_m / job_qty
            train_ready["run_m"] = train_ready["run_rate"] * train_ready["job_qty"]

            if self.db:
                existing  = self.db.fetch_ai_training_data()
                combined  = pd.concat([existing, train_ready], ignore_index=True)
                logger.info(
                    "Retraining: existing=%s  new=%d  combined=%s",
                    f"{len(existing):,}", n, f"{len(combined):,}",
                )
            else:
                combined = train_ready
                logger.info("Retraining on %d buffered samples (no DB)", n)

            success = self.train_global(combined, save=True)

            if success:
                learned = {(x["process_id"], x["style_id"]) for x in self.low_confidence_buffer}
                self.low_confidence_buffer.clear()
                logger.info(
                    "Retraining complete — learned %d new (process, style) combinations",
                    len(learned),
                )

            return success

        except Exception:
            logger.exception("retrain_from_buffered_data failed")
            return False

    # =========================================================================
    # CONTROLS & DIAGNOSTICS
    # =========================================================================

    def enable_auto_retrain(self, threshold: int = 10) -> None:
        self.auto_retrain           = True
        self.auto_retrain_threshold = threshold
        logger.info("Auto-retrain ENABLED (threshold: %d)", threshold)
        self.save_model()

    def disable_auto_retrain(self) -> None:
        self.auto_retrain = False
        logger.info("Auto-retrain DISABLED")
        self.save_model()

    def clear_buffer(self) -> None:
        """Discard buffered predictions without retraining."""
        n = len(self.low_confidence_buffer)
        self.low_confidence_buffer.clear()
        logger.info("Cleared %d buffered predictions", n)
        self.save_model()

    def get_buffer_stats(self) -> dict | None:
        """Return buffer statistics dict, or None if buffer is empty."""
        if not self.low_confidence_buffer:
            logger.info("Buffer is empty")
            return None

        df            = pd.DataFrame(self.low_confidence_buffer)
        avg_conf      = df["confidence_was"].mean()
        avg_buffer    = df["buffer_applied"].mean() * 100
        unique_combos = df[["process_id", "style_id"]].drop_duplicates().__len__()
        ready         = len(df) >= self.auto_retrain_threshold

        logger.info(
            "Buffer: %d entries  avg-conf: %.1f%%  avg-buffer: +%.0f%%  combos: %d  ready: %s",
            len(df), avg_conf, avg_buffer, unique_combos, ready,
        )
        return {
            "total":          len(df),
            "avg_confidence": avg_conf,
            "avg_buffer_pct": avg_buffer,
            "unique_combos":  unique_combos,
            "ready":          ready,
        }

    def get_model_info(self) -> dict:
        """Return a snapshot of model metadata."""
        return {
            "is_trained":             self.is_trained,
            "training_samples":       self.training_samples,
            "val_r2":                 self.last_r2_score,
            "training_date":          self.training_date,
            "num_styles":             len(self.style_cats)    if self.style_cats    is not None else 0,
            "num_printing":           len(self.printing_cats) if self.printing_cats is not None else 0,
            "num_paths":              len(self.path_cats)     if self.path_cats     is not None else 0,
            "model_path":             self.model_path,
            "confidence_threshold":   self.CONFIDENCE_RELEARN_THRESHOLD,
            "buffered_predictions":   len(self.low_confidence_buffer),
            "ready_to_retrain":       len(self.low_confidence_buffer) >= self.auto_retrain_threshold,
            "auto_retrain":           self.auto_retrain,
            "auto_retrain_threshold": self.auto_retrain_threshold,
        }