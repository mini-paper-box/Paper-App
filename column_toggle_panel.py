import tkinter as tk
from tkinter import ttk

class ColumnTogglePanel(tk.Toplevel):
    def __init__(self, master, columns, toggle_callback):
        super().__init__(master)
        self.title("Toggle Columns")
        self.toggle_callback = toggle_callback
        self.geometry("200x200")
        self.resizable(False, False)

        self.column_vars = {}
        for col in columns:
            var = tk.BooleanVar(value=True)
            cb = ttk.Checkbutton(self, text=col, variable=var, 
                                 command=lambda c=col, v=var: self.toggle_callback(c, v.get()))
            cb.pack(anchor='w', padx=10, pady=2)
            self.column_vars[col] = var

        self.protocol("WM_DELETE_WINDOW", self.withdraw)  # Hide instead of destroy

    def get_state(self):
        return {col: var.get() for col, var in self.column_vars.items()}

    def set_state(self, state):
        for col, value in state.items():
            if col in self.column_vars:
                self.column_vars[col].set(value)
                self.toggle_callback(col, value)
