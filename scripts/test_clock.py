#!/usr/bin/env python3
"""简易脚本：验证时钟控制 — 开 CH4 触发时钟，开 CH5 采样时钟"""

import socket
import sys

HOST = "192.168.1.30"
PORT = 15000

# 硬件映射（来自 NEW DATA.py）
# Ch4 → LMK(1,7), AD9508 frontend4 → ((2,2),)
# Ch5 → LMK(1,0), AD9508 frontend5 → ((3,0),)

COMMANDS = [
    # === 电源：先给 CH4 和 CH5 上电 ===
    ("power4 1",          "CH4 电源 → ON"),
    ("power5 1",          "CH5 电源 → ON"),

    # === CH4 触发时钟 ON ===
    ("lmk_state 1 7 1",   "CH4 触发时钟 LMK(1,7) → ON"),

    # === CH5 触发时钟 OFF（S21 模式：只用 CH4 触发） ===
    ("lmk_state 1 0 0",   "CH5 触发时钟 LMK(1,0) → OFF"),

    # === CH5 采样时钟 ON ===
    ("ad9508_state 3 0 1","CH5 采样时钟 AD9508(3,0) → ON"),

    # === CH4 采样时钟 OFF（S21 模式：只用 CH5 采样） ===
    ("ad9508_state 2 2 0","CH4 采样时钟 AD9508(2,2) → OFF"),
]


def send_cmd(sock, cmd):
    sock.sendall((cmd + "\n").encode())
    buf = bytearray()
    while True:
        chunk = sock.recv(1024)
        if not chunk:
            raise RuntimeError("连接关闭")
        buf.extend(chunk)
        if b"\n" in buf:
            idx = buf.find(b"\n")
            line = buf[:idx].decode().strip()
            del buf[:idx + 1]
            return line


def main():
    print(f"连接 {HOST}:{PORT} ...")
    sock = socket.create_connection((HOST, PORT), timeout=10)
    sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
    print("✓ 已连接\n")

    ok_count = 0
    for cmd, desc in COMMANDS:
        print(f"  {desc}")
        print(f"    → {cmd}")
        resp = send_cmd(sock, cmd)
        print(f"    ← {resp}")
        if resp == "okay":
            ok_count += 1
        else:
            print(f"    ⚠ 非预期应答")
        print()

    sock.close()
    print(f"完成: {ok_count}/{len(COMMANDS)} 成功")

    if ok_count == len(COMMANDS):
        print("\n当前配置 → S21 模式: CH4 触发, CH5 采样")
    else:
        print("\n有命令未返回 okay，请检查硬件连接")


if __name__ == "__main__":
    main()
