import tkinter as tk
from ttkbootstrap import Button
from ttkbootstrap import Treeview
from settings import *

class ControlButton(Button):
    def __init__(self, parent, text, func):
        super().__init__(master=parent,
                         text=text,
                         command=func)
        self.pack(side=tk.RIGHT, padx=5)
    
class MainButton(Button):
     def __init__(self, parent, col, row, text,bootstyle,func,params):
          super().__init__(master=parent,
                           text = text,
                           command = lambda: func(params),
                           bootstyle=bootstyle
                           )
          self.grid(column=col, row=row, padx=5)

class PurchaseOrderTree(Treeview):
        def __init__(self,parent, columns, yscroll):
            super().__init__(master=parent, 
                             columns=columns,
                             show="headings", 
                             style="TreeviewPrimary.Treeview",
                             yscrollcommand=yscroll.set
                             )
            
            # yscroll.pack(side=tk.RIGHT, fill=tk.Y)
            yscroll.configure(command=self.yview)

            self.tag_configure('even', background=EVEN_COLOR)
            self.tag_configure('odd', background=ODD_COLOR)
            self.grid(row=2, column=0, sticky="nsew")