# -*- mode: python ; coding: utf-8 -*-

launcher_analysis = Analysis(
    ['src/python/launcher.py'],
    datas=[('src/assets', 'src/assets')],
    hiddenimports=['battlelite_core'],
    excludes=['lobby_server', 'fastapi', 'uvicorn', 'starlette', 'pytest'],
)

game_analysis = Analysis(
    ['src/python/main.py'],
    datas=[('src/assets', 'src/assets')],
    hiddenimports=['battlelite_core'],
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
    console=True,
)

game_exe = EXE(
    game_pyz,
    game_analysis.scripts,
    [],
    exclude_binaries=True,
    name='Game',
    console=True,
)

coll = COLLECT(
    launcher_exe, launcher_analysis.binaries, launcher_analysis.datas,
    game_exe,     game_analysis.binaries,     game_analysis.datas,
    name='BattleLite',
)
