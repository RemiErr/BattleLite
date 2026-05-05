import sys
import os


def _resolve_project_root() -> str:
    if getattr(sys, 'frozen', False):
        return os.fspath(getattr(sys, '_MEIPASS'))
    return os.path.normpath(os.path.join(os.path.dirname(__file__), '..', '..'))


PROJECT_ROOT = _resolve_project_root()

if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

ROOT = PROJECT_ROOT
