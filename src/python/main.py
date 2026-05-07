import sys
import os
import json
import argparse

# 直接執行時，Python 只會先把 src/python 放進 sys.path
# 這裡先補上專案根目錄，讓後續 `src.python.*` 匯入可解析。
if not getattr(sys, 'frozen', False):
    _PROJECT_ROOT = os.path.abspath(
        os.path.join(os.path.dirname(__file__), '..', '..'))
    if _PROJECT_ROOT not in sys.path:
        sys.path.insert(0, _PROJECT_ROOT)

from src.python.app_root import PROJECT_ROOT

try:
    import battlelite_core
    from battlelite_core import OfflineSession, GGRSSession
    from src.python.assets_manager.characters.knight import Knight
    from src.python.assets_manager.characters.mage import Mage
    from src.python.assets_manager.characters.archer import Archer
    from src.python.assets_manager.characters.paladin import Paladin
    from src.python.assets_manager.characters.wizard import Wizard
    from src.python.crypto_utils import SHARED_SECRET
    from src.python.session.char_config import apply_char_config
    from src.python.session.adapter import OfflineAdapter, GGRSAdapter
    from src.python.game.loop import run_loop
except ImportError as e:
    print(f"[ERR] 匯入失敗: {e}")
    sys.exit(1)


def _parse_config(payload: str | None) -> dict:
    config = {
        "nickname": "DevPlayer",
        "is_offline": True,
        "local_id": 0,
        "num_players": 4,
        "local_port": 5000,
        "ai_players": {
            "1": {"char_type": 1, "level": 3},
            "2": {"char_type": 4, "level": 2},
            "3": {"char_type": 0, "level": 1},
        },
    }
    if payload:
        try:
            decrypted_str = battlelite_core.decrypt_payload(payload, SHARED_SECRET)
            config.update(json.loads(decrypted_str))
            print(f"[OK] Session Handoff Success: Hello {config['nickname']}")
        except Exception as e:
            print(f"[ERR] Handshake Decryption Failed: {e}")
            sys.exit(1)
    return config


def _build_char_assets() -> dict:
    return {0: Knight(), 1: Mage(), 2: Archer(), 3: Paladin(), 4: Wizard()}


def _build_session(config: dict, char_assets: dict):
    is_offline     = config["is_offline"]
    num_players    = config["num_players"]
    controlled_idx = config["local_id"]
    host_id        = config.get("host_id", 0)
    i_am_host      = is_offline or (controlled_idx == host_id)

    if is_offline:
        print("[Mode] Offline Sandbox (Pure Rust Simulation)")
        session = OfflineAdapter(OfflineSession(num_players))
    else:
        print("[Mode] Online P2P (GGRS Rollback)")
        print(f"  local_id={controlled_idx}  local_port={config['local_port']}")
        ai_player_ids = [int(k) for k in config.get("ai_players", {}).keys()]
        remote_players_list = []
        if "players" in config:
            for p in config["players"]:
                remote_players_list.append((p["id"], p["ip"], p["port"]))
                tag = "← me" if p["id"] == controlled_idx else "→ remote"
                print(f"  player id={p['id']}  {p['ip']}:{p['port']}  {tag}")
        if not i_am_host and ai_player_ids:
            host_player = next(
                (p for p in config.get("players", []) if p["id"] == host_id), None)
            if host_player:
                for pid in ai_player_ids:
                    remote_players_list.append(
                        (pid, host_player["ip"], host_player["port"]))
                    print(f"  player id={pid}  (AI @ host)"
                          f"  {host_player['ip']}:{host_player['port']}")
        bot_ids = ai_player_ids if i_am_host else []
        session = GGRSAdapter(
            GGRSSession(controlled_idx, num_players, config["local_port"],
                        remote_players_list, bot_ids),
            controlled_idx, bot_ids,
        )

    for char_type, asset in char_assets.items():
        apply_char_config(session, char_type, asset)
    return session


def run_game():
    parser = argparse.ArgumentParser()
    parser.add_argument("--payload", help="Encrypted session data from Launcher")
    args = parser.parse_args()

    config      = _parse_config(args.payload)
    char_assets = _build_char_assets()
    session     = _build_session(config, char_assets)
    run_loop(config, session, char_assets)


if __name__ == "__main__":
    run_game()
