import ttkbootstrap as tb
import os
from ttkbootstrap.constants import *
from tkinter import messagebox
from datetime import datetime, timedelta
import pandas as pd
import numpy as np
import traceback
import threading
from tkinter import messagebox, DISABLED, NORMAL


# Internal Layer Imports
from ..data.sql_manager import SQLManager
from ..core.capacity import CapacityEngine
from ..core.predictor import ProductionAI
from .scheduler_chart import SchedulerChart

class PerformanceFrame(tb.Labelframe):
    """Frame to display schedule performance metrics"""
    def __init__(self, master, **kwargs):
        super().__init__(master, text=" Schedule Performance ", padding=10, bootstyle=SUCCESS, **kwargs)
        
        self.lbl_stats = tb.Label(
            self,
            text="Total Time: --\nAvg Confidence: --\nSteps: --\nMulti-Day Jobs: --",
            justify=LEFT,
            font=("Segoe UI", 10)
        )
        self.lbl_stats.pack(anchor=W)

        
    
    def update(self, total_predicted_mins=0, avg_confidence=0, steps=0, multi_day_jobs=None):
        """Update performance statistics"""
        hours = total_predicted_mins / 60
        multi_day_count = len(multi_day_jobs) if multi_day_jobs else 0
        
        stats_text = (
            f"Total Time: {total_predicted_mins:.0f}m ({hours:.1f}h)\n"
            f"Avg Confidence: {avg_confidence:.0f}%\n"
            f"# of Processes: {steps}\n"
            f"Multi-Day Jobs: {multi_day_count}"
        )
        
        if multi_day_jobs and multi_day_count > 0:
            stats_text += "\n\nMulti-Day Breakdown:"
            for job in multi_day_jobs[:3]:  # Show first 3
                start = job['start'].strftime('%m/%d')
                end = job['end'].strftime('%m/%d')
                stats_text += f"\n  • {job['process']}: {start}-{end} ({job['days']}d)"
            if multi_day_count > 3:
                stats_text += f"\n  ... +{multi_day_count - 3} more"
        
        self.lbl_stats.config(text=stats_text)


class JobDetailsFrame(tb.Labelframe):
    """Frame to display order details"""
    def __init__(self, master, **kwargs):
        super().__init__(master, text=" Order Details ", padding=10, bootstyle=INFO, **kwargs)
        
        # Treeview for routing steps
        self.tree = tb.Treeview(
            self,
            columns=("proc", "setup", "run", "conf"),
            show="headings",
            height=5
        )
        
        configs = [
            ("proc", "Process", 150),
            ("setup", "Setup (m)", 80),
            ("run", "Run (m)", 80),
            ("conf", "Conf %", 60)
        ]
        
        for c, h, w in configs:
            self.tree.heading(c, text=h)
            self.tree.column(c, anchor=CENTER if c != "proc" else W, width=w)
        
        self.tree.pack(fill=BOTH, expand=YES)
        
        # Summary labels
        self.lbl_summary = tb.Label(
            self,
            text="Docket: --\nQty: --\nStyle: --",
            justify=LEFT,
            font=("Segoe UI", 9),
            foreground="gray"
        )
        self.lbl_summary.pack(anchor=W, pady=(5, 0))
    
    def populate(self, docket_id, qty, lead_days, style_id, routing_df):
        """Populate with order details"""
        # Clear tree
        self.tree.delete(*self.tree.get_children())
        
        # Update summary
        self.lbl_summary.config(
            text=f"Docket: {docket_id}\nQty: {qty:,}\nStyle: {style_id}\nLead: {lead_days} days"
        )
        
        # Populate tree with routing
        for _, row in routing_df.iterrows():
            self.tree.insert("", END, values=(
                row.get('process_name', f"Process {row['process_id']}"),
                f"{row.get('setup_m', 0):.1f}",
                f"{row.get('run_m', 0):.1f}",
                f"{row.get('confidence', 0):.0f}%"
            ))


class ProductionPlannerFrame(tb.Frame):
    def __init__(self, master, **kwargs):
        super().__init__(master, **kwargs)
        
        self.db = SQLManager()
        self.engine = CapacityEngine()
        self.ai_engine = ProductionAI()
        
        # State Tracking
        self.routing_data = pd.DataFrame()
        self.booked_df = pd.DataFrame(columns=['process_id', 'schedule_date', 'mins_booked'])
        self.process_df = pd.DataFrame()
        self.holidays = []
        
        self.process_schedule = []
        self.scheduled_additions = {}
        self.current_process_idx = 0
        self.bypassed_processes = set()
        
        # Lookup dictionaries for fast access
        self.booked_mins_lookup = {}
        self.booked_jobs_lookup = {}
        self.booked_sqft_lookup = {}
        
        self.setup_ui()
        self.after(100, self.initialize_capacity_cache)

        #start sync
        threading.Thread(target=self._run_sync_worker, daemon=True).start()

    def setup_ui(self):
        """Build UI layout"""
        
        # === TOP ROW ===
        top_row = tb.Frame(self)
        top_row.pack(fill=X, side=TOP, pady=5)

        # 1. Docket Input
        f_param = tb.Labelframe(top_row, text=" Docket & Parameters ", padding=10, bootstyle=INFO)
        f_param.pack(side=LEFT, fill=BOTH, expand=YES, padx=5)
        f_param.columnconfigure(1, weight=1)

        tb.Label(f_param, text="Docket ID:").grid(row=0, column=0, sticky=W)
        self.ent_docket = tb.Entry(f_param)
        self.ent_docket.insert(0, "170024")
        self.ent_docket.grid(row=0, column=1, sticky=EW, padx=5, pady=2)
        
        tb.Label(f_param, text="Run Qty:").grid(row=1, column=0, sticky=W)
        self.ent_qty = tb.Entry(f_param)
        self.ent_qty.insert(0, "3000")
        self.ent_qty.grid(row=1, column=1, sticky=EW, padx=5, pady=2)
        
        tb.Label(f_param, text="Lead Days:").grid(row=2, column=0, sticky=W)
        self.ent_lead = tb.Entry(f_param)
        self.ent_lead.insert(0, "4")
        self.ent_lead.grid(row=2, column=1, sticky=EW, padx=5, pady=2)
        

        self.btn_run = tb.Button(
            f_param,
            text="Generate Schedule",
            bootstyle=SUCCESS,
            command=self.run_scheduler
        )
        self.btn_run.grid(row=3, column=1, sticky=EW, pady=10)

        self.btn_book = tb.Button(
            f_param,
            text="Book Job",
            bootstyle=SUCCESS,
            command=self.book_job
        )
        self.btn_book.grid(row=4, column=1, sticky=EW, pady=10)

        # 2. System Control
        f_ai = tb.Labelframe(top_row, text=" System Control ", padding=10, bootstyle=PRIMARY)
        f_ai.pack(side=LEFT, fill=BOTH, expand=NO, padx=5)

        btn_frame = tb.Frame(f_ai)
        btn_frame.pack(fill=X, pady=2)

        self.btn_refresh = tb.Button(
            btn_frame,
            text="Refresh Data",
            command=self.initialize_capacity_cache,
            bootstyle="outline-info",
            width=12
        )
        self.btn_refresh.pack(side=LEFT, padx=2)

        self.btn_retrain = tb.Button(
            btn_frame,
            text="Retrain AI",
            command=self.handle_retrain,
            bootstyle="outline-primary",
            width=12
        )
        self.btn_retrain.pack(side=LEFT, padx=2)

        self.lbl_ai_status = tb.Label(
            f_ai,
            text=f"Model Date:\n{self.ai_engine.training_date or 'Never'}",
            font=("Segoe UI", 8),
            justify=CENTER,
            foreground="gray"
        )
        self.lbl_ai_status.pack(pady=(5, 0))

        # 3. Performance Frame
        self.performance_frame = PerformanceFrame(top_row)
        self.performance_frame.pack(side=LEFT, fill=BOTH, expand=YES, padx=5)

        # 4. Job Details Frame
        self.job_details_frame = JobDetailsFrame(top_row)
        self.job_details_frame.pack(side=LEFT, fill=BOTH, expand=YES, padx=5)

        # === SCHEDULE TREE ===
        tb.Label(
            self,
            text="Double-click row to view Capacity Chart | Right-click to Bypass process",
            font=("Helvetica", 9, "italic"),
            foreground='#adb5bd'
        ).pack(anchor=W, pady=(5, 0))
        
        columns = ("seq", "proc", "blank", "setup", "run", "total", "conf", "start", "end", "bypass")
        self.tree = tb.Treeview(self, columns=columns, show="headings", height=8, bootstyle=PRIMARY)
        
        configs = [
            ("seq", "Seq", 40),
            ("proc", "Process Name", 180),
            ("blank", "Blank", 60),
            ("setup", "Setup", 60),
            ("run", "Run", 60),
            ("total", "Total", 70),
            ("conf", "Confidence", 100),
            ("start", "Start Date", 90),
            ("end", "End Date", 90),
            ("bypass", "Bypass", 60)
        ]
        
        for c, h, w in configs:
            self.tree.heading(c, text=h)
            self.tree.column(c, anchor=CENTER if c != "proc" else W, width=w)
            
        self.tree.pack(fill=X, pady=5)
        
        # Bindings
        self.tree.bind("<Double-1>", self.on_tree_double_click)
        self.tree.bind("<Button-3>", self.on_tree_right_click)
        
        # Tags for coloring
        self.tree.tag_configure('warning', background='#ff6b6b', foreground='white')
        self.tree.tag_configure('bypassed', background='#9b59b6', foreground='white')

        # === CHART NAVIGATION ===
        chart_nav = tb.Frame(self)
        chart_nav.pack(fill=X)
        
        self.btn_prev = tb.Button(
            chart_nav,
            text="◀ Previous",
            bootstyle="secondary-outline",
            command=lambda: self.navigate_process(-1),
            state='disabled',
            width=12
        )
        self.btn_prev.pack(side=LEFT, padx=5)
        
        self.lbl_chart = tb.Label(
            chart_nav,
            text="Process Capacity View",
            font=("Helvetica", 11, "bold"),
            bootstyle="inverse-info"
        )
        self.lbl_chart.pack(side=LEFT, expand=YES)
        
        self.btn_next = tb.Button(
            chart_nav,
            text="Next ▶",
            bootstyle="secondary-outline",
            command=lambda: self.navigate_process(1),
            state='disabled',
            width=12
        )
        self.btn_next.pack(side=RIGHT, padx=5)

        # === CHART ===
        chart_frame = tb.Labelframe(self, text="", padding=10, bootstyle=INFO)
        chart_frame.pack(fill=BOTH, expand=YES, pady=(5, 0))
        self.chart = SchedulerChart(
            chart_frame,
            on_bar_click_callback= self.on_chart_bar_clicked)

    def on_chart_bar_clicked(self, selected_date):
        pass
        # """This is the 'on_bar_click_callback' logic."""
        # # 1. Fetch data for the specific date using your SQLManager
        # # Note: We filter by the date clicked on the bar
        # query = """
        #     SELECT docket_id, style_id, booked_sqft, mins_booked, technician
        #     FROM schedule_view 
        #     WHERE date(schedule_dte) = ?
        # """
        
        # # Assuming 'db' is your SQLManager instance
        # df_details = db.safe_fetch(query, params=[selected_date.strftime('%Y-%m-%d')])

        # if not df_details.empty:
        #     # 2. Open the styled Toplevel window we created
        #     show_breakdown_window(selected_date, df_details)
        # else:
        #     print(f"No data found for {selected_date}")
    
    def book_job(self):
        self._insert_worker()

    def run_scheduler(self):
        """Main scheduling logic"""
        self.btn_run.config(state='disabled', text="Calculating...")
        self.update()
        schedule_start_time = datetime.now()

        try:
            print("=" * 60)
            print("SCHEDULE GENERATION")
            print("=" * 60)

            # Reset
            self.tree.delete(*self.tree.get_children())
            self.process_schedule = []
            self.scheduled_additions = {}
            self.current_process_idx = 0

            # Input validation
            docket_id = self.ent_docket.get().strip()
            if not docket_id:
                messagebox.showwarning("Missing Input", "Please enter a Docket ID")
                return

            try:
                qty = int(self.ent_qty.get())
                if qty <= 0:
                    raise ValueError
            except:
                messagebox.showwarning("Invalid Quantity", "Quantity must be > 0")
                return

            try:
                lead_days = int(self.ent_lead.get())
                if lead_days < 0:
                    raise ValueError
            except:
                messagebox.showwarning("Invalid Lead Time", "Lead days must be >= 0")
                return

            print(f"✓ Docket {docket_id} | Qty {qty:,} | Lead {lead_days} days")

            # AI check
            if not self.ai_engine.is_trained:
                messagebox.showwarning("AI Not Ready", "Please train AI first.")
                return

            # Fetch routing
            self.routing_data = self.db.fetch_docket_routing(docket_id, qty)
            if self.routing_data is None or self.routing_data.empty:
                messagebox.showwarning("Routing Missing", f"No routing for {docket_id}")
                return
            
            self.presses_capacity = self.db.fetch_raw_capacity()

            num_steps = len(self.routing_data)
            print(f"✓ Routing: {num_steps} steps")

            # Get metadata
            style_id, printing_id, sqfpm = self.db.get_docket_metadata(docket_id)
            style_id = style_id or "UNKNOWN"
            printing_id = printing_id or "UNKNOWN"
            sqfpm = sqfpm or 1000.0

            path_str = "->".join(self.routing_data['process_id'].astype(str))

            # Build workdays
            h_set = set(self.holidays)

            current = datetime.now().date()
            counted = 0

            while counted < lead_days:
                current += timedelta(days=1)

                if current.weekday() < 5 and current not in h_set:
                    counted += 1

            # now build your 60-day window
            workdays = []
            while len(workdays) < 60:
                if current.weekday() < 5 and current not in h_set:
                    workdays.append(current)
                current += timedelta(days=1)

            # Predictions
            predictions = []
            for idx, row in self.routing_data.iterrows():
                total_m, setup_m, run_m, conf = self.ai_engine.predict_ai(
                    row['process_id'],
                    style_id,
                    printing_id,
                    path_str,
                    qty,
                    sqfpm,
                    buffer=True
                )
                
                self.routing_data.at[idx, 'total_m'] = total_m
                self.routing_data.at[idx, 'setup_m'] = setup_m
                self.routing_data.at[idx, 'run_m'] = run_m
                self.routing_data.at[idx, 'confidence'] = conf
                predictions.append((total_m, setup_m, run_m, conf))

            total_predicted = self.routing_data['total_m'].sum()
            avg_conf = self.routing_data['confidence'].mean()

            # Scheduling
            prev_end_date = None
            multi_day_jobs = []

            for step_idx, (_, proc) in enumerate(self.routing_data.iterrows(), 1):
                pid = proc['process_id']
                pname = proc.get('process_name', f'Process {pid}')
                total_m = proc['total_m']
                
                start_date = end_date = None
                allocation_map = {}
                
                earliest = prev_end_date + timedelta(days=1) if prev_end_date else workdays[0]

                # Find capacity
                for candidate in workdays:
                    if candidate < earliest:
                        continue

                    remaining = total_m
                    temp_alloc = {}
                    day = candidate
                    df_idx = self.process_df.set_index('process_id')
                    while remaining > 0 and day in workdays:
                        booked = self.booked_mins_lookup.get((pid, day), 0)
                        session = self.scheduled_additions.get(pid, {}).get(day, 0)
                        schedule_date = day.isoweekday() % 7 + 1
                        process_capacity = df_idx.loc[pid, f'capacity_{schedule_date}']
                        available = max(0, (process_capacity * 60) - booked - session)
                        if available >= 90:
                            alloc = min(available, remaining)
                            temp_alloc[day] = alloc
                            remaining -= alloc

                        day += timedelta(days=1)

                    if remaining <= 0:
                        start_date = candidate
                        end_date = max(temp_alloc.keys())
                        allocation_map = temp_alloc

                        if pid not in self.scheduled_additions:
                            self.scheduled_additions[pid] = {}
                        
                        for d, m in temp_alloc.items():
                            self.scheduled_additions[pid][d] = \
                                self.scheduled_additions[pid].get(d, 0) + m

                        if len(temp_alloc) > 1:
                            multi_day_jobs.append({
                                'process': pname,
                                'start': start_date,
                                'end': end_date,
                                'days': len(temp_alloc)
                            })
                        break

                prev_end_date = end_date

                # Store schedule
                proc_data = {
                    'process_id': pid,
                    'process_name': pname,
                    'seq_order': step_idx,
                    'start': start_date,
                    'end': end_date,
                    'total_m': total_m,
                    'setup_m': proc['setup_m'],
                    'run_m': proc['run_m'],
                    'required_sqft' : sqfpm / 1000 * qty,
                    'predicted_mins': total_m,
                    'blank_per_hour': int(qty/(proc['run_m']/60)),
                    'confidence': proc['confidence'],
                    'allocation_map': allocation_map
                }
                self.process_schedule.append(proc_data)
                self._add_to_schedule_ui(proc_data, start_date, end_date, allocation_map, False)

            # Update UI components
            self.current_process_idx = 0
            self.update_chart_for_current_process()

            self.performance_frame.update(
                total_predicted_mins=total_predicted,
                avg_confidence=avg_conf,
                steps=len(self.process_schedule),
                multi_day_jobs=multi_day_jobs
            )

            self.job_details_frame.populate(
                docket_id=docket_id,
                qty=qty,
                lead_days=lead_days,
                style_id=style_id,
                routing_df=self.routing_data
            )

            duration = (datetime.now() - schedule_start_time).total_seconds()
            print(f"✓ Completed in {duration:.2f}s")

        except Exception as e:
            traceback.print_exc()
            messagebox.showerror("Scheduler Error", str(e))

        finally:
            self.btn_run.config(state='normal', text="Generate Schedule")

    def _add_to_schedule_ui(self, proc, start_date, end_date, allocation_map, bypassed):
        """Add row to schedule tree"""
        if start_date and end_date:
            date_str = start_date.strftime("%m/%d/%Y")
            end_str = end_date.strftime("%m/%d/%Y") if end_date != start_date else date_str
        else:
            date_str = end_str = "OVER CAPACITY"
        
        conf = proc['confidence']
        
        # Icon
        if bypassed:
            icon = '⚪'
            tag = 'bypassed'
        elif not start_date:
            icon = '❌'
            tag = 'warning'
        elif conf >= 80:
            icon = '🟢'
            tag = ''
        elif conf >= 60:
            icon = '🟡'
            tag = ''
        else:
            icon = '🔴'
            tag = 'warning'
        
        if allocation_map and len(allocation_map) > 1:
            icon = f"📅{icon}"
        
        self.tree.insert("", "end", values=(
            proc['seq_order'],
            proc['process_name'],
            f"{proc['blank_per_hour']:.0f}/h",
            f"{proc['setup_m']:.0f}m",
            f"{proc['run_m']:.0f}m",
            f"{proc['predicted_mins']:.0f}m",
            f"{icon} {conf:.0f}%",
            date_str,
            end_str,
            "YES" if bypassed else ""
        ), tags=(tag,))

    def on_tree_double_click(self, event):
        """View chart for selected process"""
        selection = self.tree.selection()
        if not selection or not self.process_schedule:
            return
        
        item = self.tree.item(selection[0])
        seq_num = item['values'][0]
        
        for idx, proc in enumerate(self.process_schedule):
            if proc['seq_order'] == seq_num:
                self.current_process_idx = idx
                self.update_chart_for_current_process()
                break

    def on_tree_right_click(self, event):
        """Toggle bypass (placeholder)"""
        pass

    def navigate_process(self, delta):
        """Navigate between processes"""
        if not self.process_schedule:
            return
        self.current_process_idx = (self.current_process_idx + delta) % len(self.process_schedule)
        self.update_chart_for_current_process()

    def update_chart_for_current_process(self):
        """Update chart for current process"""
        if not self.process_schedule:
            return
        
        proc = self.process_schedule[self.current_process_idx]
        
        self.btn_prev.config(state='normal' if len(self.process_schedule) > 1 else 'disabled')
        self.btn_next.config(state='normal' if len(self.process_schedule) > 1 else 'disabled')
        
        start_txt = proc['start'].strftime('%m/%d') if proc.get('start') else 'N/A'
        self.lbl_chart.config(
            text=f"{proc['process_name']} (Step {proc['seq_order']}) - {start_txt}"
        )
        
        proc_scheduled = self.scheduled_additions.get(proc['process_id'], {})
        self.chart.update_chart(
            proc_name=proc['process_name'],
            proc_id=proc['process_id'],
            proc_start=proc['start'],
            proc_end=proc['end'],
            required_sqft=proc['required_sqft'],
            booked_df=self.booked_df,
            scheduled_additions=proc_scheduled,
            day_tier_usage={}
        )

    def initialize_capacity_cache(self):
        """Load capacity cache - OPTIMIZED with batch predictions"""
        top = self.winfo_toplevel()
        top.config(cursor="watch")
        self.btn_refresh.config(state="disabled", text="Loading...")
        self.update()

        try:
            print("Initializing capacity cache...")
            start_time = datetime.now()
            
            raw_jobs, self.holidays, self.process_df = self.db.fetch_booked_and_holidays_and_process()
            
            if raw_jobs.empty:
                print("No booked jobs found")
                self._initialize_empty_cache()
                return

            if not self.ai_engine.is_trained:
                print("AI not trained, using fallback")
                self._build_cache_with_fallback(raw_jobs)
                return

            print(f"Processing {len(raw_jobs)} booked jobs...")

            try:
                # Prepare batch data
                raw_jobs['style_id'] = raw_jobs.get('style_id', 'UNKNOWN').fillna('UNKNOWN')
                raw_jobs['printing_id'] = raw_jobs.get('printing_id', 'UNKNOWN').fillna('UNKNOWN')
                raw_jobs['full_path'] = raw_jobs.get('full_path', '').fillna('')
                raw_jobs['sqfpm'] = raw_jobs.get('sqfpm', 1000).fillna(1000)
                # Use batch prediction if available
                if hasattr(self.ai_engine, 'predict_batch'):
                    print("Using batch prediction...")
                    
                    # Prepare data for batch prediction
                    batch_df = pd.DataFrame({
                        'process_id': raw_jobs['process_id'],
                        'style_id': raw_jobs['style_id'],
                        'printing_id': raw_jobs['printing_id'],
                        'full_path': raw_jobs['full_path'],
                        'qty': raw_jobs['job_qty'],
                        'sqfpm': raw_jobs['sqfpm']
                    })
                    
                    # Get predictions in one batch call (100x faster!)
                    predictions = self.ai_engine.predict_batch(batch_df)
                    
                    total_mins = predictions['total_m'].values
                    total_sqft = (raw_jobs['job_qty'] * raw_jobs['sqfpm'] / 1000).values
                    
                else:
                    # Fallback to loop if no batch method
                    print("Warning: Using loop prediction...")
                    total_mins = []
                    total_sqft = []
                    
                    for idx, job in raw_jobs.iterrows():
                        try:
                            t, _, _, _ = self.ai_engine.predict_ai(
                                job['process_id'],
                                job['style_id'],
                                job['printing_id'],
                                job['full_path'],
                                job['job_qty'],
                                job['sqfpm'],
                                buffer=True
                            )
                            total_mins.append(t)
                            total_sqft.append(job['job_qty'] * job['sqfpm'] / 1000)
                        except Exception as e:
                            print(f"Prediction error for job {idx}: {e}")
                            total_mins.append(15.0 + job['job_qty'] * 0.01)
                            total_sqft.append(job['job_qty'] * job['sqfpm'] / 1000)

            except Exception as e:
                print(f"Batch prediction failed: {e}")
                traceback.print_exc()
                # Ultimate fallback
                total_mins = [15.0 + job['job_qty'] * 0.01 for _, job in raw_jobs.iterrows()]
                total_sqft = [job['job_qty'] * job.get('sqfpm', 1000) / 1000 for _, job in raw_jobs.iterrows()]

            # Build DataFrame
            processed_df = pd.DataFrame({
                'process_id': raw_jobs['process_id'].values,
                'schedule_date': raw_jobs['schedule_date'].values,
                'mins_booked': raw_jobs['total_time'],
                'booked_sqft': total_sqft
            })
            # Aggregate
            self.booked_df = processed_df.groupby(
                ['process_id', 'schedule_date'], as_index=False
            ).agg(
                mins_booked=('mins_booked', 'sum'),
                booked_sqft=('booked_sqft', 'sum'),
                booked_jobs=('process_id', 'count')
            )

            # Build lookups
            self.booked_mins_lookup = {
                (r.process_id, r.schedule_date): r.mins_booked
                for r in self.booked_df.itertuples()
            }
            
            self.booked_sqft_lookup = {
                (r.process_id, r.schedule_date): r.booked_sqft
                for r in self.booked_df.itertuples()
            }
            
            self.booked_jobs_lookup = {
                (r.process_id, r.schedule_date): r.booked_jobs
                for r in self.booked_df.itertuples()
            }

            elapsed = (datetime.now() - start_time).total_seconds()
            print(f"✓ Cache loaded: {len(self.booked_df)} entries in {elapsed:.2f}s")
            
            self.lbl_ai_status.config(
                text=f"Cache: {len(raw_jobs)} jobs\n{datetime.now().strftime('%H:%M:%S')}",
                foreground="green"
            )

        except Exception as e:
            print(f"Cache initialization error: {e}")
            traceback.print_exc()
            self._initialize_empty_cache()

        finally:
            top.config(cursor="")
            self.btn_refresh.config(state="normal", text="Refresh Data")

    def _initialize_empty_cache(self):
        """Initialize empty cache"""
        self.booked_df = pd.DataFrame(
            columns=['process_id', 'schedule_date', 'mins_booked', 'booked_sqft', 'booked_jobs']
        )
        self.booked_mins_lookup = {}
        self.booked_jobs_lookup = {}
        self.booked_sqft_lookup = {}
        print("Empty cache initialized")

    def _build_cache_with_fallback(self, raw_jobs):
        """Fallback when AI not trained"""
        setup = 15.0
        rate = 0.01
        
        total_mins = setup + (raw_jobs['job_qty'] * rate)
        total_sqft = raw_jobs['job_qty'] * raw_jobs.get('sqfpm', 1000) / 1000
        
        processed_df = pd.DataFrame({
            'process_id': raw_jobs['process_id'],
            'schedule_date': raw_jobs['schedule_date'],
            'mins_booked': total_mins,
            'booked_sqft': total_sqft 
        })
        
        self.booked_df = processed_df.groupby(
            ['process_id', 'schedule_date'], as_index=False
        ).agg(
            mins_booked=('mins_booked', 'sum'),
            booked_sqft=('booked_sqft', 'sum'),  
            booked_jobs=('process_id', 'count')
        )
        
        self.booked_mins_lookup = {
            (r.process_id, r.schedule_date): r.mins_booked
            for r in self.booked_df.itertuples()
        }
        
        self.booked_sqft_lookup = {
            (r.process_id, r.schedule_date): r.booked_sqft
            for r in self.booked_df.itertuples()
        }
        
        self.booked_jobs_lookup = {
            (r.process_id, r.schedule_date): r.booked_jobs
            for r in self.booked_df.itertuples()
        }
        
        print(f"Fallback cache built: {len(self.booked_df)} entries")
        messagebox.showwarning(
            "Fallback Mode",
            "AI not trained - using estimates.\nPlease train AI for accuracy."
        )

    def _insert_worker(self):
        try:
            for p in self.process_schedule:
                data = {
                    "process_id": p["process_id"],
                    "process_nme": p["process_name"],
                    "order_seq": p["seq_order"],
                    "schedule_dte": p["start"],
                    "setup_time": p["setup_m"],
                    "msf": p["required_sqft"],
                    "run_speed": p["blank_per_hour"],
                }

                success = self.db.insert_schedule(data)

                if success:
                    # ✅ create DataFrame as rows, not scalars
                    processed_df = pd.DataFrame([{
                        'process_id': p["process_id"],
                        'schedule_date': p["start"],
                        'mins_booked': p["total_m"],
                        'booked_sqft': p["required_sqft"]
                    }])

                    new_df = processed_df.groupby(
                        ['process_id', 'schedule_date'], as_index=False
                    ).agg(
                        mins_booked=('mins_booked', 'sum'),
                        booked_sqft=('booked_sqft', 'sum'),
                        booked_jobs=('process_id', 'count')
                    )

                    # ✅ append safely
                    if hasattr(self, "booked_df") and not self.booked_df.empty:
                        self.booked_df = (
                            pd.concat([self.booked_df, new_df], ignore_index=True)
                            .groupby(['process_id', 'schedule_date'], as_index=False)
                            .agg(
                                mins_booked=('mins_booked', 'sum'),
                                booked_sqft=('booked_sqft', 'sum'),
                                booked_jobs=('booked_jobs', 'sum')
                            )
                        )
                    else:
                        self.booked_df = new_df.copy()

        except Exception as e:
            print("Schedule processing failed:", e)

            
        except Exception as e:
            pass

    def _run_sync_worker(self):
        """The heavy lifting logic running in the background"""
        try:
            # Call the perform_full_sync method we built in SQLManager
            success = self.db.perform_full_sync()
            
            # 3. Schedule UI updates back on the Main Thread
            # IMPORTANT: Tkinter is NOT thread-safe. Use .after() to update UI.
            if success:
                pass
                # self.after(0, lambda: messagebox.showinfo("Success", "Local cache updated!"))
            else:
                # pass
                self.after(0, lambda: messagebox.showerror("Error", "Sync failed. Check network."))
                
        finally:
            pass
            # 4. Re-enable the button on the main thread
            # self.after(0, lambda: self.btn_sync.config(state=NORMAL, text="Sync Data"))
            
    def handle_retrain(self):
        """
        Triggered by the Retrain Button. Retrains AI using historical job data from the DB.
        
        IMPROVEMENTS:
        1. Shows progress feedback during long operations
        2. Validates data quality before training
        3. Runs prediction validation after training
        4. Better error messages with actionable guidance
        5. Logs training metrics for tracking over time
        """
        # Enhanced confirmation with more context
        confirm = messagebox.askyesno(
            "AI Training",
            "Retraining uses historical job data to optimize Setup & Run predictions.\n\n"
            "This will:\n"
            "• Analyze all historical jobs\n"
            "• Build a new prediction model\n"
            "• Recalculate capacity for booked jobs\n\n"
            "Continue?"
        )
        if not confirm:
            return
        
        root_window = self.winfo_toplevel()
        
        # Visual feedback
        self.btn_refresh.config(state="disabled", text="Training...")
        root_window.config(cursor="watch")
        root_window.update_idletasks()
        
        training_start_time = datetime.now()
        
        try:
            # 1️⃣ Fetch AI Training Data
            print("=" * 60)
            print("AI RETRAINING STARTED")
            print("=" * 60)
            print(f"[1/6] Fetching historical training data...")
            
            df = self.db.fetch_ai_training_data()
            
            if df is None or df.empty:
                messagebox.showwarning(
                    "No Data", 
                    "The database returned no historical data for AI training.\n\n"
                    "Ensure you have:\n"
                    "• Completed jobs with Setup and Run times recorded\n"
                    "• At least 10 historical jobs for training"
                )
                return
            
            initial_count = len(df)
            print(f"   ✓ Fetched {initial_count} historical jobs")
            
            # 2️⃣ Standardize Data Schema
            print(f"[2/6] Standardizing data schema...")
            
            column_map = {
                'process_id': 'process_id',
                'style_id': 'style_id',
                'printing_id' : 'printing_id',
                'full_path': 'full_path',
                'Qty': 'job_qty',
                'sqfpm': 'sqfpm',
                'Setup': 'setup_m',
                'Run': 'run_m'
            }
            
            actual_map = {k: v for k, v in column_map.items() if k in df.columns}
            df = df.rename(columns=actual_map)
            
            # 3️⃣ DATA QUALITY VALIDATION
            print(f"[3/6] Validating data quality...")
            
            # Check for required columns
            required_cols = ['process_id', 'style_id', 'printing_id', 'full_path', 'job_qty', 'setup_m', 'run_m']
            missing_cols = [col for col in required_cols if col not in df.columns]
            
            if missing_cols:
                error_msg = (
                    f"Missing required columns: {', '.join(missing_cols)}\n\n"
                    f"Check your database query to ensure all columns are included."
                )
                messagebox.showerror("Data Error", error_msg)
                print(f"   ✗ Missing columns: {missing_cols}")
                return
            
            # Check data types and ranges
            quality_issues = []
            
            # Check for negative or zero quantities
            bad_qty = df[df['job_qty'] <= 0]
            if len(bad_qty) > 0:
                quality_issues.append(f"{len(bad_qty)} jobs with qty ≤ 0")
            
            # Check for negative times
            bad_setup = df[df['setup_m'] < 0]
            bad_run = df[df['run_m'] < 0]
            if len(bad_setup) > 0:
                quality_issues.append(f"{len(bad_setup)} jobs with negative setup")
            if len(bad_run) > 0:
                quality_issues.append(f"{len(bad_run)} jobs with negative run time")
            
            # Check for suspicious outliers (setup > 8 hours or run rate > 2 min/unit)
            suspicious_setup = df[df['setup_m'] > 480]
            df['temp_rate'] = df['run_m'] / df['job_qty']
            suspicious_rate = df[df['temp_rate'] > 2.0]
            
            if len(suspicious_setup) > 0:
                quality_issues.append(f"{len(suspicious_setup)} jobs with setup > 8 hours")
            if len(suspicious_rate) > 0:
                quality_issues.append(f"{len(suspicious_rate)} jobs with run rate > 2 min/unit")
            
            # Show quality report
            if quality_issues:
                issue_summary = "\n• ".join(quality_issues)
                print(f"   ⚠ Data quality issues detected:\n   • {issue_summary}")
                print(f"   → These will be filtered out during training")
            else:
                print(f"   ✓ Data quality checks passed")
            
            # 4️⃣ Outlier Filtering
            print(f"[4/6] Filtering outliers...")
            
            df_filtered = self.filter_run_outliers(df, column='run_m', threshold=3.0)
            filtered_count = len(df_filtered)
            removed_count = initial_count - filtered_count
            removal_pct = (removed_count / initial_count * 100) if initial_count > 0 else 0
            
            print(f"   ✓ Filtered {removed_count} outliers ({removal_pct:.1f}%)")
            print(f"   ✓ Training on {filtered_count} clean samples")
            
            # Check if we have enough data after filtering
            if filtered_count < 10:
                messagebox.showerror(
                    "Insufficient Data",
                    f"Only {filtered_count} clean samples remain after filtering.\n\n"
                    f"AI training requires at least 10 samples.\n"
                    f"Original data: {initial_count} jobs\n"
                    f"Removed: {removed_count} outliers ({removal_pct:.1f}%)\n\n"
                    f"Recommendation: Review data quality or collect more historical jobs."
                )
                return
            
            # Warn if high removal rate
            if removal_pct > 30:
                proceed = messagebox.askyesno(
                    "High Outlier Rate",
                    f"Warning: {removal_pct:.1f}% of data was filtered as outliers.\n\n"
                    f"This suggests data quality issues. Training may be less accurate.\n\n"
                    f"Continue anyway?"
                )
                if not proceed:
                    return
            
            # 5️⃣ Train AI Engine
            print(f"[5/6] Training AI model...")
            root_window.update_idletasks()  # Keep UI responsive
            
            success = self.ai_engine.train_global(df_filtered, save=True)
            
            if not success:
                messagebox.showerror(
                    "Training Failed", 
                    "AI Training failed. This could be due to:\n\n"
                    "• Insufficient data variety\n"
                    "• Data format issues\n"
                    "• System resource constraints\n\n"
                    "Check the terminal/console for detailed error messages."
                )
                print("   ✗ Training failed - check traceback above")
                return
            
            print(f"   ✓ Model trained successfully")
            
            # 6️⃣ Model Performance Validation
            print(f"[6/6] Validating model performance...")
            
            info = self.ai_engine.get_model_info()
            r2 = info.get('r2', 0)
            samples = info.get('training_samples', 0)
            
            # Run prediction validation if method exists
            validation_passed = True
            if hasattr(self.ai_engine, 'validate_prediction_logic'):
                try:
                    validation_passed = self.ai_engine.validate_prediction_logic()
                    if validation_passed:
                        print(f"   ✓ Prediction validation passed")
                    else:
                        print(f"   ⚠ Prediction validation failed - check logic")
                except Exception as e:
                    print(f"   ⚠ Prediction validation error: {e}")
            
            # Assess model quality
            quality_status = "Excellent" if r2 > 0.8 else "Good" if r2 > 0.6 else "Fair" if r2 > 0.4 else "Poor"
            color_status = "green" if r2 > 0.6 else "orange" if r2 > 0.4 else "red"
            
            # Update UI Labels
            self.lbl_ai_status.config(
                text=f"Last Training:\n{info.get('training_date', 'Error')}",
                foreground=color_status
            )
            
            # 7️⃣ Refresh Capacity Cache
            print(f"[7/7] Recalculating capacity cache...")
            root_window.update_idletasks()
            
            self.initialize_capacity_cache()
            print(f"   ✓ Capacity cache refreshed")
            
            # Calculate training duration
            training_duration = (datetime.now() - training_start_time).total_seconds()
            
            # 8️⃣ Log training metrics (if logging is set up)
            if hasattr(self, 'log_training_metrics'):
                self.log_training_metrics({
                    'timestamp': datetime.now(),
                    'samples_original': initial_count,
                    'samples_filtered': filtered_count,
                    'removal_rate': removal_pct,
                    'r2_score': r2,
                    'training_duration_sec': training_duration,
                    'validation_passed': validation_passed
                })
            
            # Success message with detailed stats
            print("=" * 60)
            print("AI RETRAINING COMPLETED SUCCESSFULLY")
            print("=" * 60)
            
            success_msg = (
                f"AI Brain Updated Successfully!\n\n"
                f"Training Statistics:\n"
                f"• Original samples: {initial_count}\n"
                f"• Clean samples used: {filtered_count}\n"
                f"• Outliers removed: {removed_count} ({removal_pct:.1f}%)\n"
                f"• Model accuracy (R²): {r2:.3f} ({quality_status})\n"
                f"• Training time: {training_duration:.1f}s\n"
                f"• Validation: {'✓ Passed' if validation_passed else '⚠ Check logs'}\n\n"
                f"Status: Capacity cache refreshed for all booked jobs."
            )
            
            # Warn if accuracy is low
            if r2 < 0.4:
                success_msg += (
                    "\n\n⚠️ Warning: Model accuracy is low.\n"
                    "Consider collecting more diverse training data."
                )
            
            messagebox.showinfo("Training Complete", success_msg)
            
        except Exception as e:
            error_details = traceback.format_exc()
            print("=" * 60)
            print("AI RETRAINING FAILED")
            print("=" * 60)
            print(error_details)
            
            messagebox.showerror(
                "Training Error", 
                f"Fatal error during AI training:\n\n{str(e)}\n\n"
                f"Check the terminal/console for full error details."
            )
            
        finally:
            # Always restore UI state
            root_window.config(cursor="")
            self.btn_refresh.config(state="normal", text="Refresh Data")

    def filter_run_outliers(self, df, column='run_m', threshold=3.0):
        """MAD outlier filtering"""
        if column not in df.columns:
            return df.copy()
        
        median_val = df[column].median()
        mad_val = np.median(np.abs(df[column] - median_val))
        
        if mad_val == 0:
            return df.copy()
        
        mask = np.abs(df[column] - median_val) <= threshold * mad_val
        return df.loc[mask].copy()
    

    def build_schedule(self, docket_id, qty, lead_days):
        """
        Generate production routing schedule.
        Returns list of scheduled process dictionaries.
        """

        process_schedule = []
        scheduled_additions = {}

        # Fetch routing
        routing_data = self.db.fetch_docket_routing(docket_id, qty)

        if routing_data is None or routing_data.empty:
            return []

        # Metadata
        style_id, printing_id, sqfpm = self.db.get_docket_metadata(docket_id)

        style_id = style_id or "UNKNOWN"
        printing_id = printing_id or "UNKNOWN"
        sqfpm = sqfpm or 1000.0

        path_str = "->".join(routing_data['process_id'].astype(str))

        # Build workdays
        h_set = set(self.holidays)

        current = datetime.now().date()
        counted = 0

        while counted < lead_days:
            current += timedelta(days=1)

            if current.weekday() < 5 and current not in h_set:
                counted += 1

        workdays = []

        while len(workdays) < 60:
            if current.weekday() < 5 and current not in h_set:
                workdays.append(current)

            current += timedelta(days=1)

        # AI predictions
        for idx, row in routing_data.iterrows():
            total_m, setup_m, run_m, conf = self.ai_engine.predict_ai(
                row['process_id'],
                style_id,
                printing_id,
                path_str,
                qty,
                sqfpm,
                buffer=True
            )

            routing_data.at[idx, 'total_m'] = total_m
            routing_data.at[idx, 'setup_m'] = setup_m
            routing_data.at[idx, 'run_m'] = run_m
            routing_data.at[idx, 'confidence'] = conf

        # Scheduling
        prev_end_date = None

        for step_idx, (_, proc) in enumerate(routing_data.iterrows(), 1):

            pid = proc['process_id']
            pname = proc.get('process_name', f'Process {pid}')
            total_m = proc['total_m']

            start_date = end_date = None
            allocation_map = {}

            earliest = (
                prev_end_date + timedelta(days=1)
                if prev_end_date
                else workdays[0]
            )

            for candidate in workdays:

                if candidate < earliest:
                    continue

                remaining = total_m
                temp_alloc = {}
                day = candidate
                self.initialize_capacity_cache()
                df_idx = self.process_df.set_index('process_id')

                while remaining > 0 and day in workdays:

                    booked = self.booked_mins_lookup.get((pid, day), 0)
                    session = scheduled_additions.get(pid, {}).get(day, 0)

                    schedule_date = day.isoweekday() % 7 + 1

                    process_capacity = df_idx.loc[
                        pid,
                        f'capacity_{schedule_date}'
                    ]

                    available = max(
                        0,
                        (process_capacity * 60) - booked - session
                    )

                    if available >= 90:
                        alloc = min(available, remaining)
                        temp_alloc[day] = alloc
                        remaining -= alloc

                    day += timedelta(days=1)

                if remaining <= 0:

                    start_date = candidate
                    end_date = max(temp_alloc.keys())
                    allocation_map = temp_alloc

                    if pid not in scheduled_additions:
                        scheduled_additions[pid] = {}

                    for d, m in temp_alloc.items():
                        scheduled_additions[pid][d] = (
                            scheduled_additions[pid].get(d, 0) + m
                        )

                    break

            prev_end_date = end_date

            proc_data = {
                'process_id': pid,
                'process_name': pname,
                'seq_order': step_idx,
                'start': start_date,
                'end': end_date,
                'total_m': total_m,
                'setup_m': proc['setup_m'],
                'run_m': proc['run_m'],
                'required_sqft': sqfpm / 1000 * qty,
                'predicted_mins': total_m,
                'blank_per_hour': int(qty / (proc['run_m'] / 60)),
                'confidence': proc['confidence'],
                'allocation_map': allocation_map
            }

            process_schedule.append(proc_data)

        return process_schedule
        
    def get_routing(self, docket_id, qty, lead_days):
        process_schedule = self.build_schedule(
        docket_id,
        qty,
        lead_days
        )
        return process_schedule
    
if __name__ == "__main__":
    app = tb.Window(themename="darkly")  
    app.title("Production Planner")
    app.geometry("1600x900")

    frame = ProductionPlannerFrame(app)
    frame.pack(fill=BOTH, expand=YES)

    app.mainloop()