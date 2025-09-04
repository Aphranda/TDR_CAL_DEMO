# Title  : name
# Author : YEaoqi
# Email  : yeaoqi@foxmail.com
# Time   : time
import socket
import struct
import matplotlib.pyplot as plt
import matplotlib
import csv
import os
import time

matplotlib.use('TkAgg')

# 参数配置
SERVER_IP = '192.168.1.10'
SERVER_PORT = 15000
REQUEST_DATA = b'\x01'  # 任意一个字节
CHUNK_SIZE = 32768
TEST_COUNT = 10  # 测试次数
OUTPUT_DIR = 'scripts\\temp\\test_raw'  # 结果保存目录


def ensure_dir_exists(directory):
    """确保目录存在，如果不存在则创建"""
    if not os.path.exists(directory):
        os.makedirs(directory)


def perform_test(test_num):
    """执行单次测试并保存结果"""
    # 创建 TCP 连接
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        print(f"测试 {test_num + 1}/{TEST_COUNT}: 连接到 {SERVER_IP}:{SERVER_PORT}...")
        s.connect((SERVER_IP, SERVER_PORT))

        # 发送 sample 指令
        s.sendall(b'sample')
        response = s.recv(128)
        print(f"测试 {test_num + 1}: sample 响应: {response.strip().decode()}")

        if b'ok' not in response:
            print(f"测试 {test_num + 1}: 采样失败")
            return None

        # 接收采样数据
        data = bytearray()
        while True:
            s.sendall(b'read')
            chunk = s.recv(CHUNK_SIZE)

            if chunk == b'\x00':
                print(f"测试 {test_num + 1}: 采样数据接收完成")
                break

            print(f"测试 {test_num + 1}: 接收 {len(chunk)} 字节")
            data.extend(chunk)

    # 将数据解析为小端 uint32
    num_values = len(data) // 4
    u32_values = struct.unpack('<' + 'I' * num_values, data)
    return u32_values


def save_test_result(test_num, u32_values):
    """保存测试结果到文件"""
    filename = os.path.join(OUTPUT_DIR, f'test_result_{test_num + 1:04d}.csv')

    with open(filename, 'w', newline='') as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(['32位原始数据(十进制)'])

        # 直接保存每个32位值的十进制表示
        for val in u32_values:
            writer.writerow([str(val)])

    print(f"测试 {test_num + 1}: 数据已保存到 {filename}，共{len(u32_values)}个32位数据点")


def main():
    # 确保输出目录存在
    ensure_dir_exists(OUTPUT_DIR)

    # 记录开始时间
    start_time = time.time()

    # 执行多次测试
    for i in range(TEST_COUNT):
        try:
            u32_values = perform_test(i)
            if u32_values is not None:
                save_test_result(i, u32_values)
                # 每次测试后短暂暂停，避免服务器过载
                time.sleep(0.1)
        except Exception as e:
            print(f"测试 {i + 1} 发生错误: {str(e)}")
            continue

    # 计算并显示总耗时
    total_time = time.time() - start_time
    print(f"\n所有测试完成! 共进行 {TEST_COUNT} 次测试")
    print(f"总耗时: {total_time:.2f} 秒")
    print(f"平均每次测试耗时: {total_time / TEST_COUNT:.2f} 秒")
    print(f"结果文件保存在: {os.path.abspath(OUTPUT_DIR)}")


if __name__ == "__main__":
    main()
