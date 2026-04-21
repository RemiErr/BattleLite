import socket
import struct
import random


def _probe_stun(sock: socket.socket, stun_host: str, stun_port: int, timeout: float):
    """在已綁定的 socket 上執行 STUN Binding Request，不關閉 socket。"""
    sock.settimeout(timeout)
    transaction_id = bytes(random.getrandbits(8) for _ in range(12))
    request_packet = struct.pack("!HHI12s", 0x0001, 0x0000, 0x2112A442, transaction_id)
    sock.sendto(request_packet, (stun_host, stun_port))
    data, _ = sock.recvfrom(1024)

    if data[8:20] != transaction_id:
        raise Exception("STUN Transaction ID mismatch")

    ptr = 20
    while ptr < len(data):
        attr_type, attr_len = struct.unpack("!HH", data[ptr:ptr + 4])
        if attr_type == 0x0020:  # XOR-MAPPED-ADDRESS
            _, _family, x_port = struct.unpack("!BBH", data[ptr + 4:ptr + 8])
            x_ip = struct.unpack("!I", data[ptr + 8:ptr + 12])[0]
            public_port = x_port ^ (0x2112A442 >> 16)
            public_ip = socket.inet_ntoa(struct.pack("!I", x_ip ^ 0x2112A442))
            return public_ip, public_port
        ptr += 4 + attr_len

    raise Exception("MAPPED-ADDRESS not found in STUN response")


def probe_stun_on_sock(sock: socket.socket,
                       stun_host: str = "stun.l.google.com",
                       stun_port: int = 19302,
                       timeout: float = 2.0) -> tuple[str, int]:
    """用外部已綁定的 socket 探測 STUN，不關閉 socket（方案二核心）。"""
    return _probe_stun(sock, stun_host, stun_port, timeout)


def get_public_endpoint(local_port: int,
                        stun_host: str = "stun.l.google.com",
                        stun_port: int = 19302,
                        timeout: float = 2.0) -> tuple[str, int]:
    """建立新 socket、探測後立即關閉（向下相容保留）。"""
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind(('0.0.0.0', local_port))
    try:
        return _probe_stun(sock, stun_host, stun_port, timeout)
    finally:
        sock.close()


def get_local_ip() -> str:
    """取得本機在 LAN 內的私有 IP（送出路由的來源 IP）。"""
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
        s.connect(("8.8.8.8", 80))
        return s.getsockname()[0]


if __name__ == "__main__":
    try:
        ip, port = get_public_endpoint(5000)
        print(f"Public Endpoint: {ip}:{port}")
    except Exception as e:
        print(f"Error: {e}")
