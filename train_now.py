from mod_production.data.sql_manager import SQLManager
from mod_production.core.predictor import ProductionAI

# 1. Connect
db = SQLManager()
ai = ProductionAI()

# 2. Fetch the 2 years of history we defined in SQLManager
print("Fetching training data from SQL...")
df = db.fetch_training_data()

# 3. Train and Save
if not df.empty:
    print(f"Found {len(df)} records. Training now...")
    ai.train_global(df)
else:
    print("No data found. Check your 'track' and 'docket' tables.")