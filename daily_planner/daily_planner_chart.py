import sqlite3
import pandas as pd
from datetime import datetime, timedelta
import matplotlib.pyplot as plt
from matplotlib.ticker import StrMethodFormatter


class ProcessTrendChart:
    """
    Generates bar charts for selected processes for 20 working days.
    Includes comprehensive exception handling for production use.
    """
    def __init__(self, db_path, start_date=None):
        if not db_path:
            raise ValueError("Database path cannot be empty")
        
        self.db_path = db_path
        self.start_date = start_date or datetime.today().strftime("%Y-%m-%d")
        
        try:
            datetime.strptime(self.start_date, "%Y-%m-%d")
        except ValueError as e:
            raise ValueError(f"Invalid date format: {self.start_date}. Expected YYYY-MM-DD") from e
        
        self.conn = None
        self.holiday_dates = set()
        self.target_processes = ["Langston%", "United%", "Nozomi%", "Eterna%", "Bobst%"]
        self.df = pd.DataFrame()
        self.processes = []
        self.days = []

    def connect(self):
        """Establish database connection with error handling."""
        try:
            self.conn = sqlite3.connect(self.db_path)
        except sqlite3.OperationalError as e:
            raise sqlite3.OperationalError(f"Cannot open database: {e}")
        except sqlite3.Error as e:
            raise sqlite3.Error(f"Database connection failed: {e}")
        except Exception as e:
            raise Exception(f"Unexpected error connecting to database: {e}")

    def load_holidays(self):
        """Load holidays with error handling."""
        try:
            df = pd.read_sql_query("SELECT date FROM holiday", self.conn)
            self.holiday_dates = set(df["date"].tolist())
            print(f"✅ Loaded {len(self.holiday_dates)} holidays")
        except sqlite3.OperationalError as e:
            print(f"⚠️  Holiday table not found: {e}. Proceeding without holidays.")
            self.holiday_dates = set()
        except sqlite3.Error as e:
            print(f"⚠️  Database error loading holidays: {e}. Proceeding without holidays.")
            self.holiday_dates = set()
        except pd.errors.DatabaseError as e:
            print(f"⚠️  Pandas error loading holidays: {e}. Proceeding without holidays.")
            self.holiday_dates = set()
        except KeyError as e:
            print(f"⚠️  Column 'date' not found in holiday table: {e}. Proceeding without holidays.")
            self.holiday_dates = set()
        except Exception as e:
            print(f"⚠️  Unexpected error loading holidays: {e}. Proceeding without holidays.")
            self.holiday_dates = set()

    def next_working_day(self, date_obj):
        """Compute next working day with safeguard against infinite loops."""
        try:
            next_day = date_obj + timedelta(days=1)
            max_iterations = 30
            iterations = 0
            
            while (next_day.weekday() >= 5 or 
                   next_day.strftime("%Y-%m-%d") in self.holiday_dates):
                next_day += timedelta(days=1)
                iterations += 1
                if iterations >= max_iterations:
                    print(f"⚠️  Warning: Could not find working day within {max_iterations} iterations")
                    break
            
            return next_day
        except Exception as e:
            raise Exception(f"Error calculating next working day: {e}")

    def get_next_20_working_days(self):
        """Get next 20 working days with error handling."""
        try:
            days = []
            current = datetime.strptime(self.start_date, "%Y-%m-%d").date()
            
            for i in range(20):
                if i > 0:
                    current = self.next_working_day(current)
                days.append(current.strftime("%Y-%m-%d"))
            
            return days
        except ValueError as e:
            raise ValueError(f"Invalid start date: {e}")
        except Exception as e:
            raise Exception(f"Error generating working days: {e}")

    def fetch_data(self):
        """Fetch MSF data with comprehensive error handling."""
        try:
            self.days = self.get_next_20_working_days()
        except Exception as e:
            raise Exception(f"Failed to generate working days: {e}")

        # Build WHERE clause
        try:
            conditions = [f"r.process_nme LIKE '{p}'" if "%" in p else f"r.process_nme = '{p}'"
                          for p in self.target_processes]
            where_clause = " OR ".join(conditions)
        except Exception as e:
            raise Exception(f"Error building query conditions: {e}")

        # Get process names
        try:
            query = f"""
                SELECT DISTINCT r.process_nme AS process
                FROM order_routing r
                WHERE {where_clause}
                ORDER BY r.process_nme
            """
            df_process = pd.read_sql_query(query, self.conn)
            self.processes = df_process['process'].tolist()
            if not self.processes:
                print("⚠️  No matching processes found in database")
                self.df = pd.DataFrame()
                return
                
        except sqlite3.OperationalError as e:
            raise sqlite3.OperationalError(f"Table 'order_routing' not found: {e}")
        except sqlite3.Error as e:
            raise sqlite3.Error(f"Database error fetching processes: {e}")
        except KeyError as e:
            raise KeyError(f"Required column missing: {e}")
        except Exception as e:
            raise Exception(f"Error fetching process list: {e}")

        # Fetch data for each process and date
        data = []
        for process in self.processes:
            row = []
            for d in self.days:
                try:
                    q = f"""
                        SELECT SUM(r.msf) AS total_msf
                        FROM order_routing r
                        WHERE date(substr(r.schedule_dte,1,10)) = '{d}'
                          AND r.process_nme = '{process}'
                    """
                    df_val = pd.read_sql_query(q, self.conn)
                    
                    if df_val.empty or df_val["total_msf"].iloc[0] is None:
                        row.append(0)
                    else:
                        msf_value = df_val["total_msf"].iloc[0]
                        row.append(int(msf_value) if msf_value else 0)
                        
                except sqlite3.Error as e:
                    print(f"⚠️  Database error for {process} on {d}: {e}. Using 0.")
                    row.append(0)
                except (KeyError, IndexError) as e:
                    print(f"⚠️  Data error for {process} on {d}: {e}. Using 0.")
                    row.append(0)
                except ValueError as e:
                    print(f"⚠️  Value conversion error for {process} on {d}: {e}. Using 0.")
                    row.append(0)
                except Exception as e:
                    print(f"⚠️  Unexpected error for {process} on {d}: {e}. Using 0.")
                    row.append(0)
            
            data.append(row)
        
        try:
            self.df = pd.DataFrame(data, index=self.processes, columns=self.days)
        except Exception as e:
            raise Exception(f"Error creating DataFrame: {e}")

    def build_charts(self):
        """Build matplotlib charts with error handling."""
        charts = {}
        
        if self.df.empty:
            print("⚠️  No data available to build charts")
            return charts
        
        print(f"Building charts for {len(self.df.index)} processes...")
        
        for process in self.df.index:
            try:
                fig, ax = plt.subplots(figsize=(12, 5))
                
                try:
                    ax.bar(self.df.columns, self.df.loc[process], color="#4CAF50")
                except Exception as e:
                    print(f"⚠️  Error creating bars for {process}: {e}")
                    plt.close(fig)
                    continue
                
                try:
                    ax.set_title(f"{process} – 20-Day MSF Trend", fontsize=14)
                    ax.set_xlabel("Date")
                    ax.set_ylabel("Total MSF")
                    plt.setp(ax.get_xticklabels(), rotation=45, ha='right')
                    ax.yaxis.set_major_formatter(StrMethodFormatter("{x:,.0f}"))
                except Exception as e:
                    print(f"⚠️  Error formatting chart for {process}: {e}")
                
                # Add value labels
                try:
                    for i, val in enumerate(self.df.loc[process]):
                        ax.text(i, val + 0.5, f"{val:,}", ha='center', va='bottom', fontsize=8)
                except Exception as e:
                    print(f"⚠️  Error adding labels for {process}: {e}")
                
                try:
                    plt.tight_layout()
                except Exception as e:
                    print(f"⚠️  Error applying tight_layout for {process}: {e}")
                
                charts[process] = fig
                print(f"✅ Created chart for {process}")
                
            except MemoryError as e:
                print(f"❌ Memory error creating chart for {process}: {e}")
                continue
            except Exception as e:
                print(f"❌ Failed to create chart for {process}: {e}")
                if 'fig' in locals():
                    try:
                        plt.close(fig)
                    except:
                        pass
                continue
        
        print(f"✅ Successfully built {len(charts)} charts")
        return charts

    def generate(self):
        """Full workflow with comprehensive exception handling."""
        try:
            try:
                self.connect()
            except Exception as e:
                raise Exception(f"Connection failed: {e}")
            
            try:
                self.load_holidays()
            except Exception as e:
                print(f"⚠️  Warning during holiday load: {e}. Continuing...")
            
            try:
                self.fetch_data()
            except Exception as e:
                raise Exception(f"Data fetch failed: {e}")
            
            try:
                charts = self.build_charts()
                
                if charts:
                    print(f"✅ Generated {len(charts)} in-memory charts for 20-day trends.")
                else:
                    print("⚠️  No charts were generated")
                
                return charts
                
            except Exception as e:
                raise Exception(f"Chart building failed: {e}")
                
        except FileNotFoundError as e:
            print(f"❌ Database file not found: {e}")
            raise
        except sqlite3.Error as e:
            print(f"❌ SQLite error: {e}")
            raise
        except ImportError as e:
            print(f"❌ Required module not found: {e}")
            raise
        except MemoryError as e:
            print(f"❌ Memory error: {e}")
            raise
        except Exception as e:
            print(f"❌ Chart generation failed: {e}")
            raise
        finally:
            if self.conn:
                try:
                    self.conn.close()
                except Exception as e:
                    print(f"⚠️  Error closing connection: {e}")


# Example usage with exception handling
if __name__ == "__main__":
    try:
        chart_generator = ProcessTrendChart(
            db_path="prod_db.db",
            start_date="2025-11-11"
        )
        charts = chart_generator.generate()
        
        if charts:
            for process_name, fig in charts.items():
                print(f"Chart created for: {process_name}")
                # fig.savefig(f"{process_name}_chart.png")
        else:
            print("No charts generated")
            
    except FileNotFoundError as e:
        print(f"Database file not found: {e}")
    except sqlite3.Error as e:
        print(f"Database error: {e}")
    except ValueError as e:
        print(f"Invalid input: {e}")
    except Exception as e:
        print(f"Error: {e}")