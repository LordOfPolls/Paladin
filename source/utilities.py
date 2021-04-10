import logging
import pickle
from concurrent.futures.thread import ThreadPoolExecutor

import colorlog
from colorlog import ColoredFormatter

import source.pagination as pagination

paginator = pagination

thread_pool = ThreadPoolExecutor(max_workers=2)  # a thread pool

discordCharLimit = 2000

logging.SPAM = 9
logging.addLevelName(logging.SPAM, "SPAM")


def spam(self, message, *args, **kws):
    self._log(logging.SPAM, message, args, **kws)


logging.Logger.spam = spam


def getLog(filename, level=logging.DEBUG) -> logging:
    """ Sets up logging, to be imported by other files """
    streamHandler = colorlog.StreamHandler()
    streamFormatter = ColoredFormatter(
        "{asctime} {log_color}|| {levelname:^8} || {name:^15s} || {reset}{message}",
        datefmt="%H:%M:%S",
        reset=True,
        log_colors={
            "DEBUG": "cyan",
            "INFO": "green",
            "WARNING": "yellow",
            "ERROR": "red",
            "CRITICAL": "red,bg_yellow",
            "SPAM": "purple",
        },
        secondary_log_colors={},
        style="{",
    )

    streamHandler.setLevel(level)
    streamHandler.setFormatter(streamFormatter)

    _log = colorlog.getLogger(filename)

    _log.addHandler(streamHandler)
    _log.setLevel(logging.DEBUG)
    return _log


log = getLog("utils")


def getToken():
    try:
        file = open("data/token.pkl", "rb")
        token = pickle.load(file)
    except:  # if it cant load the token, ask for one, and then pickle it
        file = open("data/token.pkl", "wb")
        token = input("Input Discord Token: ").strip()
        pickle.dump(token, file)
    file.close()
    return token
