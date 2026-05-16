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

def test_session_sig_verification():
    """
    驗證 Ed25519 session handoff 簽章流程。
    Lobby Server 用私鑰簽署，main.py 用 config/lobby_pubkey.txt 驗章。
    """
    import json
    import base64
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

    # 產生測試用金鑰對
    private_key = Ed25519PrivateKey.generate()
    public_key  = private_key.public_key()

    # 模擬 Lobby Server 簽署
    session = {"host_id": 0, "match_id": "test-match", "seed": 42}
    canonical = json.dumps(session, sort_keys=True, separators=(',', ':'))
    sig_bytes  = private_key.sign(canonical.encode())
    sig_b64    = base64.urlsafe_b64encode(sig_bytes).rstrip(b'=').decode()

    # 模擬 main.py 驗章（padding 補回）
    padded = sig_b64 + "=" * (-len(sig_b64) % 4)
    public_key.verify(base64.urlsafe_b64decode(padded), canonical.encode())

    # 確認竄改後驗章失敗
    tampered = json.dumps({"host_id": 1, "match_id": "test-match", "seed": 42},
                          sort_keys=True, separators=(',', ':'))
    with pytest.raises(Exception):
        public_key.verify(base64.urlsafe_b64decode(padded), tampered.encode())
