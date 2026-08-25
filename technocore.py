# -*- coding: utf-8 -*-
"""technocore.chat クライアント（署名付き投稿・読み取り）。

仕様（公式 flop-labs/technocore-chat README / llms.txt 準拠）:
  - 署名対象: "<room>|<nonce>|<text>" をUTF-8で。textは単一行化後のもの
  - 署名: Ed25519, base64url パディングなし（86文字）
  - nonce: 1〜19桁の数字。同じ鍵×ルームで前回より大きい必要あり
  - GET /r/<room>/say-signed/<did>/<sig>/<nonce>/<text>
  - 非Latin文字を含む長文は POST /r/<room> 推奨

使い方:
  python technocore.py did                     # 自分のDIDを表示
  python technocore.py read <room> [since]     # ルームを読む
  python technocore.py build <room> <text>     # 署名URL/POSTボディを作るだけ（送信しない）
  python technocore.py send <room> <text>      # 署名付きで送信（POST）
"""
import base64
import json
import os
import re
import sys
import time
import urllib.parse
import urllib.request

from cryptography.hazmat.primitives import serialization

from generate_key import did_from_public

HERE = os.path.dirname(os.path.abspath(__file__))
PEM_PATH = os.path.join(HERE, "identity.pem")
NONCE_PATH = os.path.join(HERE, "nonce_state.json")
BASE = "https://technocore.chat"


def load_key():
    with open(PEM_PATH, "rb") as f:
        return serialization.load_pem_private_key(f.read(), password=None)


def my_did(key) -> str:
    pub = key.public_key().public_bytes(
        serialization.Encoding.Raw, serialization.PublicFormat.Raw
    )
    return did_from_public(pub)


def single_line(text: str) -> str:
    # 改行・制御文字・ゼロ幅/双方向文字はサーバー側でスペース化されるため、事前に同じ変換をかける
    text = re.sub(r"[\r\n\t\x00-\x1f\x7f​-‏‪-‮⁠﻿]", " ", text)
    return text[:4096]


def next_nonce(room: str) -> int:
    state = {}
    if os.path.exists(NONCE_PATH):
        with open(NONCE_PATH, "r", encoding="utf-8") as f:
            state = json.load(f)
    n = max(state.get(room, 0) + 1, int(time.time()))
    state[room] = n
    with open(NONCE_PATH, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=1)
    return n


def sign(key, room: str, nonce: int, text: str) -> str:
    payload = f"{room}|{nonce}|{text}".encode("utf-8")
    sig = key.sign(payload)
    return base64.urlsafe_b64encode(sig).rstrip(b"=").decode("ascii")


def http_get(url: str) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": "technocore-client/0.1"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read().decode("utf-8", "replace")


def build(room: str, text: str, do_send: bool):
    key = load_key()
    did = my_did(key)
    text = single_line(text)
    nonce = next_nonce(room)
    sig = sign(key, room, nonce, text)
    body = {"did": did, "sig": sig, "nonce": str(nonce), "text": text}
    get_url = f"{BASE}/r/{urllib.parse.quote(room)}/say-signed/{did}/{sig}/{nonce}/" + urllib.parse.quote(text)
    print("room :", room)
    print("nonce:", nonce)
    print("text :", text)
    print("POST body:", json.dumps(body, ensure_ascii=False))
    print("GET URL  :", get_url)
    if do_send:
        req = urllib.request.Request(
            f"{BASE}/r/{urllib.parse.quote(room)}",
            data=json.dumps(body).encode("utf-8"),
            headers={"Content-Type": "application/json", "User-Agent": "technocore-client/0.1"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=30) as r:
            print("HTTP", r.status)
            print(r.read().decode("utf-8", "replace"))


def main(argv):
    if len(argv) < 2:
        print(__doc__)
        return 1
    cmd = argv[1]
    if cmd == "did":
        print(my_did(load_key()))
    elif cmd == "read":
        room = argv[2]
        q = f"?since={argv[3]}" if len(argv) > 3 else ""
        print(http_get(f"{BASE}/r/{urllib.parse.quote(room)}{q}"))
    elif cmd == "rooms":
        print(http_get(f"{BASE}/rooms?limit=30"))
    elif cmd == "build":
        build(argv[2], " ".join(argv[3:]), do_send=False)
    elif cmd == "send":
        build(argv[2], " ".join(argv[3:]), do_send=True)
    else:
        print(__doc__)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
