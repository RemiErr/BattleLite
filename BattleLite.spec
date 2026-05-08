# -*- mode: python ; coding: utf-8 -*-

import os

PROJECT_ROOT = os.path.abspath(SPECPATH)
IMPORT_PATHS = [PROJECT_ROOT]

# main.py 的 import 全包在 try/except 內，PyInstaller 靜態分析不保證能追蹤，
# 因此將 session/ 與 game/ 套件明列於 hiddenimports。
_GAME_HIDDEN = [
    'battlelite_core',
    'src.python.session',
    'src.python.session.adapter',
    'src.python.session.char_config',
    'src.python.game',
    'src.python.game.loop',
    'src.python.game.input_manager',
    'src.python.game.match_manager',
    'src.python.replay',
    'src.python.replay.writer',
    'src.python.replay.reader',
]

launcher_analysis = Analysis(
    ['src/python/launcher.py'],
    pathex=IMPORT_PATHS,
    datas=[('src/assets', 'src/assets')],
    hiddenimports=[
        'battlelite_core',
        'src.python.replay', 'src.python.replay.writer', 'src.python.replay.reader',
        'PIL', 'PIL.Image', 'PIL.ImageTk', 'PIL.PngImagePlugin', 'PIL.JpegImagePlugin',
    ],
    excludes=['lobby_server', 'fastapi', 'uvicorn', 'starlette', 'pytest'],
)

game_analysis = Analysis(
    ['src/python/main.py'],
    pathex=IMPORT_PATHS,
    datas=[('src/assets', 'src/assets')],
    hiddenimports=_GAME_HIDDEN,
    excludes=['lobby_server', 'fastapi', 'uvicorn', 'starlette', 'pytest'],
)

launcher_pyz = PYZ(launcher_analysis.pure)
game_pyz     = PYZ(game_analysis.pure)

launcher_exe = EXE(
    launcher_pyz,
    launcher_analysis.scripts,
    [],
    exclude_binaries=True,
    name='BattleLite',
    console=False,
    icon='src/assets/img/launcher.ico',
)

game_exe = EXE(
    game_pyz,
    game_analysis.scripts,
    [],
    exclude_binaries=True,
    name='Game',
    console=False,
    icon='src/assets/img/game.ico',
)

coll = COLLECT(
    launcher_exe, launcher_analysis.binaries, launcher_analysis.datas,
    game_exe,     game_analysis.binaries,     game_analysis.datas,
    name='BattleLite',
)
