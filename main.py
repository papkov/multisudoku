import logging
from Tkinter import Image

import gui
import server as s
import client as c

FORMAT = '%(asctime)-15s %(levelname)s %(message)s'
logging.basicConfig(level=logging.DEBUG, format=FORMAT)
LOG = logging.getLogger()

if __name__ == "__main__":
    # Create ui
    ui = gui.MainWindow()
    # Set icon
    # https://cdn2.iconfinder.com/data/icons/games-and-sports-vol-2/32/Game_sports_calculate_counting_crosswords_numbers_sudoku-512.png
    ui.tk.call('wm',
                'iconphoto',
                ui._w,
                Image("photo", file="icon.png"))
    # Create game
    game = s.Game()
    # Create server with game
    server = s.GameServer(game)

    # Give control to UI
    ui.set_server(server)
    # Start the app
    ui.mainloop()


