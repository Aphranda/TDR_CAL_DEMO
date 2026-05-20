#!/usr/bin/env python3
"""简易脚本：验证 TCP 数据获取功能（对齐 NEW DATA.py 协议）"""

import socket
import struct
import sys

SERVER_HOST = "192.168.1.30"
SERVER_PORT = 15000
CHANNELS = [4, 5]               # 默认通道
SAMPLES_PER_BLOCK = 81920       # 每个 DMA block 的采样点数
SAMPLE_BYTES = 4                # 每个样本 4 字节
POINTS = 81920                  # 请求的采样点数（1 block）
RECV_CHUNK = 65536


def _build_link_mask(channels):
    mask = 0
    for ch in channels:
        mask |= 1 << (ch - 1)
    return mask


def send_cmd(sock, cmd):
    """发送命令并读取一行应答"""
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
    # 计算参数
    block_count = max(1, (POINTS + SAMPLES_PER_BLOCK - 1) // SAMPLES_PER_BLOCK)
    link_mask = _build_link_mask(CHANNELS)
    need_bytes = POINTS * SAMPLE_BYTES

    print(f"连接 {SERVER_HOST}:{SERVER_PORT} ...")
    sock = socket.create_connection((SERVER_HOST, SERVER_PORT), timeout=10)
    sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
    print("✓ 已连接\n")

    # ---- 1. 发送采样命令 ----
    sample_cmd = f"sample {block_count} 0x{link_mask:x}"
    print(f"[1] 发送采样命令: {sample_cmd}")
    print(f"    参数: block_count={block_count}, link_mask=0x{link_mask:x}, "
          f"channels={CHANNELS}, 每通道={POINTS}点")
    resp = send_cmd(sock, sample_cmd)
    print(f"    应答: {resp}")
    if "ok" not in resp.lower():
        print(f"✗ 采样命令失败: {resp}")
        sock.close()
        return

    # ---- 2. 逐通道读取数据 ----
    for ch in CHANNELS:
        read_cmd = f"readall{ch} {need_bytes}"
        print(f"\n[2] 读取通道 {ch}: {read_cmd}")
        sock.sendall((read_cmd + "\n").encode())

        # 读取 4 字节头
        hdr = b""
        while len(hdr) < 4:
            chunk = sock.recv(4 - len(hdr))
            if not chunk:
                raise RuntimeError("读取头部时连接关闭")
            hdr += chunk
        (data_size,) = struct.unpack("!I", hdr)
        print(f"    头部 size={data_size} bytes ({data_size // SAMPLE_BYTES} 样本)")

        if data_size == 0:
            print(f"    ✗ 通道 {ch} 返回 0 字节（空数据）")
            continue

        # 读取数据体
        data = bytearray()
        while len(data) < data_size:
            chunk = sock.recv(min(RECV_CHUNK, data_size - len(data)))
            if not chunk:
                break
            data.extend(chunk)

        print(f"    实际读取: {len(data)} bytes ({len(data) // SAMPLE_BYTES} 样本)")

        if len(data) < data_size:
            print(f"    ✗ 数据不完整: 期望 {data_size} 字节, 收到 {len(data)} 字节")

        # 解码前 10 个样本预览
        raw_words = struct.unpack(f"<{min(10, len(data) // 4)}I", data[:40])
        print(f"    前 10 个 raw32 值: {list(raw_words)}")

    # ---- 3. DMA 复位 ----
    print(f"\n[3] DMA 复位: dma_rst 1")
    resp = send_cmd(sock, "dma_rst 1")
    print(f"    应答: {resp}")

    sock.close()
    print("\n✓ 完成")


if __name__ == "__main__":
    main()
