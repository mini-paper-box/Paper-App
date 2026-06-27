import pandas as pd

class CapacityEngine:
    def __init__(self):
        self.shift_mins = 480       # Standard 8-hour shift
        self.buffer_percent = 0.90  # 10% maintenance/break buffer
        self.max_daily_mins = self.shift_mins * self.buffer_percent

    def get_remaining_capacity(self, booked_mins):
        """Calculates available space on a machine for a given day."""
        remaining = self.max_daily_mins - booked_mins
        return max(0, remaining)

    def build_matrix(self, raw_capacity_df, percentile=0.8):
        if raw_capacity_df is None or raw_capacity_df.empty:
            return pd.DataFrame(columns=['process_id', 'job_count', 'p80_capacity'])

        # 1. Statistical P80 Calculation
        matrix = (raw_capacity_df
                .groupby(['process_id', 'job_count'])['daily_msf']
                .quantile(percentile)
                .reset_index())
        
        # 2. Synthetic Fallback (The 7% Tax)
        # If a process only has data for 1 or 2 jobs, we project the rest
        clean_data = []
        for pid in matrix['process_id'].unique():
            proc_matrix = matrix[matrix['process_id'] == pid]
            
            # Use the P80 of 1 job as the 'Anchor'
            anchor_row = proc_matrix[proc_matrix['job_count'] == 1]
            if not anchor_row.empty:
                anchor = anchor_row['daily_msf'].iloc[0]
            else:
                anchor = proc_matrix['daily_msf'].max() * 0.8
                
            for jc in range(1, 16):
                # Check if we have real historical data for this job count
                hist_match = proc_matrix[proc_matrix['job_count'] == jc]
                
                if not hist_match.empty:
                    val = hist_match['daily_msf'].iloc[0]
                else:
                    # Project using the 7% tax logic if no history exists
                    tax = anchor * (0.07 * (jc - 1))
                    val = max(anchor - tax, anchor * 0.30)
                    
                clean_data.append({'process_id': pid, 'job_count': jc, 'p80_capacity': val})

        return pd.DataFrame(clean_data)

    def get_available_capacity(self, process_id, current_jobs, booked_msf, capacity_matrix):
        """
        Gets available capacity for a process on a specific day.
        
        Args:
            process_id: The process to check
            current_jobs: Number of jobs currently booked
            booked_msf: MSF already booked for this process this day
            capacity_matrix: DataFrame from build_matrix()
        
        Returns:
            float: Available MSF capacity (0 if no capacity available)
        """
        # Look for capacity at the next job tier (current + 1)
        target_jobs = current_jobs + 1
        
        cap_match = capacity_matrix[
            (capacity_matrix['process_id'] == process_id) & 
            (capacity_matrix['job_count'] == target_jobs)
        ]
        
        if cap_match.empty:
            # No exact match - use median capacity for this process
            process_caps = capacity_matrix[capacity_matrix['process_id'] == process_id]
            if process_caps.empty:
                return 0  # No capacity data for this process
            
            # Use the median across all job counts as fallback
            p80_cap = process_caps['p80_capacity'].median()
        else:
            # Use the P80 capacity for this specific job count
            p80_cap = cap_match['p80_capacity'].iloc[0]
        
        # Calculate available capacity
        available = max(p80_cap - booked_msf, 0)
        return available

    def can_schedule_job(self, process_id, required_msf, current_jobs, booked_msf, 
                        capacity_matrix, min_threshold=100):
        """
        Determines if a job can be scheduled on a given day.
        
        Args:
            process_id: The process to check
            required_msf: MSF required for the job
            current_jobs: Number of jobs currently booked
            booked_msf: MSF already booked
            capacity_matrix: DataFrame from build_matrix()
            min_threshold: Minimum available capacity to consider (default 100)
        
        Returns:
            tuple: (can_schedule: bool, available_capacity: float, tier_used: int)
        """
        available = self.get_available_capacity(
            process_id, current_jobs, booked_msf, capacity_matrix
        )
        
        can_schedule = available >= min_threshold
        tier_used = current_jobs + 1 if can_schedule else None
        
        return can_schedule, available, tier_used

    def get_process_summary(self, process_id, capacity_matrix):
        """
        Gets a summary of capacity for a specific process across all job counts.
        
        Args:
            process_id: The process to summarize
            capacity_matrix: DataFrame from build_matrix()
        
        Returns:
            DataFrame with job_count and p80_capacity for this process
        """
        if capacity_matrix is None or capacity_matrix.empty:
            return pd.DataFrame(columns=['job_count', 'p80_capacity'])
        
        process_data = capacity_matrix[
            capacity_matrix['process_id'] == process_id
        ].sort_values('job_count')
        
        return process_data[['job_count', 'p80_capacity']].reset_index(drop=True)