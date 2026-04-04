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
