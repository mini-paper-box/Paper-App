from pprint import pprint
import datetime
import pandas as pd

# Import the ScheduleService we built
from mod_production.services.schedule_service import ScheduleService

def main():
    # 1. Define your factory parameters (Holidays)
    company_holidays = [
        datetime.date(2026, 1, 1),   # New Year's
        datetime.date(2026, 12, 25), # Christmas
    ]

    # 2. Define standard daily capacities (in hours) for your processes
    # process_id 1 might be Printing, 2 might be Cutting, etc.
    # capacity_1 = Sunday ... capacity_7 = Saturday
    capacity_data = {
        'process_id': [1, 2, 3, 4, 5], 
        'capacity_1': [0.0, 0.0, 0.0, 0.0, 0.0],  # Sunday (Closed)
        'capacity_2': [8.0, 8.0, 8.0, 8.0, 8.0],  # Monday
        'capacity_3': [8.0, 8.0, 8.0, 8.0, 8.0],  # Tuesday
        'capacity_4': [8.0, 8.0, 8.0, 8.0, 8.0],  # Wednesday
        'capacity_5': [8.0, 8.0, 8.0, 8.0, 8.0],  # Thursday
        'capacity_6': [8.0, 8.0, 8.0, 8.0, 8.0],  # Friday
        'capacity_7': [0.0, 0.0, 0.0, 0.0, 0.0],  # Saturday (Closed)
    }
    process_df = pd.DataFrame(capacity_data)

    # 3. Define already booked minutes to test finite capacity
    # Example: Process 1 is heavily booked for 300 minutes on May 20th, 2026
    booked_mins_lookup = {
        (1, datetime.date(2026, 5, 20)): 300 
    }

    # 4. Initialize the Schedule Engine with your parameters
    scheduler = ScheduleService(
        holidays=company_holidays,
        process_df=process_df,
        booked_mins_lookup=booked_mins_lookup
    )

    # 5. Run the allocation engine 
    # This automatically fetches routing, calls the AI backend, and books dates
    print("Generating timeline schedule via AI engine...")
    schedule_result = scheduler.build_schedule(
        docket_id="170024",
        qty=3000,
        lead_days=2  # Skip 2 working days before starting production
    )

    # 6. View the final production calendar blocks
    pprint(schedule_result)

if __name__ == "__main__":
    main()