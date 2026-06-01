"""產生 Ed25519 keypair 供第三方主機架設 lobby server 使用。

用法：
    python scripts/gen_lobby_keypair.py

輸出兩段資訊，**請手動**貼到對應位置：
  1. 私鑰 (LOBBY_SIGNING_KEY) → 第三方主機的 .env
  2. 公鑰 → 覆寫所有 client 的 config/lobby_pubkey.txt

不會自動覆寫任何檔案，以免不慎讓既有 client 無法驗章。
"""
import hashlib

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import (
    Encoding, PrivateFormat, PublicFormat, NoEncryption,
)


def main() -> None:
    priv = Ed25519PrivateKey.generate()
    priv_bytes = priv.private_bytes(
        encoding=Encoding.Raw,
        format=PrivateFormat.Raw,
        encryption_algorithm=NoEncryption(),
    )
    pub_bytes = priv.public_key().public_bytes(
        encoding=Encoding.Raw, format=PublicFormat.Raw,
    )
    priv_hex = priv_bytes.hex()
    pub_hex = pub_bytes.hex()
    fingerprint = hashlib.sha256(pub_bytes).digest()[:8].hex()

    print("=" * 64)
    print(" Ed25519 keypair generated for BattleLite lobby")
    print(f" Pubkey fingerprint (SHA256[:8]): {fingerprint}")
    print("=" * 64)
    print()
    print("── (1) 私鑰：貼到第三方主機的 .env ──")
    print(f"LOBBY_SIGNING_KEY={priv_hex}")
    print()
    print("── (2) 公鑰：覆寫每台 client 的 config/lobby_pubkey.txt ──")
    print(pub_hex)
    print()
    print("提醒：")
    print("  * 先把 (2) 分發到所有 client 並覆寫好，才切換 LOBBY_SERVER_URL_LOCAL")
    print("  * 比對 client 與 server 的 fingerprint 一致，可避免設定錯誤")


if __name__ == "__main__":
    main()
