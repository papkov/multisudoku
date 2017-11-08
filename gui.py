import Tkinter as tk
import tkMessageBox
import logging
from functools import partial

from sudoku import *

FORMAT = '%(asctime)-15s %(levelname)s %(message)s'
logging.basicConfig(level=logging.DEBUG, format=FORMAT)
LOG = logging.getLogger()


class SudokuFrame(tk.Frame):
    def __init__(self, parent):
        tk.Frame.__init__(self, parent)

        # Set validator for boxes
        vcmd = (self.register(self.validate_entry), '%P')

        # Create trackers for sudoku boxes
        self.box_values = [tk.StringVar() for i in range(81)]
        for sv in self.box_values:
            sv.trace("w", lambda name, index, mode, sv=sv: self.report_changes(sv))

        # Generate a list of boxes
        self.boxes = [tk.Entry(self,
                               width=2,
                               font=100,
                               justify='center',
                               textvariable=sv,
                               validate='key',
                               validatecommand=vcmd,
                               state='readonly') for sv in self.box_values]

        # Fill the grid
        for i, b in enumerate(self.boxes):
            r = i // 9
            c = i % 9
            b.grid(row=r, column=c, padx=3, pady=3)

    def validate_entry(self, value):
        allowed = (len(value) == 1 and value.isalnum()) or not value
        LOG.debug("Validate %s: %s" % (value, allowed))
        if not allowed:
            self.bell()
        return allowed

    def report_changes(self, sv):
        LOG.debug("Value %s has changed" % sv)
        return self.get_current_state()

    def get_current_state(self):
        cs = [b.get() if b.get() else 0 for b in self.boxes]
        LOG.debug("Get current state: %s" % cs)
        return cs

    def generate_sudoku(self):
        LOG.debug("Trying to generate new sudoku")
        sudoku = get_sudoku()
        unsolved = sum(sudoku["u"], [])
        LOG.debug("Got unsolved sudoku with %d elements" % len(unsolved))
        for i, b in enumerate(self.boxes):
            # Fix values that are not zero
            b.config(state="normal")
            b.delete(0, 'end')
            if unsolved[i]:
                b.insert(0, unsolved[i])
                b.config(state="readonly")

        LOG.debug("New sudoku was generated")

        # tkMessageBox.showinfo("Info", "New sudoku was generated")

# Root frame
root = tk.Tk()
root.resizable(width=False, height=False)

# Main pane
main_pane = tk.PanedWindow(root, showhandle=False)
main_pane.pack(fill=tk.BOTH, expand=True)

# Menu frame for buttons
menu_frame = tk.Frame()
main_pane.add(menu_frame)
title = tk.Label(menu_frame, text="Multiplayer sudoku\nv.0.0.1", font=100)
title.pack(side=tk.TOP)

# Sudoku pane
sudoku_pane = tk.PanedWindow(main_pane, relief=tk.RAISED)
sudoku_pane.pack(fill=tk.NONE)
main_pane.add(sudoku_pane)

frame_sudoku = SudokuFrame(sudoku_pane)
frame_sudoku.pack(side=tk.TOP)

# Create username
frm_uname = tk.Frame(menu_frame)
frm_uname.pack(side=tk.BOTTOM)
lbl_uname = tk.Label(frm_uname, text="User Name")
lbl_uname.pack(side=tk.LEFT)
ent_uname = tk.Entry(frm_uname, bd=5)
ent_uname.pack(side=tk.RIGHT)

# Create menu buttons
btn_width = 30
btn_new_sudoku = tk.Button(menu_frame,
                           text="New sudoku",
                           width=btn_width,
                           command=partial(SudokuFrame.generate_sudoku, frame_sudoku))
btn_new_sudoku.pack(side=tk.BOTTOM)

btn_connect = tk.Button(menu_frame,
                        width=btn_width,
                        text="Connect")
btn_connect.pack(side=tk.BOTTOM)



root.mainloop()