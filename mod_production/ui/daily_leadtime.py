import ttkbootstrap as tb
from ttkbootstrap.constants import *

from mod_production.ui.main_frame import ProductionPlannerFrame


def main():



    # Hidden app context for ttk/bootstrap + DB init
    app = tb.Window(themename="darkly")
    app.withdraw()

    planner = ProductionPlannerFrame(app)

    # Example jobs
    result = planner.predict_only(
        docket_id="170024",
        qty=3000
    )

    print(result)

    # jobs = [
    #     {
    #         "docket_id": "188946",
    #         "qty": 2000,
    #         "lead_days": 4
    #     },
    #     {
    #         "docket_id": "188946",
    #         "qty": 5000,
    #         "lead_days": 6
    #     }
    # ]

    # print("\nDAILY LEADTIME REPORT")
    # print("=" * 80)

    # for job in jobs:

    #     print(f"\nDocket: {job['docket_id']}")
    #     print("-" * 80)

    #     try:

    #         routing = planner.get_routing(
    #             docket_id=job["docket_id"],
    #             qty=job["qty"],
    #             lead_days=job["lead_days"]
    #         )

    #         if not routing:
    #             print("No routing found")
    #             continue

    #         for step in routing:

    #             start = (
    #                 step["start"].strftime("%Y-%m-%d")
    #                 if step["start"]
    #                 else "N/A"
    #             )

    #             end = (
    #                 step["end"].strftime("%Y-%m-%d")
    #                 if step["end"]
    #                 else "N/A"
    #             )

    #             print(
    #                 f"{step['seq_order']:02d} | "
    #                 f"{step['process_name']:<25} | "
    #                 f"{start} -> {end} | "
    #                 f"{step['confidence']:.0f}%"
    #             )

    #     except Exception as e:
    #         print(f"ERROR: {e}")

    # app.destroy()


if __name__ == "__main__":
    main()