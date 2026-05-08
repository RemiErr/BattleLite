import os
import sys
from src.python.app_root import PROJECT_ROOT


def get_replay_dir() -> str:
    if getattr(sys, 'frozen', False):
        return os.path.join(os.path.dirname(sys.executable), 'replay')
    return os.path.join(PROJECT_ROOT, 'replay')
