import sys
import os
import logging
from datetime import datetime

_LOG_DIR = None
_LOG_FILE = None

class ColoredFormatter(logging.Formatter):
    COLORS = {
        'DEBUG': '\033[36m',
        'INFO': '\033[32m',
        'WARNING': '\033[33m',
        'ERROR': '\033[31m',
        'CRITICAL': '\033[35m',
    }
    RESET = '\033[0m'

    def format(self, record):
        levelname = record.levelname
        color = self.COLORS.get(levelname, self.RESET)
        record.levelname = f"{color}{levelname}{self.RESET}"
        return super().format(record)

def init_logger():
    global _LOG_DIR, _LOG_FILE
    base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    _LOG_DIR = os.path.join(base, "logs")
    os.makedirs(_LOG_DIR, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    _LOG_FILE = os.path.join(_LOG_DIR, f"neroschool_{ts}.log")

    logger = logging.getLogger("neroschool")
    logger.setLevel(logging.DEBUG)

    fh = logging.FileHandler(_LOG_FILE, encoding="utf-8")
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
    logger.addHandler(fh)

    ch = logging.StreamHandler(sys.stdout)
    ch.setLevel(logging.INFO)
    ch.setFormatter(ColoredFormatter("%(asctime)s [%(levelname)s] %(message)s", datefmt="%H:%M:%S"))
    logger.addHandler(ch)

    return logger

logger = init_logger()

def info(msg, *args):
    logger.info(msg, *args)

def warn(msg, *args):
    logger.warning(msg, *args)

def error(msg, *args):
    logger.error(msg, *args)

def debug(msg, *args):
    logger.debug(msg, *args)

def ok(msg, *args):
    logger.info("✓ " + msg, *args)
