from tempfile import mktemp
from threading import Thread, Condition, Lock
from socket import AF_INET, SOCK_STREAM, socket, SHUT_RD
from socket import inet_aton, IP_ADD_MEMBERSHIP,SOL_SOCKET, SO_REUSEADDR, SOCK_DGRAM, IPPROTO_IP
from socket import error as soc_err

from protocol import *
from syncIO import *

from xmlrpclib import ServerProxy

import logging
logfile = mktemp()
logging.basicConfig(filename=logfile,
                    filemode='a',
                    level=logging.DEBUG,
                    format='%(asctime)s (%(threadName)-2s) %(message)s')


class Client:

    __gm_states = enum(
        NOTCONNECTED=0,
        NEED_NAME=2,
        NEED_SUDOKU=3,
        NEED_NUMBER=4
    )

    __gm_ui_input_prompts = {
        __gm_states.NEED_NAME: 'Enter player name to join the game!',
        __gm_states.NEED_SUDOKU: 'Enter complexity of sudoku to generate!',
        __gm_states.NEED_NUMBER: 'Enter the number and position you guess!'
    }

    def __init__(self, io):
        # Network related
        self.__send_lock = Lock()   # Only one entity can send out at a time

        # Here we collect the received responses and notify the waiting entities
        self.__rcv_sync_msgs_lock = Condition()  # To wait/notify on received
        self.__rcv_sync_msgs = []  # To collect the received responses
        self.__rcv_async_msgs_lock = Condition()
        self.__rcv_async_msgs = []  # To collect the received notifications

        self.__io = io  # User interface IO

        # Current state of the game client
        self.__gm_state_lock = Lock()
        self.__gm_state = self.__gm_states.NOTCONNECTED
        self.__my_name = None
        self.__current_progress = []

        # RPC proxy
        self.__proxy = None

        # GUI to control
        self.gui = None

        # broadcast receiver socket
        self.receiver_sock = socket(AF_INET, SOCK_DGRAM)
        membership = inet_aton(DEFAULT_SERVER_INET_ADDR) + inet_aton(bind_addr)
        self.receiver_sock.setsockopt(IPPROTO_IP, IP_ADD_MEMBERSHIP, membership)
        self.receiver_sock.setsockopt(SOL_SOCKET, SO_REUSEADDR, 1)
        self.receiver_sock.bind((bind_addr, DEFAULT_SERVER_PORT))

    def set_gui(self, gui):
        self.gui = gui

    def __state_change(self, newstate):
        """
        Set the new state of the game
        """

        with self.__gm_state_lock:
            self.__gm_state = newstate
            logging.debug('Games state changed to [%d]' % newstate)
            self.notify(self.__gm_ui_input_prompts[newstate])

    def set_my_name(self, name):
        """
        Setup player name before we can join the game
        """

        #payload = serialize(name)
        logging.debug('Requesting the server to set player\'s name to %s ...' % name)
        #rsp = self.__sync_request(REQ_GM_SET_NAME, payload)
        with self.__send_lock:
            rsp = self.__proxy.check_name(name)
        if rsp is not None:
            if rsp:
                logging.debug('Server confirmed player\'s name')
                self.__my_name = name
                self.notify('You joined the game!')
                return True
            else:
                logging.debug('Server rejected player\'s name')
                self.notify('Please select different name.')
                return False

    def set_new_sudoku_to_guess(self, complexity):
        """
        Propose the new word to guess
        """

        #payload = serialize(complexity)
        logging.debug('Requesting the server to the new sudoku to guess with complexity %s ...' % complexity)
        #rsp = self.__sync_request(REQ_GM_SET_SUDOKU, payload)
        with self.__send_lock:
            rsp = self.__proxy.set_new_sudoku(self.__my_name, complexity)
        if rsp is not None:
            if rsp:
                logging.debug('Server confirmed complexity settings: %s' % complexity)
                self.notify('Let others guess')
                return True
            else:
                logging.debug('Server rejected player\'s complexity %s' % complexity)
                self.notify('Someone was faster in setting complexity!')
                return False


    def guess_number(self, input_str):
        """
        Guess the number
        """
        logging.debug("Guess number: incoming string %s" % input_str)
        num, pos1, pos2 = input_str.split(' ')
        num = int(num)
        pos1 = int(pos1)
        pos2 = int(pos2)
        pos = [pos1, pos2]
        logging.debug('Requesting the server to guess %i on [%i][%i] ...' % (num, pos1, pos2))
        #payload = serialize((num,pos, self.__my_name))
        #rsp = self.__sync_request(REQ_GM_GUESS, payload)
        with self.__send_lock:
            rsp = self.__proxy.guess_number(num,pos, self.__my_name)
        if rsp is not None:
            if rsp:
                logging.debug('Server confirmed %i on [%i][%i]' % (num, pos[0], pos[1]))
                return True
            else:
                logging.debug('Server rejected %i on [%i][%i]' % (num, pos[0], pos[1]))
                self.notify('Wrong number %i on [%i][%i]' % (num, pos[0], pos[1]))
                self.get_current_progress()
                return False

    def get_current_progress(self):
        """
        Get current progress of sudoku guessing and players leaderboard (tuple)
        """

        logging.debug('Requesting the current state ...')
        #rsp = self.__sync_request(REQ_GM_GET_STATE)
        uncovered_sudoku, leaderboard = None, None
        with self.__send_lock:
            rsp = self.__proxy.get_current_state()
        if rsp is not None:
            #head, payload = rsp
            #if head == RSP_GM_STATE:
            #    uncovered_sudoku, leaderboard = deserialize(payload)
            uncovered_sudoku, leaderboard = rsp
            self.__current_progress = uncovered_sudoku
            if len(uncovered_sudoku) > 0:
                logging.debug('Current uncovered sudoku [%s] received' %
                              [' '.join([str(c) for c in lst]) for lst in uncovered_sudoku])
                self.notify('Current progress: [%s]' %
                                      [' '.join([str(c) for c in lst]) for lst in uncovered_sudoku])
                self.notify('Current leaderboard: [%s]' % str(leaderboard))
                self.__state_change(self.__gm_states.NEED_NUMBER)
            else:
                if self.__gm_state != self.__gm_states.NEED_SUDOKU:
                    self.__state_change(self.__gm_states.NEED_SUDOKU)
        # Return 1D list
        return [item for sublist in self.__current_progress for item in sublist], leaderboard

    def stop(self):
        """
        Stop the game client
        """

        try:
            self.__s.shutdown(SHUT_RD)
        except soc_err:
            logging.warn('Was not connected anyway ..')
        finally:
            self.__s.close()
        self.__sync_response('DIE!')
        self.__async_notification('DIE!')

    def connect(self, srv_addr):
        """
        Connect to server, start game session
        """

        self.__s = socket(AF_INET, SOCK_STREAM)
        try:
            self.__s.connect(srv_addr)
            logging.info('Connected to Game server at %s:%d' % srv_addr)
            self.__state_change(self.__gm_states.NEED_NAME)
            return True
        except soc_err as e:
            logging.error('Can not connect to Game server at %s:%d %s ' % (srv_addr+(str(e),)))
            self.__io.output_sync('Can\'t connect to server!')
        return False

    def connect_proxy(self, srv_addr):
        """
        Connect to proxy server, start game session
        """
        try:
            self.__proxy = ServerProxy("http://%s:%d" % srv_addr)
            self.__proxy.__allow_none = True
            logging.info('Connected to Game server at %s:%d' % srv_addr)
            self.__state_change(self.__gm_states.NEED_NAME)
            methods = filter(lambda x: 'system.' not in x, self.__proxy.system.listMethods())
            logging.debug('Remote methods are: [%s] ' % (', '.join(methods)))
            return True
        except KeyboardInterrupt:
            logging.warn('Ctrl+C issued, terminating')
            return False
        except Exception as e:
            logging.error('Communication error %s ' % str(e))
            self.__io.output_sync('Can\'t connect to server!')
            return False

    def __sync_request(self, header, payload=''):
        """
        Send request and wait for response
        """

        with self.__send_lock:
            req = header + MSG_FIELD_SEP + payload
            if self.__session_send(req):
                with self.__rcv_sync_msgs_lock:
                    while len(self.__rcv_sync_msgs) <= 0:
                        self.__rcv_sync_msgs_lock.wait()
                    rsp = self.__rcv_sync_msgs.pop()
                if rsp != 'DIE!':
                    return rsp.split(MSG_FIELD_SEP)
            return None

    def __sync_response(self, rsp):
        """
        Collect the received response, notify waiting threads
        """

        with self.__rcv_sync_msgs_lock:
            was_empty = len(self.__rcv_sync_msgs) <= 0
            self.__rcv_sync_msgs.append(rsp)
            if was_empty:
                self.__rcv_sync_msgs_lock.notifyAll()

    def __async_notification(self, msg):
        """
        Collect the received server notifications, notify waiting threads
        """

        with self.__rcv_async_msgs_lock:
            was_empty = len(self.__rcv_async_msgs) <= 0
            self.__rcv_async_msgs.append(msg)
            if was_empty:
                self.__rcv_async_msgs_lock.notifyAll()

    def __session_rcv(self):
        """
        Receive the block of data till next block separator
        """

        m, b = '', ''
        try:
            b = self.__s.recv(DEFAULT_RCV_BUFSIZE)
            m += b
            while len(b) > 0 and not (b.endswith(MSG_SEP)):
                b = self.__s.recv(DEFAULT_RCV_BUFSIZE)
                m += b
            if len(b) <= 0:
                logging.debug('Socket receive interrupted')
                self.__s.close()
                m = ''
            m = m[:-1]
        except KeyboardInterrupt:
            self.__s.close()
            logging.info('Ctrl+C issued, terminating ...')
            m = ''
        except soc_err as e:
            if e.errno == 107:
                logging.warn('Server closed connection, terminating ...')
            else:
                logging.error('Connection error: %s' % str(e))
            self.__s.close()
            logging.info('Disconnected')
            m = ''
        return m

    def __session_send(self,msg):
        """
        Just wrap the data, append the block separator and send out
        """

        m = msg + MSG_SEP

        r = False
        try:
            self.__s.sendall(m)
            r = True
        except KeyboardInterrupt:
            self.__s.close()
            logging.info('Ctrl+C issued, terminating ...')
        except soc_err as e:
            if e.errno == 107:
                logging.warn('Server closed connection, terminating ...')
            else:
                logging.error('Connection error: %s' % str(e))
            self.__s.close()
            logging.info( 'Disconnected' )
        return r

    def __protocol_rcv(self, message):
        """
        Process received message:
        server notifications and request/responses separately
        """

        logging.debug('Received [%d bytes] in total' % len(message))
        if len(message) < 2:
            logging.debug('Not enough data received from %s ' % message)
            return
        logging.debug('Response control code [%s]' % message[0])
        if message.startswith(RSP_GM_NOTIFY + MSG_FIELD_SEP):
            payload = message[2:]
            notification = deserialize(payload)
            logging.debug('Server notification received: %s' % notification)
            self.__async_notification(notification)
        elif message[:2] in map(lambda x: x+MSG_FIELD_SEP,  [RSP_GM_GUESS,
                                                             RSP_GM_SET_SUDOKU,
                                                             RSP_GM_SET_NAME,
                                                             RSP_GM_STATE]):
            self.__sync_response(message)
        else:
            logging.debug('Unknown control message received: %s ' % message)
            return RSP_UNKNCONTROL

    def __get_user_input(self):
        """
        Gather user input
        """

        try:
            print('Trying!!!')
            msg = self.__io.input_sync()
            logging.debug('User entered: %s' % msg)
            return msg
        except InputClosedException:
            return None

    def game_loop(self):
        """
        Main game loop (assuming network-loop and notifications-loop are
        running already
        """

        logging.info('Falling to game loop ...')
        self.__io.output_sync('Press Enter to initiate input, ')
        self.__io.output_sync('Type in your message (or Q to quit), hit Enter to submit')
        while True:
            user_input = self.__get_user_input()
            print user_input
            if user_input == 'Q':
                break
            if self.__gm_state == self.__gm_states.NEED_NAME:
                self.set_my_name(user_input)
            elif self.__gm_state == self.__gm_states.NEED_SUDOKU:
                self.set_new_sudoku_to_guess(user_input)
            elif self.__gm_state == self.__gm_states.NEED_NUMBER:
                self.guess_number(user_input)
        self.__io.output_sync('Q entered, disconnecting ...')

    def notifications_loop(self):
        """
        Iterate over received notifications, show them to user, wait if
        no notifications
        """

        logging.info('Falling to notifier loop ...')
        while True:
            with self.__rcv_async_msgs_lock:
                if len(self.__rcv_async_msgs) <= 0:
                    self.__rcv_async_msgs_lock.wait()
                msg = self.__rcv_async_msgs.pop(0)
                if msg == 'DIE!':
                    return
            self.notify('Server Notification: %s' % msg)
            state, lb = self.get_current_progress()

            # If GUI mode, update sudoku board
            if state and self.gui is not None:
                self.gui.set_sudoku(state)
                self.gui.set_leaderboard(lb)


    def network_loop(self):
        """
        Network Receiver/Message Processor loop
        """

        logging.info('Falling to receiver loop ...')
        while True:
            m = self.__session_rcv()
            if len(m) <= 0:
                break
            self.__protocol_rcv(m)

    def notify(self, text):
        if self.gui is None:
            self.__io.output_sync(text)
        else:
            self.gui.notify(text)

    def receiver_loop(self):
        logging.info('Falling to receiver loop ...')
        try:
            while True:
                try:
                    #logging.debug("Entered")
                    data, addr = self.receiver_sock.recvfrom(DEFAULT_RCV_BUFFSIZE)
                    #message = data.split()
                    #logging.info('Received message type: %s', type(data))
                    #logging.info('Received message: %s', data)
                    #print('Received message: ', data)
                    logging.debug("Received broadcast notification")
                    self.notify('Server Notification: %s' % data)
                    state, lb = self.get_current_progress()

                    # If GUI mode, update sudoku board
                    if state and self.gui is not None:
                        self.gui.set_sudoku(state)
                        self.gui.set_leaderboard(lb)
                except:
                        #socket.timeout:
                    logging.error('Time out exceeded, no more responses')
                    break
        finally:
            logging.debug('Shutting socket down')
            self.receiver_sock.shutdown(2)
            self.receiver_sock.close()



if __name__ == '__main__':
    srv_addr = ('127.0.0.1', 7777)

    logging.debug('Application start ...')
    logging.debug('Will write log to %s' % logfile)

    sync_io = SyncConsoleAppenderRawInputReader()
    client = Client(sync_io)
    logging.debug('Created client')
    #if client.connect(srv_addr):
    if client.connect_proxy(srv_addr):

        #network_thread = Thread(name='NetworkThread',target=client.network_loop)
        #notifications_thread = Thread(name='NotificationsThread',target=client.notifications_loop)
        #network_thread.start()
        #notifications_thread.start()
        receiver_thread = Thread(name='ReceiverThread',target=client.receiver_loop)
        receiver_thread.start()

        try:
            client.game_loop()
        except KeyboardInterrupt:
            logging.warn('Ctrl+C issued, terminating ...')
        finally:
            client.stop()

        #network_thread.join()
        #notifications_thread.join()
        receiver_thread.join()

    logging.info('Terminating')
