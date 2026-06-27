import tkinter as tk
from tkinter import ttk

class SortableEditableTreeview(ttk.Treeview):
    def __init__(self, master=None, **kwargs):
        super().__init__(master, **kwargs)
        self._sort_column = None
        self._sort_reverse = False
        self._original_data = []
        self._editing_entry = None
        self.make_sortable()
        self.bind("<Double-1>", self._start_edit_cell)
        self._drag_data = {"item": None}
        self.bind("<ButtonPress-1>", self._on_drag_start)
        self.bind("<B1-Motion>", self._on_drag_motion)
        self.bind("<ButtonRelease-1>", self._on_drag_release)

    def make_sortable(self):
        for col in self["columns"]:
            self.heading(col, command=lambda c=col: self.sort_by_column(c))

    def sort_by_column(self, col):
        data = [(self.set(k, col), k) for k in self.get_children('')]
        try:
            data.sort(key=lambda t: float(t[0]), reverse=self._sort_column == col and not self._sort_reverse)
        except ValueError:
            data.sort(key=lambda t: t[0], reverse=self._sort_column == col and not self._sort_reverse)

        for index, (_, k) in enumerate(data):
            self.move(k, '', index)

        for c in self["columns"]:
            arrow = ""
            if c == col:
                arrow = " ↓" if self._sort_reverse else " ↑"
            self.heading(c, text=c + arrow)

        self._sort_column = col
        self._sort_reverse = not (self._sort_column == col and self._sort_reverse)

    def store_original_data(self):
        self._original_data = [self.item(i)["values"] for i in self.get_children()]

    def filter_rows(self, query):
        self.delete(*self.get_children())
        for row in self._original_data:
            if query.lower() in " ".join(map(str, row)).lower():
                self.insert("", "end", values=row)

    def _start_edit_cell(self, event):
        region = self.identify("region", event.x, event.y)
        if region != "cell":
            return

        row_id = self.identify_row(event.y)
        col = self.identify_column(event.x)
        col_index = int(col[1:]) - 1
        x, y, width, height = self.bbox(row_id, col)

        value = self.set(row_id, self["columns"][col_index])
        self._editing_entry = ttk.Entry(self)
        self._editing_entry.insert(0, value)
        self._editing_entry.place(x=x, y=y, width=width, height=height)
        self._editing_entry.focus()

        def save_edit(event):
            new_value = self._editing_entry.get()
            self.set(row_id, self["columns"][col_index], new_value)
            self._editing_entry.destroy()
            self._editing_entry = None

        self._editing_entry.bind("<Return>", save_edit)
        self._editing_entry.bind("<FocusOut>", save_edit)

    # --- Drag and Drop Support ---

    def _on_drag_start(self, event):
        row_id = self.identify_row(event.y)
        if row_id:
            self._drag_data["item"] = row_id

    def _on_drag_motion(self, event):
        if not self._drag_data["item"]:
            return
        target = self.identify_row(event.y)
        if target and target != self._drag_data["item"]:
            self.move(self._drag_data["item"], self.parent(target), self.index(target))

    def _on_drag_release(self, event):
        self._drag_data["item"] = None

# --- GUI Setup ---
root = tk.Tk()
root.title("Enhanced Treeview with All Features")
root.geometry("700x500")

# Filter bar
filter_frame = tk.Frame(root)
filter_frame.pack(fill=tk.X, padx=10, pady=5)

tk.Label(filter_frame, text="Filter:").pack(side=tk.LEFT)
filter_var = tk.StringVar()

# Treeview
columns = ("Item", "Qty", "Price")
tree = SortableEditableTreeview(root, columns=columns, show="headings", selectmode="browse")
tree.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

for col in columns:
    tree.heading(col, text=col)
    tree.column(col, width=120, anchor="center")

# Sample data
sample_data = [
    ("Apple", 2, 1.50),
    ("Banana", 3, 2.00),
    ("Cherry", 1, 3.00),
    ("Orange", 5, 0.99),
    ("Peach", 4, 2.25),
    ("Grapes", 6, 2.75)
]
for row in sample_data:
    tree.insert("", "end", values=row)

tree.store_original_data()

# Filter callback
def on_filter_change(*_):
    tree.filter_rows(filter_var.get())

entry = ttk.Entry(filter_frame, textvariable=filter_var)
entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(5, 0))
filter_var.trace_add("write", on_filter_change)

root.mainloop()
