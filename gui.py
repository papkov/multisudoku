import Tkinter as tk
import tkFont
import tkMessageBox
import logging
from functools import partial
import re
import sudoku as su

FORMAT = '%(asctime)-15s %(levelname)s %(message)s'
logging.basicConfig(level=logging.DEBUG, format=FORMAT)
LOG = logging.getLogger()


class SudokuFrame(tk.Frame):
    def __init__(self, parent):
        tk.Frame.__init__(self, parent)

        # Create trackers for sudoku boxes
        self.box_values = [tk.StringVar() for i in range(81)]
        for sv in self.box_values:
            sv.trace("w", lambda name, index, mode, sv=sv: self.report_changes(sv))

        # Generate a list of boxes
        self.boxes = [tk.Entry(self,
                               width=3,
                               font="Helvetica 24",
                               justify='center',
                               textvariable=sv,
                               validate='key',
                               validatecommand=(self.register(self.validate_entry), '%P'),
                               state='readonly') for sv in self.box_values]

        # Fill the grid
        for i, b in enumerate(self.boxes):
            r = i // 9
            c = i % 9
            b.grid(row=r, column=c, ipadx=0, padx=3, ipady=4, pady=4)

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

    def generate_sudoku(self, valid_username=False):
        LOG.debug("Trying to generate new sudoku")
        # If some information is not valid
        if not valid_username:
            LOG.debug("Generation is not allowed")
            tkMessageBox.showinfo("Info", "Username should not be longer than "
                                          "8 alphanumeric characters "
                                          "(empty strings not allowed, "
                                          "spaces not allowed)")
            return

        sudoku = su.get_sudoku()
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


class LeaderboardFrame(tk.Frame):
    def __init__(self, parent, players_limit=8):
        tk.Frame.__init__(self, parent)
        self.title = tk.Label(self,
                              text="Leaderboard",
                              height=1,
                              font="Helvetica 12 bold")
        self.players_limit = players_limit

        # Create string vars for every player with names and point
        self.sv_players = [tk.StringVar() for i in range(self.players_limit)]
        self.sv_points = [tk.StringVar() for i in range(self.players_limit)]

        # Create labels for static representation
        self.lbl_players = [tk.Label(self,
                                     width=8,
                                     textvariable=sv,
                                     justify="left",
                                     font="Courier 10") for sv in self.sv_players]
        self.lbl_points = [tk.Label(self,
                                    width=8,
                                    textvariable=sv,
                                    justify="left",
                                    font="Courier 10") for sv in self.sv_points]

        # Fill the leaderboard table grid
        self.title.grid(row=0,
                        column=0,
                        columnspan=2)

        for i in range(self.players_limit):
            self.lbl_players[i].grid(row=i+1,
                                     column=0,
                                     padx=2,
                                     pady=0,
                                     sticky="e")

            self.lbl_points[i].grid(row=i+1,
                                    column=1,
                                    padx=2,
                                    pady=0,
                                    sticky="w")

    def fill(self, table):
        """
        Fill leaderboard with data from server
        :param table: dict, player: points
        :return: None
        """
        for i, player in enumerate(table):
            self.sv_players[i].set(player)
            self.sv_points[i].set(table[player])


class MenuFrame(tk.Frame):
    def __init__(self, parent, frm_sudoku, width=25):
        tk.Frame.__init__(self, parent)
        self.title = tk.Label(self, text="Multiplayer sudoku\nv0.0.1", font="Helvetica 16 bold")
        self.title.pack(side=tk.TOP)

        # Create username frame with label and textfield
        self.frm_username = tk.Frame(self)
        self.frm_username.pack(side=tk.BOTTOM)

        # Label
        self.lbl_username = tk.Label(self.frm_username,
                                     text="Username: ",
                                     font="Helvetica 12")
        self.lbl_username.pack(side=tk.LEFT)

        # Test entry
        self.sv_username = tk.StringVar()
        self.ent_username = tk.Entry(self.frm_username,
                                     bd=3,
                                     textvariable=self.sv_username,
                                     validate='key',
                                     validatecommand=(self.register(self.validate_username), '%P'))
        self.ent_username.pack(side=tk.RIGHT)

        # Create buttons
        self.valid_username = False
        self.frm_sudoku = frm_sudoku
        self.vcmd_username = partial(SudokuFrame.generate_sudoku, self.frm_sudoku, self.valid_username)
        self.btn_new = tk.Button(self,
                                 text="New game",
                                 width=width,
                                 font="Helvetica 12",
                                 command=self.vcmd_username)

        self.btn_connect = tk.Button(self,
                                     width=width,
                                     text="Connect",
                                     font="Helvetica 12",
                                     command=self.connect)

        self.frm_leaderboard = LeaderboardFrame(self)

        # Organise objects
        self.btn_new.pack(side=tk.BOTTOM)
        self.btn_connect.pack(side=tk.BOTTOM)
        self.frm_leaderboard.pack(side=tk.TOP)

    def validate_username(self, username):
        p = re.compile('^[0-9A-Za-z]{1,8}$')
        if not re.match(p, username):
            self.valid_username = False
            self.vcmd_username = partial(SudokuFrame.generate_sudoku, self.frm_sudoku, self.valid_username)
            self.btn_new.config(command=self.vcmd_username)
            LOG.debug("Invalid username [%s], status %s" % (username, self.valid_username))
        else:
            self.valid_username = True
            self.vcmd_username = partial(SudokuFrame.generate_sudoku, self.frm_sudoku, self.valid_username)
            self.btn_new.config(command=self.vcmd_username)
            LOG.debug("Valid username [%s], status %s" % (username, self.valid_username))
        return True

    def connect(self):
        self.frm_leaderboard.fill({"Misha": 10, "Vlad": 10})


class MainWindow(tk.Tk):
    def __init__(self):
        tk.Tk.__init__(self)
        # Set window properties
        self.title("multisudoku")
        self.resizable(width=False, height=False)

        # Main pane
        self.pn_main = tk.PanedWindow(self, showhandle=False)
        self.pn_main.pack(fill=tk.BOTH, expand=True)

        # Sudoku pane
        self.pn_sudoku = tk.PanedWindow(self.pn_main, relief=tk.RAISED)
        self.pn_sudoku.pack(fill=tk.NONE)
        self.frm_sudoku = SudokuFrame(self.pn_sudoku)
        self.frm_sudoku.pack(side=tk.TOP)

        # Create menu frame and bound it with sudoku
        self.frm_menu = MenuFrame(self.pn_main, self.frm_sudoku)

        # Add panes to main pane
        self.pn_main.add(self.frm_menu)
        self.pn_main.add(self.pn_sudoku)


if __name__ == "__main__":
    LOG.error("This file was not designed to run standalone")
    exit(0)


