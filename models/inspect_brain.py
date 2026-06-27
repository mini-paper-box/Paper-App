import joblib
import os
import pandas as pd
import numpy as np

def inspect_brain(file_path='factory_brain.pkl', sample_count=5):
    """
    Advanced diagnostic tool for the Production AI 'Brain'.
    Validates feature sets, category mapping, and multi-output regression health.
    """
    if not os.path.exists(file_path):
        print(f"❌ ERROR: '{file_path}' not found in current directory.")
        return

    try:
        # Using mmap_mode='r' can be faster for large models but isn't strictly necessary here
        brain_data = joblib.load(file_path)

        print("\n" + "="*50)
        print(" 🧠  PRODUCTION AI BRAIN DIAGNOSTICS ".center(50))
        print("="*50)

        # --- 1. METADATA SUMMARY ---
        meta = {
            "File": os.path.basename(file_path),
            "Size": f"{os.path.getsize(file_path) / 1024:.1f} KB",
            "Last Trained": brain_data.get('training_date', 'Unknown'),
            "Total Samples": brain_data.get('training_samples', 0),
            "Global Accuracy": f"{brain_data.get('r2', 0):.2%}"
        }
        
        for key, val in meta.items():
            print(f"{key:15}: {val}")

        # --- 2. FEATURE INTEGRITY CHECK ---
        # Crucial for verifying your 'Qty Bracket' upgrade
        features = brain_data.get('feature_cols', [])
        print(f"\n--- Feature Architecture ({len(features)} inputs) ---")
        
        vital_features = ['qty_bracket', 'log_qty', 'style_code', 'sqfpm_bracket']
        for feat in features:
            status = "⭐" if feat in vital_features else "  "
            print(f"{status} {feat}")
        
        if not any(f in features for f in vital_features):
            print("⚠️  WARNING: Vital scaling features (brackets/log) missing from this brain.")

        # --- 3. MODEL ARCHITECTURE ---
        model = brain_data.get('model')
        if model is not None:
            m_type = type(model).__name__
            print(f"\n--- Model Engine: {m_type} ---")
            
            # If MultiOutputRegressor, peek at the internal estimators
            if hasattr(model, "estimators_"):
                # MultiOutput usually has [0] for Setup and [1] for Run Rate
                targets = ["Setup Time", "Run Rate"]
                for i, est in enumerate(model.estimators_):
                    print(f"  └─ Sub-Model [{targets[i]}]: {type(est).__name__} (Trees: {len(est.estimators_)})")
        else:
            print("\n❌ CRITICAL: No model object found in the brain file.")

        # --- 4. CATEGORY MAPPINGS ---
        # Verify that the AI knows your specific factory's styles/paths
        print(f"\n--- Category Memory ---")
        for cat_name in ['style_cats', 'path_cats', 'printing_cats']:
            cats = brain_data.get(cat_name)
            if cats is not None:
                count = len(cats)
                sample = ", ".join(map(str, list(cats)[:sample_count]))
                print(f"- {cat_name:12}: {count} items. Sample: [{sample}...]")
            else:
                print(f"- {cat_name:12}: ⚠️ NOT FOUND")

        # --- 5. FEATURE IMPORTANCE (IF AVAILABLE) ---
        importances = brain_data.get('feature_importance', {})
        if importances:
            print(f"\n--- Impact on Prediction (Top Factors) ---")
            # Sort by value descending
            sorted_imp = sorted(importances.items(), key=lambda x: x[1], reverse=True)
            for feature, val in sorted_imp:
                bar = "█" * int(val * 20)
                print(f"{feature:15}: {val:6.1%} {bar}")

        print("="*50 + "\n")

    except Exception as e:
        print(f"❌ DIAGNOSTIC FAILED: {str(e)}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    inspect_brain('factory_brain.pkl')