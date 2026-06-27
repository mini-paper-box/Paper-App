import sqlite3
import tkinter as tk
from tkinter import ttk
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import matplotlib.pyplot as plt
import numpy as np
from datetime import datetime, timedelta

# -----------------------------
# Database query
# -----------------------------
def fetch_data():
    conn = sqlite3.connect("prod_db.db")
    cur = conn.cursor()

    query = """
        SELECT p.process_name, o.scheduled_dte, SUM(o.msf) AS total_msf
        FROM order_routing o
        JOIN process p ON o.process_nme = p.process_name
        WHERE p.id IN (1, 2, 3, 6)
        GROUP BY p.process_name, o.scheduled_dte
    """
    cur.execute(query)
    rows = cur.fetchall()
    conn.close()
    return rows

# -----------------------------
# Prepare data
# -----------------------------
def prepare_data(rows):
    # Robust date parsing and mapping
    process_data = {}
    for process_name, day, total_sqft in rows:
        # Parse date regardless of format
        for fmt in ("%Y-%m-%d", "%Y-%m-%d %H:%M", "%Y-%m-%d %H:%M:%S"):
            try:
                date_obj = datetime.strptime(day, fmt).date()
                break
            except ValueError:
                continue
        else:
            date_obj = datetime.strptime(day[:10], "%Y-%m-%d").date()

        process_data.setdefault(date_obj, {})
        process_data[date_obj][process_name] = total_sqft
    return process_data

# -----------------------------
# Generate next 30 weekdays
# -----------------------------
def get_next_30_weekdays():
    today = datetime.today().date()
    days = []
    delta = 0
    while len(days) < 30:
        current = today + timedelta(days=delta)
        if current.weekday() < 5:  # 0=Monday, 4=Friday
            days.append(current)
        delta += 1
    return days

# -----------------------------
# Plot bar graph
# -----------------------------
def plot_graph():
    rows = fetch_data()
    data = prepare_data(rows)
    dates = get_next_30_weekdays()

    # Get all processes
    processes = sorted({p for day_data in data.values() for p in day_data.keys()})

    # Bar settings
    bar_width = 0.15
    x = np.arange(len(dates))

    fig, ax = plt.subplots(figsize=(12, 6))

    for i, process_name in enumerate(processes):
        values = [data.get(date, {}).get(process_name, 0) for date in dates]
        ax.bar(x + i * bar_width, values, width=bar_width, label=process_name)

    ax.set_title("Total SqFt per Process (Next 30 Weekdays)")
    ax.set_xlabel("Date")
    ax.set_ylabel("Total SqFt")
    ax.set_xticks(x + bar_width * (len(processes) - 1) / 2)
    ax.set_xticklabels([d.strftime("%Y-%m-%d") for d in dates], rotation=45, ha="right")
    ax.legend()
    ax.grid(True, axis='y', linestyle='--', alpha=0.7)

    # Embed in Tkinter
    for widget in frame_graph.winfo_children():
        widget.destroy()
    canvas = FigureCanvasTkAgg(fig, master=frame_graph)
    canvas.draw()
    canvas.get_tk_widget().pack(fill="both", expand=True)

# -----------------------------
# Tkinter UI
# -----------------------------
root = tk.Tk()
root.title("Process SqFt Bar Graph (Next 30 Weekdays)")
root.geometry("1200x600")

frame_graph = ttk.Frame(root)
frame_graph.pack(fill="both", expand=True)

plot_graph()

root.mainloop()
