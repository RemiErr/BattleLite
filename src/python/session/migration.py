"""Host 斷線後的 GGRS Session 重建邏輯。"""
import gc

from src.python.session.adapter import GGRSAdapter
from battlelite_core import GGRSSession  # type: ignore[import]


def rebuild_after_host_death(
    config: dict,
    old_adapter: GGRSAdapter,
    new_host_id: int,
    num_players: int,
    char_assets: dict,
    apply_char_config_fn,
) -> GGRSAdapter:
    """
    重建 GGRS session 以完成 host 轉移。

    步驟：
    1. 快照現有玩家狀態（all fields via get/set）
    2. 釋放舊 GGRS session（關閉 UDP socket）
    3. 以新拓撲建立 GGRSSession（新 host 承載 AI bot_ids）
    4. 套用角色設定
    5. 還原玩家狀態（entities 放棄，短暫中斷可接受）
    6. 回傳新 GGRSAdapter
    """
    controlled_idx = config["local_id"]
    ai_player_ids  = [int(k) for k in config.get("ai_players", {}).keys()]
    i_am_new_host  = (controlled_idx == new_host_id)

    snapshots = [old_adapter.get_player(i) for i in range(num_players)]

    old_adapter._s = None
    gc.collect()

    remote_players_list = [
        (p["id"], p["ip"], p["port"])
        for p in config.get("players", [])
    ]
    if not i_am_new_host and ai_player_ids:
        new_host_player = next(
            (p for p in config.get("players", []) if p["id"] == new_host_id), None)
        if new_host_player:
            for pid in ai_player_ids:
                remote_players_list.append(
                    (pid, new_host_player["ip"], new_host_player["port"]))
    bot_ids = ai_player_ids if i_am_new_host else []

    new_ggrs    = GGRSSession(
        controlled_idx, num_players, config["local_port"],
        remote_players_list, bot_ids,
    )
    new_adapter = GGRSAdapter(new_ggrs, controlled_idx, bot_ids)

    for ct, asset in char_assets.items():
        apply_char_config_fn(new_adapter, ct, asset)

    for i, p in enumerate(snapshots):
        new_adapter.set_player(i, p)

    return new_adapter
