import tkinter as tk
from tkinter import ttk
from ttkbootstrap import Style
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import random

class HoverChartApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Interactive Chart with Hover Tooltips")
        self.style = Style("cosmo")

        self.create_widgets()
        self.plot_chart()

    def create_widgets(self):
        # Control panel
        control_frame = ttk.Frame(self.root, padding=10)
        control_frame.pack(fill="x")

        ttk.Label(control_frame, text="Chart Type:").pack(side="left", padx=5)
        self.chart_type = ttk.Combobox(control_frame, values=["Bar", "Line"], state="readonly")
        self.chart_type.set("Bar")
        self.chart_type.pack(side="left", padx=5)

        ttk.Button(control_frame, text="Refresh Chart", command=self.plot_chart).pack(side="left", padx=10)

        # Matplotlib figure
        self.figure = plt.Figure(figsize=(6, 4), dpi=100)
        self.ax = self.figure.add_subplot(111)
        self.canvas = FigureCanvasTkAgg(self.figure, master=self.root)
        self.canvas.get_tk_widget().pack(fill="both", expand=True)

        # Connect mouse hover event
        self.canvas.mpl_connect("motion_notify_event", self.on_hover)

        # Annotation (tooltip)
        self.annot = self.ax.annotate(
            "",
            xy=(0, 0),
            xytext=(15, 15),
            textcoords="offset points",
            bbox=dict(boxstyle="round,pad=0.5", fc="yellow", alpha=0.8),
            arrowprops=dict(arrowstyle="->", color="gray"),
        )
        self.annot.set_visible(False)

    def plot_chart(self):
        # Create sample data
        self.x_labels = [f"Day {i}" for i in range(1, 11)]
        self.y_values = [random.randint(5, 20) for _ in self.x_labels]

        # Clear and replot
        self.ax.clear()

        if self.chart_type.get() == "Bar":
            self.bars = self.ax.bar(self.x_labels, self.y_values, color="skyblue")
            self.points = None
        else:
            self.bars = None
            self.points, = self.ax.plot(self.x_labels, self.y_values, marker="o", linestyle="-", color="teal")

        self.ax.set_title("Production Output per Day")
        self.ax.set_xlabel("Date")
        self.ax.set_ylabel("Jobs")
        self.ax.grid(True, linestyle="--", alpha=0.6)
        self.figure.tight_layout()
        self.canvas.draw()

    def update_annot(self, x, y, label):
        """Update position and text of the annotation tooltip."""
        self.annot.xy = (x, y)
        text = f"{label}\nJobs: {y}"
        self.annot.set_text(text)
        self.annot.get_bbox_patch().set_alpha(0.8)

    def on_hover(self, event):
        """Handle mouse hover over data points or bars."""
        vis = self.annot.get_visible()
        if event.inaxes == self.ax:
            if self.chart_type.get() == "Bar" and self.bars:
                for bar, label, y in zip(self.bars, self.x_labels, self.y_values):
                    contains, _ = bar.contains(event)
                    if contains:
                        self.update_annot(bar.get_x() + bar.get_width()/2, y, label)
                        self.annot.set_visible(True)
                        self.canvas.draw_idle()
                        return
            elif self.chart_type.get() == "Line" and self.points:
                for i, (x, y) in enumerate(zip(range(len(self.x_labels)), self.y_values)):
                    if abs(event.xdata - x) < 0.3 and abs(event.ydata - y) < 1:
                        self.update_annot(x, y, self.x_labels[i])
                        self.annot.set_visible(True)
                        self.canvas.draw_idle()
                        return
        if vis:
            self.annot.set_visible(False)
            self.canvas.draw_idle()

if __name__ == "__main__":
    root = tk.Tk()
    app = HoverChartApp(root)
    root.mainloop()
