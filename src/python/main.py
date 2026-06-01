import sys
import os
import json
import base64
import argparse
import logging

# 直接執行時，Python 只會先把 src/python 放進 sys.path
# 這裡先補上專案根目錄，讓後續 `src.python.*` 匯入可解析。
if not getattr(sys, 'frozen', False):
    _PROJECT_ROOT = os.path.abspath(
        os.path.join(os.path.dirname(__file__), '..', '..'))
    if _PROJECT_ROOT not in sys.path:
        sys.path.insert(0, _PROJECT_ROOT)

from src.python.app_root import PROJECT_ROOT

try:
    from battlelite_core import OfflineSession, GGRSSession
    from src.python.assets_manager.characters.knight import Knight
    from src.python.assets_manager.characters.mage import Mage
    from src.python.assets_manager.characters.archer import Archer
    from src.python.assets_manager.characters.paladin import Paladin
    from src.python.assets_manager.characters.wizard import Wizard
    from src.python.session.char_config import apply_char_config
    from src.python.session.adapter import OfflineAdapter, GGRSAdapter
    from src.python.game.loop import run_loop
except ImportError as e:
    print(f"[ERR] 匯入失敗: {e}")
    sys.exit(1)


def _load_pubkey():
    """從 config/lobby_pubkey.txt 讀取 Ed25519 公鑰（hex 格式）。"""
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
    if getattr(sys, 'frozen', False):
        base = os.path.dirname(sys.executable)   # 打包後：exe 所在目錄
    else:
        base = os.path.normpath(os.path.join(os.path.dirname(__file__), '..', '..'))
    pubkey_path = os.path.join(base, 'config', 'lobby_pubkey.txt')
    with open(pubkey_path, encoding="utf-8") as f:
        hex_key = f.read().strip()
    return Ed25519PublicKey.from_public_bytes(bytes.fromhex(hex_key))


def _verify_session_sig(config_data: dict, sig_b64: str) -> None:
    """驗證 lobby server 的 Ed25519 簽章；失敗時 raise ValueError。

    若 payload 含 `relay` 欄位，會一併納入簽章驗證（與 lobby `_sign_session` 對應）。
    """
    canonical_dict = {
        "host_id":  config_data["host_id"],
        "match_id": config_data["match_id"],
        "seed":     config_data["seed"],
    }
    if config_data.get("relay"):
        canonical_dict["relay"] = config_data["relay"]
    canonical = json.dumps(canonical_dict, sort_keys=True, separators=(',', ':'))
    # base64url without padding → add padding back
    padded = sig_b64 + "=" * (-len(sig_b64) % 4)
    sig_bytes = base64.urlsafe_b64decode(padded)
    _load_pubkey().verify(sig_bytes, canonical.encode())


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
            config_data = json.loads(payload)
            sig = config_data.pop("sig", "")
            if sig:
                _verify_session_sig(config_data, sig)
            config.update(config_data)
            print(f"[OK] Session Handoff Success: Hello {config['nickname']}")
        except Exception as e:
            print(f"[ERR] Session Validation Failed: {e}")
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
            if host_player is None:
                logging.warning(
                    "[WARN] host_player (id=%s) 不在 players 列表中；AI 遠端端點略過，AI 可能凍結。",
                    host_id,
                )
            else:
                for pid in ai_player_ids:
                    remote_players_list.append(
                        (pid, host_player["ip"], host_player["port"]))
                    print(f"  player id={pid}  (AI @ host)"
                          f"  {host_player['ip']}:{host_player['port']}")
        bot_ids = ai_player_ids if i_am_host else []
        sock_fd = int(os.environ.get("BATTLELITE_SOCK_FD", "0")) or None
        print(f"[GGRS] sock_fd={sock_fd}  local_port={config['local_port']}")
        session = GGRSAdapter(
            GGRSSession(controlled_idx, num_players, config["local_port"],
                        remote_players_list, bot_ids, sock_fd),
            controlled_idx, bot_ids,
        )

    for char_type, asset in char_assets.items():
        apply_char_config(session, char_type, asset)
    return session


def _build_replay_config(replay_path: str) -> dict:
    import json as _json
    with open(replay_path, encoding="utf-8") as f:
        header = _json.load(f)
    num_players = header.get("num_players", 2)
    players     = header.get("players", [])
    config = {
        "nickname":    "REPLAY",
        "is_offline":  True,
        "local_id":    0,
        "num_players": num_players,
        "local_port":  5000,
        "seed":        header.get("seed", 0),
        "replay_path": replay_path,
        "ai_players":  {},
        "players":     players,
    }
    return config


def run_game():
    parser = argparse.ArgumentParser()
    parser.add_argument("--payload", help="Encrypted session data from Launcher")
    parser.add_argument("--replay",  help="Path to replay file", default=None)
    args = parser.parse_args()

    if args.replay:
        config = _build_replay_config(args.replay)
    else:
        config = _parse_config(args.payload)
    run_loop(config, _build_char_assets, lambda ca: _build_session(config, ca))


if __name__ == "__main__":
    run_game()
