from threading import Thread, Lock, currentThread
from socket import AF_INET, SOCK_STREAM, socket
from socket import error as soc_err

from protocol import *
from sudoku import *

import logging
logging.basicConfig(level=logging.DEBUG,
                    format='%(asctime)s (%(threadName)-2s) %(message)s')
LOG = logging.getLogger()


class Game:
    def __init__(self):
        self.__gm_lock = Lock()
        self.__scores = {}
        self.__players = []
        self.__sudoku_to_guess = []
        self.__sudoku_uncovered = []

    def __notify_update(self, message):
        caller = currentThread().getName()
        joined = filter(lambda x: x.is_joined(), self.__players)
        map(lambda x: x.notify('%s %s' % (caller, message)), joined)

    def remove_me(self):
        caller = currentThread()
        if caller in self.__players:
            self.__players.remove(caller)
            logging.info('%s left game' % caller.getName())
            self.__notify_update('left game')

    def join(self, name, client_session):
        players = map(lambda x: x.getName(),self.__players)
        if name in players:
            return False
        self.__players.append(client_session)
        self.__notify_update('joined game!')
        return True

    def set_new_sudoku(self, complexity):
        r = False
        with self.__gm_lock:
            if len(self.__sudoku_to_guess) <= 0:
                sudoku = get_sudoku(int(complexity))
                self.__sudoku_to_guess = sudoku["s"]
                self.__sudoku_uncovered = sudoku["u"]
                self.__notify_update('did set new sudoku to guess!')
                r = True
        return r

    def __reset(self):
        # self.__to_guess = ''
        # self.__uncovered = ''
        # self.__ok_letters = []
        self.__sudoku_to_guess = []
        self.__sudoku_uncovered = []

    def guess_number(self, num, pos,name):
        with self.__gm_lock:
            r = False
            if num == self.__sudoku_to_guess[pos[0]][pos[1]]:
                self.__sudoku_uncovered[pos[0]][pos[1]] = num
                self.__notify_update('did guess %i in position [%i][%i]!' % (num,pos[0],pos[1]))
                r = True
                self.__scores[name] = self.__scores[name] + 1
                print(self.__scores)
             else:
                self.__scores[name] = self.__scores[name] - 1
                print(self.__scores)
            if self.__sudoku_uncovered == self.__sudoku_to_guess:
                self.__reset()
                self.__notify_update('did solve the sudoku')
        return r

    def get_current_state(self):
        """Returns unsolved sudoku and leaderboard"""
        with self.__gm_lock:
            # s = self.__uncovered
            s = self.__sudoku_uncovered
            l = self.__scores
        return s, l


class PlayerSession(Thread):
    def __init__(self, soc, soc_addr, game):
        Thread.__init__(self)
        self.__s = soc
        self.__addr = soc_addr
        self.__send_lock = Lock()
        self.__game = game
        self.__name = None

    def getName(self):
        return self.__name

    def __join(self, name, game):
        self.__name = name
        ok = game.join(name,self)
        return self.__reply_join(ok)

    def __reply_join(self,ok):
        return RSP_GM_SET_NAME+MSG_FIELD_SEP+('1' if ok else '0')

    def is_joined(self):
        return self.__game != None

    def __reply_err_not_joined(self):
        return RSP_GM_NOT_JOINED+MSG_FIELD_SEP

    def __reply_set_new_sudoku(self, ok):
        return RSP_GM_SET_SUDOKU+MSG_FIELD_SEP+('1' if ok else '0')

    def __reply_guess_number(self, ok):
        return RSP_GM_GUESS+MSG_FIELD_SEP+('1' if ok else '0')

    def __set_new_sudoku(self, complexity):
        if not self.is_joined():
            return self.__reply_err_not_joined()
        return self.__reply_set_new_sudoku(self.__game.set_new_sudoku(complexity))

    def __guess_number(self, num, pos,name):
        if not self.is_joined():
            return self.__reply_err_not_joined()
        return self.__reply_guess_number(self.__game.guess_number(num,pos,name))

    def __current_state(self):
        if not self.is_joined():
            return self.__reply_err_not_joined()
        return RSP_GM_STATE + MSG_FIELD_SEP + serialize(self.__game.get_current_state())

    def __session_rcv(self):
        m, b = '', ''
        try:
            b = self.__s.recv(DEFAULT_RCV_BUFSIZE)
            m += b
            while len(b) > 0 and not (b.endswith(MSG_SEP)):
                b = self.__s.recv(DEFAULT_RCV_BUFSIZE)
                m += b
            if len(b) <= 0:
                self.__s.close()
                LOG.info('Client %s:%d disconnected' % self.__addr)
                m = ''
            m = m[:-1]
        except KeyboardInterrupt:
            self.__s.close()
            LOG.info('Ctrl+C issued, disconnecting client %s:%d' % self.__addr)
            m = ''
        except soc_err as e:
            if e.errno == 107:
                LOG.warn( 'Client %s:%d left before server could handle it' %  self.__addr)
            else:
                LOG.error('Error: %s' % str(e))
            self.__s.close()
            LOG.info('Client %s:%d disconnected' % self.__addr)
            m = ''
        return m

    def __protocol_rcv(self, message):
        LOG.debug('Received request [%d bytes] in total' % len(message))
        if len(message) < 2:
            LOG.debug('Not enough data received from %s ' % message)
            return RSP_BADFORMAT
        payload = message[2:]

        if message.startswith(REQ_GM_SET_NAME + MSG_FIELD_SEP):
            name = deserialize(payload)
            LOG.debug('Client %s:%d will use name %s' % (self.__addr+(name,)))
            rsp = self.__join(name, self.__game)

        elif message.startswith(REQ_GM_SET_SUDOKU + MSG_FIELD_SEP):
            complexity = deserialize(payload)
            LOG.debug('Client %s:%d wants to set new sudoku with complexity %s' % (self.__addr+(complexity,)))
            rsp = self.__set_new_sudoku(complexity)

        elif message.startswith(REQ_GM_GUESS + MSG_FIELD_SEP):
            user_input = deserialize(payload)
            num, pos, name = user_input
            pos = [int(x) for x in pos]
            LOG.debug('Client %s:%d proposes number %s' % (self.__addr+(num,)))
            rsp = self.__guess_number(num, pos, name)

        elif message.startswith(REQ_GM_GET_STATE + MSG_FIELD_SEP):
            LOG.debug('Client %s:%d asks for current uncovered sudoku' % self.__addr)
            rsp = self.__current_state()

        else:
            LOG.debug('Unknown control message received: %s ' % message)
            rsp = RSP_UNKNCONTROL
        return rsp

    def __session_send(self, msg):
        m = msg + MSG_SEP
        with self.__send_lock:
            r = False
            try:
                self.__s.sendall(m)
                r = True
            except KeyboardInterrupt:
                self.__s.close()
                LOG.info('Ctrl+C issued, disconnecting client %s:%d' % self.__addr)
            except soc_err as e:
                if e.errno == 107:
                    LOG.warn('Client %s:%d left before server could handle it' %  self.__addr )
                else:
                    LOG.error('Error: %s' % str(e) )
                self.__s.close()
                LOG.info('Client %s:%d disconnected' % self.__addr )
            return r

    def notify(self, message):
        payload = serialize(message)
        self.__session_send(RSP_GM_NOTIFY+MSG_FIELD_SEP+payload)

    def run(self):
        while 1:
            m = self.__session_rcv()
            if len(m) <= 0:
                break
            rsp = self.__protocol_rcv(m)
            if rsp == RSP_BADFORMAT:
                break
            if not self.__session_send(rsp):
                break
        self.__game.remove_me()


class GameServer:
    def __init__(self, game):
        self.__clients = []
        self.__game = game

    def listen(self, sock_addr, backlog=1):
        self.__sock_addr = sock_addr
        self.__backlog = backlog
        self.__s = socket(AF_INET, SOCK_STREAM)
        self.__s.bind(self.__sock_addr)
        self.__s.listen(self.__backlog)
        LOG.debug('Socket %s:%d is in listening state' % self.__s.getsockname() )

    def loop(self):
        LOG.info('Falling to serving loop, press Ctrl+C to terminate ...' )
        clients = []
        client_socket = None

        try:
            while True:
                client_socket = None
                LOG.info('Awaiting new clients ...')
                client_socket, client_addr = self.__s.accept()
                c = PlayerSession(client_socket, client_addr, self.__game)
                clients.append(c)
                c.start()
        except KeyboardInterrupt:
            LOG.warn('Ctrl+C issued closing server ...')
        finally:
            if client_socket is not None:
                client_socket.close()
            self.__s.close()
        map(lambda x: x.join(), clients)


if __name__ == '__main__':
    game = Game()
    server = GameServer(game)
    server.listen(('127.0.0.1', 7777))
    server.loop()
    LOG.info('Terminating...')
