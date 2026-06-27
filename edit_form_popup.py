import tkinter as tk
from tkinter import ttk, messagebox
from ttkbootstrap import DateEntry

class EditFormPopup(tk.Toplevel):
    def __init__(self, parent, title, field_config, row_data, on_submit):
        super().__init__(parent)
        self.title(title)
        self.geometry("600x800")
        self.resizable(False, False)
        self.grab_set()
        self.configure(padx=20, pady=20)

        self.field_config = field_config
        self.row_data = row_data
        self.on_submit = on_submit

        self.widgets = {}
        self.errors = {}

        self._build_ui()

    def _build_ui(self):
        ttk.Label(self, text=self.title(), font=("Segoe UI", 12, "bold")).pack(pady=(0, 15))

        form_frame = ttk.Frame(self)
        form_frame.pack(fill="both", expand=True)

        row_num = 0
        for key, config in self.field_config.items():
            label_text = config.get("label", key.title().replace("_", " "))
            widget_type = config.get("type", "text")
            options = config.get("options", [])

            ttk.Label(form_frame, text=label_text).grid(row=row_num, column=0, sticky="e", padx=5, pady=8)

            if widget_type == "dropdown":
                widget = ttk.Combobox(form_frame, values=options, state="readonly", width=22)
                widget.set(self.row_data.get(key, ""))
            elif widget_type == "date":
                widget = DateEntry(form_frame, dateformat="%Y-%m-%d", width=20, bootstyle="secondary")
                try:
                    widget.set_date(self.row_data.get(key, ""))
                except:
                    pass
            elif widget_type == "number":
                var = tk.StringVar(value=self.row_data.get(key, ""))
                widget = ttk.Entry(form_frame, textvariable=var, width=24)
                widget.configure(validate="focusout",
                                validatecommand=lambda v=var, w=widget, k=key: self._validate_number(k, w, v))
                widget.bind("<FocusOut>", lambda e, v=var, w=widget, k=key: self._validate_number(k, w, v))
                self.errors[key] = False
            else:
                widget = ttk.Entry(form_frame, width=24)
                widget.insert(0, self.row_data.get(key, ""))

            widget.grid(row=row_num, column=1, sticky="w", padx=5, pady=8)
            widget.grid(row=row_num, column=2, sticky="w", padx=5, pady=8)
            self.widgets[key] = widget
            row_num += 1

        ttk.Separator(self).pack(fill="x", pady=15)
        btn_frame = ttk.Frame(self)
        btn_frame.pack(pady=5)

        ttk.Button(btn_frame, text="📎 Save", bootstyle="success", command=self._save).pack(side="left", padx=10)
        ttk.Button(btn_frame, text="Cancel", bootstyle="secondary", command=self.destroy).pack(side="left", padx=10)

    def _validate_number(self, key, widget, var):
        # Check if field is exempt from validation
        if not self.field_config.get(key, {}).get("validate", True):
            widget.configure(bootstyle="default")
            self.errors[key] = False
            return

        try:
            float(var.get())
            widget.configure(bootstyle="success")
            self.errors[key] = False
        except ValueError:
            widget.configure(bootstyle="danger")
            self.errors[key] = True

    def _save(self):
        if any(v for k, v in self.errors.items() if self.field_config.get(k, {}).get("validate", True)):
            messagebox.showerror("Validation Error", "Please fix invalid fields.")
            return
        for widget, has_error in self.errors.items():
            if has_error:
                messagebox.showerror("Validation Error", "Please fix numeric fields.")
                return

        updated = {}
        for key, widget in self.widgets.items():
            if hasattr(widget, "entry"):  # DateEntry
                updated[key] = widget.entry.get()
            elif isinstance(widget, ttk.Combobox):
                updated[key] = widget.get()
            else:
                updated[key] = widget.get()

        self.on_submit(updated)
        self.destroy()
