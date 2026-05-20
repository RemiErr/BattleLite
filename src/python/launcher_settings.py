import json
import os
import sys


def _default_settings_path() -> str:
    if getattr(sys, 'frozen', False):
        return os.path.join(os.path.dirname(sys.executable), 'settings.json')
    return os.path.abspath(
        os.path.join(os.path.dirname(__file__), '..', '..', 'settings.json'))


class SettingsManager:
    """
    管理 Launcher 與遊戲的設定存取與持久化。
    支援儲存視窗位置、大小、音量與玩家暱稱。
    """
    DEFAULT_SETTINGS = {
        "nickname":           "Player",
        "volume":             50,
        "sound_enabled":      True,
        "window_pos":         [100, 100],
        "fullscreen":         False,
        "last_room":          "",
        "key_preset":         0,
        "background_enabled": True,
        "background_id":      1,
    }

    def __init__(self, filepath: str | None = None):
        self.filepath = filepath or _default_settings_path()
        self.settings = self.DEFAULT_SETTINGS.copy()
        self.load()

    def load(self):
        """從檔案載入設定，如果失敗則維持預設值。"""
        if os.path.exists(self.filepath):
            try:
                with open(self.filepath, 'r', encoding='utf-8') as f:
                    loaded = json.load(f)
                    # 使用 update 確保新加入的設定項也能獲得預設值
                    self.settings.update(loaded)
            except Exception as e:
                print(f"[WARN] 無法載入設定檔: {e}，將使用預設值。")

    def save(self):
        """將目前設定寫入檔案。"""
        try:
            with open(self.filepath, 'w', encoding='utf-8') as f:
                json.dump(self.settings, f, indent=4, ensure_ascii=False)
        except Exception as e:
            print(f"[ERR] 儲存設定失敗: {e}")

    def get(self, key: str):
        """獲取特定設定項，保證有 DEFAULT_SETTINGS 中定義的 key 一定有值。"""
        value = self.settings.get(key, self.DEFAULT_SETTINGS.get(key))
        assert value is not None, f"Missing key in DEFAULT_SETTINGS: {key}"
        return value

    def set(self, key, value):
        """修改特定設定項。"""
        self.settings[key] = value

    def get_all(self):
        """獲取所有設定內容。"""
        return self.settings.copy()
