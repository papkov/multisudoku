import Tkinter as tk
import ttk
import tkMessageBox
import logging
import threading
from functools import partial
import re
import sudoku as su

FORMAT = '%(asctime)-15s (%(threadName)-2s) %(levelname)s %(message)s'
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
            # Add bold borders for 3x3 blocks
            padx = (20, 3) if c == 3 or c == 6 else 3
            pady = (20, 4) if r == 3 or r == 6 else 4

            b.grid(row=r, column=c, ipadx=0, padx=padx, ipady=4, pady=pady)

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

    def generate_sudoku(self, valid_username=False, valid_address=False):
        LOG.debug("Trying to generate new sudoku")
        # If some information is not valid
        if not valid_username:
            LOG.debug("Generation is not allowed")
            tkMessageBox.showinfo("Info", "Username should not be longer than "
                                          "8 alphanumeric characters "
                                          "(empty strings not allowed, "
                                          "spaces not allowed)")
            return

        if not valid_address:
            LOG.debug("Generation is not allowed")
            tkMessageBox.showinfo("Info", "Please specify the correct server address"
                                          "in format xxx.xxx.xxx.xxx:xxxx")
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
    def __init__(self, parent, players_limit=8, width=25):
        tk.Frame.__init__(self, parent, width=width)
        self.title = tk.Label(self,
                              text="Leaderboard",
                              height=1,
                              font="Helvetica 12")
        self.title.pack(side=tk.TOP)
        self.players_limit = players_limit

        self.scrollbar_sessions = tk.Scrollbar(self)
        self.tree = ttk.Treeview(self,
                                 columns=('Player', 'Points'),
                                 height=5,
                                 # width=width,
                                 yscrollcommand=self.scrollbar_sessions.set)

        # self.tree.heading('#0', text='Place')
        self.tree.heading('#1', text='Player')
        self.tree.heading('#2', text='Points')
        self.tree.column('#0', minwidth=0, width=30, stretch=tk.NO, anchor=tk.W)
        self.tree.column('#1', minwidth=0, width=120, stretch=tk.NO)
        self.tree.column('#2', minwidth=0, width=120, stretch=tk.NO)
        self.scrollbar_sessions.config(command=self.tree.yview)
        self.scrollbar_sessions.pack(side=tk.RIGHT, fill=tk.Y)
        self.tree.pack(fill=tk.X)

    def fill(self, table):
        """
        Fill leaderboard with data from server
        :param table: dict, player: points
        :return: None
        """
        self.tree.delete(*self.tree.get_children())
        for i, player in enumerate(sorted(table, key=table.get)):
            self.tree.insert("", "end", text=str(i+1), values=(player, table[player]))


class SessionsFrame(tk.Frame):
    def __init__(self, parent):
        tk.Frame.__init__(self, parent)

        self.lbl_sessions = tk.Label(self, text="Available sessions", font="Helvetica 12")
        self.scrollbar_sessions = tk.Scrollbar(self)
        self.list_sessions = tk.Listbox(self,
                                        selectmode=tk.SINGLE,
                                        selectbackground="blue",
                                        selectforeground="white",
                                        height=5,  # This value is in lines
                                        yscrollcommand=self.scrollbar_sessions.set)
        self.lbl_sessions.pack(side=tk.TOP, fill=tk.BOTH)
        self.scrollbar_sessions.pack(side=tk.RIGHT, fill=tk.Y)
        self.list_sessions.pack(fill=tk.X)
        self.scrollbar_sessions.config(command=self.list_sessions.yview)

    def fill(self, sessions):
        self.list_sessions.delete(0, tk.END)
        for s in sessions:
            self.list_sessions.insert(tk.END, s)


class NotificationsFrame(tk.Frame):
    def __init__(self, parent, width=38):
        tk.Frame.__init__(self, parent)

        self.lbl_notifications = tk.Label(self, text="Notifications", font="Helvetica 12")
        self.scrollbar_notifications = tk.Scrollbar(self)
        self.txt_notifications = tk.Text(self,
                                         height=5,
                                         yscrollcommand=self.scrollbar_notifications.set,
                                         wrap=tk.WORD,
                                         padx=2,
                                         pady=2,
                                         spacing1=4,
                                         width=width)

        self.lbl_notifications.pack(side=tk.TOP, fill=tk.BOTH)
        self.scrollbar_notifications.pack(side=tk.RIGHT, fill=tk.Y)
        self.txt_notifications.pack(fill=tk.X)
        self.scrollbar_notifications.config(command=self.txt_notifications.yview)

    def add(self, text):
        self.txt_notifications.insert(tk.END, text + "\n" )


class MenuFrame(tk.Frame):
    def __init__(self, parent, frm_sudoku, width=25, address="127.0.0.1:7777"):
        tk.Frame.__init__(self, parent)

        # Control
        self.server = None
        self.client = None
        # Threads for server and client
        self.thread_server = None
        self.thread_client_notifications = None
        self.thread_client_network = None

        self.title = tk.Label(self,
                              text="Multiplayer sudoku\nv0.0.1",
                              font="Helvetica 16 bold")
        self.title.pack(side=tk.TOP)

        # FRAMES
        self.frm_sudoku = frm_sudoku  # Bind with sudoku frame in order to have control on it
        self.frm_leaderboard = LeaderboardFrame(self)
        self.frm_username = tk.Frame(self)  # username frame with label and textfield
        self.frm_address = tk.Frame(self)   # address frame with IP and port fields
        self.frm_sessions = SessionsFrame(self)
        self.frm_notifications = NotificationsFrame(self)
        self.frm_host = tk.Frame(self)      # Host/Join buttons

        # VALIDATION
        self.valid_username = False
        self.valid_address = False
        self.vcmd_fields = partial(SudokuFrame.generate_sudoku,  # Validation partial command
                                   self.frm_sudoku,
                                   self.valid_username,
                                   self.valid_address)

        # USERNAME
        self.lbl_username = tk.Label(self.frm_username,
                                     text="Username: ",
                                     font="Helvetica 12")

        self.sv_username = tk.StringVar()
        self.ent_username = tk.Entry(self.frm_username,
                                     bd=3,
                                     textvariable=self.sv_username,
                                     validate='key',
                                     validatecommand=(self.register(self.validate_username), '%P'))
        # Position
        self.ent_username.pack(side=tk.RIGHT)
        self.lbl_username.pack(side=tk.RIGHT)

        # ADDRESS
        self.lbl_address = tk.Label(self.frm_address,
                                    text="Address:     ",
                                    font="Helvetica 12")
        self.sv_address = tk.StringVar()
        self.sv_address.set(address)
        self.ent_address = tk.Entry(self.frm_address,
                                    bd=3,
                                    textvariable=self.sv_address,
                                    validate='key',
                                    validatecommand=(self.register(self.validate_address), '%P'))
        # Position
        self.ent_address.pack(side=tk.RIGHT, fill=tk.X)
        self.lbl_address.pack(side=tk.RIGHT, fill=tk.X)

        # BUTTONS
        self.btn_new = tk.Button(self,
                                 text="New game",
                                 width=width,
                                 font="Helvetica 12",
                                 command=self.vcmd_fields)

        self.btn_connect = tk.Button(self,
                                     width=width,
                                     text="Connect",
                                     font="Helvetica 12",
                                     command=self.connect)

        self.btn_host = tk.Button(self.frm_host,
                                  width=width//2-1,
                                  text="Host",
                                  font="Helvetica 12",
                                  command=self.host)

        self.btn_join = tk.Button(self.frm_host,
                                  width=width//2-1,
                                  text="Join",
                                  font="Helvetica 12",
                                  command=self.join)

        self.btn_host.pack(side=tk.LEFT)
        self.btn_join.pack(side=tk.RIGHT)

        # ORGANISE
        self.frm_username.pack(side=tk.BOTTOM)
        self.frm_address.pack(side=tk.BOTTOM)
        self.btn_new.pack(side=tk.BOTTOM)
        self.btn_connect.pack(side=tk.BOTTOM)
        self.frm_host.pack(side=tk.BOTTOM)
        self.frm_sessions.pack(side=tk.BOTTOM, fill=tk.X)
        self.frm_leaderboard.pack(side=tk.BOTTOM)
        self.frm_notifications.pack(side=tk.BOTTOM)

    def validate_username(self, username):
        p = re.compile('^[0-9A-Za-z]{1,8}$')
        if not re.match(p, username):
            self.valid_username = False
            LOG.debug("Invalid username [%s], status %s" % (username, self.valid_username))
        else:
            self.valid_username = True
            LOG.debug("Valid username [%s], status %s" % (username, self.valid_username))

        self.update_vcmd()
        return True

    def validate_address(self, address):
        p = re.compile('^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}:\d{1,5}$')
        if not re.match(p, address):
            self.valid_address = False
            LOG.debug("Invalid address [%s], status %s" % (address, self.valid_address))
        else:
            self.valid_address = True
            LOG.debug("Valid address [%s], status %s" % (address, self.valid_address))

        self.update_vcmd()
        return True

    def update_vcmd(self):
        self.vcmd_fields = partial(SudokuFrame.generate_sudoku,
                                   self.frm_sudoku,
                                   self.valid_username,
                                   self.valid_address)
        try:
            self.btn_new.config(command=self.vcmd_fields)
        except AttributeError:
            LOG.error("btn_new is not exist")

    def connect(self):
        self.frm_leaderboard.fill({"Misha": 10, "Vlad": 10})
        self.frm_sessions.fill(["Session1", "Session2"])

    def host(self):
        """
        Host a server on localhost
        :return: boolean, status
        """
        # TODO handle exceptions
        # Check if server was set up and not yet running
        if not self.valid_address or self.server is None:
            LOG.debug("Failed to host a server")
            return False
        if self.thread_server is not None:
            LOG.debug("Server is already running")
            return False
        # Address should be valid at this point
        ip, port = self.ent_address.get().split(":")

        LOG.debug("Hosting a server: %s:%s" % (ip, port))
        self.server.listen((ip, int(port)))
        self.thread_server = threading.Thread(target=self.server.loop, name="server")

        LOG.debug("Starting a server thread")
        self.thread_server.daemon = True
        self.thread_server.start()

        tkMessageBox.showinfo("Info", "Hosting a server: %s:%s\nAsk your friends to join!" % (ip, port))
        return True

    def join(self):
        """
        Join a server by address provided through text field
        :return:
        """
        if not self.valid_address or self.server is None:
            LOG.debug("Failed to join a server")
            return False
        # TODO: ability to restart client with different name
        if self.thread_client_network is not None:
            LOG.debug("Client is already running")
            return False
        if not self.valid_username:
            LOG.debug("Username is invalid")
            tkMessageBox.showinfo("Info", "Username should not be longer than "
                                          "8 alphanumeric characters "
                                          "(empty strings not allowed, "
                                          "spaces not allowed)")
            return False

        # Address should be valid at this point
        ip, port = self.ent_address.get().split(":")
        server_address = (ip, int(port))

        if self.client.connect(server_address):
            logging.debug("Client connected to %s:%s" % (ip, port))

            # Set and start client threads
            self.thread_client_network = threading.Thread(name='client_network',
                                                          target=self.client.network_loop)
            self.thread_client_notifications = threading.Thread(name='client_notifications',
                                                                target=self.client.notifications_loop)
            self.thread_client_notifications.daemon = True
            self.thread_client_network.daemon = True
            self.thread_client_network.start()
            self.thread_client_notifications.start()
            logging.debug("Client threads are running")

        else:
            LOG.debug("Failed to connect to server %s:%s" % (ip, port))
            return False

        # TODO handle name rejection
        # Trying to set a name
        name = self.sv_username.get()
        if self.client.set_my_name(name):
            logging.debug("Your are connected to the game server by name [%s]" % name)
            return True
        else:
            logging.debug("Server rejected name [%s]" % name)
            return False


    def set_server(self, server):
        self.server = server

    def set_client(self, client):
        self.client = client


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

    def set_server(self, server):
        return self.frm_menu.set_server(server)

    def set_client(self, client):
        return self.frm_menu.set_client(client)

    def notify(self, notification):
        return self.frm_menu.frm_notifications.add(notification)


if __name__ == "__main__":
    LOG.error("This file was not designed to run standalone")
    exit(0)


