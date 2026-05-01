import sys
import os

if getattr(sys, 'frozen', False):
    ROOT = sys._MEIPASS
else:
    ROOT = os.path.normpath(os.path.join(os.path.dirname(__file__), '..', '..'))
