"""Client-side UDP relay proxy — 由 launcher 在 relay 模式下 spawn 為子程序。

啟動方式：
    python -m src.python.relay_proxy \\
        --relay-ip 192.168.1.50 --relay-port 9000 \\
        --match-id <uuid> --my-peer-id 2 \\
        --peer-ids 0,1,2,3 --proxy-base-port 30000

功能：在 GGRS (Rust) 與 relay server 之間轉封包，讓 GGRS 完全不需要修改：
    - GGRS 看到的「remote peer」是 127.0.0.1:30000+pid（fake loopback 端點）
    - GGRS 對某 fake peer 送封包 → proxy 包 header [dst_pid, my_pid, match_prefix16] → 送 relay
    - 從 relay 收到的封包拆 header → 從對應 loopback socket 送回 GGRS
      （讓 GGRS 看到 src addr = 127.0.0.1:30000+src_pid，得以區分 peer）
"""
from __future__ import annotations

import argparse
import hashlib
import selectors
import signal
import socket
import sys
import uuid

HEADER_LEN = 1 + 1 + 16  # dst_pid, src_pid, match_prefix


def _match_prefix(match_id: str) -> bytes:
    try:
        return uuid.UUID(match_id).bytes
    except ValueError:
        return hashlib.sha256(match_id.encode()).digest()[:16]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--relay-ip", required=True)
    ap.add_argument("--relay-port", type=int, required=True)
    ap.add_argument("--match-id", required=True)
    ap.add_argument("--my-peer-id", type=int, required=True)
    ap.add_argument("--peer-ids", required=True, help="comma-separated, e.g. 0,1,2,3")
    ap.add_argument("--proxy-base-port", type=int, default=30000)
    args = ap.parse_args()

    my_pid = args.my_peer_id
    peer_ids = [int(x) for x in args.peer_ids.split(",")]
    remote_pids = [p for p in peer_ids if p != my_pid]
    match_prefix = _match_prefix(args.match_id)

    # Relay-facing socket
    sock_relay = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock_relay.bind(("127.0.0.1", 0))
    sock_relay.setblocking(False)
    relay_addr = (args.relay_ip, args.relay_port)

    # GGRS-facing loopback sockets（一個 remote peer 一個 fake 端點）
    loop_socks: dict[int, socket.socket] = {}
    for pid in remote_pids:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.bind(("127.0.0.1", args.proxy_base_port + pid))
        s.setblocking(False)
        loop_socks[pid] = s

    # 發 REGISTER 給 relay 讓它學 endpoint。dst=my_pid 安全 noop（會 bounce 回自己，
    # 但 loop_socks 沒 my_pid 所以會被 ignore）。
    sock_relay.sendto(bytes([my_pid, my_pid]) + match_prefix, relay_addr)
    print(f"[PROXY] my={my_pid} peers={remote_pids} match={args.match_id} "
          f"→ relay={relay_addr}", flush=True)

    ggrs_addr: tuple[str, int] | None = None

    sel = selectors.DefaultSelector()
    sel.register(sock_relay, selectors.EVENT_READ, "relay")
    for pid, s in loop_socks.items():
        sel.register(s, selectors.EVENT_READ, pid)

    running = True

    def _stop(*_args) -> None:
        nonlocal running
        running = False

    signal.signal(signal.SIGTERM, _stop)
    signal.signal(signal.SIGINT, _stop)

    try:
        while running:
            for key, _mask in sel.select(timeout=0.5):
                if key.data == "relay":
                    while True:
                        try:
                            data, _src = sock_relay.recvfrom(2048)
                        except BlockingIOError:
                            break
                        if len(data) < HEADER_LEN or ggrs_addr is None:
                            continue
                        src_pid = data[1]
                        payload = data[HEADER_LEN:]
                        sock_b = loop_socks.get(src_pid)
                        if sock_b is None or not payload:
                            continue
                        try:
                            sock_b.sendto(payload, ggrs_addr)
                        except OSError:
                            pass
                else:
                    pid = key.data  # int: 對方 peer_id
                    sock_b = loop_socks[pid]
                    while True:
                        try:
                            data, src = sock_b.recvfrom(2048)
                        except BlockingIOError:
                            break
                        if ggrs_addr is None:
                            ggrs_addr = src
                            print(f"[PROXY] learned GGRS addr {src}", flush=True)
                        pkt = bytes([pid, my_pid]) + match_prefix + data
                        try:
                            sock_relay.sendto(pkt, relay_addr)
                        except OSError:
                            pass
    finally:
        sock_relay.close()
        for s in loop_socks.values():
            s.close()
        print("[PROXY] exit", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
