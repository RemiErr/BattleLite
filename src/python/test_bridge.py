import sys
import os

# 確保我們在虛擬環境中，或者手動加入編譯產物的路徑
# 通常 maturin develop 已經幫我們安裝進 venv 了
try:
    import battlelite_core
    print("✅ 成功匯入 battlelite_core 模組！")
    
    # 呼叫 Rust 函式
    result = battlelite_core.hello_from_rust()
    print(f"🦀 Rust 核心的回傳值: {result}")
    
    if result == "Hello from BattleLite Rust Core!":
        print("✨ 橋接測試成功！Rust 與 Python 通訊正常。")
    else:
        print("⚠️ 雖然有回傳值，但內容不符。")

except ImportError as e:
    print(f"❌ 匯入失敗: {e}")
    print("提示: 確保你已經執行過 'source venv/bin/activate' 並且在 'src/rust_core' 執行過 'maturin develop'。")
except Exception as e:
    print(f"❌ 發生意外錯誤: {e}")
