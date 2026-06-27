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
VERSION: 2.1 - Self-Improving AI with Auto-Retrain
"""

import pandas as pd
import numpy as np
import joblib
import os
import traceback
from datetime import datetime
from sklearn.ensemble import RandomForestRegressor
from sklearn.multioutput import MultiOutputRegressor

import warnings

warnings.filterwarnings(
    "ignore",
    message="pandas only supports SQLAlchemy connectable"
)

warnings.filterwarnings(
    "ignore",
    message="X does not have valid feature names",
    category=UserWarning,
    module="sklearn"
)

print = lambda *args, **kwargs: None
traceback.print_exc = lambda *args, **kwargs: None

class ProductionAI:
    def __init__(self, db_manager=None, model_path="models/factory_brain.pkl",
                 auto_retrain=True, auto_retrain_threshold=10):
        """
        Initialize ProductionAI with optional auto-retrain capability.
        
        Args:
            db_manager: Database connection
            model_path: Path to save/load model
            auto_retrain: Enable automatic retraining (default: False)
            auto_retrain_threshold: Min samples before auto-retrain (default: 10)
        """
        self.db = db_manager
        self.model_path = os.path.abspath(model_path)

        self.model = None
        self.is_trained = False

        self.style_cats = None
        self.printing_cats = None
        self.path_cats = None

        self.feature_cols = [
            'process_id',
            'style_code',
            'printing_code',
            'path_code',
            'log_qty',
            'sqfpm_bracket'
        ]

        # Relearning configuration
        self.CONFIDENCE_RELEARN_THRESHOLD = 80 # Only buffer and relearn below this
        self.low_confidence_buffer = []  # Store buffered predictions for relearning
        
        # Auto-retrain configuration
        self.auto_retrain = auto_retrain
        self.auto_retrain_threshold = auto_retrain_threshold

        # Metadata
        self.training_date = "Never"
        self.training_samples = 0
        self.last_r2_score = 0.0

        os.makedirs(os.path.dirname(self.model_path), exist_ok=True)
        self.load_model()

    # ==========================================================
    # LOAD / SAVE
    # ==========================================================
    def load_model(self):
        """Load trained model and low-confidence buffer from disk."""
        if not os.path.exists(self.model_path):
            print("ℹ No trained AI model found")
            return

        try:
            data = joblib.load(self.model_path)

            # Validate required keys
            required_keys = ['model', 'style_cats','printing_cats', 'path_cats', 'feature_cols']
            missing = [k for k in required_keys if k not in data]
            if missing:
                print(f"✗ Model file corrupted - missing: {missing}")
                return

            self.model = data['model']
            self.style_cats = data['style_cats']
            self.printing_cats = data['printing_cats']
            self.path_cats = data['path_cats']
            self.feature_cols = data['feature_cols']
            self.low_confidence_buffer = data.get('low_confidence_buffer', [])
            
            # Load auto-retrain settings
            self.auto_retrain = data.get('auto_retrain', self.auto_retrain)
            self.auto_retrain_threshold = data.get('auto_retrain_threshold', self.auto_retrain_threshold)

            self.training_date = data.get('training_date', 'Unknown')
            self.training_samples = data.get('training_samples', 0)
            self.last_r2_score = data.get('r2', 0.0)

            self.is_trained = True

            print("✓ AI Brain Loaded")
            print(f"  • Samples: {self.training_samples:,}")
            print(f"  • R²: {self.last_r2_score:.3f}")
            print(f"  • Buffered predictions: {len(self.low_confidence_buffer)}")
            if self.auto_retrain:
                print(f"  • Auto-retrain: ENABLED (threshold: {self.auto_retrain_threshold})")
            else:
                print(f"  • Auto-retrain: DISABLED")

        except Exception as e:
            print(f"✗ Failed to load model: {e}")
            traceback.print_exc()

    def save_model(self):
        """Save model and low-confidence buffer to disk."""
        if not self.is_trained:
            print("⚠ Cannot save - model not trained")
            return False

        try:
            # Backup existing model
            if os.path.exists(self.model_path):
                backup_path = self.model_path + ".backup"
                try:
                    import shutil
                    shutil.copy2(self.model_path, backup_path)
                except Exception as e:
                    print(f"  ⚠ Backup failed: {e}")

            # Save everything including auto-retrain settings
            joblib.dump({
                'model': self.model,
                'style_cats': self.style_cats,
                'printing_cats' : self.printing_cats,
                'path_cats': self.path_cats,
                'feature_cols': self.feature_cols,
                'low_confidence_buffer': self.low_confidence_buffer,
                'auto_retrain': self.auto_retrain,
                'auto_retrain_threshold': self.auto_retrain_threshold,
                'training_samples': self.training_samples,
                'training_date': self.training_date,
                'r2': self.last_r2_score
            }, self.model_path, compress=3)

            file_size = os.path.getsize(self.model_path) / 1024 / 1024
            print(f"✓ Model saved ({file_size:.2f} MB)")
            return True

        except Exception as e:
            print(f"✗ Failed to save model: {e}")
            traceback.print_exc()
            return False

    # ==========================================================
    # TRAINING
    # ==========================================================

    def train_global(self, df, save=True):
        print("*"*80)
        print(df)
        """
        Train AI model on historical production data.
        
        Improvements:
        - Detailed progress logging
        - Physical reality filters
        - Outlier removal
        """
        if df is None or df.empty:
            print("✗ No data provided for training")
            return False

        if len(df) < 10:
            print(f"✗ Insufficient data: {len(df)} samples (need ≥10)")
            return False

        try:
            print("\n" + "=" * 60)
            print("AI TRAINING")
            print("=" * 60)

            work = df.copy()
            initial_count = len(work)
            print(f"[1/5] Starting with {initial_count:,} samples")

            # Feature engineering
            print(f"[2/5] Engineering features...")
            work['run_rate'] = work['run_m'] / work['job_qty']
            work['log_qty'] = np.log1p(work['job_qty'])
            work['sqfpm_bracket'] = (
                work['sqfpm'].fillna(1000).clip(lower=1).div(100).round().mul(100)
            )

            # Physical reality filters
            print(f"[3/5] Applying filters...")
            pre_filter = len(work)
            work = work[
                (work['run_rate'] > 0) &
                (work['run_rate'] < 2.0) &
                (work['setup_m'] >= 0) &
                (work['setup_m'] < 240) &
                (work['job_qty'] > 0)
            ]
            removed = pre_filter - len(work)
            print(f"  • Removed {removed:,} outliers ({removed/pre_filter*100:.1f}%)")

            if len(work) < 10:
                print(f"✗ Too few samples after filtering: {len(work)}")
                return False

            # Encoding
            print(f"[4/5] Encoding categories...")
            work['style_id'] = work['style_id'].astype(str).astype('category')
            work['printing_id'] = work['printing_id'].astype(str).astype('category')
            work['full_path'] = work['full_path'].astype(str).astype('category')

            self.style_cats = work['style_id'].cat.categories
            self.printing_cats = work['printing_id'].cat.categories
            self.path_cats = work['full_path'].cat.categories

            work['style_code'] = work['style_id'].cat.codes
            work['printing_code'] = work['printing_id'].cat.codes
            work['path_code'] = work['full_path'].cat.codes

            print(f"  • Unique styles: {len(self.style_cats)}")
            print(f"  • Unique printing: {len(self.printing_cats)}")
            print(f"  • Unique paths: {len(self.path_cats)}")

            # Train model
            print(f"[5/5] Training Random Forest (250 trees)...")
            X = work[self.feature_cols]
            y = work[['setup_m', 'run_rate']]

            self.model = MultiOutputRegressor(
                RandomForestRegressor(
                    n_estimators=250,
                    max_depth=14,
                    min_samples_leaf=2,
                    random_state=42,
                    n_jobs=-1
                )
            )
            self.model.fit(X, y)

            self.last_r2_score = self.model.score(X, y)
            self.training_samples = len(work)
            self.training_date = datetime.now().strftime("%Y-%m-%d %H:%M")
            self.is_trained = True

            print(f"  • R² Score: {self.last_r2_score:.3f}")
            print(f"  • Training samples: {self.training_samples:,}")

            if save:
                self.save_model()

            print("=" * 60)
            print("✓ AI TRAINING COMPLETE")
            print("=" * 60)
            return True

        except Exception as e:
            print("\n" + "=" * 60)
            print("✗ TRAINING FAILED")
            print("=" * 60)
            print(f"Error: {e}")
            traceback.print_exc()
            return False
    # ==========================================================
    # PREDICTION WITH CONFIDENCE BUFFER
    # ==========================================================
    def _normalize_sqfpm(self, sqfpm):
        """Normalize SQFPM to 100-unit buckets."""
        if sqfpm is None or sqfpm <= 0:
            return 1000.0
        try:
            return round(float(sqfpm) / 100) * 100
        except (ValueError, TypeError):
            return 1000.0

    def predict_ai(self, process_id, style_id, printing_id, full_path, qty, sqfpm, buffer=True):
        """
        AI-ONLY PREDICTION WITH ADAPTIVE CONFIDENCE BUFFER
        
        KEY LOGIC:
        - Confidence < 80%: Apply buffer (correction for uncertainty)
        - Confidence ≥ 80%: Use raw prediction (AI is reliable)
        - Buffer approximates reality better than uncertain predictions
        - Buffered values are logged for relearning
        - AUTO-RETRAIN triggers when buffer reaches threshold
        
        Args:
            process_id: Process ID
            style_id: Style ID
            printing_id: Printing ID
            full_path: Routing path
            qty: Job quantity
            sqfpm: Square feet per thousand
            buffer: Whether to apply buffer (default True)
        
        Returns:
            (total_minutes, setup_minutes, run_minutes, confidence)
        """
        # Input validation
        try:
            qty = float(qty)
            if qty <= 0:
                qty = 1
        except (ValueError, TypeError):
            qty = 1

        # Fallback if not trained
        if not self.is_trained:
            run = qty * 0.01
            return run + 15, 15, run, 0.0

        try:
            sid = str(style_id).strip()
            pid = str(printing_id).strip()

            # Encode with median fallback for unknowns
            s_code = (
                self.style_cats.get_loc(sid)
                if sid in self.style_cats else len(self.style_cats) // 2
            )
            print_code = (
                self.printing_cats.get_loc(pid)
                if pid in self.printing_cats else len(self.printing_cats) // 2
            )
            p_code = (
                self.path_cats.get_loc(str(full_path))
                if str(full_path) in self.path_cats else len(self.path_cats) // 2
            )

            # Build feature vector
            X = pd.DataFrame({
                'process_id': int(process_id),
                'style_code': s_code,
                'printing_code': print_code,
                'path_code': p_code,
                'log_qty': np.log1p(qty),
                'sqfpm_bracket': self._normalize_sqfpm(sqfpm)
            }, index=[0]) 
            
            # Reorder columns to match feature_cols exactly
            X = X[self.feature_cols]

            # Get AI prediction
            preds = self.model.predict(X)[0]
            ai_setup = max(0, preds[0])
            ai_rate = max(0, preds[1])

            # predict_ai — tree confidence loop
            run_estimator = self.model.estimators_[1]
            X_values = X.values  # extract once, reuse for all trees
            tree_preds = np.array([t.predict(X_values)[0] for t in run_estimator.estimators_])
            tree_mean = np.mean(tree_preds)
            tree_std = np.std(tree_preds)
            
            # Confidence: inverse of coefficient of variation
            confidence = np.clip((1 - tree_std / (tree_mean + 1e-6)) * 100, 0, 100)

            # DECISION POINT: Apply buffer if confidence is low
            if buffer and confidence < self.CONFIDENCE_RELEARN_THRESHOLD:
                # Square-root adaptive buffer (smoother than linear)
                buffer_multiplier = 1.0 + np.sqrt(
                    max(0, (self.CONFIDENCE_RELEARN_THRESHOLD - confidence) / self.CONFIDENCE_RELEARN_THRESHOLD)
                ) * 0.8
                
                buffered_setup = ai_setup * buffer_multiplier
                buffered_rate = ai_rate * buffer_multiplier
                
                run_total = buffered_rate * qty
                total = buffered_setup + run_total
                
                # LOG BUFFERED PREDICTION FOR RELEARNING
                self.low_confidence_buffer.append({
                    'timestamp': datetime.now().isoformat(),
                    'process_id': int(process_id),
                    'style_id': sid,
                    'printing_id' : pid,
                    'full_path': str(full_path),
                    'job_qty': float(qty),
                    'sqfpm': float(sqfpm) if sqfpm else 1000.0,
                    'setup_m': float(buffered_setup),
                    'run_m': float(run_total),
                    'confidence_was': float(confidence),
                    'buffer_applied': float(buffer_multiplier - 1.0),
                    'ai_raw_setup': float(ai_setup),
                    'ai_raw_rate': float(ai_rate)
                })
                
                # Boost reported confidence after buffering
                adjusted_confidence = min(98, confidence + (buffer_multiplier - 1.0) * self.CONFIDENCE_RELEARN_THRESHOLD)
                
                # AUTO-RETRAIN CHECK
                if self.auto_retrain and len(self.low_confidence_buffer) >= self.auto_retrain_threshold:
                    print(f"\n🔄 AUTO-RETRAIN TRIGGERED ({len(self.low_confidence_buffer)} buffered predictions)")
                    self.retrain_from_buffered_data(min_samples=self.auto_retrain_threshold)
                
                return (
                    round(total, 1),
                    round(buffered_setup, 1),
                    round(run_total, 1),
                    round(adjusted_confidence, 1)
                )
            
            else:
                # High confidence - AI is reliable, use raw prediction
                run_total = ai_rate * qty
                total = ai_setup + run_total
                
                return (
                    round(total, 1),
                    round(ai_setup, 1),
                    round(run_total, 1),
                    round(confidence, 1)
                )

        except Exception as e:
            print(f"⚠ Prediction error: {e}")
            traceback.print_exc()
            run = qty * 0.01
            return run + 15, 15, run, 0.0

    # ==========================================
    # BATCH PREDICTION (AI-ONLY + CONFIDENCE BUFFER)
    # ==========================================
    def predict_batch(self, jobs_df, buffer=True):
        """
        High-speed vectorized AI prediction with adaptive confidence buffering.
        Guarantees parity with predict_ai by standardizing structural dataframe evaluations.
        """
        df = jobs_df.copy()

        # --- FIX 1: Clamp qty to minimum 1, matching predict_ai ---
        df['qty'] = df['qty'].apply(lambda q: max(1.0, float(q)) if pd.notna(q) else 1.0)

        if not self.is_trained:
            df['setup_m'] = 15.0
            df['run_m'] = df['qty'] * 0.01
            df['total_m'] = df['setup_m'] + df['run_m']
            df['confidence'] = 0.0
            return df[['total_m', 'setup_m', 'run_m', 'confidence']]

        try:
            # Vectorized categorical translations
            median_style = len(self.style_cats) // 2
            median_path = len(self.path_cats) // 2
            median_print = len(self.printing_cats) // 2

            df['s_code'] = df['style_id'].astype(str).apply(
                lambda x: self.style_cats.get_loc(x) if x in self.style_cats else median_style
            )
            df['p_code'] = df['full_path'].astype(str).apply(
                lambda x: self.path_cats.get_loc(x) if x in self.path_cats else median_path
            )
            if 'printing_id' in df.columns:
                df['print_code'] = df['printing_id'].astype(str).apply(
                    lambda x: self.printing_cats.get_loc(x) if x in self.printing_cats else median_print
                )
            else:
                df['print_code'] = median_print

            # FIX 1 already applied above — qty is clean, use it directly here
            df['log_qty'] = np.log1p(df['qty'])
            df['sq_b'] = df['sqfpm'].fillna(1000).apply(self._normalize_sqfpm)

            # Secure Positional Alignment Feature Extraction
            mapping = {
                'process_id': df['process_id'].astype(int),
                'style_code': df['s_code'].astype(int),
                's_code': df['s_code'].astype(int),
                'printing_code': df['print_code'].astype(int),
                'print_code': df['print_code'].astype(int),
                'path_code': df['p_code'].astype(int),
                'p_code': df['p_code'].astype(int),
                'log_qty': df['log_qty'].astype(float),
                'sqfpm_bracket': df['sq_b'].astype(float),
                'sq_b': df['sq_b'].astype(float)
            }

            X_built = pd.DataFrame({col: mapping[col] for col in self.feature_cols})
            X_matrix = X_built.values

            # Raw multi-output core inference
            # preds = self.model.predict(X_matrix)
            preds = self.model.predict(X_built)

            df['setup_final'] = np.maximum(0, preds[:, 0])
            df['rate_final'] = np.maximum(0, preds[:, 1])

            # predict_batch — tree confidence loop  
            run_estimator = self.model.estimators_[1]
            X_values = X_built.values  # already have X_matrix = X_built.values, just reuse it
            tree_preds = np.array([t.predict(X_matrix) for t in run_estimator.estimators_])
            tree_mean = np.mean(tree_preds, axis=0)
            tree_std = np.std(tree_preds, axis=0)
            df['confidence'] = np.clip((1.0 - (tree_std / (tree_mean + 1e-6))) * 100, 0, 100)

            # --- FIX 2: Preserve raw confidence before any mutation, for accurate logging ---
            df['raw_confidence'] = df['confidence'].copy()

            if buffer:
                low_conf_mask = df['confidence'] < self.CONFIDENCE_RELEARN_THRESHOLD

                if low_conf_mask.any():
                    buffer_multipliers = 1.0 + np.sqrt(
                        (self.CONFIDENCE_RELEARN_THRESHOLD - df.loc[low_conf_mask, 'raw_confidence'])
                        / self.CONFIDENCE_RELEARN_THRESHOLD
                    ) * 0.8

                    # Apply buffer to setup and rate — same as predict_ai's buffered_setup / buffered_rate
                    df.loc[low_conf_mask, 'setup_final'] *= buffer_multipliers
                    df.loc[low_conf_mask, 'rate_final'] *= buffer_multipliers

                    # --- FIX 3: Adjusted confidence formula matches predict_ai exactly ---
                    #   predict_ai: min(98, confidence + (buffer_multiplier - 1.0) * THRESHOLD)
                    #   Use raw_confidence (pre-boost) as the base, matching predict_ai's local `confidence` var
                    df.loc[low_conf_mask, 'confidence'] = np.minimum(
                        98.0,
                        df.loc[low_conf_mask, 'raw_confidence'] + (buffer_multipliers - 1.0) * self.CONFIDENCE_RELEARN_THRESHOLD
                    )

                    # --- FIX 4: Log uses raw_confidence for confidence_was, and correct run_m ---
                    for idx, r in df.loc[low_conf_mask].iterrows():
                        current_mult = buffer_multipliers.loc[idx]
                        # rate_final is already buffered; run_m = buffered_rate * qty
                        calculated_run = r['rate_final'] * r['qty']

                        self.low_confidence_buffer.append({
                            'timestamp': datetime.now().isoformat(),
                            'process_id': int(r['process_id']),
                            'style_id': str(r['style_id']),
                            'printing_id': str(r.get('printing_id', '')),
                            'full_path': str(r['full_path']),
                            'job_qty': float(r['qty']),
                            'sqfpm': float(r['sqfpm']) if pd.notna(r['sqfpm']) else 1000.0,
                            'setup_m': float(r['setup_final']),
                            'run_m': float(calculated_run),
                            # FIX 4: use raw_confidence, not the already-boosted confidence column
                            'confidence_was': float(r['raw_confidence']),
                            'buffer_applied': float(current_mult - 1.0),
                            # FIX 4: log ai_raw values before buffer, matching predict_ai's log fields
                            'ai_raw_setup': float(r['setup_final'] / current_mult),
                            'ai_raw_rate': float(r['rate_final'] / current_mult),
                        })

            # Final output columns
            df['setup_m'] = df['setup_final'].round(1)
            df['run_m'] = (df['rate_final'] * df['qty']).round(1)
            df['total_m'] = (df['setup_m'] + df['run_m']).round(1)
            df['confidence'] = df['confidence'].round(1)

            if self.auto_retrain and len(self.low_confidence_buffer) >= self.auto_retrain_threshold:
                print(f"🔄 AUTO-RETRAIN TRIGGERED ({len(self.low_confidence_buffer)} buffered jobs)")
                self.retrain_from_buffered_data(min_samples=self.auto_retrain_threshold)

            return df[['total_m', 'setup_m', 'run_m', 'confidence']]

        except Exception as e:
            print(f"✗ Batch prediction error: {e}")
            traceback.print_exc()

            df['setup_m'] = 15.0
            df['run_m'] = df['qty'] * 0.01
            df['total_m'] = df['setup_m'] + df['run_m']
            df['confidence'] = 0.0
            return df[['total_m', 'setup_m', 'run_m', 'confidence']]

    # ==========================================================
    # RELEARNING FROM BUFFERED DATA
    # ==========================================================
    def retrain_from_buffered_data(self, min_samples=10):
        """
        Retrain AI using buffered predictions from low-confidence jobs.
        
        RATIONALE:
        When confidence is low (< 80%), buffered predictions are MORE
        ACCURATE than raw AI predictions. Training on buffered data
        teaches AI to predict conservatively and accurately.
        
        PROCESS:
        1. Collect buffered predictions (confidence < 80%)
        2. Combine with existing training data
        3. Retrain model
        4. Confidence increases for learned combinations
        5. Buffer naturally decreases/disappears
        
        Args:
            min_samples: Minimum buffered predictions needed (default 10)
        
        Returns:
            bool: True if retraining succeeded
        """
        if len(self.low_confidence_buffer) < min_samples:
            print(f"⚠ Need {min_samples} buffered samples, have {len(self.low_confidence_buffer)}")
            return False

        try:
            print("\n" + "=" * 60)
            print("RETRAINING FROM BUFFERED LOW-CONFIDENCE PREDICTIONS")
            print("=" * 60)
            print(f"Buffered predictions: {len(self.low_confidence_buffer)}")
            print(f"Threshold: Confidence < {self.CONFIDENCE_RELEARN_THRESHOLD}%")
            print("\nRATIONALE:")
            print("Low-confidence predictions are unreliable guesses.")
            print("Buffered values approximate reality better.")
            print("AI will learn conservative, accurate predictions.")
            print("=" * 60)

            # Convert buffered data to training format
            new_training_df = pd.DataFrame(self.low_confidence_buffer)
            
            # Show what's being learned
            avg_conf = new_training_df['confidence_was'].mean()
            avg_buffer = new_training_df['buffer_applied'].mean() * 100
            unique_combos = len(new_training_df[['process_id', 'style_id']].drop_duplicates())
            
            print(f"\nBuffered Data Statistics:")
            print(f"  • Samples: {len(new_training_df)}")
            print(f"  • Avg original confidence: {avg_conf:.1f}%")
            print(f"  • Avg buffer applied: +{avg_buffer:.0f}%")
            print(f"  • Unique (process, style) combos: {unique_combos}")

            # Fetch existing training data
            if self.db:
                print("\nFetching existing training data...")
                existing_df = self.db.fetch_ai_training_data()
                combined_df = pd.concat([existing_df, new_training_df], ignore_index=True)
                print(f"  • Existing: {len(existing_df):,} samples")
                print(f"  • New: {len(new_training_df):,} samples")
                print(f"  • Combined: {len(combined_df):,} samples")
            else:
                combined_df = new_training_df
                print(f"\nTraining on {len(combined_df):,} buffered samples")

            # Retrain
            print("\nRetraining AI model...")
            success = self.train_global(combined_df, save=True)

            if success:
                # Clear buffer after successful retraining
                learned_combos = set(
                    (x['process_id'], x['style_id'])
                    for x in self.low_confidence_buffer
                )
                self.low_confidence_buffer.clear()
                
                print("\n" + "=" * 60)
                print("✓ RETRAINING COMPLETE")
                print("=" * 60)
                print(f"AI learned {len(learned_combos)} new combinations")
                print("These will now predict with higher confidence")
                print("Buffer will naturally decrease/disappear")
                print("=" * 60)

            return success

        except Exception as e:
            print(f"\n✗ Retraining failed: {e}")
            traceback.print_exc()
            return False

    def get_buffer_stats(self):
        """
        Show statistics about buffered predictions waiting to be learned.
        
        Returns:
            dict: Statistics or None if no buffered data
        """
        if not self.low_confidence_buffer:
            print("ℹ No low-confidence predictions logged yet")
            return None

        df = pd.DataFrame(self.low_confidence_buffer)

        avg_confidence = df['confidence_was'].mean()
        avg_buffer = df['buffer_applied'].mean() * 100
        unique_combos = len(df[['process_id', 'style_id']].drop_duplicates())
        ready_to_retrain = len(df) >= 10

        print("\n" + "=" * 60)
        print("LOW-CONFIDENCE BUFFER STATISTICS")
        print("=" * 60)
        print(f"Total buffered predictions: {len(df)}")
        print(f"Average original confidence: {avg_confidence:.1f}%")
        print(f"Average buffer applied: +{avg_buffer:.0f}%")
        print(f"Unique (process, style) combos: {unique_combos}")
        print(f"Ready to retrain: {'Yes ✓' if ready_to_retrain else f'No (need {10-len(df)} more)'}")

        # Show sample
        if len(df) > 0:
            print("\nSample of buffered predictions:")
            for i, row in df.head(3).iterrows():
                style_short = str(row['style_id'])[:30]
                print(f"\n  [{i+1}] Process {row['process_id']}, Style: {style_short}")
                print(f"      Raw AI: {row['ai_raw_setup']:.1f}m setup, {row['ai_raw_rate']:.4f} rate")
                print(f"      Buffered: {row['setup_m']:.1f}m setup (better estimate)")
                print(f"      Confidence: {row['confidence_was']:.0f}% → Buffer: +{row['buffer_applied']*100:.0f}%")

        print("=" * 60)

        return {
            'total': len(df),
            'avg_confidence': avg_confidence,
            'avg_buffer_pct': avg_buffer,
            'unique_combos': unique_combos,
            'ready': ready_to_retrain
        }

    def clear_buffer(self):
        """
        Clear the low-confidence buffer without retraining.
        Use this if you want to discard logged predictions.
        """
        count = len(self.low_confidence_buffer)
        self.low_confidence_buffer.clear()
        print(f"✓ Cleared {count} buffered predictions")
        self.save_model()

    # ==========================================================
    # AUTO-RETRAIN CONTROLS
    # ==========================================================
    def enable_auto_retrain(self, threshold=10):
        """
        Enable automatic retraining when buffer reaches threshold.
        
        Args:
            threshold: Number of buffered predictions before auto-retrain (default 10)
        """
        self.auto_retrain = True
        self.auto_retrain_threshold = threshold
        print(f"✓ Auto-retrain ENABLED (threshold: {threshold} samples)")
        self.save_model()
    
    def disable_auto_retrain(self):
        """Disable automatic retraining."""
        self.auto_retrain = False
        print("✓ Auto-retrain DISABLED")
        self.save_model()

    # ==========================================================
    # MODEL INFO
    # ==========================================================
    def get_model_info(self):
        """
        Get comprehensive model information.
        
        Returns:
            dict: Model metadata and statistics
        """
        info = {
            "is_trained": self.is_trained,
            "training_samples": self.training_samples,
            "r2": self.last_r2_score,
            "training_date": self.training_date,
            "num_styles": len(self.style_cats) if self.style_cats is not None else 0,
            "num_printing": len(self.printing_cats) if self.printing_cats is not None else 0,
            "num_paths": len(self.path_cats) if self.path_cats is not None else 0,
            "model_path": self.model_path,
            "confidence_threshold": self.CONFIDENCE_RELEARN_THRESHOLD,
            "buffered_predictions": len(self.low_confidence_buffer),
            "ready_to_retrain": len(self.low_confidence_buffer) >= 10,
            "auto_retrain": self.auto_retrain,
            "auto_retrain_threshold": self.auto_retrain_threshold
        }

        return info