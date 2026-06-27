import tkinter as tk
from ttkbootstrap import Button
from ttkbootstrap import Treeview
from ttkbootstrap import Meter
from settings import *

class CustomlButton(Button):
    def __init__(self, parent, text, func):
        super().__init__(master=parent,
                         text=text,
                         command=func)
        self.pack(side=tk.RIGHT, padx=5)

class CustomTreeview(Treeview):
    def __init__(self,parent, columns, mode):
        super().__init__(master=parent, 
                            columns=columns,
                            show="headings", 
                            style="TreeviewPrimary.Treeview",
                            selectmode=mode
                            # yscrollcommand=yscroll.set
                            )
        
        # yscroll.pack(side=tk.RIGHT, fill=tk.Y)
        # yscroll.configure(command=self.yview)

        self.tag_configure('even', background=EVEN_COLOR)
        self.tag_configure('odd', background=ODD_COLOR)
        self.columnconfigure(99,weight=1)
        self.grid(row=0, column=0, sticky="nsew")

class CustomMeter(Meter):
    def __init__(self, parent,row, col,style, text, value, key, callback=None):
        super().__init__(
        master=parent,
        bootstyle=style,
        subtext=text,
        amountused=value,
        metertype='semi',
        interactive=False,
        )
        self.title = text
        
        self.grid(column=col, row=row, padx=5)

        self.key = key
        self.value = value
        self.callback = callback

        # Bind click to this specific meter
        # self.bind("<Button-1>", self.on_click)
        self._bind_all_widgets()

    def _bind_all_widgets(self):
        def bind_recursively(widget):
            widget.bind("<Button-1>", self.on_click)
            for child in widget.winfo_children():
                bind_recursively(child)

        bind_recursively(self)

    def get_title(self):
        return self.title
    
    def on_click(self, event):
        if self.callback:
            self.callback(self.key, self.value)
        else:
            print(f"🟢 Meter clicked: {self.key} → {self.value}")
    
        #  bootstyle="info", subtext="Total Orders", amountused=0, metertype='semi'),