import Tkinter as tk
import ttk
import tkMessageBox
# import tkSimpleDialog
import logging
import threading
# from functools import partial
import re
import netifaces as ni
# import sudoku as su

from protocol import *

FORMAT = '%(asctime)-15s (%(threadName)-2s) %(levelname)s %(message)s'
logging.basicConfig(level=logging.DEBUG, format=FORMAT)
LOG = logging.getLogger()


class SudokuFrame(tk.Frame):
    """
    Class for sudoku board
    """
    def __init__(self, parent):
        tk.Frame.__init__(self, parent)

        self.client = None
        self.lb = None
        self.lock = threading.Lock()

        # Create trackers for sudoku boxes
        self.box_values = [tk.StringVar() for i in range(81)]
        self.box_tracers = []
        # Generate a list of boxes
        self.boxes = [tk.Entry(self,
                               width=3,
                               font="Helvetica 24",
                               justify='center',
                               textvariable=sv,
                               validate='key',
                               validatecommand=(self.register(self.validate_entry), '%P', '%s'),
                               state=tk.DISABLED) for sv in self.box_values]

        # Fill the grid
        for i, b in enumerate(self.boxes):
            r = i // 9
            c = i % 9
            # Add bold borders for 3x3 blocks
            padx = (20, 3) if c == 3 or c == 6 else 3
            pady = (20, 4) if r == 3 or r == 6 else 4

            b.grid(row=r, column=c, ipadx=0, padx=padx, ipady=4, pady=pady)

    def set_client(self, client):
        """
        Set client to control the board (render updates)
        :param client: class Client
        :return:
        """
        self.client = client

    def set_leaderboard(self, lb):
        """
        Set leaderboard to update after each try
        :param lb: LeaderboardFrame
        :return: None
        """
        self.lb = lb

    def validate_entry(self, value, prior_value):
        """
        Validation for sudoku number box
        :param value: str, new value of box
        :param prior_value: str, prior value of box
        :return: boolean, is new value allowed?
        """
        allowed = (len(value) == 1 and value.isdigit()) or not value
        # Debug only new values
        if value != prior_value:
            LOG.debug("Validate %s: %s" % (value, allowed))
        if not allowed:
            self.bell()
        return allowed

    def report_changes(self, sv):
        """
        Trigger for sudoku changing
        :param sv: StringVar, changed variable
        :return: current state of sudoku
        """
        with self.lock:
            v = sv.get()
            i = self.box_values.index(sv)
            r = i // 9
            c = i % 9
            LOG.debug("Value %s has changed: %s" % (sv, v))

            if self.client is None:
                logging.error("Client is not connected to SudokuFrame")
                return self.get_current_state()

            if self.client.guess_number("%s %s %s" % (v, r, c)):
                logging.debug("Number confirmed")
                self.boxes[i].config(state="readonly")
            else:
                logging.debug("Number rejected")
                # TODO: do we need to clear this field immediately?
                sv.set("")

            state, lb = self.client.get_current_progress()

            self.lb.fill(lb)
            return self.get_current_state()

    def get_current_state(self):
        """
        :return: current state of sudoku
        """
        cs = [b.get() if b.get() else 0 for b in self.boxes]
        LOG.debug("Get current state: %s" % cs)
        return cs

    # def generate_sudoku(self, valid_username=False, valid_address=False):
    #     LOG.debug("Trying to generate new sudoku")
    #     # If some information is not valid
    #     if not valid_username:
    #         LOG.debug("Generation is not allowed")
    #         tkMessageBox.showinfo("Info", "Username should not be longer than "
    #                                       "8 alphanumeric characters "
    #                                       "(empty strings not allowed, "
    #                                       "spaces not allowed)")
    #         return
    #
    #     if not valid_address:
    #         LOG.debug("Generation is not allowed")
    #         tkMessageBox.showinfo("Info", "Please specify the correct server address"
    #                                       "in format xxx.xxx.xxx.xxx:xxxx")
    #         return
    #
    #     sudoku = su.get_sudoku()
    #     unsolved = sum(sudoku["u"], [])
    #     self.set_sudoku(unsolved)
    #
    #     LOG.debug("New sudoku was generated")

    def set_sudoku(self, sudoku):
        """
        Render list sudoku on the board
        :param sudoku: list, length 81
        :return: None
        """
        LOG.debug("Got unsolved sudoku with %d elements" % len(sudoku))

        with self.lock:
            # Remove tracers for updating
            if self.box_tracers:
                for i, sv in enumerate(self.box_values):
                    # print self.box_tracers[i]
                    sv.trace_vdelete("w", self.box_tracers[i])

            for i, b in enumerate(self.boxes):
                # Fix values that are not zero
                b.config(state=tk.NORMAL)
                # b.delete(0, 'end')
                if sudoku[i]:
                    self.box_values[i].set(sudoku[i])
                    # b.insert(0, sudoku[i])
                    b.config(state=tk.DISABLED)

            # Track changes in sudoku
            self.box_tracers = [sv.trace("w", lambda name, index, mode, sv=sv: self.report_changes(sv)) for sv in self.box_values]
            # tkMessageBox.showinfo("Info", "New sudoku was generated")


class LeaderboardFrame(tk.Frame):
    """
    Class for leaderboard
    tkinter Treeview
    """
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
    """
    Class for available sessions
    tkinter Listbox
    """
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
        """
        Fill list with data from the server
        :param sessions:
        :return:
        """
        self.list_sessions.delete(0, tk.END)
        for s in sessions:
            self.list_sessions.insert(tk.END, s)


class NotificationsFrame(tk.Frame):
    """
    Class for notifications log
    tkinter Text
    """
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
        self.txt_notifications.insert(tk.END, text + "\n")
        self.txt_notifications.see(tk.END)


class MenuFrame(tk.Frame):
    """
    Class for total control
    """
    def __init__(self, parent, frm_sudoku, root, width=25, address="127.0.0.1:7777"):
        tk.Frame.__init__(self, parent)

        # Main pane
        self.root = root

        # Control
        self.server = None
        self.client = None
        # Threads for server and client
        self.thread_server = None
        self.thread_client_notifications = None
        self.thread_client_network = None
        self.thread_receiver = None
        self.thread_discovery = None

        self.title = tk.Label(self,
                              text="Multiplayer sudoku\nv0.0.2",
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

        # DIALOG BOXES FOR HOST/JOIN
        # Run by buttons
        self.db_host = None
        self.db_join = None

        # Set control to update
        self.frm_sudoku.set_leaderboard(self.frm_leaderboard)

        # VALIDATION
        self.valid_username = False
        self.valid_address = False
        # self.vcmd_fields = partial(SudokuFrame.generate_sudoku,  # Validation partial command
        #                            self.frm_sudoku,
        #                            self.valid_username,
        #                            self.valid_address)

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
        # self.ent_address.pack(side=tk.RIGHT, fill=tk.X)
        # self.lbl_address.pack(side=tk.RIGHT, fill=tk.X)

        # BUTTONS
        self.btn_new = tk.Button(self,
                                 text="New game",
                                 width=width,
                                 font="Helvetica 12",
                                 command=self.new_sudoku)

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
        # self.btn_connect.pack(side=tk.BOTTOM)
        self.frm_host.pack(side=tk.BOTTOM)
        self.frm_sessions.pack(side=tk.BOTTOM, fill=tk.X)
        self.frm_leaderboard.pack(side=tk.BOTTOM)
        self.frm_notifications.pack(side=tk.BOTTOM)

    def validate_username(self, username):
        """
        Validation command for username
        (set valid_username inside)
        :param username: str
        :return: boolean, always True - all changes are allowed
        """
        p = re.compile('^[0-9A-Za-z]{1,8}$')
        if not re.match(p, username):
            self.valid_username = False
            LOG.debug("Invalid username [%s], status %s" % (username, self.valid_username))
        else:
            self.valid_username = True
            LOG.debug("Valid username [%s], status %s" % (username, self.valid_username))

        # self.update_vcmd()
        return True

    def validate_address(self, address):
        """
        Validation command for address
        (set valid_address inside)
        :param address: str
        :return: boolean, always True - all changes are allowed
        """
        p = re.compile('^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}:\d{1,5}$')
        if not re.match(p, address):
            self.valid_address = False
            LOG.debug("Invalid address [%s], status %s" % (address, self.valid_address))
        else:
            self.valid_address = True
            LOG.debug("Valid address [%s], status %s" % (address, self.valid_address))

        # self.update_vcmd()
        return True

    # def update_vcmd(self):
    #     self.vcmd_fields = partial(SudokuFrame.generate_sudoku,
    #                                self.frm_sudoku,
    #                                self.valid_username,
    #                                self.valid_address)
    #     try:
    #         self.btn_new.config(command=self.vcmd_fields)
    #     except AttributeError:
    #         LOG.error("btn_new is not exist")

    def connect(self):
        """
        Connect to the existing session
        :return: None
        """
        self.frm_leaderboard.fill({"Misha": 10, "Vlad": 10})
        self.frm_sessions.fill(["Session1", "Session2"])

    def host(self):
        """
        Host a server on localhost
        :return: boolean, status
        """
        # Call a dialog box
        # port = tkSimpleDialog.askinteger("Port:", "Select hosting port",
        #                                  parent=self.parent,
        #                                  minvalue=1030, maxvalue=65535)

        self.db_host = HostDialog(self.root, self.server)
        self.root.wait_window(self.db_host.top)
        logging.info("Hosting through local network %s:%s" % (self.server.ip, self.server.port))
        # self.server.port = port
        # self.server.ip = ip

        # TODO handle exceptions
        # Check if server was set up and not yet running
        if self.server.port is None or self.server.ip is None:
            LOG.debug("Failed to host a server")
            return False
        if self.thread_server is not None:
            LOG.debug("Server is already running")
            return False
        # Address should be valid at this point
        # ip, port = self.ent_address.get().split(":")

        self.server.listen()
        self.thread_server = threading.Thread(target=self.server.loop, name="server")
        LOG.debug("Starting a server thread")
        self.thread_server.daemon = True
        self.thread_server.start()

        # Set target port for broadcasting the near the proxy port
        self.server.set_broadcast_port(self.server.port+1)

        tkMessageBox.showinfo("Info", "Hosting a server: %s:%s\nAsk your friends to join!" % (self.server.ip, self.server.port))
        return True

    def join(self):
        """
        Join a server by address provided through text field
        :return:
        """
        # Start discovering servers

        if self.thread_discovery is None:
            self.thread_discovery = threading.Thread(name='DiscoveryThread', target=self.client.discovery_loop)
            self.thread_discovery.daemon = True
            self.thread_discovery.start()

        # Call a dialog box
        self.db_join = JoinDialog(self.root, self.client)
        self.root.wait_window(self.db_join.top)

        if self.client.ip is None or self.client.port is None:
            LOG.debug("Failed to join a server")
            return False
        # TODO: ability to restart client with different name

        if self.thread_receiver is not None:
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
        server_address = (self.client.ip, int(self.client.port))
        logging.debug("Trying to connect to %s:%s" % server_address)

        #if self.client.connect(server_address):
        if self.client.connect_proxy(server_address):
            logging.debug("Client connected to %s:%s" % server_address)

            # Setup notification socket to receive broadcast notifications
            self.client.setup_notification_socket()
            # Set and start client threads
            self.thread_receiver = threading.Thread(name='ReceiverThread', target=self.client.receiver_loop)
            self.thread_receiver.daemon = True
            self.thread_receiver.start()
            #self.thread_client_network = threading.Thread(name='client_network',target=self.client.network_loop)
            #self.thread_client_notifications = threading.Thread(name='client_notifications',target=self.client.notifications_loop)
            #self.thread_client_notifications.daemon = True
            #self.thread_client_network.daemon = True
            #self.thread_client_network.start()
            #self.thread_client_notifications.start()
            logging.debug("Client threads are running")

        else:
            logging.debug("Failed to connect to server %s:%s" % (self.client.ip, self.client.port))
            return False

        # TODO handle name rejection (do we need that?)
        # Trying to set a name
        name = self.sv_username.get()
        if self.client.set_my_name(name):
            logging.debug("Your are connected to the game server by name [%s]" % name)
        else:
            logging.debug("Server rejected name [%s]" % name)
            return False

        # Check if there is an active game, render board
        state, lb = self.client.get_current_progress()
        logging.debug("Current progress: %s" % state)
        if state:
            self.frm_sudoku.set_sudoku(state)
            self.frm_leaderboard.fill(lb)

        return True

    def new_sudoku(self, complexity=5):
        """
        Request new sudoku from the server
        :param complexity:
        :return:
        """
        if not self.client.in_game:
            tkMessageBox.showerror("No connection!", "You need to join a server before requesting sudoku")
            return

        if self.client.set_new_sudoku_to_guess(complexity):
            state, lb = self.client.get_current_progress()
            logging.debug("Received new sudoku %s" % len(state))
            self.frm_sudoku.set_sudoku(state)
            self.frm_leaderboard.fill(lb)
        else:
            logging.error("Failed to receive new sudoku")

    def set_server(self, server):
        """
        Set server to control (run by Host button)
        :param server: class Server
        :return: None
        """
        self.server = server

    def set_client(self, client):
        """
        Set client to control (Join to the server, UI triggers)
        :param client: class Client
        :return: None
        """
        self.client = client


class HostDialog:

    def __init__(self, parent, server):

        self.top = tk.Toplevel(parent)
        # Control server parameters: IP and port
        self.server = server

        self.lbl_port = tk.Label(self.top, text="Enter port:")
        self.lbl_ip = tk.Label(self.top, text="Select IP:")
        self.ent_port = tk.Entry(self.top)
        self.list_ip = tk.Listbox(self.top,
                                  selectmode=tk.SINGLE,
                                  width=70)
        self.btn_save = tk.Button(self.top, text="Select", command=self.select)

        # Set default port
        self.ent_port.insert(0, DEFAULT_HOSTING_PORT)

        # Get list of all ips for different interfaces
        ips = ["%s  -  %s" % (iface, ni.ifaddresses(iface)[ni.AF_INET][0]["addr"])
               for iface in ni.interfaces()
               if ni.AF_INET in ni.ifaddresses(iface)]

        for ip in ips:
            self.list_ip.insert(tk.END, ip)

        # Organise
        self.lbl_ip.pack(side=tk.TOP)
        self.list_ip.pack(side=tk.TOP)
        self.lbl_port.pack(side=tk.TOP)
        self.ent_port.pack(side=tk.TOP)
        self.btn_save.pack(side=tk.TOP)

    def select(self):
        if not self.valid_port():
            logging.error("Invalid port")
            return

        try:
            port = int(self.ent_port.get())
            ip = self.list_ip.get(tk.ACTIVE).split(" - ")[1].strip()

            if port < 1029 or port > 65536:
                tkMessageBox.showerror("Wrong port!",
                                       "Enter port number between 1029 and 65536")
                return
        except:
            logging.error("Something went wrong during IP selection")
            return

        self.server.ip = ip
        self.server.port = port

        logging.debug("Selected IP %s port %s" % (ip, port))
        self.top.destroy()

    def valid_port(self):
        """
        Validation for port
        :param value: str, new value of box
        :param prior_value: str, prior value of box
        :return: boolean, is new value allowed?
        """
        allowed = self.ent_port.get().isdigit() or not self.ent_port.get()
        return allowed


class JoinDialog:
    def __init__(self, parent, client):

        self.top = tk.Toplevel(parent)
        # Control client parameters: IP and port
        self.client = client

        self.lbl_ip = tk.Label(self.top, text="Select server:")
        self.list_ip = tk.Listbox(self.top,
                                  selectmode=tk.SINGLE,
                                  width=30)
        self.btn_save = tk.Button(self.top, text="Select", command=self.select)

        for ip in self.client.available_servers:
            self.list_ip.insert(tk.END, ip)

        # Organise
        self.lbl_ip.pack(side=tk.TOP)
        self.list_ip.pack(side=tk.TOP)
        self.btn_save.pack(side=tk.TOP)

    def select(self):

        try:
            ip, port = self.list_ip.get(tk.ACTIVE).split(":")
        except:
            logging.error("Something went wrong during IP selection")
            return

        self.client.ip = ip
        self.client.port = int(port)

        logging.debug("Selected IP %s port %s" % (ip, port))
        self.top.destroy()


class MainWindow(tk.Tk):
    """
    Main class
    """
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
        self.frm_menu = MenuFrame(self.pn_main, self.frm_sudoku, self)

        # Add panes to main pane
        self.pn_main.add(self.frm_menu)
        self.pn_main.add(self.pn_sudoku)

    def set_server(self, server):
        """
        Set server to control (run by Host button)
        :param server: class Server
        :return: None
        """
        self.frm_menu.set_server(server)

    def set_client(self, client):
        """
        Set client to control (Join to the server, UI triggers)
        :param client: class Client
        :return: None
        """
        self.frm_sudoku.set_client(client)
        self.frm_menu.set_client(client)

    def notify(self, notification):
        """
        Add a new notification to the notification textbox
        :param notification:
        :return: None
        """
        return self.frm_menu.frm_notifications.add(notification)

    def set_sudoku(self, sudoku):
        """
        Set sudoku to the board
        :param sudoku: list, 81 elements
        :return: None
        """
        self.frm_sudoku.set_sudoku(sudoku)

    def set_leaderboard(self, lb):
        """
        Set leaderboard
        :param lb: leaderboard, dict name: points
        :return: None
        """
        self.frm_menu.frm_leaderboard.fill(lb)


if __name__ == "__main__":
    LOG.error("This file was not designed to run standalone")
    exit(0)


