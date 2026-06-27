import os
import sys
import webbrowser
from datetime import datetime, timedelta, date
from calendar import Calendar, month_name
from pathlib import Path
import ttkbootstrap as ttk
from ttkbootstrap.constants import *
from ttkbootstrap.dialogs import Messagebox
from PyPDF2 import PdfMerger
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('daily_planner_gui.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


def find_paper_app_folder():
    """Locate the Paper App folder with error handling."""
    try:
        possible_paths = [
            Path.home() / "OneDrive - whitebird.ca" / "Paper App",
            Path.home() / "OneDrive" / "Paper App",
            Path(__file__).parent,
        ]
        
        for path in possible_paths:
            try:
                if path.exists():
                    logger.info(f"Found Paper App folder: {path}")
                    return path
            except PermissionError as e:
                logger.warning(f"Permission denied accessing {path}: {e}")
                continue
            except Exception as e:
                logger.warning(f"Error checking path {path}: {e}")
                continue
        
        logger.warning("Paper App folder not found, using script directory")
        return Path(__file__).parent
        
    except Exception as e:
        logger.error(f"Error in find_paper_app_folder: {e}")
        return Path(__file__).parent


PAPER_APP_FOLDER = find_paper_app_folder()
sys.path.append(str(PAPER_APP_FOLDER))

try:
    from daily_planner_report import DailyPlannerReport
    logger.info("Successfully imported DailyPlannerReport")
except ImportError as e:
    logger.error(f"Could not import daily_planner_report: {e}")
    DailyPlannerReport = None
except Exception as e:
    logger.error(f"Unexpected error importing daily_planner_report: {e}")
    DailyPlannerReport = None


class DailyPlannerGUI(ttk.Frame):
    def __init__(self, master, db_path=None):
        super().__init__(master)
        
        try:
            if db_path is None:
                db_path = PAPER_APP_FOLDER / "prod_db.db"
            self.db_path = str(db_path)
            
            self.pdf_path = None
            self.grid(row=0, column=0, sticky="nsew", padx=15, pady=15)
            
            self.setup_ui()
            self.validate_dependencies()
            
            logger.info("GUI initialized successfully")
            
        except Exception as e:
            logger.error(f"Error initializing GUI: {e}")
            Messagebox.show_error(f"Failed to initialize GUI: {e}", "Initialization Error")

    def validate_dependencies(self):
        """Check if required files exist with error handling."""
        try:
            if not os.path.exists(self.db_path):
                msg = f"⚠️ Database not found: {self.db_path}"
                self.status_label.config(text=msg, foreground="orange")
                logger.warning(msg)
            else:
                logger.info(f"Database found: {self.db_path}")
            
            if DailyPlannerReport is None:
                msg = "⚠️ daily_planner_report module not found"
                self.status_label.config(text=msg, foreground="orange")
                logger.warning(msg)
                
        except Exception as e:
            logger.error(f"Error validating dependencies: {e}")

    def setup_ui(self):
        """Setup user interface with error handling."""
        try:
            self.columnconfigure(0, weight=1)
            self.rowconfigure(0, weight=1)

            # Header
            header = ttk.Label(self, text="📅 Daily Planner Generator", 
                             font=("Segoe UI", 14, "bold"))
            header.grid(row=0, column=0, columnspan=3, pady=(0, 15))

            # Date Frame
            frame = ttk.Labelframe(self, text="Select Date Range")
            frame.grid(row=1, column=0, sticky="n", padx=10, pady=10)
            frame.columnconfigure(1, weight=1)

            # Start Date
            ttk.Label(frame, text="Start Date:").grid(row=0, column=0, sticky=W, padx=5, pady=5)
            self.start_var = ttk.StringVar(value=datetime.today().strftime("%Y-%m-%d"))
            self.start_var.trace_add("write", self.sync_end_date)
            
            start_entry = ttk.Entry(frame, textvariable=self.start_var, width=15)
            start_entry.grid(row=0, column=1, padx=5, pady=5)
            start_entry.bind("<FocusOut>", lambda e: self.validate_date_entry(self.start_var))
            
            ttk.Button(frame, text="📅", width=3, 
                      command=lambda: self.open_calendar(self.start_var)).grid(row=0, column=2, padx=3)

            # End Date
            ttk.Label(frame, text="End Date:").grid(row=1, column=0, sticky=W, padx=5, pady=5)
            self.end_var = ttk.StringVar(value=datetime.today().strftime("%Y-%m-%d"))
            
            end_entry = ttk.Entry(frame, textvariable=self.end_var, width=15)
            end_entry.grid(row=1, column=1, padx=5, pady=5)
            end_entry.bind("<FocusOut>", lambda e: self.validate_date_entry(self.end_var))
            
            ttk.Button(frame, text="📅", width=3, 
                      command=lambda: self.open_calendar(self.end_var)).grid(row=1, column=2, padx=3)

            # Quick date selection
            quick_frame = ttk.Frame(frame)
            quick_frame.grid(row=2, column=0, columnspan=3, pady=10)
            
            ttk.Button(quick_frame, text="Today", width=10, bootstyle=SECONDARY,
                      command=lambda: self.set_quick_date("today")).pack(side=LEFT, padx=3)
            ttk.Button(quick_frame, text="Next 7 Days", width=12, bootstyle=SECONDARY,
                      command=lambda: self.set_quick_date("week")).pack(side=LEFT, padx=3)
            ttk.Button(quick_frame, text="This Month", width=12, bootstyle=SECONDARY,
                      command=lambda: self.set_quick_date("month")).pack(side=LEFT, padx=3)

            # Trend charts checkbox
            self.include_trends_var = ttk.BooleanVar(value=False)
            trend_check = ttk.Checkbutton(
                self,
                text="📊 Include 20-Day Process Trend Charts",
                variable=self.include_trends_var,
                bootstyle="success-round-toggle"
            )
            trend_check.grid(row=2, column=0, pady=5, sticky=W, padx=50)
            
            trend_info = ttk.Label(
                self,
                text="(Adds trend charts for Langston, United, Nozomi, Eterna, and Bobst)",
                font=("Segoe UI", 8),
                foreground="gray"
            )
            trend_info.grid(row=3, column=0, pady=0, sticky=W, padx=70)

            # Generate button
            ttk.Button(
                self,
                text="Generate Combined Planner PDF",
                bootstyle=SUCCESS,
                width=35,
                command=self.generate_combined_report
            ).grid(row=4, column=0, pady=15)

            # View button
            self.view_btn = ttk.Button(
                self,
                text="📄 View Last Generated PDF",
                bootstyle=INFO,
                width=35,
                command=self.open_pdf,
                state=DISABLED
            )
            self.view_btn.grid(row=5, column=0, pady=5)

            # Progress bar
            self.progress = ttk.Progressbar(
                self,
                mode='determinate',
                bootstyle=SUCCESS
            )
            self.progress.grid(row=6, column=0, pady=5, sticky="ew", padx=50)
            self.progress.grid_remove()

            # Status label
            self.status_label = ttk.Label(self, text="", font=("Segoe UI", 10))
            self.status_label.grid(row=7, column=0, pady=10)
            
            logger.info("UI setup complete")
            
        except Exception as e:
            logger.error(f"Error setting up UI: {e}")
            raise

    def validate_date_entry(self, date_var):
        """Validate and correct date format with error handling."""
        try:
            date_str = date_var.get().strip()
            datetime.strptime(date_str, "%Y-%m-%d")
            return True
            
        except ValueError:
            try:
                # Try common formats
                for fmt in ["%m/%d/%Y", "%d/%m/%Y", "%Y/%m/%d", "%m-%d-%Y"]:
                    try:
                        parsed = datetime.strptime(date_str, fmt)
                        date_var.set(parsed.strftime("%Y-%m-%d"))
                        logger.info(f"Auto-corrected date format: {date_str} -> {parsed.strftime('%Y-%m-%d')}")
                        return True
                    except ValueError:
                        continue
                
                # Reset to today if nothing works
                date_var.set(datetime.today().strftime("%Y-%m-%d"))
                logger.warning(f"Invalid date '{date_str}', reset to today")
                return False
                
            except Exception as e:
                logger.error(f"Error validating date: {e}")
                date_var.set(datetime.today().strftime("%Y-%m-%d"))
                return False

    def set_quick_date(self, period):
        """Set date range based on quick selection."""
        try:
            today = date.today()
            
            if period == "today":
                self.start_var.set(today.strftime("%Y-%m-%d"))
                self.end_var.set(today.strftime("%Y-%m-%d"))
                
            elif period == "week":
                self.start_var.set(today.strftime("%Y-%m-%d"))
                self.end_var.set((today + timedelta(days=6)).strftime("%Y-%m-%d"))
                
            elif period == "month":
                self.start_var.set(today.replace(day=1).strftime("%Y-%m-%d"))
                next_month = today.replace(day=28) + timedelta(days=4)
                last_day = next_month - timedelta(days=next_month.day)
                self.end_var.set(last_day.strftime("%Y-%m-%d"))
            
            logger.info(f"Quick date selected: {period}")
            
        except Exception as e:
            logger.error(f"Error setting quick date: {e}")
            Messagebox.show_error(f"Error setting date range: {e}", "Date Error")

    def sync_end_date(self, *args):
        """Auto-sync end date to match or follow start date."""
        try:
            start_d = datetime.strptime(self.start_var.get(), "%Y-%m-%d").date()
            end_d = datetime.strptime(self.end_var.get(), "%Y-%m-%d").date()
            
            if end_d < start_d:
                self.end_var.set(start_d.strftime("%Y-%m-%d"))
                
        except ValueError:
            pass
        except Exception as e:
            logger.error(f"Error syncing dates: {e}")

    def open_calendar(self, target_var):
        """Open calendar popup with error handling."""
        try:
            top = ttk.Toplevel(self)
            top.title("Select Date")
            top.geometry("480x380")
            top.resizable(False, False)
            
            # Center window
            top.update_idletasks()
            x = (top.winfo_screenwidth() // 2) - (480 // 2)
            y = (top.winfo_screenheight() // 2) - (380 // 2)
            top.geometry(f"480x380+{x}+{y}")

            self.cal_target = target_var
            
            # Start with current date
            try:
                current_date = datetime.strptime(target_var.get(), "%Y-%m-%d")
                self.cal_year = current_date.year
                self.cal_month = current_date.month
            except ValueError:
                self.cal_year = datetime.today().year
                self.cal_month = datetime.today().month

            # Header
            header_frame = ttk.Frame(top)
            header_frame.pack(pady=5)

            self.month_label = ttk.Label(
                header_frame,
                text=f"{month_name[self.cal_month]} {self.cal_year}",
                font=("Segoe UI", 12, "bold")
            )
            self.month_label.pack(side=TOP, pady=4)

            # Navigation buttons
            btn_frame = ttk.Frame(header_frame)
            btn_frame.pack()
            
            ttk.Button(btn_frame, text="◀ Prev", width=10, 
                      command=lambda: self.change_month(-1)).pack(side=LEFT, padx=5)
            ttk.Button(btn_frame, text="Today", width=10, bootstyle=INFO, 
                      command=lambda: self.jump_to_today()).pack(side=LEFT, padx=5)
            ttk.Button(btn_frame, text="Next ▶", width=10, 
                      command=lambda: self.change_month(1)).pack(side=LEFT, padx=5)

            self.days_frame = ttk.Frame(top)
            self.days_frame.pack(pady=10)
            self.render_calendar(self.cal_year, self.cal_month)
            self.calendar_window = top
            
            logger.info("Calendar opened")
            
        except Exception as e:
            logger.error(f"Error opening calendar: {e}")
            Messagebox.show_error(f"Could not open calendar: {e}", "Calendar Error")

    def jump_to_today(self):
        """Jump calendar to current month."""
        try:
            today = datetime.today()
            self.cal_year = today.year
            self.cal_month = today.month
            self.month_label.config(text=f"{month_name[self.cal_month]} {self.cal_year}")
            self.render_calendar(self.cal_year, self.cal_month)
        except Exception as e:
            logger.error(f"Error jumping to today: {e}")

    def render_calendar(self, year, month):
        """Render calendar grid."""
        try:
            for widget in self.days_frame.winfo_children():
                widget.destroy()

            weekdays = ["Su", "Mo", "Tu", "We", "Th", "Fr", "Sa"]
            for c, d in enumerate(weekdays):
                ttk.Label(self.days_frame, text=d, width=5, 
                         font=("Segoe UI", 10, "bold")).grid(row=0, column=c, pady=2)

            cal = Calendar(firstweekday=6)
            month_days = cal.monthdayscalendar(year, month)
            today = date.today()

            for r, week in enumerate(month_days, start=1):
                for c, day in enumerate(week):
                    if day == 0:
                        ttk.Label(self.days_frame, text="", width=5).grid(row=r, column=c)
                    else:
                        day_date = date(year, month, day)
                        is_today = day_date == today
                        is_weekend = day_date.weekday() in (5, 6)
                        style = INFO if is_today else (SECONDARY if is_weekend else LIGHT)
                        
                        ttk.Button(
                            self.days_frame,
                            text=str(day),
                            width=5,
                            bootstyle=style,
                            command=lambda d=day: self.pick_date(self.calendar_window, year, month, d)
                        ).grid(row=r, column=c, padx=4, pady=4)
                        
        except Exception as e:
            logger.error(f"Error rendering calendar: {e}")

    def change_month(self, offset):
        """Change calendar month."""
        try:
            self.cal_month += offset
            if self.cal_month < 1:
                self.cal_month = 12
                self.cal_year -= 1
            elif self.cal_month > 12:
                self.cal_month = 1
                self.cal_year += 1
            
            self.month_label.config(text=f"{month_name[self.cal_month]} {self.cal_year}")
            self.render_calendar(self.cal_year, self.cal_month)
            
        except Exception as e:
            logger.error(f"Error changing month: {e}")

    def pick_date(self, window, year, month, day):
        """Pick a date from calendar."""
        try:
            picked = date(year, month, day).strftime("%Y-%m-%d")
            self.cal_target.set(picked)
            window.destroy()
            logger.info(f"Date selected: {picked}")
        except Exception as e:
            logger.error(f"Error picking date: {e}")

    def generate_combined_report(self):
        """Generate combined PDF with comprehensive error handling."""
        if DailyPlannerReport is None:
            Messagebox.show_error(
                "Daily planner module not found. Cannot generate report.", 
                "Module Missing"
            )
            logger.error("DailyPlannerReport module not available")
            return
        
        start = self.start_var.get().strip()
        end = self.end_var.get().strip()

        # Validate dates
        try:
            start_d = datetime.strptime(start, "%Y-%m-%d").date()
            end_d = datetime.strptime(end, "%Y-%m-%d").date()
        except ValueError as e:
            msg = f"Invalid date format: {e}\nPlease use YYYY-MM-DD format."
            Messagebox.show_error(msg, "Invalid Date")
            logger.error(f"Date validation failed: {e}")
            return

        if end_d < start_d:
            Messagebox.show_error("End date cannot be before start date.", "Invalid Range")
            logger.error("End date before start date")
            return

        # Warn about large ranges
        days_count = (end_d - start_d).days + 1
        if days_count > 31:
            result = Messagebox.show_question(
                f"You're about to generate {days_count} daily planners. "
                f"This may take several minutes. Continue?",
                "Large Date Range"
            )
            if result != "Yes":
                logger.info("User cancelled large date range generation")
                return

        pdf_list = []
        failed_dates = []
        include_trends = self.include_trends_var.get()
        
        try:
            # Setup output directory
            try:
                output_dir = Path.home() / "Desktop"
                output_dir.mkdir(exist_ok=True)
            except PermissionError as e:
                raise PermissionError(f"Cannot access Desktop folder: {e}")
            except Exception as e:
                raise Exception(f"Error creating output directory: {e}")
            
            combined_pdf = output_dir / f"Daily_Planner_{start}_to_{end}.pdf"
            
            # Initialize PDF merger
            try:
                merger = PdfMerger()
            except Exception as e:
                raise Exception(f"Failed to initialize PDF merger: {e}")

            # Show progress
            self.progress.grid()
            self.progress['maximum'] = days_count
            self.progress['value'] = 0
            
            current = start_d
            day_num = 0
            
            logger.info(f"Starting generation for {days_count} days from {start} to {end}")
            
            # Generate each daily planner
            while current <= end_d:
                day_num += 1
                status_msg = f"Generating planner {day_num}/{days_count}: {current.strftime('%Y-%m-%d')}"
                if include_trends:
                    status_msg += " (with trend charts)"
                
                self.status_label.config(text=status_msg, foreground="blue")
                self.update_idletasks()
                
                try:
                    planner = DailyPlannerReport(
                        db_path=self.db_path,
                        planned_date=current.strftime("%Y-%m-%d"),
                        output_dir=str(output_dir),
                        include_trend_charts=include_trends
                    )
                    
                    try:
                        planner.generate()
                        logger.info(f"Generated planner for {current}")
                    except FileNotFoundError as e:
                        logger.error(f"Database not found for {current}: {e}")
                        failed_dates.append(current.strftime("%Y-%m-%d"))
                        current += timedelta(days=1)
                        self.progress['value'] = day_num
                        continue
                    except Exception as e:
                        logger.error(f"Generation failed for {current}: {e}")
                        failed_dates.append(current.strftime("%Y-%m-%d"))
                        current += timedelta(days=1)
                        self.progress['value'] = day_num
                        continue
                    
                    # Add to merger
                    if planner.pdf_path and os.path.exists(planner.pdf_path):
                        try:
                            merger.append(planner.pdf_path)
                            pdf_list.append(planner.pdf_path)
                            logger.info(f"Added to merger: {planner.pdf_path}")
                        except Exception as e:
                            logger.error(f"Failed to add PDF to merger for {current}: {e}")
                            failed_dates.append(current.strftime("%Y-%m-%d"))
                    else:
                        logger.warning(f"PDF not found for {current}")
                        failed_dates.append(current.strftime("%Y-%m-%d"))
                        
                except Exception as e:
                    logger.error(f"Unexpected error for {current}: {e}")
                    failed_dates.append(current.strftime("%Y-%m-%d"))
                
                current += timedelta(days=1)
                self.progress['value'] = day_num

            # Write combined PDF
            if pdf_list:
                try:
                    logger.info(f"Writing combined PDF with {len(pdf_list)} pages")
                    merger.write(str(combined_pdf))
                    merger.close()
                    logger.info(f"Combined PDF written: {combined_pdf}")
                    
                except PermissionError as e:
                    raise PermissionError(
                        f"Cannot write to {combined_pdf}. "
                        f"File may be open in another program: {e}"
                    )
                except Exception as e:
                    raise Exception(f"Failed to write combined PDF: {e}")
                
                self.pdf_path = str(combined_pdf)
                self.view_btn.config(state=NORMAL)
                
                success_msg = f"✅ Combined PDF ready: {combined_pdf.name}"
                if failed_dates:
                    success_msg += f"\n⚠️ Failed: {len(failed_dates)} date(s)"
                
                self.status_label.config(text=success_msg, foreground="green")
                
                msg = f"Combined planner created:\n{combined_pdf}\n\n"
                msg += f"Successfully generated: {len(pdf_list)} day(s)"
                
                if failed_dates:
                    msg += f"\n\nFailed to generate {len(failed_dates)} date(s):\n"
                    msg += ", ".join(failed_dates[:5])
                    if len(failed_dates) > 5:
                        msg += f"\n...and {len(failed_dates) - 5} more"
                
                Messagebox.show_info(msg, "Generation Complete")
                logger.info(f"Generation complete: {len(pdf_list)} successful, {len(failed_dates)} failed")
                
            else:
                raise Exception("No planners were successfully generated")

            # Clean up temporary files
            for f in pdf_list:
                try:
                    os.remove(f)
                    logger.info(f"Deleted temp file: {f}")
                except PermissionError as e:
                    logger.warning(f"Could not delete {f}: File in use - {e}")
                except FileNotFoundError:
                    logger.warning(f"File already deleted: {f}")
                except Exception as e:
                    logger.warning(f"Could not delete {f}: {e}")

        except FileNotFoundError as e:
            msg = f"File not found: {e}"
            Messagebox.show_error(msg, "File Error")
            self.status_label.config(text=f"❌ {msg}", foreground="red")
            self.view_btn.config(state=DISABLED)
            logger.error(msg)
            
        except PermissionError as e:
            msg = f"Permission denied: {e}"
            Messagebox.show_error(msg, "Permission Error")
            self.status_label.config(text=f"❌ {msg}", foreground="red")
            self.view_btn.config(state=DISABLED)
            logger.error(msg)
            
        except MemoryError as e:
            msg = f"Out of memory: {e}\nTry generating fewer days at once."
            Messagebox.show_error(msg, "Memory Error")
            self.status_label.config(text="❌ Out of memory", foreground="red")
            self.view_btn.config(state=DISABLED)
            logger.error(msg)
            
        except Exception as e:
            msg = f"Unexpected error: {e}"
            Messagebox.show_error(msg, "Generation Failed")
            self.status_label.config(text=f"❌ Error: {e}", foreground="red")
            self.view_btn.config(state=DISABLED)
            logger.error(msg, exc_info=True)
            
        finally:
            self.progress.grid_remove()
            logger.info("Generation process completed")

    def open_pdf(self):
        """Open the last generated PDF."""
        try:
            if self.pdf_path and os.path.exists(self.pdf_path):
                webbrowser.open(self.pdf_path)
                logger.info(f"Opened PDF: {self.pdf_path}")
            else:
                Messagebox.show_warning("No file found to open.", "Missing File")
                logger.warning("PDF file not found for opening")
                
        except Exception as e:
            logger.error(f"Error opening PDF: {e}")
            Messagebox.show_error(f"Could not open PDF: {e}", "Error")


def main():
    """Main entry point with error handling."""
    try:
        root = ttk.Window(themename="flatly")
        root.title("📅 Daily Planner Generator")
        root.geometry("550x600")
        root.rowconfigure(0, weight=1)
        root.columnconfigure(0, weight=1)
        
        # Center window
        root.update_idletasks()
        x = (root.winfo_screenwidth() // 2) - (550 // 2)
        y = (root.winfo_screenheight() // 2) - (600 // 2)
        root.geometry(f"550x600+{x}+{y}")

        # Database path
        db_path = PAPER_APP_FOLDER / "prod_db.db"
        
        app = DailyPlannerGUI(root, db_path=str(db_path))
        
        logger.info("Application started")
        root.mainloop()
        logger.info("Application closed")
        
    except Exception as e:
        logger.error(f"Fatal error in main: {e}", exc_info=True)
        try:
            Messagebox.show_error(
                f"Application failed to start: {e}\n\nCheck daily_planner_gui.log for details",
                "Fatal Error"
            )
        except:
            print(f"FATAL ERROR: {e}")
            print("Check daily_planner_gui.log for details")


if __name__ == "__main__":
    main()