# -*- coding: utf-8 -*-
"""Ed25519鍵をローカル生成し、did:key を導出する。
秘密鍵は identity.pem に保存。絶対に外部へ送信・共有しないこと。
既に identity.pem がある場合は上書きせず、既存鍵のDIDを表示する。
"""
import os
import sys
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives import serialization

HERE = os.path.dirname(os.path.abspath(__file__))
PEM_PATH = os.path.join(HERE, "identity.pem")

B58_ALPHABET = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"


def b58encode(data: bytes) -> str:
    n = int.from_bytes(data, "big")
    out = ""
    while n > 0:
        n, r = divmod(n, 58)
        out = B58_ALPHABET[r] + out
    # leading zero bytes -> '1'
    for b in data:
        if b == 0:
            out = "1" + out
        else:
            break
    return out


def did_from_public(pub_raw: bytes) -> str:
    # multicodec ed25519-pub (0xed 0x01) + raw 32 bytes, multibase base58btc ('z')
    return "did:key:z" + b58encode(b"\xed\x01" + pub_raw)


def main():
    if os.path.exists(PEM_PATH):
        with open(PEM_PATH, "rb") as f:
            key = serialization.load_pem_private_key(f.read(), password=None)
        print("既存の identity.pem を使用します（上書きしません）")
    else:
        key = Ed25519PrivateKey.generate()
        pem = key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        )
        # 先にファイルを作って権限を絞ってから書き込む
        fd = os.open(PEM_PATH, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "wb") as f:
            f.write(pem)
        print(f"新しい鍵を生成し {PEM_PATH} に保存しました")
        print("!!! このファイルは必ずバックアップし、誰にも渡さないこと !!!")

    pub_raw = key.public_key().public_bytes(
        serialization.Encoding.Raw, serialization.PublicFormat.Raw
    )
    did = did_from_public(pub_raw)
    print("DID:", did)
    with open(os.path.join(HERE, "did.txt"), "w", encoding="utf-8") as f:
        f.write(did + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
