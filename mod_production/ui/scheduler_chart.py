import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure
import pandas as pd
import tkinter as tk
from tkinter import ttk
from datetime import datetime, timedelta
import matplotlib.ticker as mticker

class SchedulerChart:
    def __init__(self, parent_frame, on_bar_click_callback = None):
        """Initializes the Matplotlib figure and embeds it into the Tkinter frame."""
        self.fig = Figure(figsize=(10, 3.5), dpi=100, facecolor='#2b3e50')
        self.ax = self.fig.add_subplot(111)
        self.ax.set_facecolor('#2b3e50')
        self.ax_mins = None
        
        #Store date
        self.current_dates = []
        self.on_bar_click_callback = on_bar_click_callback

        # Setup the Canvas
        self.canvas = FigureCanvasTkAgg(self.fig, master=parent_frame)
        
        # IMPORTANT: This must be called before packing to ensure the backend is ready
        self.canvas.draw()
        
        #Click event
        self.canvas.mpl_connect('button_press_event', self.on_click)

        # Pack the widget
        self.chart_widget = self.canvas.get_tk_widget()
        self.chart_widget.pack(fill="both", expand=True)
        
        # Initial empty state text
        self.show_placeholder("Run scheduler to view capacity data")

    def on_click(self, event):
        """Identifies which date was clicked and triggers the external callback."""
        if event.inaxes not in [self.ax, self.ax_mins]:
            return
        
        # event.xdata gives the float index of the bar (0, 1, 2...)
        try:
            x_index = int(round(event.xdata))
            if 0 <= x_index < len(self.current_dates):
                clicked_date = self.current_dates[x_index]
                print(f"Date clicked: {clicked_date}")
                # Execute the callback passed in __init__
                if self.on_bar_click_callback:
                    self.on_bar_click_callback(clicked_date)
        except (TypeError, ValueError):
            pass # Click was likely on an axis or outside the bar area

    def show_placeholder(self, message):
        """Helper to show a message when no data is loaded."""
        self.ax.clear()
        self.ax.set_facecolor('#2b3e50')
        self.ax.text(0.5, 0.5, message, 
                     ha='center', va='center', transform=self.ax.transAxes,
                     color='#adb5bd', fontsize=12)
        self.ax.set_xticks([])
        self.ax.set_yticks([])
        self.canvas.draw()
    
    def format_mins_to_hhmm(mins):
        """Converts 135.0 to '02:15'"""
        hrs = int(mins // 60)
        m = int(mins % 60)
        return f"{hrs:02d}:{m:02d}"

    def update_chart(
        self, proc_name, proc_id, proc_start, proc_end, required_sqft,
        booked_df, scheduled_additions, day_tier_usage
    ):
        """
        Redraws the chart with updated data:
        - Left Y-axis: SqFt stacked bars (Existing + Scheduled)
        - Right Y-axis: Minutes booked (line)
        - Job counts inside bars
        - Tier usage labels on top
        """

        # Clear previous chart
        self.ax.clear()
        self.ax.set_facecolor('#2b3e50')

        # Time Range (Next 25 days)
        today = datetime.now().date()
        self.current_dates = [today + timedelta(days=i) for i in range(25)]
        # dates = [today + timedelta(days=i) for i in range(25)]
        dates = self.current_dates
        x = range(len(dates))

        # Initialize daily series
        daily_booked = pd.Series(0.0, index=dates)
        daily_jobs = pd.Series(0, index=dates)
        daily_scheduled = pd.Series(0.0, index=dates)

        # Map existing bookings
        if booked_df is not None and not booked_df.empty:
            booked_df = booked_df.copy()
            booked_df['schedule_date'] = pd.to_datetime(booked_df['schedule_date']).dt.date
            p_booked = booked_df[booked_df['process_id'] == proc_id]

            for row in p_booked.itertuples(index=False):
                d = row.schedule_date
                if d in daily_booked.index:
                    daily_booked[d] += float(row.booked_sqft)
                    daily_jobs[d] += int(row.booked_jobs)

        # Map scheduled additions
        if scheduled_additions:
            for d, sqft in scheduled_additions.items():
                # Force conversion to date object
                if hasattr(d, 'date'):
                    d_obj = d.date()
                elif isinstance(d, str):
                    d_obj = pd.to_datetime(d).date()
                else:
                    d_obj = d

                    
                if d_obj in daily_scheduled.index:
                    print(proc_start)
                    print(proc_end)
                    if proc_start and proc_end:
                        days_span = (proc_end - proc_start).days + 1
                        avg_per_day = required_sqft / days_span if days_span > 0 else 0
                        daily_scheduled[d_obj] += float(avg_per_day)

        # Draw stacked bars
        bars_booked = self.ax.bar(
            x, daily_booked.values,
            color='#3498db', alpha=0.7, edgecolor='#2980b9', linewidth=1.5,
            label='Existing Bookings'
        )
        bars_scheduled = self.ax.bar(
            x, daily_scheduled.values,
            bottom=daily_booked.values, 
            color='#e74c3c', alpha=0.9, edgecolor='#c0392b',
            linewidth=1.5, label='This Job (Scheduled)'
        )

        # Draw required capacity line
        if proc_start and proc_end:
            days_span = (proc_end - proc_start).days + 1
            avg_per_day = required_sqft / days_span if days_span > 0 else 0
            schedule_indices = [i for i, d in enumerate(dates) if proc_start <= d <= proc_end]
            if schedule_indices:
                self.ax.hlines(
                    avg_per_day,
                    min(schedule_indices) - 0.4, max(schedule_indices) + 0.4,
                    colors='#f39c12', linewidth=2, linestyle='--',
                    label=f'Required Avg: {avg_per_day:,.0f} sqft/day'
                )

        # Add job count and tier labels on bars
        for i, (d, booked, scheduled, jobs) in enumerate(
            zip(dates, daily_booked.values, daily_scheduled.values, daily_jobs.values)
        ):
            total_sqft = booked + scheduled
            if total_sqft > 0:
                tier_used = day_tier_usage.get(d) if day_tier_usage else None
                label_text = f'{total_sqft:,.0f}'
                if tier_used:
                    label_text += f' [T{tier_used}]'
                self.ax.text(
                    i, total_sqft + (self.ax.get_ylim()[1] * 0.02),
                    label_text, ha='center', va='bottom',
                    color='#f39c12' if tier_used else '#adb5bd',
                    fontsize=7, fontweight='bold'
                )
                # Jobs inside bar
                y_pos = booked / 2 if booked > 0 else booked + (scheduled / 2)
                display_jobs = jobs + (1 if scheduled > 0 else 0)
                self.ax.text(
                    i, y_pos,
                    f'{int(display_jobs)}', ha='center', va='center',
                    color='white', fontsize=7, fontweight='bold',
                    bbox=dict(boxstyle='round,pad=0.3', facecolor='#34495e',
                            edgecolor='none', alpha=0.8)
                )

        # Add right Y-axis for minutes
        if self.ax_mins is None:
            self.ax_mins = self.ax.twinx()
        else:
            self.ax_mins.clear() 
            # Only create the twin once

        # 1. Initialize the series with 0.0 for all dates in the chart range
        daily_booked = pd.Series(0.0, index=dates)
        daily_mins = pd.Series(0.0, index=dates)

        # Map existing bookings
        if booked_df is not None and not booked_df.empty:
            p_booked = booked_df[booked_df['process_id'] == proc_id].copy()
            p_booked['schedule_date'] = pd.to_datetime(p_booked['schedule_date']).dt.date
            
            # Calculate sums
            booked_sums = p_booked.groupby('schedule_date')['booked_sqft'].sum()
            mins_sums = p_booked.groupby('schedule_date')['mins_booked'].sum()
            
            # Reindex to exactly the 25 dates range, filling outside dates with 0
            daily_booked = booked_sums.reindex(dates, fill_value=0.0)
            daily_mins = mins_sums.reindex(dates, fill_value=0.0)

        # Map scheduled additions
        if scheduled_additions:
            formatted_additions = {
                (pd.to_datetime(d).date() if isinstance(d, (str, pd.Timestamp)) else d): float(sqft)
                for d, sqft in scheduled_additions.items()
            }
            # Add to daily_booked and reindex again to ensure shape remains (25,)
            added_series = pd.Series(formatted_additions).reindex(dates, fill_value=0.0)
            daily_scheduled = added_series
                
        # Draw the Stem Plot time
        markerline, stemlines, baseline = self.ax_mins.stem(
            x, daily_mins.values,
            linefmt=':', 
            markerfmt='o', 
            basefmt=" "
        )
        plt.setp(stemlines, 'color', '#1abc9c', 'alpha', 0.5)
        plt.setp(markerline, 'color', '#1abc9c', 'markersize', 4)

        # Conver to HH:MM Format on the right
        self.ax_mins.yaxis.set_major_formatter(
            mticker.FuncFormatter(lambda val, pos: f'{int(val//60):02d}:{int(val%60):02d}')
        )

        # APPLY STYLING (Clearing the axis removes these)
        self.ax_mins.set_ylabel('Hours Booked', color='#1abc9c', fontsize=10, fontweight='bold', labelpad=10)
        self.ax_mins.tick_params(axis='y', colors='#1abc9c')

        # Explicitly ensure the spine is visible and on the right
        self.ax_mins.spines['right'].set_visible(True)
        self.ax_mins.spines['right'].set_color('#1abc9c')
        self.ax_mins.yaxis.set_label_position("right")
        self.ax_mins.yaxis.tick_right()

        # Optional: minutes labels on top of line
        for i, mins in enumerate(daily_mins.values):
            if mins > 0:
                self.ax_mins.text(i + 0.05, mins, f'{int(mins//60):02d}:{int(mins%60):02d}h', color='#1abc9c', fontsize=7, va='center')

        # X-axis formatting
        self.ax.set_xlabel('Date', color='#adb5bd', fontsize=10, fontweight='bold')
        self.ax.set_ylabel('Capacity (SqFt)', color='#adb5bd', fontsize=10, fontweight='bold')
        self.ax.set_xticks(x)
        self.ax.set_xticklabels([d.strftime('%m/%d') for d in dates],
                                rotation=45, ha='right', color='#adb5bd', fontsize=8)
        self.ax.tick_params(colors='#adb5bd')
        self.ax.grid(True, alpha=0.2, color='#adb5bd', linestyle='--', linewidth=0.5, axis='y')
        self.ax.set_axisbelow(True)

        # Legend
        # self.ax.legend(loc='upper left', facecolor='#2b3e50', edgecolor='#adb5bd',
        #             labelcolor='#adb5bd', fontsize=9, framealpha=0.9)
        
        self.ax.legend(
            loc='lower left',
            bbox_to_anchor=(0, 1.02),
            ncol=2,
            facecolor='#2b3e50',
            edgecolor='#adb5bd',
            labelcolor='#adb5bd',
            fontsize=9,
            framealpha=0.9
        )

        # Summary stats
        total_booked = daily_booked.sum()
        total_scheduled = daily_scheduled.sum()
        total_jobs = daily_jobs.sum()
        summary = f"Existing: {total_booked:,.0f} sqft ({int(total_jobs)} jobs) | Scheduled: {total_scheduled:,.0f} mins | Required: {required_sqft:,.0f} sqft"
        self.ax.text(
            0.98, 0.98, summary, transform=self.ax.transAxes,
            fontsize=8, color='#adb5bd', ha='right', va='top',
            bbox=dict(boxstyle='round', facecolor='#2b3e50', edgecolor='#adb5bd', alpha=0.8)
        )

        # Style spines
        self.ax.spines['bottom'].set_color('#adb5bd')
        self.ax.spines['left'].set_color('#adb5bd')
        self.ax.spines['top'].set_visible(False)
        self.ax.spines['right'].set_visible(False)

        # Add some padding at top for labels
        y_max = self.ax.get_ylim()[1]
        self.ax.set_ylim(0, y_max * 1.15)

        self.fig.tight_layout()
        self.canvas.draw_idle()

    def show_breakdown_window(date_obj, df):
        """Styled popup window for schedule details."""
        top = tk.Toplevel()
        top.title(f"Breakdown: {date_obj.strftime('%m/%d/%Y')}")
        top.geometry("700x450")
        top.configure(bg='#2b3e50') # Match chart background

        # 1. Create a Custom Style for the Treeview
        style = ttk.Style()
        style.theme_use("default") # Base theme that allows color overrides

        # Style the Main Treeview area
        style.configure("Treeview",
            background="#2b3e50",
            foreground="#ffffff",
            fieldbackground="#2b3e50",
            rowheight=30,
            borderwidth=0,
            font=('Segoe UI', 10)
        )
        
        # Style the Headers
        style.configure("Treeview.Heading",
            background="#34495e",  # Slightly lighter blue for contrast
            foreground="#adb5bd",  # Grey text like chart labels
            font=('Segoe UI', 10, 'bold'),
            borderwidth=1
        )
        
        # Change color when a row is selected
        style.map("Treeview", background=[('selected', '#3498db')])

        # Layout Elements
        title_label = tk.Label(
            top, text=f"Jobs Scheduled for {date_obj.strftime('%A, %b %d')}",
            bg='#2b3e50', fg='#f39c12',  # Orange accent from your chart
            font=('Segoe UI', 12, 'bold'), pady=10
        )
        title_label.pack()

        # Create Frame for Treeview and Scrollbar
        container = tk.Frame(top, bg='#2b3e50')
        container.pack(fill="both", expand=True, padx=15, pady=5)

        # Build the Treeview
        cols = list(df.columns)
        tree = ttk.Treeview(container, columns=cols, show='headings', style="Treeview")
        
        for col in cols:
            # Format headers to be user-friendly
            clean_name = col.replace('_', ' ').title()
            tree.heading(col, text=clean_name)
            tree.column(col, width=110, anchor="center")

        # Add Scrollbar
        scrollbar = ttk.Scrollbar(container, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=scrollbar.set)

        # Insert Data & Alternating Row Colors
        tree.tag_configure('oddrow', background='#324458') # Subtle zebra striping
        tree.tag_configure('evenrow', background='#2b3e50')

        for i, row in enumerate(df.itertuples(index=False)):
            tag = 'oddrow' if i % 2 == 0 else 'evenrow'
            tree.insert("", "end", values=row, tags=(tag,))

        tree.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        # Footer Summary
        summary_text = f"Total Dockets: {len(df)} | Total SqFt: {df['booked_sqft'].sum():,.0f}" if 'booked_sqft' in df else ""
        footer = tk.Label(top, text=summary_text, bg='#2b3e50', fg='#adb5bd', font=('Segoe UI', 9))
        footer.pack(pady=10)

        # Close button with chart accent color
        btn = tk.Button(
            top, text="CLOSE", command=top.destroy, 
            bg='#e74c3c', fg='white', font=('Segoe UI', 9, 'bold'),
            relief="flat", padx=20, pady=5, cursor="hand2"
        )
        btn.pack(pady=10)
