'''
Created on Oct 18, 2016

@author: devel
'''
from tempfile import mktemp
logfile = mktemp()
import logging
FORMAT='%(asctime)s (%(threadName)-2s) %(message)s'
logging.basicConfig(filename=logfile,\
                            filemode='a',level=logging.DEBUG,format=FORMAT)
from threading import Thread, Condition, Lock, currentThread
from getpass import getpass
from base64 import decodestring, encodestring
from socket import AF_INET, SOCK_STREAM, socket, SHUT_RD
from socket import error as soc_err

import pickle

# Requests --------------------------------------------------------------------
REQ_GM_GET_STATE = 'A'
REQ_GM_GUESS = 'B'
REQ_GM_SET_SUDOKU = 'C'
REQ_GM_SET_NAME = 'D'
REQ_GM_GET_SESSIONS = 'S'
CTR_MSGS = { REQ_GM_GET_STATE:'Get the current state of the guessed word',
             REQ_GM_GUESS:'Propose a letter to guess',
             REQ_GM_SET_SUDOKU:'Propose a new word to guess',
             REQ_GM_GET_SESSIONS: 'Get all possible sessions'
            }
# Responses--------------------------------------------------------------------
RSP_GM_STATE = 'a'
RSP_GM_GUESS = 'b'
RSP_GM_SET_SUDOKU = 'c'
RSP_GM_SET_NAME = 'd'
RSP_GM_NOT_JOINED = 'x'
RSP_UNKNCONTROL = '4'
RSP_BADFORMAT = '5'
RSP_GM_NOTIFY = 'e'
RSP_GM_SESSIONS = 's'
# Assuming message itself is base64 encoded
# Field separator for sending multiple values ---------------------------------
MSG_FIELD_SEP = ':'
# Message separator for sending multiple messages------------------------------
MSG_SEP = ';'

DEFAULT_RCV_BUFSIZE = 1

def serialize(msg):
    #return encodestring(msg)
    return pickle.dumps(msg)

def deserialize(msg):
    #return decodestring(msg)
    return pickle.loads(msg)

class OutputClosedException(Exception):

    def __init__(self):
        Exception.__init__(self, 'Output PIPE closed!')

class InputClosedException(Exception):

    def __init__(self):
        Exception.__init__(self, 'Input PIPE closed!')


def enum(**vals):
    return type('Enum', (), vals)

class AbstractSyncIO:

    ioclose = enum(IN=0,OUT=1,BOTH=2)

    def __init__(self):
        self.__console_lock = Condition()
        self.__input_lock = False
        self.__output_closed = False
        self.__input_closed = False

    def output(self,msg):
        raise NotImplementedError

    def output_sync(self,msg):
        if self.__output_closed:
            raise OutputClosedException
        with self.__console_lock:
            while self.__input_lock:
                self.__console_lock.wait()
                if self.__output_closed:
                    raise OutputClosedException
            self.output(msg)

    def input(self,prompt='',hidden=False):
        raise NotImplementedError

    def __input_closed_excpetion_wrap(self,prompt='',hidden=False):
        if self.__input_closed:
            raise InputClosedException
        return self.input(prompt, hidden)

    def input_sync(self,prompt='>> '):
        self.__input_closed_excpetion_wrap(hidden=True)
        with self.__console_lock:
            self.__input_lock = True
        msg = self.__input_closed_excpetion_wrap(prompt)
        while len(msg) <= 0:
            msg = self.__input_closed_excpetion_wrap(prompt)
        with self.__console_lock:
            self.__input_lock = False
            self.__console_lock.notifyAll()
        return msg

    def close(self,pipe=ioclose.BOTH):
        if pipe in [self.ioclose.BOTH, self.ioclose.IN]:
            with self.__console_lock:
                if not self.__input_closed:
                    self.__input_closed = True
        if pipe in [self.ioclose.BOTH, self.ioclose.OUT]:
            with self.__console_lock:
                if not self.__output_closed:
                    self.__output_closed = True

class SyncConsoleAppenderRawInputReader(AbstractSyncIO):

    def output(self, msg, show_caller=False):
        if show_caller:
            caller = currentThread()
            print '%s: %s' % (caller.name, msg)
        else:
            print msg

    def input(self, prompt='', hidden=False):
        if hidden:
            return getpass(prompt)
        return raw_input(prompt)

    #def input(self, prompt='', hidden=False):
     #  return raw_input(prompt)

class Client():

    __gm_states = enum(
        NOTCONNECTED = 0,
        NEED_SESSION = 1,
        NEED_NAME = 2,
        NEED_SUDOKU = 3,
        NEED_NUMBER = 4
    )

    __gm_ui_input_prompts = {
        __gm_states.NEED_SESSION : 'Select session or create new',
        __gm_states.NEED_NAME : 'Enter player name to join the game!',
        __gm_states.NEED_SUDOKU : 'Enter complexity of sudoku to generate!',
        __gm_states.NEED_NUMBER : 'Enter the number and position you guess!'
    }

    def __init__(self,io):
        # Network related
        self.__send_lock = Lock()   # Only one entity can send out at a time

        # Here we collect the received responses and notify the waiting
        # entities
        self.__rcv_sync_msgs_lock = Condition()  # To wait/notify on received
        self.__rcv_sync_msgs = [] # To collect the received responses
        self.__rcv_async_msgs_lock = Condition()
        self.__rcv_async_msgs = [] # To collect the received notifications

        self.__io = io  # User interface IO

        # Current state of the game client
        self.__gm_state_lock = Lock()
        self.__gm_state = self.__gm_states.NOTCONNECTED
        self.__my_name = None
        self.__current_progress = []

    def __state_change(self,newstate):
        '''Set the new state of the game'''
        with self.__gm_state_lock:
            self.__gm_state = newstate
            logging.debug('Games state changed to [%d]' % newstate)
            self.__io.output_sync(self.__gm_ui_input_prompts[newstate])

    def set_my_name(self,name):
        '''Setup player name before we can join the game'''
        payload = serialize(name)
        logging.debug(\
            'Requesting the server to set player\'s name to %s ...' % name)
        rsp = self.__sync_request(REQ_GM_SET_NAME, payload)
        if rsp != None:
            head,payload = rsp
            if head == RSP_GM_SET_NAME:
                if payload[0] == '1':
                    logging.debug('Server confirmed player\'s name')
                    self.__my_name = name
                    self.__io.output_sync('Joined the game!')
                    return True
                else:
                    logging.debug('Server rejected player\'s name')
                    self.__io.output_sync('Select different name!')
                    return False
            else:
                logging.warn('Protocol error, unexpected control code!')
                logging.warn(\
                    'Expected [%s] received [%s]' % (RSP_GM_SET_NAME,head))

    def set_new_sudoku_to_guess(self,complexity):
        '''Propose the new word to guess'''
        payload = serialize(complexity)
        logging.debug(\
            'Requesting the server to the new sudoku to guess with complexity %s ...' % complexity)
        rsp = self.__sync_request(REQ_GM_SET_SUDOKU, payload)
        if rsp != None:
            head,payload = rsp
            if head == RSP_GM_SET_SUDOKU:
                if payload[0] == '1':
                    logging.debug('Server confirmed complexity settings: %s' % complexity)
                    self.__io.output_sync('Let others guess')
                    return True
                else:
                    logging.debug('Server rejected player\'s complexity %s' % complexity)
                    logging.debug('Someone was faster in setting complexity!')
                    return False
            else:
                logging.warn('Protocol error, unexpected control code!')
                logging.warn(\
                    'Expected [%s] received [%s]' % (RSP_GM_SET_SUDOKU,head))

    def guess_number(self,input_str):
        '''Guess the number'''
        num,pos1,pos2 = input_str.split(' ')
        num=int(num)
        pos1 = int(pos1)
        pos2 = int(pos2)
        pos = [pos1,pos2]
        logging.debug(\
            'Requesting the server to guess %i on [%i][%i] ...' % (num,pos1,pos2))
        payload = serialize((num,pos))
        rsp = self.__sync_request(REQ_GM_GUESS, payload)
        if rsp != None:
            head,payload = rsp
            if head == RSP_GM_GUESS:
                if payload[0] == '1':
                    logging.debug('Server confirmed %i on [%i][%i]' % (num,pos[0],pos[1]))
                    return True
                else:
                    logging.debug('Server rejected %i on [%i][%i]' % (num,pos[0],pos[1]))
                    self.__io.output_sync('Wrong number %i on [%i][%i]' % (num,pos[0],pos[1]))
                    self.get_current_progress()
                    return False
            else:
                logging.warn('Protocol error, unexpected control code!')
                logging.warn(\
                    'Expected [%s] received [%s]' % (RSP_GM_GUESS,head))

    def get_current_progress(self):
        '''Get current progress of word guessing'''
        logging.debug(\
            'Requesting the current state ...')
        rsp = self.__sync_request(REQ_GM_GET_STATE)
        if rsp != None:
            head,payload = rsp
            if head == RSP_GM_STATE:
                uncovered_sudoku = deserialize(payload)
                self.__current_progress = uncovered_sudoku
                if len(uncovered_sudoku) > 0:
                    logging.debug('Current uncovered sudoku [%s] received' %
                                  [' '.join([str(c) for c in lst]) for lst in uncovered_sudoku])
                    self.__io.output_sync('Current progress: [%s]' %
                                          [' '.join([str(c) for c in lst]) for lst in uncovered_sudoku])
                    self.__state_change(self.__gm_states.NEED_NUMBER)
                else:
                    if self.__gm_state != self.__gm_states.NEED_SUDOKU:
                        self.__state_change(self.__gm_states.NEED_SUDOKU)
            else:
                logging.warn('Protocol error, unexpected control code!')
                logging.warn(\
                    'Expected [%s] received [%s]' % (RSP_GM_STATE,head))

    def stop(self):
        '''Stop the game client'''
        try:
            self.__s.shutdown(SHUT_RD)
        except soc_err:
            logging.warn('Was not connected anyway ..')
        finally:
            self.__s.close()
        self.__sync_response('DIE!')
        self.__async_notification('DIE!')

    def connect(self,srv_addr):
        '''Connect to server, start game session'''
        self.__s = socket(AF_INET,SOCK_STREAM)
        try:
            self.__s.connect(srv_addr)
            logging.info('Connected to Game server at %s:%d' % srv_addr)
            self.__state_change(self.__gm_states.NEED_SESSION)
            return True
        except soc_err as e:
            logging.error('Can not connect to Game server at %s:%d'\
                      ' %s ' % (srv_addr+(str(e),)))
            self.__io.output_sync('Can\'t connect to server!')
        return False

    def __sync_request(self,header,payload=''):
        '''Send request and wait for response'''
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

    def __sync_response(self,rsp):
        '''Collect the received response, notify waiting threads'''
        with self.__rcv_sync_msgs_lock:
            was_empty = len(self.__rcv_sync_msgs) <= 0
            self.__rcv_sync_msgs.append(rsp)
            if was_empty:
                self.__rcv_sync_msgs_lock.notifyAll()

    def __async_notification(self,msg):
        '''Collect the received server notifications, notify waiting threads'''
        with self.__rcv_async_msgs_lock:
            was_empty = len(self.__rcv_async_msgs) <= 0
            self.__rcv_async_msgs.append(msg)
            if was_empty:
                self.__rcv_async_msgs_lock.notifyAll()

    def __session_rcv(self):
        '''Receive the block of data till next block separator'''
        m,b = '',''
        try:
            b = self.__s.recv(DEFAULT_RCV_BUFSIZE)
            m += b
            while len(b) > 0 and not (b.endswith(MSG_SEP)):
                b = self.__s.recv(DEFAULT_RCV_BUFSIZE)
                m += b
            if len(b) <= 0:
                logging.debug( 'Socket receive interrupted'  )
                self.__s.close()
                m = ''
            m = m[:-1]
        except KeyboardInterrupt:
            self.__s.close()
            logging.info( 'Ctrl+C issued, terminating ...' )
            m = ''
        except soc_err as e:
            if e.errno == 107:
                logging.warn( 'Server closed connection, terminating ...' )
            else:
                logging.error( 'Connection error: %s' % str(e) )
            self.__s.close()
            logging.info( 'Disconnected' )
            m = ''
        return m

    def __session_send(self,msg):
        '''Just wrap the data, append the block separator and send out'''
        m = msg + MSG_SEP + session_number # sens message (data from prompt + message separator ?? + number of session

        r = False
        try:
            self.__s.sendall(m)
            r = True
        except KeyboardInterrupt:
            self.__s.close()
            logging.info( 'Ctrl+C issued, terminating ...' )
        except soc_err as e:
            if e.errno == 107:
                logging.warn( 'Server closed connection, terminating ...' )
            else:
                logging.error( 'Connection error: %s' % str(e) )
            self.__s.close()
            logging.info( 'Disconnected' )
        return r

    def __protocol_rcv(self,message):
        '''Process received message:
        server notifications and request/responses separately'''
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
        '''Gather user input'''
        try:
            print('Trying!!!')
            msg = self.__io.input_sync()
            logging.debug('User entered: %s' % msg)
            return msg
        except InputClosedException:
            return None

    def game_loop(self):
        '''Main game loop (assuming network-loop and notifications-loop are
        running already'''

        logging.info('Falling to game loop ...')
        self.__io.output_sync('Press Enter to initiate input, ')
        self.__io.output_sync(\
            'Type in your message (or Q to quit), hit Enter to submit')
        available_sessions = self.get_sessions()
        self.__io.output_sync('Available sessions: %s' % ' '.join(available_sessions))
        while 1:
            user_input = self.__get_user_input()
            print(user_input)
            if user_input == 'Q':
                break
            if self.__gm_state == self.__gm_states.NEED_SESSION:
                self.join_session(user_input)                           # create function!!!!!!!!!
            elif self.__gm_state == self.__gm_states.NEED_NAME:
                self.set_my_name(user_input)
            elif self.__gm_state == self.__gm_states.NEED_SUDOKU:
                self.set_new_sudoku_to_guess(user_input)
            elif self.__gm_state == self.__gm_states.NEED_NUMBER:
                self.guess_number(user_input)
        self.__io.output_sync('Q entered, disconnecting ...')

    def notifications_loop(self):
        '''Iterate over received notifications, show them to user, wait if
        no notifications'''

        logging.info('Falling to notifier loop ...')
        while 1:
            with self.__rcv_async_msgs_lock:
                if len(self.__rcv_async_msgs) <= 0:
                    self.__rcv_async_msgs_lock.wait()
                msg = self.__rcv_async_msgs.pop(0)
                if msg == 'DIE!':
                    return
            self.__io.output_sync('Server Notification: %s' % msg)
            self.get_current_progress()

    def network_loop(self):
        '''Network Receiver/Message Processor loop'''
        logging.info('Falling to receiver loop ...')
        while 1:
            m = self.__session_rcv()
            if len(m) <= 0:
                break
            self.__protocol_rcv(m)

    def get_sessions(self):
        '''Get current sessions'''
        logging.debug( \
            'Requesting the current sessions ...')

        rsp = self.__sync_request(REQ_GM_GET_SESSIONS)
        available_sessions = []
        if rsp is not None:
            head, payload = rsp
            if head == RSP_GM_SESSIONS:
                available_sessions = deserialize(payload)
                if len(available_sessions) > 0:
                    logging.debug('Current sessions [%s] received' %
                                  ' '.join(available_sessions))
                    self.__io.output_sync('Available sessions: [%s]' %
                                          ' '.join(available_sessions))
                else:
                    logging.debug('No available sessions')
                    self.__io.output_sync('No available sessions')
            else:
                logging.warn('Protocol error, unexpected control code!')
                logging.warn( \
                    'Expected [%s] received [%s]' % (RSP_GM_SESSIONS, head))
        return available_sessions

    def join_session(self,num):
        if num == 0:  # start new session
            self.start_new_session()
        else:
            self.join_session(num)
        self.__state_change(self.__gm_states.NEED_NAME)




if __name__ == '__main__':
    srv_addr = ('127.0.0.1',7777)

    print 'Application start ...'
    print 'Will write log to %s' % logfile

    sync_io = SyncConsoleAppenderRawInputReader()
    client = Client(sync_io)
    print('Created client')
    if client.connect(srv_addr):

        network_thread = Thread(name='NetworkThread',target=client.network_loop)
        notifications_thread =\
             Thread(name='NotificationsThread',target=client.notifications_loop)
        network_thread.start()
        notifications_thread.start()

        try:
            client.game_loop()
        except KeyboardInterrupt:
            logging.warn('Ctrl+C issued, terminating ...')
        finally:
            client.stop()

        network_thread.join()
        notifications_thread.join()

    logging.info('Terminating')