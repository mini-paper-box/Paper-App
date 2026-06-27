import joblib
import numpy as np
import pandas as pd

# 1. Load AI brain
pkl_file = "models/factory_brain.pkl"
brain = joblib.load(pkl_file)

model = brain['model']
style_cats = brain['style_cats']
path_cats = brain['path_cats']
feature_cols = brain.get('feature_cols', ['process_id', 'style_code', 'path_code', 'log_qty', 'sqfpm_bracket'])

# 2. Test input
process_id = 189
style_id = 47
full_path = "189->213"
qty = 500000 
sqfpm = 300 

# 3. Feature Engineering (Must match training exactly)
# Style and Path encoding
style_code = style_cats.get_loc(str(style_id)) if str(style_id) in style_cats else len(style_cats) // 2
path_code = path_cats.get_loc(str(full_path)) if str(full_path) in path_cats else len(path_cats) // 2

# Log transform the quantity
log_qty = np.log1p(max(0, qty))

# Bracket SQFPM
sqfpm_bracket = round(max(1, sqfpm) / 100) * 100

print(f"Features -> Style: {style_code}, Path: {path_code}, LogQty: {log_qty:.2f}, Bracket: {sqfpm_bracket}")

# 4. Prepare input DataFrame (ensuring correct column order)
X_df = pd.DataFrame([{
    'process_id': process_id,
    'style_code': style_code,
    'path_code': path_code,
    'log_qty': log_qty,
    'sqfpm_bracket': sqfpm_bracket
}])
X = X_df[feature_cols]

# 5. Predict
# Output 0: Setup Minutes | Output 1: Run Rate (mins/unit)
preds = model.predict(X)[0] 
setup_pred = max(0, preds[0])
run_rate_pred = max(0, preds[1])

# Convert Rate back to Total Time
total_run_mins = run_rate_pred * qty
total_pred = setup_pred + total_run_mins

print("-" * 30)
print(f"Predicted Setup: {setup_pred:.1f} mins")
print(f"Predicted Rate:  {run_rate_pred:.4f} mins/unit")
print(f"Predicted Run:   {total_run_mins:.1f} mins (for {qty} units)")
print(f"Predicted Total: {total_pred:.1f} mins")

# 6. Confidence Analysis (using Coefficient of Variation)
# We look at the run-rate estimator (index 1)
run_estimator = model.estimators_[1]
tree_preds = np.array([tree.predict(X.values)[0] for tree in run_estimator.estimators_])
cv = np.std(tree_preds) / np.mean(tree_preds) if np.mean(tree_preds) > 0 else 1.0
confidence = max(0, min(100, 100 * (1 - cv)))

print(f"Confidence:      {confidence:.1f}%")
print("-" * 30)