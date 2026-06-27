import os

# 1. DATABASE CONNECTION STRINGS
# ---------------------------------------------------------
DB_CONFIG = {
    "server": "wbdbserver",
    "database": "flute_data",
    # "driver": "{ODBC Driver 18 for SQL Server}",
    "driver": "{SQL Server}",
    "trusted_connection": "yes",
    "encrypt": "yes",
    "trust_cert": "yes"
}

# CONN_STRING = (
#     'DRIVER={SQL Server};'
#     f'SERVER={server};'
#     f'DATABASE={database};'
#     'Trusted_Connection=yes;'

# 2. SCHEDULING LOGIC CONSTANTS
# ---------------------------------------------------------
SCHEDULING_RULES = {
    "penalty_per_setup": 0.07,    # The 7% capacity tax
    "anchor_percent": 0.60,       # Initial P80 calculation point
    "capacity_floor": 0.30,       # Never drop below 30% of max
    "max_jobs_per_day": 10,       # The "Gate" limit
    # Process IDs that don't follow normal rules
    "bypass_ids": (
        "40", "237", "238", "239", "240", 
        "241", "242", "245", "193", "243", "235"
    )
}

# 3. FILE PATHS
# ---------------------------------------------------------
# We use os.path to ensure paths work on both User A and User B's computers
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

PATHS = {
    "local_data": os.path.join(BASE_DIR, "data", "booked_jobs.json"),
    "icons": os.path.join(BASE_DIR, "ui", "assets"),
}

# 4. UI THEMING
# ---------------------------------------------------------
UI_SETTINGS = {
    "theme": "superhero",
    "chart_bg": "#2b3e50",
    "chart_grid": "#4e5d6c",
    "primary_color": "#3498db"
}

# A simple dictionary to bundle everything together
CONFIG = {
    "DATABASE": DB_CONFIG,
    "RULES": SCHEDULING_RULES,
    "PATHS": PATHS,
    "UI": UI_SETTINGS
}