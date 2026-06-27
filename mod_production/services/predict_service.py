from time import perf_counter
from mod_production.data.sql_manager import SQLManager
from mod_production.core.predictor import ProductionAI
import pandas as pd

class PredictService:

    def __init__(self):
        self.db = SQLManager()
        self.ai = ProductionAI()

    def predict_only(self, docket_id, qty):

        total_start = perf_counter()

        # -----------------------------
        # Routing Fetch
        # -----------------------------
        t0 = perf_counter()
        routing_df = self.db.fetch_docket_routing(docket_id, qty)
        fetch_time = perf_counter() - t0

        if routing_df is None or routing_df.empty:
            return {
                "docket_id": docket_id,
                "qty": qty,
                "routing": [],
                "timing": {
                    "fetch_routing_sec": round(fetch_time, 4),
                    "metadata_sec": 0,
                    "predict_sec": 0,
                    "total_sec": round(perf_counter() - total_start, 4)
                }
            }

        # -----------------------------
        # Metadata
        # -----------------------------
        t1 = perf_counter()
        style_id, printing_id, sqfpm = self.db.get_docket_metadata(docket_id)
        metadata_time = perf_counter() - t1

        style_id = style_id or "UNKNOWN"
        printing_id = printing_id or "UNKNOWN"
        sqfpm = sqfpm or 1000.0

        # build path once
        path_str = "->".join(routing_df['process_id'].astype(str))

        # -----------------------------
        # BUILD BATCH INPUT
        # -----------------------------
        batch_df = routing_df.copy()
        batch_df['style_id'] = style_id
        batch_df['printing_id'] = printing_id
        batch_df['full_path'] = path_str
        batch_df['qty'] = qty
        batch_df['sqfpm'] = sqfpm

        # -----------------------------
        # BATCH PREDICTION (FAST)
        # -----------------------------
        t2 = perf_counter()

        pred_df = self.ai.predict_batch(batch_df, buffer=True)

        predict_time = perf_counter() - t2

        # -----------------------------
        # FORMAT OUTPUT
        # -----------------------------
        results = []

        for i, row in routing_df.iterrows():
            p = pred_df.iloc[i]

            results.append({
                "process_id": row["process_id"],
                "process_name": row.get("process_name"),
                "setup_m": round(float(p["setup_m"]), 2),
                "run_m": round(float(p["run_m"]), 2),
                "total_m": round(float(p["total_m"]), 2),
                "confidence": round(float(p["confidence"]), 1)
            })

        total_time = perf_counter() - total_start

        return {
            "docket_id": docket_id,
            "qty": qty,
            "routing": results,
            "timing": {
                "fetch_routing_sec": round(fetch_time, 4),
                "metadata_sec": round(metadata_time, 4),
                "predict_sec": round(predict_time, 4),
                "total_sec": round(total_time, 4)
            }
        }