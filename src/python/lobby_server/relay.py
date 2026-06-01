"""UDP relay server — 第三方主機備援的「mini TURN」。

封包格式（最小 header）:
    [1 byte: dst_peer_id][1 byte: src_peer_id][16 bytes: match_id_prefix][payload...]

行為:
    1. 收到 datagram → 從 source addr 學該 (match, src_peer_id) 的 endpoint
    2. 查 (match, dst_peer_id) 的已知 endpoint → 原 payload (含 header) 轉送
    3. 未知 match 或未知 dst → drop + 累計計數

由 lobby_server.main 在 FastAPI lifespan 啟動，與 lobby 同 process。
"""
from __future__ import annotations

import asyncio
import time
import uuid
from typing import Dict, Iterable, Tuple

HEADER_LEN = 1 + 1 + 16          # dst, src, match_prefix
MATCH_PREFIX_LEN = 16
MATCH_TTL_SECONDS = 60 * 10      # 10 分鐘沒活動的 match 清掉
GC_INTERVAL_SECONDS = 60
STATS_INTERVAL_SECONDS = 30


def _match_prefix(match_id: str) -> bytes:
    """把任意長度的 match_id 轉成 16 bytes 前綴（UUID hex 直接取 16 bytes，其餘 hash）。"""
    try:
        return uuid.UUID(match_id).bytes
    except (ValueError, AttributeError):
        import hashlib
        return hashlib.sha256(match_id.encode()).digest()[:MATCH_PREFIX_LEN]


class _MatchState:
    __slots__ = ("peer_ids", "endpoints", "last_activity")

    def __init__(self, peer_ids: Iterable[int]) -> None:
        self.peer_ids: set[int] = set(peer_ids)
        self.endpoints: Dict[int, Tuple[str, int]] = {}
        self.last_activity: float = time.monotonic()


class RelayProtocol(asyncio.DatagramProtocol):
    def __init__(self) -> None:
        self.transport: asyncio.DatagramTransport | None = None
        self._matches: Dict[bytes, _MatchState] = {}
        self._total_bytes: int = 0
        self._dropped: int = 0

    # ── lifecycle ─────────────────────────────────────────────────────────
    def connection_made(self, transport: asyncio.BaseTransport) -> None:  # type: ignore[override]
        self.transport = transport  # type: ignore[assignment]

    def datagram_received(self, data: bytes, addr: Tuple[str, int]) -> None:
        if len(data) < HEADER_LEN:
            self._dropped += 1
            return
        dst_pid = data[0]
        src_pid = data[1]
        prefix = bytes(data[2:2 + MATCH_PREFIX_LEN])

        match = self._matches.get(prefix)
        if match is None or src_pid not in match.peer_ids or dst_pid not in match.peer_ids:
            self._dropped += 1
            return

        match.endpoints[src_pid] = addr
        match.last_activity = time.monotonic()
        self._total_bytes += len(data)

        dst_addr = match.endpoints.get(dst_pid)
        if dst_addr is None:
            self._dropped += 1
            return
        assert self.transport is not None
        self.transport.sendto(data, dst_addr)

    # ── public API（給 lobby 同 process 呼叫） ─────────────────────────────
    def register_match(self, match_id: str, peer_ids: Iterable[int]) -> None:
        prefix = _match_prefix(match_id)
        self._matches[prefix] = _MatchState(peer_ids)
        print(f"[RELAY] match={match_id} registered peers={sorted(self._matches[prefix].peer_ids)}")

    def unregister_match(self, match_id: str) -> None:
        self._matches.pop(_match_prefix(match_id), None)

    def get_stats(self) -> dict:
        return {
            "matches": len(self._matches),
            "total_bytes": self._total_bytes,
            "dropped": self._dropped,
        }

    # ── background tasks ──────────────────────────────────────────────────
    async def gc_loop(self) -> None:
        while True:
            await asyncio.sleep(GC_INTERVAL_SECONDS)
            now = time.monotonic()
            stale = [k for k, m in self._matches.items()
                     if now - m.last_activity > MATCH_TTL_SECONDS]
            for k in stale:
                del self._matches[k]
            if stale:
                print(f"[RELAY] gc removed {len(stale)} stale matches")

    async def stats_loop(self) -> None:
        while True:
            await asyncio.sleep(STATS_INTERVAL_SECONDS)
            s = self.get_stats()
            print(f"[RELAY] matches={s['matches']} "
                  f"total_bytes={s['total_bytes']} dropped={s['dropped']}")


async def start_relay(host: str, port: int) -> tuple[RelayProtocol, list[asyncio.Task]]:
    """啟動 relay；回傳 protocol 與 background tasks（給呼叫端 cancel）。"""
    loop = asyncio.get_running_loop()
    proto = RelayProtocol()
    await loop.create_datagram_endpoint(lambda: proto, local_addr=(host, port))
    print(f"[RELAY] listening on {host}:{port}")
    tasks = [
        asyncio.create_task(proto.gc_loop(), name="relay-gc"),
        asyncio.create_task(proto.stats_loop(), name="relay-stats"),
    ]
    return proto, tasks
