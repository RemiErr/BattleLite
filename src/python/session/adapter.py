"""
SessionAdapter — 統一 OfflineSession / GGRSSession 的 Python 接口。

兩種 session 的 advance() 簽名不同：
  OfflineSession.advance(inputs: list[int])
  GGRSSession.advance(local_input: int, bot_inputs=None)

Adapter 將兩者統一為 advance(inputs: list[int])，讓呼叫端不需要 if is_offline 分支。
"""


class _SessionAdapterBase:
    """兩個 Adapter 共用的直通 getter/setter，全部委派給底層 Rust session。"""

    def __init__(self, session):
        self._s = session

    def advance(self, inputs: list) -> None:
        raise NotImplementedError

    def get_last_inputs(self) -> list:
        raise NotImplementedError

    def clear_entities(self) -> None:
        raise NotImplementedError

    def get_player(self, pid: int):
        return self._s.get_player(pid)

    def set_player(self, pid: int, player) -> None:
        self._s.set_player(pid, player)

    def get_entity_count(self) -> int:
        return self._s.get_entity_count()

    def get_entity(self, eid: int):
        return self._s.get_entity(eid)

    def current_frame(self) -> int:
        return self._s.current_frame()

    def is_synchronized(self) -> bool:
        return self._s.is_synchronized()

    def set_physics_config(self, *args, **kwargs) -> None:
        self._s.set_physics_config(*args, **kwargs)

    def set_ability(self, *args, **kwargs) -> None:
        self._s.set_ability(*args, **kwargs)

    def get_disconnected_mask(self) -> int:
        return self._s.get_disconnected_mask()


class OfflineAdapter(_SessionAdapterBase):
    def __init__(self, session):
        super().__init__(session)
        self._last_inputs: list = []

    def advance(self, inputs: list) -> None:
        self._last_inputs = list(inputs)
        self._s.advance(inputs)

    def get_last_inputs(self) -> list:
        return list(self._last_inputs)

    def clear_entities(self) -> None:
        self._s.clear_entities()

    def is_synchronized(self) -> bool:
        return True

    def get_disconnected_mask(self) -> int:
        return 0


class GGRSAdapter(_SessionAdapterBase):
    def __init__(self, session, local_player_id: int, bot_ids: list):
        super().__init__(session)
        self._local_id = local_player_id
        self._bot_ids = bot_ids

    def advance(self, inputs: list) -> None:
        local_input = inputs[self._local_id] if self._local_id < len(inputs) else 0
        bot_inputs = [(pid, inputs[pid]) for pid in self._bot_ids if pid < len(inputs)]
        self._s.advance(local_input, bot_inputs if bot_inputs else None)

    def get_last_inputs(self) -> list:
        return list(self._s.get_last_inputs())

    def clear_entities(self) -> None:
        pass  # GGRSSession 透過 rollback 管理狀態，無需手動清除
