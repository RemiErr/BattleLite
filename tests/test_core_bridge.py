import pytest

def test_rust_bridge_connection():
    """
    驗證 Python 是否能成功匯入 Rust 編譯的核心模組，並呼叫基礎函式。
    """
    try:
        import battlelite_core
    except ImportError:
        pytest.fail("無法匯入 battlelite_core 模組。請確保已執行 'maturin develop'。")

    # 呼叫 Rust 函式
    result = battlelite_core.hello_from_rust()
    
    # 驗證回傳值是否符合預期
    expected_msg = "Hello from BattleLite Rust Core!"
    assert result == expected_msg, f"預期回傳 '{expected_msg}'，但得到 '{result}'"

def test_rust_module_attributes():
    """
    確保模組包含我們預期定義的函式。
    """
    import battlelite_core
    assert hasattr(battlelite_core, 'hello_from_rust'), "模組中找不到 'hello_from_rust' 函式"

def test_crypto_handoff_contract():
    """
    驗證跨語言加解密合約。
    Python 使用 cryptography 加密，傳給 Rust 進行解密。
    """
    import json
    import base64
    from cryptography.hazmat.primitives.ciphers.aead import ChaCha20Poly1305
    import battlelite_core

    # 1. 準備資料與金鑰 (32 bytes 固定金鑰用於測試)
    key = b"very_secret_32_byte_key_for_test"
    nonce = b"unique_nonce" # 12 bytes
    data = {"p1": "1.2.3.4:5000", "seed": 999}
    data_str = json.dumps(data)

    # 2. Python 端加密
    cipher = ChaCha20Poly1305(key)
    ciphertext = cipher.encrypt(nonce, data_str.encode(), None)
    
    # 將 Nonce 與密文打包成 Base64 字串 (Launcher 傳給 Client 的格式)
    payload = base64.b64encode(nonce + ciphertext).decode('utf-8')

    # 3. 呼叫 Rust 端進行解密 (預期會失敗，因為 Rust 還沒實作 decrypt_payload)
    if hasattr(battlelite_core, 'decrypt_payload'):
        # 我們預期 Rust 函式簽名為: decrypt_payload(payload_str, key_bytes)
        decrypted_json = battlelite_core.decrypt_payload(payload, key)
        result = json.loads(decrypted_json)
        
        assert result["p1"] == "1.2.3.4:5000"
        assert result["seed"] == 999
    else:
        pytest.fail("battlelite_core 模組中找不到 'decrypt_payload' 函式。")
