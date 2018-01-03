import logging
from Tkinter import Image

import gui
import server as s
import client as c
from syncIO import SyncConsoleAppenderRawInputReader

FORMAT = '%(asctime)-15s %(levelname)s %(message)s'
logging.basicConfig(level=logging.DEBUG, format=FORMAT)
LOG = logging.getLogger()

if __name__ == "__main__":
    # Create ui
    ui = gui.MainWindow()
    # Set icon
    # https://cdn2.iconfinder.com/data/icons/games-and-sports-vol-2/32/Game_sports_calculate_counting_crosswords_numbers_sudoku-512.png
    #ui.tk.call('wm',
    #            'iconphoto',
    #            ui._w,
    #            Image("photo", file="icon.png"))
    # Create game
    game = s.Game()

    # Pre-set server with game
    server = s.GameServer(game, ('', 7777))

    # Create client
    # TODO: remove syncIO dependency for GUI
    sync_io = SyncConsoleAppenderRawInputReader()
    client = c.Client(sync_io)

    # Set UI for client
    client.set_gui(ui)
    ui.set_client(client)

    # Give to UI possibility to host a server
    ui.set_server(server)
    # Start the app
    ui.mainloop()


