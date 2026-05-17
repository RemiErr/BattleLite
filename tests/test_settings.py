import pytest
import os
import json
import sys

# 確保路徑正確
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

def test_settings_manager_defaults():
    """
    驗證當設定檔不存在時，是否能回傳正確的預設值。
    """
    try:
        from src.python.launcher_settings import SettingsManager
    except ImportError:
        pytest.fail("找不到 'src.python.launcher_settings' 模組。")

    test_file = "test_settings.json"
    if os.path.exists(test_file):
        os.remove(test_file)

    mgr = SettingsManager(test_file)
    settings = mgr.get_all()
    
    assert settings["nickname"] == "Player"
    assert settings["volume"] == 50
    assert "window_pos" in settings
    assert settings["fullscreen"] is False
    
    if os.path.exists(test_file):
        os.remove(test_file)

def test_settings_save_and_load():
    """
    驗證儲存設定後，再次讀取是否內容一致。
    """
    from src.python.launcher_settings import SettingsManager
    test_file = "test_save_load.json"
    
    mgr = SettingsManager(test_file)
    mgr.set("nickname", "BattleMaster")
    mgr.set("volume", 85)
    mgr.save()
    
    # 建立一個新的實例來讀取剛存好的檔案
    new_mgr = SettingsManager(test_file)
    assert new_mgr.get("nickname") == "BattleMaster"
    assert new_mgr.get("volume") == 85
    
    if os.path.exists(test_file):
        os.remove(test_file)
