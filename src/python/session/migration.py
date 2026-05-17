"""Host 斷線後的 GGRS Session 重建邏輯。"""
import gc

from src.python.session.adapter import _SessionAdapterBase, GGRSAdapter, OfflineAdapter
from battlelite_core import GGRSSession, OfflineSession  # type: ignore[import]


def rebuild_after_host_death(
    config: dict,
    old_adapter: _SessionAdapterBase,
    new_host_id: int,
    num_players: int,
    char_assets: dict,
    apply_char_config_fn,
) -> _SessionAdapterBase:
    """
    重建 session 以完成 host 轉移。

    步驟：
    1. 快照現有玩家狀態
    2. 釋放舊 GGRS session（關閉 UDP socket）
    3. 判斷是否還有人類遠端：
       - 無 → 切換 OfflineSession（2P+2AI 場景：host 掛掉後只剩本地+AI）
       - 有 → 以新拓撲建立 GGRSSession
    4. 套用角色設定
    5. 還原玩家狀態
    """
    old_host_id    = config.get("host_id", 0)
    controlled_idx = config["local_id"]
    ai_player_ids  = [int(k) for k in config.get("ai_players", {}).keys()]
    i_am_new_host  = (controlled_idx == new_host_id)

    snapshots = [old_adapter.get_player(i) for i in range(num_players)]

    old_adapter._s = None
    gc.collect()

    def _apply_and_restore(adapter):
        for ct, asset in char_assets.items():
            apply_char_config_fn(adapter, ct, asset)
        for i, p in enumerate(snapshots):
            adapter.set_player(i, p)
        return adapter

    # 過濾出仍活躍的人類遠端（排除自己和已斷線的 old_host）
    human_remote_ids = [
        p["id"] for p in config.get("players", [])
        if p["id"] != controlled_idx
        and p["id"] != old_host_id
        and p["id"] not in ai_player_ids
    ]

    if not human_remote_ids:
        # 無其他人類遠端 → 改用 OfflineSession（不需要重新握手）
        print(f"[MIGRATION] 無人類遠端，切換至 OfflineSession")
        return _apply_and_restore(OfflineAdapter(OfflineSession(num_players)))

    # 有人類遠端 → 重建 GGRSSession
    # 排除自己與已斷線的 old_host，避免 GGRS 嘗試向無效端點握手
    remote_players_list = [
        (p["id"], p["ip"], p["port"])
        for p in config.get("players", [])
        if p["id"] != controlled_idx
        and p["id"] != old_host_id
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
    return _apply_and_restore(GGRSAdapter(new_ggrs, controlled_idx, bot_ids))
