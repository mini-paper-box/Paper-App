import sys
import pyodbc
import ttkbootstrap as tb
from tkinter import messagebox
from mod_production.ui.main_frame import ProductionPlannerFrame

def check_system_requirements():
    """Verify that the required SQL drivers are installed before launching."""
    drivers = [d for d in pyodbc.drivers() if 'ODBC Driver 18' in d]
    
    if not drivers:
        # Create a temporary hidden root to show the error message
        root = tb.Window()
        messagebox.showerror(
            "System Error", 
            "Required Driver Missing!\n\n"
            "Please install 'ODBC Driver 18 for SQL Server'.\n"
            "The application will now exit."
        )
        sys.exit()

def main():
    # 1. Check for SQL Driver 18
    #check_system_requirements()

    # 2. Create the Main Application Window
    # We use the 'superhero' theme to match your previous UI style
    app = tb.Window(
        title="Production Scheduler v2.0",
        themename="superhero",
        minsize=(1200, 800)
    )
    
    # 3. Maximize the window for a better dashboard view
    app.state('zoomed')

    # 4. Load the Modular Production Planner Frame
    # This acts as the 'Container' for everything we built
    planner = ProductionPlannerFrame(app)
    planner.pack(fill="both", expand=True)

    # 5. Start the Application
    app.mainloop()

if __name__ == "__main__":
    main()