import pytest
import sys
import os

# 確保路徑正確
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

def test_stun_endpoint_retrieval():
    """
    驗證是否能成功透過 STUN 伺服器獲取公網 IP 與 埠號。
    """
    try:
        from src.python.stun_utils import get_public_endpoint
    except ImportError:
        pytest.fail("找不到 'src.python.stun_utils' 模組。")

    # 使用埠號 5000 進行測試
    # 注意：如果你的網路環境完全禁止 UDP 或無法聯網，此測試會失敗
    try:
        public_ip, public_port = get_public_endpoint(5000)
        
        print(f"\n🌍 Detected Public Endpoint: {public_ip}:{public_port}")
        
        assert public_ip is not None
        assert isinstance(public_port, int)
        assert public_port > 0
    except Exception as e:
        pytest.fail(f"STUN 探測失敗: {e}")
