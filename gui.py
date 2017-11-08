import Tkinter as tk
import tkMessageBox
import logging
from functools import partial

from sudoku import *

FORMAT = '%(asctime)-15s %(levelname)s %(message)s'
logging.basicConfig(level=logging.DEBUG, format=FORMAT)
LOG = logging.getLogger()


def generate_sudoku(spinboxes):
    LOG.debug("Trying to generate new sudoku")
    sudoku = get_sudoku()
    unsolved = sum(sudoku["u"], [])
    LOG.debug("Got unsolved sudoku with %d elements" % len(unsolved))
    for i, sb in enumerate(spinboxes):
        # Fix values that are not zero
        if unsolved[i]:
            sb.config(values=(unsolved[i],), fg="green")
        else:
            sb.config(values=[v for v in range(10)], fg="black")
    LOG.debug("New sudoku was generated")

    tkMessageBox.showinfo("Info", "New sudoku was generated")


root = tk.Tk()
frame_sudoku = tk.Frame(root)
frame_sudoku.pack(side=tk.TOP)

# Generate a list of spinboxes
spinboxes = [tk.Spinbox(frame_sudoku, from_=0, to=9, width=1, font=100) for i in range(81)]

# Fill sudoku grid
for i, s in enumerate(spinboxes):
    r = i // 9
    c = i % 9
    s.grid(row=r, column=c, padx=3, pady=3)

# Preserve function
generate_sudoku_sp = partial(generate_sudoku, spinboxes)

# Create button
btn_new_sudoku = tk.Button(root, text="Generate", command=generate_sudoku_sp)
btn_new_sudoku.pack(side=tk.BOTTOM)

root.mainloop()