import tkinter as tk
from tkinter import ttk
import pyautogui
import pyperclip
import time
import threading

class AutoUnitize(tk.Frame):
    def __init__(self, master=None, title="Auto Unitize Tool"):
        super().__init__(master)
        self.master = master
        self.running = False

        if isinstance(master, tk.Tk):
            self.master.title(title)

        self.create_widgets()

    def create_widgets(self):
        # Configure grid weights for responsiveness
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        # --- Text Input ---
        ttk.Label(self, text="Enter items (one per line):").grid(row=0, column=0, sticky="w", padx=10, pady=(10, 2))
        self.text_input = tk.Text(self, height=10, width=50)
        self.text_input.grid(row=1, column=0, sticky="nsew", padx=10, pady=2)

        # --- Timing Controls ---
        controls_frame = ttk.LabelFrame(self, text="Timing Settings")
        controls_frame.grid(row=2, column=0, sticky="ew", padx=10, pady=8)
        controls_frame.grid_columnconfigure((1, 3), weight=1)

        self.start_delay_var = tk.DoubleVar(value=5.0)
        self.interval_var = tk.DoubleVar(value=0.5)

        ttk.Label(controls_frame, text="Start delay (s):").grid(row=0, column=0, padx=5, pady=5, sticky="e")
        ttk.Spinbox(
            controls_frame, from_=0, to=30, increment=0.5,
            textvariable=self.start_delay_var, width=6
        ).grid(row=0, column=1, padx=5, pady=5, sticky="w")

        ttk.Label(controls_frame, text="Interval (s):").grid(row=0, column=2, padx=5, pady=5, sticky="e")
        ttk.Spinbox(
            controls_frame, from_=0, to=5, increment=0.1,
            textvariable=self.interval_var, width=6
        ).grid(row=0, column=3, padx=5, pady=5, sticky="w")

        # --- Buttons ---
        button_frame = ttk.Frame(self)
        button_frame.grid(row=3, column=0, pady=10)
        button_frame.grid_columnconfigure((0, 1), weight=1)

        self.start_button = ttk.Button(button_frame, text="Start", command=self.start_loop)
        self.start_button.grid(row=0, column=0, padx=10, sticky="ew")

        self.stop_button = ttk.Button(button_frame, text="Stop", command=self.stop_loop, state="disabled")
        self.stop_button.grid(row=0, column=1, padx=10, sticky="ew")

        # --- Status Label ---
        self.status_label = ttk.Label(self, text="", anchor="center")
        self.status_label.grid(row=4, column=0, sticky="ew", padx=10, pady=(5, 10))

    def start_loop(self):
        raw_text = self.text_input.get("1.0", tk.END).strip()
        if not raw_text:
            self.status_label.config(text="Please enter at least one item.")
            return

        items = raw_text.splitlines()
        start_delay = float(self.start_delay_var.get())
        interval = float(self.interval_var.get())

        self.status_label.config(text=f"Starting in {start_delay}s... Switch to target window!")
        self.start_button.config(state="disabled")
        self.stop_button.config(state="normal")
        self.running = True

        threading.Thread(
            target=self.paste_and_enter,
            args=(items, start_delay, interval),
            daemon=True
        ).start()

    def stop_loop(self):
        self.running = False
        self.start_button.config(state="normal")
        self.stop_button.config(state="disabled")
        self.status_label.config(text="Stopped.")

    def paste_and_enter(self, items, start_delay, interval):
        time.sleep(start_delay)

        for i, item in enumerate(items, start=1):
            if not self.running:
                return

            pyperclip.copy(item.strip())
            pyautogui.hotkey("ctrl", "v")
            pyautogui.press("enter")
            self.status_label.config(text=f"Sent {i}/{len(items)}")
            time.sleep(interval)

        self.status_label.config(text="✅ Done.")
        self.start_button.config(state="normal")
        self.stop_button.config(state="disabled")
        self.running = False


if __name__ == "__main__":
    root = tk.Tk()
    root.geometry("420x400")
    app = AutoUnitize(root)
    app.grid(sticky="nsew")  # fill the window with frame
    root.grid_columnconfigure(0, weight=1)
    root.grid_rowconfigure(0, weight=1)
    root.mainloop()
