import binascii
from Generation import *
import os
import pickle
from threading import Thread, Lock, Condition
import time
from protocol import *
import operator

M = [] # Received messages (array of tuples like ((ip, port), data)
All_Sessions = {} # sessions
OUTBOX = {}
INBOX = {}
sessions_counter = 0
condition_session = Condition()
lc_message = Lock()


def get_name(key):
    print "Name of key holder", key
    return All_Sessions[key].get_name()


def add_player(key, players_name, socket):
    All_Sessions[key].add_player(players_name, socket)


def delete_player(key, players_name, socket):
    All_Sessions[key].delete_player(players_name, socket)


class Player():
    def __init__(self, name, socket):
        self.name = name
        self.socket = socket

    def get_name(self):
        return self.name

    def get_socket(self):
        return self.socket

    def send(self, data):
        try:
            self.socket.send(data)
            return True
        except:
            print "Impossible send to player ", self.name
            return False


class GameHandler(Thread):

    def __init__(self, game_session):
        Thread.__init__(self)
        self.session = game_session
        self.players = {}
        self.scores = {}
        self.condition_player = Condition()
        self.condition_turn = Condition()
        self.game = False # wtf ??
        self.m_game = Lock() # wtf ?
        self.m_update = Lock() # WTF ?????
