from threading import Thread, Lock, currentThread
from socket import AF_INET, SOCK_STREAM, socket, SOCK_DGRAM, SOL_SOCKET, SO_BROADCAST
from socket import IPPROTO_IP, IP_MULTICAST_TTL
from socket import error as soc_err
import struct

from protocol import *
from sudoku import *

from SimpleXMLRPCServer import SimpleXMLRPCServer
from SimpleXMLRPCServer import SimpleXMLRPCRequestHandler

import logging

logging.basicConfig(level=logging.DEBUG,
                    format='%(asctime)s (%(threadName)-2s) %(message)s')
LOG = logging.getLogger()

class MyServerRequestHandler(SimpleXMLRPCRequestHandler):
    rpc_paths = ('/RPC2',)


class Game:
    def __init__(self):
        self.__gm_lock = Lock()
        self.__scores = {}
        self.__players = []
        self.__sudoku_to_guess = []
        self.__sudoku_uncovered = []

        # broadcast sender socket
        self.sender_sock = socket(AF_INET, SOCK_DGRAM)
        self.sender_sock.setsockopt(SOL_SOCKET, SO_BROADCAST, 1)

        # ttl = struct.pack('b', 1)
        # self.sender_sock.setsockopt(IPPROTO_IP, IP_MULTICAST_TTL, ttl)

    def send_to_all(self, name, message):
        logging.debug("Broadcast notification: %s - %s" % (name, message))
        if message != 'EXIT':
            self.sender_sock.sendto(name + ' ' + message, (DEFAULT_BROADCAST_ADDR, DEFAULT_SERVER_PORT))
        else:
            self.sender_sock.close()

    def check_name(self, name):
        # Function for RPC
        # (copy from self.join, added PlayerSession)
        #players = map(lambda x: x.getName(), self.__players)
        if name in self.__players:
            return False
        # ??? do we need PlayerSession?
        #client_session = PlayerSession(name,self)
        self.__players.append(name)
        self.send_to_all(name, 'joined the game!')
        self.__scores[name] = 0
        #self.__notify_update('joined game!')
        return True

    #def __notify_update(self, message):
    #    caller = currentThread().getName()
    #    joined = filter(lambda x: x.is_joined(), self.__players)
    #    map(lambda x: x.notify('%s %s' % (caller, message)), joined)

    #can delete
    def remove_me(self):
        caller = currentThread()
        if caller in self.__players:
            self.__players.remove(caller)
            logging.info('%s left game' % caller.getName())
            self.__notify_update('left game')

    #can delete
    def join(self, name, client_session):
        players = map(lambda x: x.getName(),self.__players)
        if name in players:
            return False
        self.__players.append(client_session)
        self.__notify_update('joined game!')
        return True

    def set_new_sudoku(self, name, complexity):
        # Function for RPC
        r = False
        with self.__gm_lock:
            if len(self.__sudoku_to_guess) <= 0:
                sudoku = get_sudoku(int(complexity))
                self.__sudoku_to_guess = sudoku["s"]
                self.__sudoku_uncovered = sudoku["u"]
                self.send_to_all(name, 'did set new sudoku to guess!')
                r = True
        return r

    def __reset(self):
        self.__sudoku_to_guess = []
        self.__sudoku_uncovered = []

    def guess_number(self, num, pos,name):
        # Function for RPC
        with self.__gm_lock:
            r = False
            if num == self.__sudoku_to_guess[pos[0]][pos[1]]:
                self.__sudoku_uncovered[pos[0]][pos[1]] = num
                self.send_to_all(name, 'did guess %i in position [%i][%i]!' % (num,pos[0],pos[1]))
                r = True
                self.__scores[name] = self.__scores[name] + 1
                logging.debug(self.__scores)
            else:
                self.__scores[name] = self.__scores[name] - 1
                logging.debug(self.__scores)
            if self.__sudoku_uncovered == self.__sudoku_to_guess:
                # sud = self.__sudoku_to_guess
                self.__reset()
                self.send_to_all(name, 'did solve the sudoku')
        return r

    def set_name(self, name):
        self.__scores[name] = 0

    def get_current_state(self):
        """
        Returns unsolved sudoku and leaderboard
        """
        with self.__gm_lock:
            # s = self.__uncovered
            s = self.__sudoku_uncovered
            l = self.__scores
        return s, l


#can delete
class PlayerSession(Thread):
    def __init__(self, game, name):
        Thread.__init__(self)
        #self.__s = soc
        #self.__addr = soc_addr
        self.__send_lock = Lock()
        self.__game = game
        self.__name = name

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

    def __guess_number(self, num, pos, name):
        if not self.is_joined():
            return self.__reply_err_not_joined()
        return self.__reply_guess_number(self.__game.guess_number(num, pos, name))

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
            self.__game.set_name(name)
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
    def __init__(self, game, sock_addr):
        self.__clients = []
        self.__game = game
        self.server_sock = sock_addr
        self.server = None

    def listen(self):
        # Create XML_server
        self.server = SimpleXMLRPCServer(self.server_sock, requestHandler=MyServerRequestHandler)
        LOG.debug('Server started')
        self.server.register_introspection_functions()
        # Register all functions
        # Register server-side functions into RPC middleware
        self.server.register_instance(self.__game)
        # self.server.register_function(function_name)

    # def listen(self, sock_addr, backlog=1):
    #     self.__sock_addr = sock_addr
    #     self.__backlog = backlog
    #     self.__s = socket(AF_INET, SOCK_STREAM)
    #     self.__s.bind(self.__sock_addr)
    #     self.__s.listen(self.__backlog)
    #     LOG.debug('Socket %s:%d is in listening state' % self.__s.getsockname() )


    def loop(self):
        # LOG.info('Falling to serving loop, press Ctrl+C to terminate ...' )
        # clients = []
        # client_socket = None
        #
        # try:
        #     while True:
        #         client_socket = None
        #         LOG.info('Awaiting new clients ...')
        #         client_socket, client_addr = self.__s.accept()
        #         c = PlayerSession(client_socket, client_addr, self.__game)
        #         clients.append(c)
        #         c.start()
        # except KeyboardInterrupt:
        #     LOG.warn('Ctrl+C issued closing server ...')
        # finally:
        #     if client_socket is not None:
        #         client_socket.close()
        #     self.__s.close()
        # map(lambda x: x.join(), clients)
        try:
            self.server.serve_forever()
        except KeyboardInterrupt:
            print 'Ctrl+C issued, terminating ...'
        finally:
            self.server.shutdown()  # Stop the serve-forever loop
            self.server.server_close()  # Close the sockets
        print 'Terminating ...'


if __name__ == '__main__':
    game = Game()
    server = GameServer(game,('127.0.0.1', 7777))
    #server.listen(('127.0.0.1', 7777))
    server.loop()
    LOG.info('Terminating...')
