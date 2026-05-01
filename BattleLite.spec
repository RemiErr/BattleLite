# -*- mode: python ; coding: utf-8 -*-

launcher_analysis = Analysis(
    ['src/python/launcher.py'],
    datas=[('src/assets', 'src/assets')],
    excludes=['lobby_server', 'fastapi', 'uvicorn', 'starlette', 'pytest'],
)

game_analysis = Analysis(
    ['src/python/main.py'],
    datas=[('src/assets', 'src/assets')],
    excludes=['lobby_server', 'fastapi', 'uvicorn', 'starlette', 'pytest'],
)

MERGE(
    (launcher_analysis, 'launcher', 'BattleLite'),
    (game_analysis,     'main',     'BattleLiteGame'),
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
)

game_exe = EXE(
    game_pyz,
    game_analysis.scripts,
    [],
    exclude_binaries=True,
    name='BattleLiteGame',
    console=False,
)

coll = COLLECT(
    launcher_exe, launcher_analysis.binaries, launcher_analysis.datas,
    game_exe,     game_analysis.binaries,     game_analysis.datas,
    name='BattleLite',
)
