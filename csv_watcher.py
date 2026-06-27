import os
import time
import json
import pandas as pd

class CSVWatcher:
    def __init__(self, file_path, state_file="csv_state.json"):
        self.file_path = file_path
        self.state_file = state_file
        self.last_known_time = None
        self._load_state()

    def _load_state(self):
        """Load last saved state from JSON."""
        if os.path.exists(self.state_file):
            with open(self.state_file, "r") as f:
                state = json.load(f)
                self.last_known_time = state.get("last_modified")
        else:
            self.last_known_time = None

    def _save_state(self, new_time):
        """Save state to JSON file."""
        with open(self.state_file, "w") as f:
            json.dump({"last_modified": new_time}, f)

    def has_update(self):
        """Check if file has been updated since last check."""
        if not os.path.exists(self.file_path):
            print("⚠️ CSV file not found.")
            return False

        modified_time = os.path.getmtime(self.file_path)

        if self.last_known_time is None:
            print(f"First run → File last modified at: {time.ctime(modified_time)}")
            self._save_state(modified_time)
            self.last_known_time = modified_time
            return False

        if modified_time > self.last_known_time:
            print(f"✅ CSV updated at {time.ctime(modified_time)}")
            self._save_state(modified_time)
            self.last_known_time = modified_time
            return True
        else:
            print("⏳ No update detected.")
            return False

    def load_csv(self):
        """Load CSV into pandas DataFrame."""
        try:
            df = pd.read_csv(self.file_path, encoding="utf-8")
            print(f"📂 Loaded CSV with {len(df)} rows, {len(df.columns)} columns.")
            return df
        except Exception as e:
            print(f"❌ Error loading CSV: {e}")
            return None
