import socket
import struct
import random

def get_public_endpoint(local_port: int, stun_host: str = "stun.l.google.com", stun_port: int = 19302, timeout: float = 2.0):
    """
    透過 STUN 伺服器探測本機的公網 IP 與 埠號。
    實作 RFC 5389 的極簡 Binding Request。
    """
    # 1. 建立並綁定 UDP Socket
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.settimeout(timeout)
    
    try:
        # 綁定到本地埠號，以便打洞
        sock.bind(('0.0.0.0', local_port))
        
        # 2. 建構 STUN Binding Request 封包
        # STUN Message Type: 0x0001 (Binding Request)
        # Message Length: 0x0000
        # Magic Cookie: 0x2112A442
        # Transaction ID: 12 bytes 隨機數
        transaction_id = bytes(random.getrandbits(8) for _ in range(12))
        request_packet = struct.pack("!HHI12s", 0x0001, 0x0000, 0x2112A442, transaction_id)
        
        # 3. 發送請求
        sock.sendto(request_packet, (stun_host, stun_port))
        
        # 4. 接收與解析響應
        data, addr = sock.recvfrom(1024)
        
        # 檢查 Transaction ID 是否對應
        if data[8:20] != transaction_id:
            raise Exception("STUN Transaction ID mismatch")
            
        # 遍歷 STUN Attributes 尋找 MAPPED-ADDRESS (0x0001) 或 XOR-MAPPED-ADDRESS (0x0020)
        # 這裡為了簡化，實作常見的 XOR-MAPPED-ADDRESS 解析
        ptr = 20 # 跳過 Header
        while ptr < len(data):
            attr_type, attr_len = struct.unpack("!HH", data[ptr:ptr+4])
            if attr_type == 0x0020: # XOR-MAPPED-ADDRESS
                # 解析 XOR 位址 (RFC 5389)
                _, family, x_port = struct.unpack("!BBH", data[ptr+4:ptr+8])
                x_ip = struct.unpack("!I", data[ptr+8:ptr+12])[0]
                
                # XOR 運算還原真實數據
                public_port = x_port ^ (0x2112A442 >> 16)
                public_ip_int = x_ip ^ 0x2112A442
                public_ip = socket.inet_ntoa(struct.pack("!I", public_ip_int))
                
                return public_ip, public_port
            
            ptr += 4 + attr_len
            
        raise Exception("MAPPED-ADDRESS not found in STUN response")
        
    finally:
        # 5. 方法 A：立刻釋放埠號
        sock.close()

if __name__ == "__main__":
    # 本地快速測試
    try:
        ip, port = get_public_endpoint(5000)
        print(f"Public Endpoint: {ip}:{port}")
    except Exception as e:
        print(f"Error: {e}")
