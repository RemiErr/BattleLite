# -*- mode: python ; coding: utf-8 -*-

import os

PROJECT_ROOT = os.path.abspath(SPECPATH)
IMPORT_PATHS = [PROJECT_ROOT]

# main.py / loop.py 的 inline import 靜態分析不保證能追蹤，明列 hiddenimports。
_GAME_HIDDEN = [
    'battlelite_core',
    # session
    'src.python.session',
    'src.python.session.adapter',
    'src.python.session.char_config',
    'src.python.session.migration',           # loop.py inline import（host 轉移）
    # game
    'src.python.game',
    'src.python.game.loop',
    'src.python.game.input_manager',
    'src.python.game.match_manager',
    # replay
    'src.python.replay',
    'src.python.replay.codec',
    'src.python.replay.writer',
    'src.python.replay.reader',
    # AI
    'src.python.ai',
    'src.python.ai.factory',
    'src.python.ai.controllers.base',
    'src.python.ai.controllers.fsm_ai',
    'src.python.ai.controllers.pattern_ai',
    'src.python.ai.controllers.goap_ai',
    'src.python.ai.characters.knight_ai',
    'src.python.ai.characters.mage_ai',
    'src.python.ai.characters.archer_ai',
    'src.python.ai.characters.paladin_ai',
    'src.python.ai.characters.wizard_ai',
    # third-party（replay 壓縮）
    'msgpack',
    'zstandard',
    # crypto（Ed25519 驗簽，函式內 import）
    'cryptography',
    'cryptography.hazmat.primitives.asymmetric.ed25519',
]

launcher_analysis = Analysis(
    ['src/python/launcher.py'],
    pathex=IMPORT_PATHS,
    datas=[('src/assets', 'src/assets')],
    hiddenimports=[
        'battlelite_core',
        'src.python.replay',
        'src.python.replay.codec',
        'src.python.replay.writer',
        'src.python.replay.reader',
        'msgpack',
        'zstandard',
        'PIL', 'PIL.Image', 'PIL.ImageTk', 'PIL.PngImagePlugin', 'PIL.JpegImagePlugin',
    ],
    excludes=['lobby_server', 'fastapi', 'uvicorn', 'starlette', 'pytest'],
)

game_analysis = Analysis(
    ['src/python/main.py'],
    pathex=IMPORT_PATHS,
    datas=[
        ('src/assets', 'src/assets'),
        ('config/lobby_pubkey.txt', 'config'),  # Ed25519 公鑰，隨 exe 發布
    ],
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
