import json
import base64
import os
from cryptography.hazmat.primitives.ciphers.aead import ChaCha20Poly1305

# 預共享金鑰 (必須與 Rust 端測試時使用的 Key 對齊)
# 32 Bytes 固定 Key (開發測試用)
SHARED_SECRET = b"very_secret_32_byte_key_for_test"

def encrypt_payload(data_dict: dict) -> str:
    """
    將資料字典加密為 Base64 字串。
    格式: Base64(Nonce[12 bytes] + Ciphertext)
    """
    data_str = json.dumps(data_dict)
    
    # 1. 產生 12 bytes 的隨機 Nonce
    nonce = os.urandom(12)
    
    # 2. ChaCha20-Poly1305 加密
    cipher = ChaCha20Poly1305(SHARED_SECRET)
    ciphertext = cipher.encrypt(nonce, data_str.encode('utf-8'), None)
    
    # 3. 組合並編碼
    return base64.b64encode(nonce + ciphertext).decode('utf-8')

def decrypt_payload_py(payload_str: str) -> dict:
    """
    (備用) Python 版的解密邏輯，用於本地測試。
    """
    try:
        raw_data = base64.b64decode(payload_str)
        nonce = raw_data[:12]
        ciphertext = raw_data[12:]
        
        cipher = ChaCha20Poly1305(SHARED_SECRET)
        plaintext = cipher.decrypt(nonce, ciphertext, None)
        return json.loads(plaintext.decode('utf-8'))
    except Exception as e:
        print(f"❌ Python 解密失敗: {e}")
        return {}
