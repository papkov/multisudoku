import gui
import sudoku
import logging

FORMAT = '%(asctime)-15s %(levelname)s %(message)s'
logging.basicConfig(level=logging.DEBUG, format=FORMAT)
LOG = logging.getLogger()

if __name__ == "__main__":
    root = gui.MainWindow()
    root.mainloop()


