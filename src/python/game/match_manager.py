try:
    from src.python.game_constants import STATE_IDLE, STATE_DEAD
except ImportError:
    STATE_IDLE = 0
    STATE_DEAD = 5


class MatchManager:
    """擁有對戰進行中的可變狀態，封裝勝負判定與重開邏輯。"""

    def __init__(self, session, num_players: int, char_assets: dict,
                 fx_manager, hud):
        self._session = session
        self._num_players = num_players
        self._char_assets = char_assets
        self._fx_manager = fx_manager
        self._hud = hud

        self.match_result: int | None = None
        self.player_elapsed_frames: list[int] = [0] * num_players
        self.last_states: list[int] = [STATE_IDLE] * num_players
        self.paused: bool = False
        self.countdown_frames: int = 3 * 60
        self._result_submitted: bool = False

    def check_match(self) -> int | None:
        """回傳勝者 idx、-2（平手），或 None（仍在進行）。不修改內部狀態。"""
        alive = [i for i in range(self._num_players)
                 if self._session.get_player(i).state != STATE_DEAD]
        if len(alive) == 1:
            return alive[0]
        if len(alive) == 0:
            return -2
        return None

    def restart(self, spawn_fn):
        """重置所有對戰狀態並重新生成玩家。spawn_fn(session, num_players) 負責設定初始位置。"""
        self.paused = False
        self.countdown_frames = 3 * 60
        self._session.clear_entities()
        for i in range(self._num_players):
            p = self._session.get_player(i)
            asset = self._char_assets.get(p.character_type, self._char_assets[0])
            p.hp = asset.physics.max_hp
            p.mp = asset.physics.max_mp
            p.state = STATE_IDLE
            p.timer = 0
            p.vx = p.vy = p.vz = 0
            p.z = 0
            p.hitstop = 0
            p.shield_hp = 0
            self._session.set_player(i, p)
        spawn_fn(self._session, self._num_players)
        self.match_result = None
        self.player_elapsed_frames = [0] * self._num_players
        self.last_states = [STATE_IDLE] * self._num_players
        self._result_submitted = False
        self._fx_manager.effects_front.clear()
        self._fx_manager.effects_behind.clear()
        self._fx_manager._player_fx.clear()
        self._hud._hp_drain.clear()
        self._hud._mp_drain.clear()
