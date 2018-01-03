import pickle
from base64 import decodestring, encodestring
# Requests --------------------------------------------------------------------
REQ_GM_GET_STATE = 'A'
REQ_GM_GUESS = 'B'
REQ_GM_SET_SUDOKU = 'C'
REQ_GM_SET_NAME = 'D'
CTR_MSGS = { REQ_GM_GET_STATE:'Get the current state of the guessed word',
             REQ_GM_GUESS:'Propose a letter to guess',
             REQ_GM_SET_SUDOKU:'Propose a new word to guess'
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
# Assuming message itself is base64 encoded
# Field separator for sending multiple values ---------------------------------
MSG_FIELD_SEP = ':'
# Message separator for sending multiple messages------------------------------
MSG_SEP = ';'

DEFAULT_RCV_BUFSIZE = 1

# Broadcast parameters
DEFAULT_SERVER_PORT = 5007
DEFAULT_SERVER_INET_ADDR = '224.0.0.2'
bind_addr = '0.0.0.0'
DEFAULT_RCV_BUFFSIZE = 1024
DEFAULT_BROADCAST_ADDR = "<broadcast>"


def serialize(msg):
    #return encodestring(msg)
    return pickle.dumps(msg)


def deserialize(msg):
    #return decodestring(msg)
    return pickle.loads(msg)


def enum(**vals):
    return type('Enum', (), vals)