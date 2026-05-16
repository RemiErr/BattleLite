import os
import sys
from src.python.app_root import PROJECT_ROOT

REPLAY_FORMAT_VERSION: int = 2
# v1 = 未壓縮 JSON list-of-lists（舊格式，向下相容）
# v2 = Columnar+bytes()+MessagePack+Zstd+base64


def get_replay_dir() -> str:
    if getattr(sys, 'frozen', False):
        return os.path.join(os.path.dirname(sys.executable), 'replay')
    return os.path.join(PROJECT_ROOT, 'replay')
