import gui
import sudoku
import logging
from Tkinter import Image

FORMAT = '%(asctime)-15s %(levelname)s %(message)s'
logging.basicConfig(level=logging.DEBUG, format=FORMAT)
LOG = logging.getLogger()

if __name__ == "__main__":
    root = gui.MainWindow()
    # Set icon
    # https://cdn2.iconfinder.com/data/icons/games-and-sports-vol-2/32/Game_sports_calculate_counting_crosswords_numbers_sudoku-512.png
    root.tk.call('wm',
                 'iconphoto',
                 root._w,
                 Image("photo", file="icon.png"))
    root.mainloop()
