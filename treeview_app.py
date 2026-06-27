import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import csv

class UndoRedoManager:
    def __init__(self):
        self.undo_stack = []
        self.redo_stack = []

    def record(self, undo_action, redo_action):
        self.undo_stack.append((undo_action, redo_action))
        self.redo_stack.clear()

    def undo(self):
        if self.undo_stack:
            undo, redo = self.undo_stack.pop()
            undo()
            self.redo_stack.append((undo, redo))

    def redo(self):
        if self.redo_stack:
            undo, redo = self.redo_stack.pop()
            redo()
            self.undo_stack.append((undo, redo))

class ColumnTogglePanel(tk.Toplevel):
    def __init__(self, master, columns, toggle_callback):
        super().__init__(master)
        self.title("Toggle Columns")
        self.geometry("200x200")
        self.toggle_callback = toggle_callback
        self.resizable(False, False)

        self.column_vars = {}
        for col in columns:
            var = tk.BooleanVar(value=True)
            cb = ttk.Checkbutton(self, text=col, variable=var,
                                 command=lambda c=col, v=var: self.toggle_callback(c, v.get()))
            cb.pack(anchor="w", padx=10, pady=2)
            self.column_vars[col] = var

        self.protocol("WM_DELETE_WINDOW", self.withdraw)

class TreeviewApp(tk.Frame):
    def __init__(self, master):
        super().__init__(master)
        self.columns = ["Item", "Qty", "Price", "Total"]
        self.data = [
            ("Apple", 2, 1.50),
            ("Banana", 3, 2.00),
            ("Cherry", 1, 3.00),
            ("Orange", 5, 0.99),
            ("Peach", 4, 2.25),
            ("Grapes", 6, 2.75)
        ]
        self.undo_redo = UndoRedoManager()
        self.create_widgets()
        self.load_data()

    def create_widgets(self):
        toolbar = tk.Frame(self)
        toolbar.pack(fill=tk.X, padx=5, pady=2)

        tk.Label(toolbar, text="Filter:").pack(side=tk.LEFT)
        self.filter_var = tk.StringVar()
        entry = ttk.Entry(toolbar, textvariable=self.filter_var)
        entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(5, 10))
        self.filter_var.trace_add("write", self.on_filter)

        ttk.Button(toolbar, text="Export CSV", command=self.export_csv).pack(side=tk.RIGHT)
        ttk.Button(toolbar, text="Undo", command=self.undo_redo.undo).pack(side=tk.RIGHT, padx=5)
        ttk.Button(toolbar, text="Redo", command=self.undo_redo.redo).pack(side=tk.RIGHT)
        ttk.Button(toolbar, text="Columns", command=self.toggle_column_panel).pack(side=tk.RIGHT, padx=5)

        self.tree = ttk.Treeview(self, columns=self.columns, show="headings")
        self.tree.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        for col in self.columns:
            self.tree.heading(col, text=col, command=lambda c=col: self.sort_column(c))
            self.tree.column(col, width=100, anchor="center")

        self.tree.bind("<Double-1>", self.edit_cell)
        self.tree.bind("<Button-3>", self.show_context_menu)
        self.tree.bind("<ButtonPress-1>", self.drag_start)
        self.tree.bind("<B1-Motion>", self.drag_motion)
        self.tree.bind("<ButtonRelease-1>", self.drag_end)

        self.context_menu = tk.Menu(self, tearoff=0)
        self.context_menu.add_command(label="Edit", command=self.context_edit)
        self.context_menu.add_command(label="Delete", command=self.context_delete)

        self.drag_data = {"item": None}
        self.column_toggle_panel = None

    def load_data(self):
        self.tree.delete(*self.tree.get_children())
        for item, qty, price in self.data:
            total = round(qty * price, 2)
            self.tree.insert("", "end", values=(item, qty, price, total))
        self.all_data = list(self.data)

    def on_filter(self, *_):
        query = self.filter_var.get().lower()
        self.tree.delete(*self.tree.get_children())
        for row in self.all_data:
            total = round(row[1] * row[2], 2)
            if query in " ".join(map(str, (*row, total))).lower():
                self.tree.insert("", "end", values=(*row, total))

    def sort_column(self, col):
        data = [(self.tree.set(k, col), k) for k in self.tree.get_children("")]
        try:
            data.sort(key=lambda t: float(t[0]))
        except ValueError:
            data.sort(key=lambda t: t[0])
        for index, (_, k) in enumerate(data):
            self.tree.move(k, "", index)

    def edit_cell(self, event):
        rowid = self.tree.identify_row(event.y)
        column = self.tree.identify_column(event.x)
        col_index = int(column[1:]) - 1
        if not rowid or self.columns[col_index] == "Total":
            return
        x, y, width, height = self.tree.bbox(rowid, column)
        value = self.tree.set(rowid, self.columns[col_index])
        entry = ttk.Entry(self.tree)
        entry.place(x=x, y=y, width=width, height=height)
        entry.insert(0, value)
        entry.focus()

        def on_edit(event):
            new_value = entry.get()
            old_value = self.tree.set(rowid, self.columns[col_index])
            self.undo_redo.record(
                lambda: self.tree.set(rowid, self.columns[col_index], old_value),
                lambda: self.tree.set(rowid, self.columns[col_index], new_value)
            )
            self.tree.set(rowid, self.columns[col_index], new_value)
            entry.destroy()

            if self.columns[col_index] in ("Qty", "Price"):
                try:
                    qty = float(self.tree.set(rowid, "Qty"))
                    price = float(self.tree.set(rowid, "Price"))
                    self.tree.set(rowid, "Total", round(qty * price, 2))
                except ValueError:
                    self.tree.set(rowid, "Total", "")

        entry.bind("<Return>", on_edit)
        entry.bind("<FocusOut>", on_edit)

    def drag_start(self, event):
        self.drag_data["item"] = self.tree.identify_row(event.y)

    def drag_motion(self, event):
        target = self.tree.identify_row(event.y)
        if target and target != self.drag_data["item"]:
            self.tree.move(self.drag_data["item"], "", self.tree.index(target))

    def drag_end(self, event):
        self.drag_data["item"] = None

    def show_context_menu(self, event):
        rowid = self.tree.identify_row(event.y)
        if rowid:
            self.tree.selection_set(rowid)
            self.context_menu_rowid = rowid
            self.context_menu.post(event.x_root, event.y_root)

    def context_edit(self):
        if hasattr(self, 'context_menu_rowid'):
            x, y, width, height = self.tree.bbox(self.context_menu_rowid, "#1")
            fake_event = type("Event", (object,), {"x": x + 5, "y": y + 5})()
            self.edit_cell(fake_event)

    def context_delete(self):
        rowid = getattr(self, 'context_menu_rowid', None)
        if not rowid:
            return
        values = self.tree.item(rowid, 'values')
        index = self.tree.index(rowid)
        self.undo_redo.record(
            lambda: self.tree.insert("", index, iid=rowid, values=values),
            lambda: self.tree.delete(rowid)
        )
        self.tree.delete(rowid)

    def export_csv(self):
        file_path = filedialog.asksaveasfilename(defaultextension=".csv", filetypes=[("CSV files", "*.csv")])
        if not file_path:
            return
        try:
            with open(file_path, "w", newline="") as f:
                writer = csv.writer(f)
                writer.writerow(self.columns)
                for row_id in self.tree.get_children():
                    writer.writerow(self.tree.item(row_id)["values"])
            messagebox.showinfo("Export", "Data exported successfully.")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to export: {e}")

    def toggle_column_panel(self):
        if self.column_toggle_panel and self.column_toggle_panel.winfo_exists():
            self.column_toggle_panel.lift()
        else:
            self.column_toggle_panel = ColumnTogglePanel(self, self.columns, self.set_column_visibility)

    def set_column_visibility(self, column, visible):
        self.tree.heading(column, text=column if visible else "")
        self.tree.column(column, width=100 if visible else 0)

if __name__ == "__main__":
    root = tk.Tk()
    root.title("Tkinter Treeview App")
    root.geometry("600x400")
    app = TreeviewApp(root)
    app.pack(fill=tk.BOTH, expand=True)
    root.mainloop()
