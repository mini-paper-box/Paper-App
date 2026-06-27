import pyodbc
import sys
import pandas as pd
import ttkbootstrap as tb
from ttkbootstrap.constants import *
from tkinter import messagebox
from datetime import datetime, timedelta
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure

class AutoScheduler:
    def __init__(self, server, database):
        self.conn_str = (
            "DRIVER={ODBC Driver 18 for SQL Server};"
            f"SERVER={server}; DATABASE={database};"
            "Trusted_Connection=yes; Encrypt=yes; TrustServerCertificate=yes;"
        )
        self.conn = None

    def connect(self):
        if self.conn is None: 
            self.conn = pyodbc.connect(self.conn_str)
        return self.conn

    def close(self):
        if self.conn:
            self.conn.close()
            self.conn = None

    def fetch_docket_history(self, docket_id):
        """Pulls historical data from the track table for the specific docket."""
        query = """
        SELECT TOP 10
            CAST(t.start_date AS DATE) as [Date],
            t.process_nme as Process,
            t.setup_min as [Setup],
            t.run_min as [Run],
            t.process_qty as [Qty],
            CAST(t.process_qty / NULLIF(t.run_min, 0) AS DECIMAL(18,1)) as [Speed],
            CAST(t.process_qty * (d.sqfpm / 1000.0) AS DECIMAL(18,2)) as [MSF]
        FROM track t
        JOIN docket d ON d.docket_id = t.docket_id
        WHERE t.docket_id = ? AND t.run_min > 0
        ORDER BY t.start_date DESC
        """
        return pd.read_sql(query, self.connect(), params=[docket_id])

    def fetch_capacity_matrix(self):
        query = """
        SELECT t.process_id, 
            SUM(t.process_qty * (d.sqfpm / 1000.0)) as daily_msf
        FROM track t 
        JOIN docket d ON d.docket_id = t.docket_id
        WHERE t.run_min > 0 AND t.start_date >= DATEADD(YEAR, -1, GETDATE())
        GROUP BY t.process_id, CAST(t.start_date AS DATE)
        """
        raw_hist = pd.read_sql(query, self.connect())
        
        clean_data = []
        for pid in raw_hist['process_id'].unique():
            proc_data = raw_hist[raw_hist['process_id'] == pid]
            
            # 1. The 'Hero Day' - Absolute Max
            absolute_max = proc_data['daily_msf'].max()
            
            # 2. The Anchor - 75% of the record
            anchor = absolute_max * 0.60 
            
            # 3. Parameters
            penalty_per_setup = 0.07  # 7% flat tax
            min_capacity_floor = 0.30 # 30% hard floor

            for jc in range(1, 16):
                if jc == 1:
                    current_cap = anchor
                else:
                    # Linear subtraction: Anchor - (Anchor * 7% * number of extra setups)
                    tax = anchor * (penalty_per_setup * (jc - 1))
                    calculated_cap = anchor - tax
                    
                    # Apply the floor so we don't plan for 0 capacity
                    current_cap = max(calculated_cap, anchor * min_capacity_floor)
                
                clean_data.append({
                    'process_id': pid, 
                    'job_count': jc, 
                    'p80_capacity': current_cap
                })

        return pd.DataFrame(clean_data)

    def fetch_docket_routing(self, docket_id, run_qty):
        query = """
        WITH RankedRouting AS (
            SELECT 
                dr.sequence AS seq_order, 
                dr.process_id, 
                dr.routing_dsc AS process_name,
                ? * (d.sqfpm / 1000.0) AS run_sqft,
                ROW_NUMBER() OVER (PARTITION BY dr.sequence ORDER BY dr.process_id) as route_rank
            FROM docket d
            JOIN docket_routing dr ON dr.docket_id = CASE 
                WHEN d.linked_docket_id > 0 THEN d.linked_docket_id ELSE d.docket_id END
            WHERE d.docket_id = ?
        )
        SELECT seq_order, process_id, process_name, run_sqft
        FROM RankedRouting
        WHERE route_rank = 1
        ORDER BY seq_order;
        """
        try:
            conn = self.connect()
            return pd.read_sql(query, conn, params=[run_qty, docket_id])
        except Exception as e:
            messagebox.showerror("Query Error", f"Failed to retrieve routing:\n{str(e)}")
            return pd.DataFrame()

    def fetch_booked_and_holidays(self, lookahead=60):
        booked_query = """
            SELECT process_id, CAST(schedule_dte AS DATE) AS schedule_date,
                   SUM(msf) AS booked_sqft, COUNT(*) AS booked_jobs
            FROM schedule_view
            WHERE schedule_dte >= CAST(GETDATE() AS DATE)
              AND schedule_dte < DATEADD(DAY, ?, CAST(GETDATE() AS DATE))
            GROUP BY process_id, CAST(schedule_dte AS DATE)
        """
        hol_query = "SELECT holiday_dte FROM company_holidays"
        return pd.read_sql(booked_query, self.connect(), params=[lookahead * 2]), \
               pd.to_datetime(pd.read_sql(hol_query, self.connect())["holiday_dte"])

class SchedulerGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Production Demo")
        self.root.geometry("1350x900")
        self.root.state("zoomed")
        self.sched = AutoScheduler("wbdbserver", "flute_data")
        self.process_data = []
        self.booked_df = None
        self.current_idx = 0
        self.day_tier_usage = {}  # Track which tier was used each day
        self.scheduled_additions = {}  # Track scheduled job additions per day

        self.main = tb.Frame(root, padding=10)
        self.main.pack(fill=BOTH, expand=YES)

        # --- TOP PANELS (Docket, Style, History) ---
        top_row = tb.Frame(self.main)
        top_row.pack(fill=X, side=TOP, pady=5)

        # 1 Left. Docket
        f_param = tb.Labelframe(top_row, text=" Docket ", padding=10, bootstyle=INFO)
        f_param.pack(side=LEFT, fill=BOTH, expand=YES, padx=5)
        tb.Label(f_param, text="Docket ID:").grid(row=0, column=0, sticky=W)
        self.ent_docket = tb.Entry(f_param)
        self.ent_docket.insert(0, "170024")
        self.ent_docket.grid(row=0, column=1, sticky=EW, padx=5)
        
        tb.Label(f_param, text="Run Qty:").grid(row=1, column=0, sticky=W)
        self.ent_qty = tb.Entry(f_param)
        self.ent_qty.insert(0, "3000")
        self.ent_qty.grid(row=1, column=1, sticky=EW, padx=5, pady=5)
        
        tb.Label(f_param, text="Lead Days:").grid(row=2, column=0, sticky=W)
        self.ent_lead = tb.Entry(f_param)
        self.ent_lead.insert(0, "4")
        self.ent_lead.grid(row=2, column=1, sticky=EW, padx=5, pady=5)
        
        self.btn_run = tb.Button(f_param, text="Generate Schedule", bootstyle=SUCCESS, command=self.run_scheduler)
        self.btn_run.grid(row=3, column=1, sticky=E)

        # 2 Middle. STYLE (Dynamic stats based on docket)
        f_style = tb.Labelframe(top_row, text=" Performance ", padding=10, bootstyle=SECONDARY)
        f_style.pack(side=LEFT, fill=BOTH, expand=YES, padx=5)
        self.lbl_style_stats = tb.Label(f_style, text="Avg Speed: --\nAvg Setup: --\nAggression: 80 Percentile", justify=LEFT, font=("Consolas", 9))
        self.lbl_style_stats.pack(anchor=W)

        # 3 Right. HISTORY TABLE
        f_hist = tb.Labelframe(top_row, text=" Docket History ", padding=5, bootstyle=WARNING)
        f_hist.pack(side=LEFT, fill=BOTH, expand=YES, padx=5)
        self.hist_tree = tb.Treeview(f_hist, columns=("d","s","sp","m"), show="headings", height=4)
        for c, h in [("d","Date"),("s","Setup Min"),("sp","Qty/Min"),("m","Processed MSF")]:
            self.hist_tree.heading(c, text=h)
            self.hist_tree.column(c, width=70, anchor=CENTER)
        self.hist_tree.pack(fill=BOTH, expand=YES)
        
        # Store matrix for display
        self.capacity_matrix = None

        # --- TREEVIEW (Schedule Results) ---
        tb.Label(self.main, text="Double-click any row to view process chart", 
                font=("Helvetica", 9, "italic"), foreground='#adb5bd').pack(anchor=W, pady=(5,0))
        
        self.tree = tb.Treeview(self.main, columns=("seq","proc","sqft","start","end","days"), 
                                show="headings", height=8, bootstyle=PRIMARY)
        for c, h, w in [("seq","Routing Sequence",50), ("proc","Process Name",250), ("sqft","Req SqFt",100), 
                        ("start","Start Date",100), ("end","End Date",100), ("days","Days",60)]:
            self.tree.heading(c, text=h)
            self.tree.column(c, anchor=CENTER if c != "proc" else W, width=w)
        self.tree.pack(fill=X, pady=5)
        
        # Bind double-click event, switch chart
        self.tree.bind("<Double-1>", self.on_tree_double_click)

        # --- CHART NAVIGATION & DISPLAY ---
        chart_nav = tb.Frame(self.main)
        chart_nav.pack(fill=X)
        
        self.btn_prev = tb.Button(chart_nav, text="◀ Previous", bootstyle="secondary-outline", 
                                   command=lambda: self.nav(-1), state='disabled', width=12)
        self.btn_prev.pack(side=LEFT, padx=5)
        
        self.lbl_chart = tb.Label(chart_nav, text="Process Capacity View", 
                                  font=("Helvetica", 14, "bold"))
        self.lbl_chart.pack(side=LEFT, expand=YES)
        
        self.btn_next = tb.Button(chart_nav, text="Next ▶", bootstyle="secondary-outline", 
                                   command=lambda: self.nav(1), state='disabled', width=12)
        self.btn_next.pack(side=RIGHT, padx=5)

        # Chart Frame
        chart_frame = tb.Labelframe(self.main, text="", padding=10, bootstyle=INFO)
        chart_frame.pack(fill=BOTH, expand=YES, pady=(5,0))

        self.fig = Figure(figsize=(10, 3.5), dpi=100, facecolor='#2b3e50')
        self.ax = self.fig.add_subplot(111)
        self.ax.set_facecolor('#2b3e50')
        
        # Initial empty state
        self.ax.text(0.5, 0.5, 'Run scheduler to view capacity data', 
                    ha='center', va='center', transform=self.ax.transAxes,
                    color='#adb5bd', fontsize=12)
        self.ax.set_xticks([])
        self.ax.set_yticks([])
        
        self.canvas = FigureCanvasTkAgg(self.fig, master=chart_frame)
        self.canvas.draw()
        self.canvas.get_tk_widget().pack(fill=BOTH, expand=YES)

    def on_tree_double_click(self, event):
        """Handle double-click on treeview to show process chart"""
        selection = self.tree.selection()
        if not selection or not self.process_data:
            return
        
        # Get the clicked item's sequence number
        item = self.tree.item(selection[0])
        seq_num = item['values'][0]
        
        # Find matching process index
        for idx, proc in enumerate(self.process_data):
            if proc['seq'] == seq_num:
                self.current_idx = idx
                self.update_chart()
                break

    def nav(self, delta):
        if not self.process_data: 
            return
        self.current_idx = (self.current_idx + delta) % len(self.process_data)
        self.update_chart()

    def update_chart(self):
        """High-detail bar chart with 25-day view - stacked bars for scheduled additions"""
        proc = self.process_data[self.current_idx]
        
        # Update navigation buttons
        self.btn_prev.config(state='normal' if self.current_idx > 0 else 'disabled')
        self.btn_next.config(state='normal' if self.current_idx < len(self.process_data) - 1 else 'disabled')
        
        # Update label
        self.lbl_chart.config(text=f"{proc['name']} ({self.current_idx + 1}/{len(self.process_data)})")
        
        # Update style panel with matrix data for this process
        if self.capacity_matrix is not None:
            proc_matrix = self.capacity_matrix[self.capacity_matrix['process_id'] == proc['id']].sort_values('job_count')
            if not proc_matrix.empty:
                matrix_text = "Capacity tier:\n"
                
                # Get tier usage for this process
                proc_tier_usage = self.day_tier_usage.get(proc['id'], {})
                
                for _, row in proc_matrix.head(8).iterrows():
                    job_count = int(row['job_count'])
                    capacity = row['p80_capacity']
                    
                    # Check if this tier was used
                    tier_used = any(tier == job_count for tier in proc_tier_usage.values())
                    
                    # Only display what tier was used
                    if tier_used:
                        matrix_text += f"► {job_count} jobs: {capacity:,.0f} sqft ◄\n"
                    else:
                        matrix_text += f"  {job_count} jobs: {capacity:,.0f} sqft\n"
                        
                
                # Get historical avg
                hist_df = self.sched.fetch_docket_history(self.ent_docket.get())
                if not hist_df.empty:
                    avg_speed = hist_df['Speed'].mean()
                    avg_setup = hist_df['Setup'].mean()
                    full_text = f"Avg Speed: {avg_speed:.1f} Qty/Min\nAvg Setup: {avg_setup:.1f} min\n\n{matrix_text}"
                else:
                    full_text = f"Aggression: 80 Percentile\n\n{matrix_text}"
                
                self.lbl_style_stats.config(text=full_text)
        
        self.ax.clear()
        self.ax.set_facecolor('#2b3e50')
        
        today = datetime.now().date()
        dates = [today + timedelta(days=i) for i in range(25)]
        
        # Load booked data for this specific process
        daily_booked = pd.Series(0, index=dates)
        daily_jobs = pd.Series(0, index=dates)
        daily_scheduled = pd.Series(0, index=dates) 
        
        if self.booked_df is not None and not self.booked_df.empty:
            p_booked = self.booked_df[self.booked_df['process_id'] == proc['id']]
            for _, row in p_booked.iterrows():
                if row['schedule_date'] in daily_booked.index:
                    daily_booked[row['schedule_date']] = row['booked_sqft']
                    daily_jobs[row['schedule_date']] = row['booked_jobs']
        
        # Get scheduled additions for this process
        proc_scheduled = self.scheduled_additions.get(proc['id'], {})
        for date, sqft in proc_scheduled.items():
            if date in daily_scheduled.index:
                daily_scheduled[date] = sqft

        x = range(len(dates))
        
        # Create stacked bars: booked (blue) at bottom, scheduled (red) on top
        bars_booked = self.ax.bar(x, daily_booked.values, color='#3498db', alpha=0.7, 
                                   edgecolor='#2980b9', linewidth=1.5, label='Existing Bookings')
        
        bars_scheduled = self.ax.bar(x, daily_scheduled.values, bottom=daily_booked.values,
                                      color='#e74c3c', alpha=0.9, edgecolor='#c0392b', 
                                      linewidth=1.5, label='This Job (Scheduled)')
        
        # Add required capacity line
        if proc['start'] and proc['end']:
            required_sqft = proc['sqft']
            days_span = (proc['end'] - proc['start']).days + 1
            avg_per_day = required_sqft / days_span if days_span > 0 else 0
            
            schedule_indices = [i for i, d in enumerate(dates) if proc['start'] <= d <= proc['end']]
            if schedule_indices:
                self.ax.hlines(avg_per_day, min(schedule_indices) - 0.4, max(schedule_indices) + 0.4,
                             colors='#f39c12', linewidth=2, linestyle='--', 
                             label=f'Required Avg: {avg_per_day:,.0f} sqft/day')

        # Add text labels on bars
        proc_tier_usage = self.day_tier_usage.get(proc['id'], {})
        
        for i, (d, booked, scheduled, jobs) in enumerate(zip(dates, daily_booked.values, daily_scheduled.values, daily_jobs.values)):
            total = booked + scheduled
            if total > 0:
                # Get tier used for this day if it was scheduled
                tier_used = proc_tier_usage.get(d)
                
                # Show total sqft/tier on top of stacked bar
                label_text = f'{total:,.0f}'
                if tier_used:
                    label_text += f' [T{tier_used}]'
                
                self.ax.text(i, total + (self.ax.get_ylim()[1] * 0.02), 
                           label_text, ha='center', va='bottom', 
                           color='#f39c12' if tier_used else '#adb5bd', 
                           fontsize=7, fontweight='bold')
                
                # Show job count inside bar (on booked portion if exists, otherwise on scheduled)
                if jobs > 0 or scheduled > 0:
                    y_pos = booked / 2 if booked > 0 else booked + (scheduled / 2)
                    display_jobs = jobs + (1 if scheduled > 0 else 0)
                    self.ax.text(i, y_pos, 
                               f'{int(display_jobs)} \njobs', ha='center', va='center', 
                               color='white', fontsize=7, fontweight='bold',
                               bbox=dict(boxstyle='round,pad=0.3', facecolor='#34495e', 
                                       edgecolor='none', alpha=0.8))

        # Formatting
        self.ax.set_xlabel('Date', color='#adb5bd', fontsize=10, fontweight='bold')
        self.ax.set_ylabel('Capacity (SqFt)', color='#adb5bd', fontsize=10, fontweight='bold')
        self.ax.set_xticks(x)
        self.ax.set_xticklabels([d.strftime('%m/%d') for d in dates], 
                               rotation=45, ha='right', color='#adb5bd', fontsize=8)
        self.ax.tick_params(colors='#adb5bd')
        
        # Grid
        self.ax.grid(True, alpha=0.2, color='#adb5bd', linestyle='--', linewidth=0.5, axis='y')
        self.ax.set_axisbelow(True)
        
        # Legend
        self.ax.legend(loc='upper left', facecolor='#2b3e50', edgecolor='#adb5bd', 
                      labelcolor='#adb5bd', fontsize=9, framealpha=0.9)
        
        # Summary stats
        total_booked = daily_booked.sum()
        total_scheduled = daily_scheduled.sum()
        total_jobs = daily_jobs.sum()
        summary = f"Existing: {total_booked:,.0f} sqft ({int(total_jobs)} jobs) | Scheduled: {total_scheduled:,.0f} sqft | Required: {proc['sqft']:,.0f} sqft"
        self.ax.text(0.98, 0.98, summary, transform=self.ax.transAxes,
                    fontsize=8, color='#adb5bd', ha='right', va='top',
                    bbox=dict(boxstyle='round', facecolor='#2b3e50', edgecolor='#adb5bd', alpha=0.8))
        
        # Style
        self.ax.spines['bottom'].set_color('#adb5bd')
        self.ax.spines['left'].set_color('#adb5bd')
        self.ax.spines['top'].set_visible(False)
        self.ax.spines['right'].set_visible(False)
        
        # Add some padding at top for labels
        y_max = self.ax.get_ylim()[1]
        self.ax.set_ylim(0, y_max * 1.15)
        
        self.fig.tight_layout()
        self.canvas.draw()

    def run_scheduler(self):
        self.btn_run.config(state='disabled', text="Processing...")
        self.root.update()
        
        try:
            d_id = int(self.ent_docket.get())
            qty = int(self.ent_qty.get())
            lead_days = int(self.ent_lead.get())
            
            # Reset tracking
            self.day_tier_usage = {}
            self.scheduled_additions = {}
            
            # 1. Update History & Style Stats
            hist_df = self.sched.fetch_docket_history(d_id)
            for item in self.hist_tree.get_children(): 
                self.hist_tree.delete(item)
            
            if not hist_df.empty:
                avg_speed = hist_df['Speed'].mean()
                avg_setup = hist_df['Setup'].mean()
                self.lbl_style_stats.config(text=f"Avg Speed: {avg_speed:.1f} Qty/Min\nAvg Setup: {avg_setup:.1f} min\nAggression: 80 Percentile")
                for _, r in hist_df.iterrows():
                    self.hist_tree.insert("", END, values=(r['Date'], r['Setup'], r['Speed'], f"{r['MSF']:.1f}"))

            # 2. Fetch routing and capacity data
            routing = self.sched.fetch_docket_routing(d_id, qty)
            
            if routing.empty:
                messagebox.showwarning("Warning", f"No routing found for Docket {d_id}")
                return
            
            matrix = self.sched.fetch_capacity_matrix()
            self.capacity_matrix = matrix
            self.booked_df, holidays = self.sched.fetch_booked_and_holidays()
            h_set = set(holidays.dt.date) if not holidays.empty else set()

            # Generate workdays
            workdays = []
            curr = datetime.now().date() + timedelta(days=lead_days)
            while len(workdays) < 60:
                if curr.weekday() < 5 and curr not in h_set: 
                    workdays.append(curr)
                curr += timedelta(days=1)

            # 3. Build schedule
            self.process_data = []
            for item in self.tree.get_children(): 
                self.tree.delete(item)
            
            prev_end = None
            schedule_feasible = True
            
            for _, prow in routing.iterrows():
                start, end, cum_sqft, days_count = None, None, 0, 0
                pid = prow['process_id']
                required_sqft = prow['run_sqft']
                
                # Initialize tracking
                if pid not in self.day_tier_usage:
                    self.day_tier_usage[pid] = {}
                if pid not in self.scheduled_additions:
                    self.scheduled_additions[pid] = {}
                
                # Bypass certain processes
                if pid in ("40","237","238","239","240","241","242","245","193","243","235"):
                    if prev_end:
                        start = prev_end + timedelta(days=1)
                        while start.weekday() >= 5 or start in h_set:
                            start += timedelta(days=1)
                    else:
                        start = datetime.now().date() + timedelta(days=lead_days)
                    end = start
                    days_count = 1
                else:
                    for d in workdays:
                        if prev_end and d <= prev_end: 
                            continue
                        
                        day_load = self.booked_df[
                            (self.booked_df['process_id'] == pid) & 
                            (self.booked_df['schedule_date'] == d)
                        ]
                        booked_jobs = int(day_load['booked_jobs'].iloc[0]) if not day_load.empty else 0
                        booked_msf = float(day_load['booked_sqft'].iloc[0]) if not day_load.empty else 0.0
                        
                        target_jobs = booked_jobs + 1
                        cap_match = matrix[
                            (matrix['process_id'] == pid) & 
                            (matrix['job_count'] == target_jobs)
                        ]
                        
                        if cap_match.empty:
                            process_caps = matrix[matrix['process_id'] == pid]
                            p80_cap = process_caps['p80_capacity'].median() if not process_caps.empty else 1000
                        else:
                            p80_cap = cap_match['p80_capacity'].iloc[0]
                        
                        avail = max(p80_cap - booked_msf, 0)
                        
                        if avail < 100: 
                            continue
                        
                        if start is None: 
                            start = d
                        cum_sqft += avail
                        days_count += 1
                        
                        # Track tier and scheduled addition
                        self.day_tier_usage[pid][d] = target_jobs
                        self.scheduled_additions[pid][d] = avail
                        
                        if cum_sqft >= required_sqft:
                            end = d
                            break
                
                if end is None:
                    schedule_feasible = False
                
                prev_end = end
                
                self.process_data.append({
                    'seq': prow['seq_order'], 
                    'id': pid, 
                    'name': prow['process_name'],
                    'sqft': required_sqft,
                    'start': start, 
                    'end': end
                })
                
                start_str = start.strftime("%m/%d/%Y") if start else "N/A"
                end_str = end.strftime("%m/%d/%Y") if end else "N/A"
                
                item_id = self.tree.insert("", END, values=(
                    prow['seq_order'], 
                    prow['process_name'], 
                    f"{required_sqft:,.0f}", 
                    start_str,
                    end_str,
                    days_count if days_count > 0 else "-"
                ))
                
                if end is None:
                    self.tree.item(item_id, tags=('warning',))
            
            self.tree.tag_configure('warning', background='#ff6b6b', foreground='white')

            # 4. Update chart
            if self.process_data:
                self.current_idx = 0
                self.update_chart()

            # Summary
            if schedule_feasible:
                last_date = end.strftime("%m/%d/%Y") if end else "N/A"
                messagebox.showinfo("Success", f"Schedule generated successfully!\n\nEstimated completion: {last_date}")
            else:
                messagebox.showwarning("Warning", "Schedule completed with warnings.\n\nSome processes have insufficient capacity.")
                
        except ValueError as ve:
            messagebox.showerror("Input Error", str(ve))
        except pyodbc.Error as db_err:
            messagebox.showerror("Database Error", f"Database connection error:\n\n{db_err}")
        except Exception as e:
            messagebox.showerror("Error", f"An unexpected error occurred:\n\n{str(e)}")
        finally:
            self.btn_run.config(state='normal', text="Generate Schedule")
            self.sched.close()

def main():
    # 1. ODBC Driver Check before launching UI
    drivers = [d for d in pyodbc.drivers() if 'ODBC Driver 18' in d]
    
    if not drivers:
        root = tb.Window(visible=False)
        messagebox.showerror("System Error", 
            "Required Driver Missing!\n\n"
            "Please install 'ODBC Driver 18 for SQL Server'.\n"
            "Download from Microsoft or contact IT.")
        sys.exit()

    # 2. Launch Application
    app = SchedulerGUI(tb.Window(themename="superhero"))
    app.root.mainloop()

if __name__ == "__main__":
    main()