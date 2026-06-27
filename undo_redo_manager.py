class UndoRedoManager:
    def __init__(self):
        self.undo_stack = []
        self.redo_stack = []

    def record(self, undo_action, redo_action):
        self.undo_stack.append((undo_action, redo_action))
        self.redo_stack.clear()

    def undo(self):
        if not self.undo_stack:
            return
        undo_action, redo_action = self.undo_stack.pop()
        undo_action()
        self.redo_stack.append((undo_action, redo_action))

    def redo(self):
        if not self.redo_stack:
            return
        undo_action, redo_action = self.redo_stack.pop()
        redo_action()
        self.undo_stack.append((undo_action, redo_action))
