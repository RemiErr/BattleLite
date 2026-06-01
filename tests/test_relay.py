"""UDP relay server 單元測試 — 純 asyncio，不依賴 lobby 或 GGRS。"""
import asyncio
import os
import socket
import sys
import uuid

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from src.python.lobby_server.relay import (  # noqa: E402
    HEADER_LEN, MATCH_PREFIX_LEN, RelayProtocol, _match_prefix, start_relay,
)


def _pkt(dst_pid: int, src_pid: int, match_id: str, payload: bytes) -> bytes:
    return bytes([dst_pid, src_pid]) + _match_prefix(match_id) + payload


def _free_port() -> int:
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.bind(("127.0.0.1", 0))
    p = s.getsockname()[1]
    s.close()
    return p


async def _send_from_recv_on(src_sock: socket.socket, dst_sock: socket.socket,
                              data: bytes, relay_addr,
                              timeout: float = 0.5) -> bytes | None:
    """從 src_sock 送出封包，在 dst_sock 等收 — 避免單一 socket 既送又收
    讓 relay 把它的 endpoint 同時學成 src 與 dst 而互相覆蓋。"""
    src_sock.sendto(data, relay_addr)
    loop = asyncio.get_running_loop()
    try:
        data2, _ = await asyncio.wait_for(
            loop.sock_recvfrom(dst_sock, 2048), timeout=timeout)
        return data2
    except asyncio.TimeoutError:
        return None


async def _drain(sock: socket.socket) -> None:
    await asyncio.sleep(0.05)
    try:
        sock.recvfrom(2048)
    except BlockingIOError:
        pass


async def _routes_packet_impl():
    port = _free_port()
    proto, tasks = await start_relay("127.0.0.1", port)
    match_id = str(uuid.uuid4())
    proto.register_match(match_id, [0, 1])

    s0 = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s0.bind(("127.0.0.1", 0)); s0.setblocking(False)
    s1 = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s1.bind(("127.0.0.1", 0)); s1.setblocking(False)
    relay_addr = ("127.0.0.1", port)

    # 兩端各送 REGISTER (dst=self) 讓 relay 學 endpoint；bounce 回來直接 drain
    s1.sendto(_pkt(1, 1, match_id, b""), relay_addr)
    s0.sendto(_pkt(0, 0, match_id, b""), relay_addr)
    await _drain(s0); await _drain(s1)

    # peer0 → peer1：從 s0 送、在 s1 收
    out = await _send_from_recv_on(
        s0, s1, _pkt(1, 0, match_id, b"hello"), relay_addr)
    assert out is not None, "peer1 應收到 peer0 轉送的封包"
    assert out[HEADER_LEN:] == b"hello"
    assert out[1] == 0  # src_pid 保留

    # peer1 → peer0
    out2 = await _send_from_recv_on(
        s1, s0, _pkt(0, 1, match_id, b"world"), relay_addr)
    assert out2 is not None and out2[HEADER_LEN:] == b"world"

    s0.close(); s1.close()
    for t in tasks:
        t.cancel()


def test_relay_routes_packet():
    asyncio.run(_routes_packet_impl())


async def _drops_unknown_peer_impl():
    port = _free_port()
    proto, tasks = await start_relay("127.0.0.1", port)
    match_id = str(uuid.uuid4())
    proto.register_match(match_id, [0, 1])  # peer 7 故意不註冊

    s7 = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s7.bind(("127.0.0.1", 0)); s7.setblocking(False)
    s_other = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s_other.bind(("127.0.0.1", 0)); s_other.setblocking(False)
    out = await _send_from_recv_on(
        s7, s_other, _pkt(0, 7, match_id, b"x"), ("127.0.0.1", port),
        timeout=0.2)
    assert out is None, "未註冊 peer_id 應被 drop"
    assert proto.get_stats()["dropped"] >= 1
    s7.close(); s_other.close()
    for t in tasks:
        t.cancel()


def test_relay_drops_unknown_peer():
    asyncio.run(_drops_unknown_peer_impl())


def test_relay_drops_short_packet():
    proto = RelayProtocol()
    proto.register_match("00000000-0000-0000-0000-000000000000", [0, 1])
    proto.datagram_received(b"\x00", ("127.0.0.1", 1234))  # 短於 HEADER_LEN
    assert proto.get_stats()["dropped"] == 1


def test_unregister_match():
    proto = RelayProtocol()
    proto.register_match("aa", [0, 1])
    assert proto.get_stats()["matches"] == 1
    proto.unregister_match("aa")
    assert proto.get_stats()["matches"] == 0


def test_match_prefix_length():
    assert len(_match_prefix(str(uuid.uuid4()))) == MATCH_PREFIX_LEN
    assert len(_match_prefix("not-a-uuid")) == MATCH_PREFIX_LEN
