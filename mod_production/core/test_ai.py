import pandas as pd
from datetime import datetime
from predictor import ProductionAI  # replace with actual import

# 1️⃣ Initialize AI
ai = ProductionAI("models/factory_brain.pkl")

# 2️⃣ Create sample docket
sample_docket = pd.DataFrame({
    'process_id': [189, 213],
    'style_id': [47]*25,
    'full_path': ['189->213']*25,
    'Qty': [1000 + i*50 for i in range(25)],    # example quantities
    'sqfpm': [300 + i*5 for i in range(25)]     # example sqft per minute
})

print("Sample Docket:")
print(sample_docket.head())

# 3️⃣ Map categories (must match AI training)
style_map = {s: i for i, s in enumerate(ai.style_cats)}
path_map = {p: i for i, p in enumerate(ai.path_cats)}

sample_docket['style_code'] = sample_docket['style_id'].map(lambda s: style_map.get(s, -1))
sample_docket['path_code'] = sample_docket['full_path'].map(lambda p: path_map.get(p, -1))
sample_docket['sqfpm_bracket'] = sample_docket['sqfpm'].apply(ai._normalize_sqfpm)

# 4️⃣ Step-by-step prediction
for idx, row in sample_docket.iterrows():
    total, setup, run, confidence = ai.predict_with_confidence(
        process_id=row['process_id'],
        style_id=row['style_id'],
        full_path=row['full_path'],
        qty=row['Qty'],
        sqfpm=row['sqfpm']
    )
    print(f"Process {row['process_id']}: Setup={setup:.1f} mins, Run={run:.1f} mins, Total={total:.1f} mins, Confidence={confidence:.1f}%")
