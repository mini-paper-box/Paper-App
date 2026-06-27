import pandas as pd
import matplotlib.pyplot as plt
from pathlib import Path
from datetime import datetime, timedelta
from typing import Optional, Tuple


class OnTimeChart:
    """Generates charts for on-time delivery performance analysis."""

    def __init__(self, output_dir: Path):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        plt.style.use('ggplot')

    @staticmethod
    def get_previous_week_range() -> Tuple[datetime, datetime]:
        """
        Get the date range for the previous complete week (Sun-Sat).
        
        Returns:
            Tuple of (start_date, end_date) for previous week
        """
        today = datetime.now()
        
        # Calculate days since last Sunday
        days_since_sunday = (today.weekday() + 1) % 7  # Sunday = 0
        
        # Last week's Sunday (start)
        last_sunday = (today - timedelta(days=days_since_sunday + 7)).replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        
        # Last week's Saturday (end)
        last_saturday = last_sunday + timedelta(days=6, hours=23, minutes=59, seconds=59)
        
        return last_sunday, last_saturday

    @staticmethod
    def filter_previous_week(df: pd.DataFrame, date_column: str = 'requested_date') -> pd.DataFrame:
        """
        Filter dataframe to only include previous week's data (Sun-Sat).
        
        Args:
            df: Input dataframe
            date_column: Name of the date column to filter on
            
        Returns:
            Filtered dataframe containing only previous week's data
        """
        if df.empty:
            return df
        
        # Ensure date column is datetime
        df = df.copy()
        if not pd.api.types.is_datetime64_any_dtype(df[date_column]):
            df[date_column] = pd.to_datetime(df[date_column])
        
        # Get previous week range
        start_date, end_date = OnTimeChart.get_previous_week_range()
        
        # Filter
        mask = (df[date_column] >= start_date) & (df[date_column] <= end_date)
        filtered_df = df[mask].copy()
        
        return filtered_df

    @staticmethod
    def get_current_week_range() -> Tuple[datetime, datetime]:
        """
        Get the date range for the current week (Sun-Sat).
        
        Returns:
            Tuple of (start_date, end_date) for current week
        """
        today = datetime.now()
        
        # Calculate days since last Sunday
        days_since_sunday = (today.weekday() + 1) % 7  # Sunday = 0
        
        # This week's Sunday (start)
        this_sunday = (today - timedelta(days=days_since_sunday)).replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        
        # This week's Saturday (end) or today if we haven't reached Saturday yet
        this_saturday = this_sunday + timedelta(days=6, hours=23, minutes=59, seconds=59)
        
        return this_sunday, min(this_saturday, today)

    @staticmethod
    def filter_current_week(df: pd.DataFrame, date_column: str = 'requested_date') -> pd.DataFrame:
        """
        Filter dataframe to only include current week's data (Sun-today).
        
        Args:
            df: Input dataframe
            date_column: Name of the date column to filter on
            
        Returns:
            Filtered dataframe containing only current week's data
        """
        if df.empty:
            return df
        
        # Ensure date column is datetime
        df = df.copy()
        if not pd.api.types.is_datetime64_any_dtype(df[date_column]):
            df[date_column] = pd.to_datetime(df[date_column])
        
        # Get current week range
        start_date, end_date = OnTimeChart.get_current_week_range()
        
        # Filter
        mask = (df[date_column] >= start_date) & (df[date_column] <= end_date)
        filtered_df = df[mask].copy()
        
        return filtered_df

    @staticmethod
    def get_week_metrics(df: pd.DataFrame) -> dict:
        """
        Calculate summary metrics for a given dataframe.
        
        Args:
            df: DataFrame with on_time_code column (1=on time, -1=late)
            
        Returns:
            Dictionary with metrics: total_orders, on_time_count, on_time_pct, avg_days
        """
        if df.empty:
            return {
                'total_orders': 0,
                'on_time_count': 0,
                'on_time_pct': 0.0,
                'avg_days': 0.0
            }
        
        total_orders = len(df)
        
        # Use on_time_code (1 = on time, -1 = late)
        on_time_count = len(df[df['on_time_code'] == 1])
        on_time_pct = (on_time_count / total_orders * 100) if total_orders > 0 else 0.0
        
        # Average days difference (use num_days column)
        avg_days = df['num_days'].mean() if 'num_days' in df.columns else 0.0
        avg_days = 0.0 if pd.isna(avg_days) else avg_days
        
        return {
            'total_orders': total_orders,
            'on_time_count': on_time_count,
            'on_time_pct': on_time_pct,
            'avg_days': avg_days
        }

    def build(self, df: pd.DataFrame) -> Path:
        """Legacy method - generates status code bar chart using on_time_dsc."""
        if df.empty:
            return self._create_empty_chart("on_time_performance.png")

        # 1. Aggregate counts for each status description
        status_counts = df['on_time_dsc'].value_counts().sort_index()
        
        # 2. Define Colors (On Time/Early = green, others = red)
        colors = [
            '#2ecc71' if code in ['On Time', 'Early'] else '#e74c3c' 
            for code in status_counts.index
        ]

        # 3. Plotting
        fig, ax = plt.subplots(figsize=(10, 6), dpi=100)
        
        # Create the bars
        bars = ax.bar(status_counts.index, status_counts.values, color=colors, edgecolor='#333333')

        # 4. Formatting
        ax.set_title('Order Volume by Status', fontsize=16, pad=20, fontweight='bold')
        ax.set_xlabel('Status', fontsize=12, fontweight='bold')
        ax.set_ylabel('Number of Orders', fontsize=12, fontweight='bold')
        
        # Add a custom legend
        from matplotlib.lines import Line2D
        legend_elements = [
            Line2D([0], [0], color='#2ecc71', lw=4, label='On Time / Early'),
            Line2D([0], [0], color='#e74c3c', lw=4, label='Late / Other')
        ]
        ax.legend(handles=legend_elements, loc='upper right')

        # 5. Add value labels on top of bars
        for bar in bars:
            height = bar.get_height()
            ax.text(
                bar.get_x() + bar.get_width()/2., 
                height + (max(status_counts.values) * 0.01),
                f'{int(height)}',
                ha='center', va='bottom', fontweight='bold'
            )

        plt.tight_layout()
        
        # 6. Save
        output_path = self.output_dir / "on_time_performance.png"
        fig.savefig(output_path, bbox_inches='tight')
        plt.close(fig)
        
        return output_path
    
    def build_weekly_trend(self, df: pd.DataFrame) -> Path:
        """
        Shows daily performance for a single week or weekly aggregation for multiple weeks.
        Automatically adapts based on date range.
        """
        if df.empty:
            return self._create_empty_chart("weekly_trend.png")

        df = df.copy()

        # Ensure requested_date is datetime
        if not pd.api.types.is_datetime64_any_dtype(df['requested_date']):
            df['requested_date'] = pd.to_datetime(df['requested_date'])

        # Determine if this is a single week or multi-week dataset
        date_range = (df['requested_date'].max() - df['requested_date'].min()).days
        
        if date_range <= 7:
            # DAILY VIEW (for single week)
            return self._build_daily_trend(df)
        else:
            # WEEKLY VIEW (for multiple weeks)
            return self._build_multi_week_trend(df)

    def _build_daily_trend(self, df: pd.DataFrame) -> Path:
        """Daily breakdown for a single week."""
        df = df.copy()
        
        # Create date labels
        df['date_label'] = df['requested_date'].dt.strftime('%a\n%m/%d')
        df['sort_date'] = df['requested_date'].dt.date
        
        # Binary grouping using on_time_code (1 = On Time, -1 = Late)
        df['status_group'] = df['on_time_code'].apply(
            lambda x: 'On Time' if x == 1 else 'Late'
        )
        
        # Group by date and status
        summary = df.groupby(['sort_date', 'date_label', 'status_group']).size().reset_index(name='count')
        summary = summary.pivot_table(
            index=['sort_date', 'date_label'],
            columns='status_group',
            values='count',
            fill_value=0
        ).reset_index()
        
        # Ensure both columns exist
        for col in ['On Time', 'Late']:
            if col not in summary.columns:
                summary[col] = 0
        
        # Sort by date
        summary = summary.sort_values('sort_date')
        
        # Calculate percentages
        summary['Total'] = summary['On Time'] + summary['Late']
        summary['On Time %'] = (summary['On Time'] / summary['Total'] * 100).fillna(0)
        summary['Late %'] = (summary['Late'] / summary['Total'] * 100).fillna(0)
        
        # Prepare for plotting
        summary_plot = summary.set_index('date_label')
        summary_pct = summary_plot[['On Time %', 'Late %']].copy()
        summary_pct.columns = ['On Time', 'Late']
        
        # Plot
        fig, ax = plt.subplots(figsize=(12, 5), dpi=100)
        
        summary_pct.plot(
            kind='bar',
            stacked=True,
            ax=ax,
            color=['#2ecc71', '#e74c3c'],
            width=0.4,
            edgecolor='white',
            linewidth=0.5
        )
        
        # Title
        start_date = summary['sort_date'].min()
        end_date = summary['sort_date'].max()
        ax.set_title(
            f'Daily On-Time Performance ({start_date:%b %d} – {end_date:%b %d})',
            fontsize=14, fontweight='bold', pad=15
        )
        
        ax.set_xlabel('Date', fontsize=11, fontweight='bold')
        ax.set_ylabel('Percentage (%)', fontsize=11, fontweight='bold')
        ax.set_ylim(0, 105)
        
        # Add percentage labels
        for i, (idx, row) in enumerate(summary_pct.iterrows()):
            if row['On Time'] > 5:
                ax.text(i, row['On Time'] / 2, f"{row['On Time']:.0f}%",
                       ha='center', va='center', fontweight='bold',
                       color='white', fontsize=9)
            
            if row['Late'] > 5:
                ax.text(i, row['On Time'] + row['Late'] / 2, f"{row['Late']:.0f}%",
                       ha='center', va='center', fontweight='bold',
                       color='white', fontsize=9)
        
        # Add sample counts
        for i, (idx, row) in enumerate(summary_plot.iterrows()):
            total = int(row['Total'])
            ax.text(i, -8, f'n={total}', ha='center', va='top', fontsize=8, color='#555')
        
        ax.legend(loc='upper left', framealpha=0.9)
        plt.xticks(rotation=0)
        plt.tight_layout()
        
        path = self.output_dir / "weekly_trend.png"
        fig.savefig(path, bbox_inches='tight')
        plt.close(fig)
        
        return path

    def _build_multi_week_trend(self, df: pd.DataFrame) -> Path:
        """Weekly aggregation for multiple weeks."""
        df = df.copy()

        # ISO year/week (prevents week 1 collisions across years)
        iso = df['requested_date'].dt.isocalendar()
        df['iso_year'] = iso.year
        df['iso_week'] = iso.week

        # Week start / end for labeling (Monday-based for ISO week)
        df['week_start'] = df['requested_date'] - pd.to_timedelta(df['requested_date'].dt.weekday, unit='D')
        df['week_end'] = df['week_start'] + pd.Timedelta(days=6)

        df['week_label'] = (
            # 'Wk ' + df['iso_week'].astype(str) +
            # '\n' +
            df['week_start'].dt.strftime('%b %d') +
            '–' +
            df['week_end'].dt.strftime('%b %d')
        )

        # Binary grouping using on_time_code (1 = On Time, -1 = Late)
        df['status_group'] = df['on_time_code'].apply(
            lambda x: 'On Time' if x == 1 else 'Late'
        )

        # Aggregate weekly counts
        summary = (
            df.groupby(['iso_year', 'iso_week', 'week_label', 'week_start', 'status_group'])
            .size()
            .reset_index(name='count')
        )

        summary = summary.pivot_table(
            index=['iso_year', 'iso_week', 'week_label', 'week_start'],
            columns='status_group',
            values='count',
            fill_value=0
        ).reset_index()

        # Ensure both columns exist
        for col in ['On Time', 'Late']:
            if col not in summary.columns:
                summary[col] = 0

        # Sort chronologically
        summary = summary.sort_values(['iso_year', 'iso_week'])

        # Calculate totals and percentages
        summary['Total'] = summary['On Time'] + summary['Late']
        summary['On Time %'] = (summary['On Time'] / summary['Total'] * 100).fillna(0)
        summary['Late %'] = (summary['Late'] / summary['Total'] * 100).fillna(0)

        # Prepare for plotting
        summary_plot = summary.set_index('week_label')
        summary_pct = summary_plot[['On Time %', 'Late %']].copy()
        summary_pct.columns = ['On Time', 'Late']

        # Plot
        fig, ax = plt.subplots(figsize=(max(12, len(summary) * 2), 5), dpi=100)

        summary_pct.plot(
            kind='bar',
            stacked=True,
            ax=ax,
            color=['#2ecc71', '#e74c3c'],
            width=0.4,
            edgecolor='white',
            linewidth=0.5
        )

        # Title with date range
        start_week = summary['week_start'].min()
        end_week = summary['week_start'].max() + pd.Timedelta(days=6)

        title = f'Weekly On-Time Performance Trend ({start_week:%b %d} – {end_week:%b %d})'
        ax.set_title(title, fontsize=14, fontweight='bold', pad=15)
        ax.set_xlabel('Week', fontsize=11, fontweight='bold')
        ax.set_ylabel('Percentage (%)', fontsize=11, fontweight='bold')
        ax.set_ylim(0, 105)

        # Add percentage labels on bars
        for i, (idx, row) in enumerate(summary_pct.iterrows()):
            on_time_pct = row['On Time']
            late_pct = row['Late']

            if on_time_pct > 5:
                ax.text(
                    i, on_time_pct / 2, f"{on_time_pct:.0f}%",
                    ha='center', va='center', fontweight='bold',
                    color='white', fontsize=9
                )

            if late_pct > 5:
                ax.text(
                    i, on_time_pct + late_pct / 2, f"{late_pct:.0f}%",
                    ha='center', va='center', fontweight='bold',
                    color='white', fontsize=9
                )

        # Add sample count labels below x-axis
        for i, (idx, row) in enumerate(summary_plot.iterrows()):
            total = int(row['Total'])
            ax.text(
                i, -8, f'n={total}',
                ha='center', va='top', fontsize=8, color='#555'
            )

        ax.legend(loc='upper left', framealpha=0.9)
        plt.xticks(rotation=0)
        plt.tight_layout()

        path = self.output_dir / "weekly_trend.png"
        fig.savefig(path, bbox_inches='tight')
        plt.close(fig)

        return path

    def build_ytd_summary(self, df: pd.DataFrame) -> Path:
        """Shows total volume per status code for the year."""
        if df.empty:
            return self._create_empty_chart("ytd_summary.png")
        
        # Get status counts using on_time_dsc and sort by value
        status_counts = df['on_time_dsc'].value_counts().sort_values(ascending=True)
        
        # Assign colors (On Time/Early = green, others = red)
        colors = ['#2ecc71' if x in ['On Time', 'Early'] else '#e74c3c' for x in status_counts.index]

        # Plotting
        fig, ax = plt.subplots(figsize=(10, 6), dpi=100)
        
        bars = status_counts.plot(
            kind='barh', 
            color=colors, 
            ax=ax,
            edgecolor='#333333',
            linewidth=0.5
        )
        
        ax.set_title('Year-to-Date: Order Volume by Status', fontsize=14, fontweight='bold', pad=15)
        ax.set_xlabel('Number of Orders', fontsize=11, fontweight='bold')
        ax.set_ylabel('Status', fontsize=11, fontweight='bold')
        
        # Add value labels at the end of bars
        for i, v in enumerate(status_counts):
            ax.text(v + (status_counts.max() * 0.02), i, f' {v:,}', 
                   va='center', fontweight='bold', fontsize=10)
        
        # Add legend
        from matplotlib.patches import Patch
        legend_elements = [
            Patch(facecolor='#2ecc71', edgecolor='#333333', label='On Time / Early'),
            Patch(facecolor='#e74c3c', edgecolor='#333333', label='Late / Other')
        ]
        ax.legend(handles=legend_elements, loc='lower right', framealpha=0.9)
        
        plt.tight_layout()
        
        path = self.output_dir / "ytd_summary.png"
        fig.savefig(path, bbox_inches='tight')
        plt.close(fig)
        
        return path

    def _create_empty_chart(self, filename: str = "no_data.png") -> Path:
        """Creates a placeholder chart when no data is available."""
        fig, ax = plt.subplots(figsize=(10, 6), dpi=100)
        
        ax.text(
            0.5, 0.5, 
            "No Data Available\n\nNo orders found for the selected period.", 
            ha='center', 
            va='center', 
            fontsize=14,
            color='#7f8c8d',
            weight='bold'
        )
        ax.set_xlim(0, 1)
        ax.set_ylim(0, 1)
        ax.set_axis_off()
        
        path = self.output_dir / filename
        fig.savefig(path, bbox_inches='tight')
        plt.close(fig)
        
        return path