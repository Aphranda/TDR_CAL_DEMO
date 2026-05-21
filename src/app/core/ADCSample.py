# src/app/core/ADCSample.py
import struct
import time
import socket
import logging
import numpy as np
try:
    from .TcpClient import TcpClient
    from .FileManager import FileManager
    from .PerformanceMonitor import timeit, performance_monitor
    from .ConfigManager import ADCMode
except ImportError:
    from TcpClient import TcpClient
    from FileManager import FileManager
    from PerformanceMonitor import timeit, performance_monitor
    from ConfigManager import ADCMode

logger = logging.getLogger(__name__)

# 协议常量（对齐 scripts/NEW DATA.py）
SAMPLES_PER_BLOCK = 81920      # 每个 DMA block 的采样点数
SAMPLE_BYTES = 4                # 每个样本 4 字节（32-bit 小端）
RECV_CHUNK = 65536              # socket 接收缓冲区大小
DEFAULT_CHANNELS = [4, 5]       # 默认采集通道（Port1=Ch4, Port2=Ch5）
CHANNEL_KEY_MAP = {4: 'adc1', 5: 'adc2'}  # 通道号 → 数据字典键


def _build_link_mask(channels):
    """构建通道位掩码：每个通道占 1 bit"""
    mask = 0
    for ch in channels:
        mask |= 1 << (ch - 1)
    return mask


class ADCSample:
    """ADC 采样类 — 对齐 NEW DATA.py TCP 协议

    使用 sample + readall 命令进行数据采集：
      sample <block_count> 0x<link_mask>   →  启动采样
      readall<channel> <byte_count>        →  读取数据（4字节头+数据体）
      dma_rst 1                            →  DMA 复位
    """

    def __init__(self, tcp_client=None, file_manager=None):
        self.tcp_client = tcp_client or TcpClient()
        self.file_manager = file_manager or FileManager()
        self.connected = self.tcp_client.connected if self.tcp_client else False
        self.server_ip = self.tcp_client.server_ip if self.tcp_client and self.tcp_client.server_ip else '192.168.1.30'
        self.server_port = self.tcp_client.server_port if self.tcp_client and self.tcp_client.server_port else 15000
        self.output_dir = 'data\\results\\test'
        self.sample_number = 1  # 默认 1 个 block
        self.adc_mode = ADCMode.ADC1_ONLY
        self.data_type = 'uint32'
        self.channels = list(DEFAULT_CHANNELS)  # 当前采集通道列表

    # =========================================================================
    # 配置方法
    # =========================================================================

    def set_data_type(self, data_type):
        self.data_type = data_type
        logger.info(f"ADC输出数据类型设置为: {data_type}")

    def set_adc_mode(self, adc_mode: ADCMode):
        """设置 ADC 采集模式，自动更新通道列表"""
        self.adc_mode = adc_mode
        if adc_mode == ADCMode.ADC1_ONLY:
            self.channels = [4]
        elif adc_mode == ADCMode.ADC2_ONLY:
            self.channels = [5]
        else:  # BOTH_ADCS
            self.channels = [4, 5]
        logger.info(f"ADC采集模式: {adc_mode.value}, 通道: {self.channels}")

    def set_channels(self, channels):
        """直接设置采集通道列表"""
        self.channels = list(channels)

    def get_channels(self):
        return list(self.channels)

    def set_sample_number(self, sample_number: int):
        self.sample_number = sample_number

    def set_tcp_client(self, tcp_client):
        self.tcp_client = tcp_client
        self.connected = tcp_client.connected if tcp_client else False
        if tcp_client:
            self.server_ip = tcp_client.server_ip
            self.server_port = tcp_client.server_port

    def set_server_config(self, ip, port):
        self.server_ip = ip
        self.server_port = port

    def set_output_dir(self, output_dir):
        self.output_dir = output_dir

    def is_connected(self):
        return self.tcp_client and self.tcp_client.connected

    # =========================================================================
    # 命令收发
    # =========================================================================

    def send_command(self, command, max_retries=3):
        """发送文本命令并读取一行应答"""
        if not self.is_connected():
            return False, "未连接到服务器"

        success, _ = self.tcp_client.send(command + "\n", max_retries)
        if not success:
            return False, "命令发送失败"

        success, response_data = self.tcp_client.receive(max_retries=max_retries)
        return success, response_data

    # =========================================================================
    # 二进制数据读取（readall 协议）
    # =========================================================================

    def _read_channel_data(self, channel, byte_count, max_retries=3):
        """通过 readall 协议读取单个通道的二进制数据

        协议: 发送 readall<channel> <byte_count>
              接收 4 字节大端头 → 数据长度
              接收对应长度的数据体
        """
        sock = self.tcp_client.sock
        if not sock:
            return None

        cmd = f"readall{channel} {byte_count}"
        total_data = bytearray()

        for retry in range(max_retries):
            try:
                # 发送 readall 命令
                sock.sendall((cmd + "\n").encode())

                # 读取 4 字节头（大端无符号 int）
                hdr = b""
                while len(hdr) < 4:
                    chunk = sock.recv(4 - len(hdr))
                    if not chunk:
                        raise RuntimeError("读取头部时连接关闭")
                    hdr += chunk
                (size,) = struct.unpack("!I", hdr)

                if size == 0:
                    raise RuntimeError(f"link{channel} 返回空数据")

                # 读取数据体
                data = bytearray()
                while len(data) < size:
                    chunk = sock.recv(min(RECV_CHUNK, size - len(data)))
                    if not chunk:
                        break
                    data.extend(chunk)

                if len(data) < size:
                    raise RuntimeError(
                        f"link{channel} 数据不完整: 期望 {size} 字节, 收到 {len(data)} 字节"
                    )

                return bytes(data)

            except (socket.timeout, ConnectionError, RuntimeError) as e:
                logger.warning(f"link{channel} 读取重试 {retry + 1}/{max_retries}: {e}")
                if retry < max_retries - 1:
                    time.sleep(0.2 * (retry + 1))
                total_data = bytearray()

        return None

    # =========================================================================
    # 数据接收（替代旧的 receive_binary_data）
    # =========================================================================

    def receive_binary_data(self, points, max_retries=3, base_timeout=2.0):
        """接收所有活跃通道的二进制数据

        返回: (成功标志, {'adc1': bytes, 'adc2': bytes} 或错误信息)
        """
        if not self.is_connected() or not self.tcp_client.sock:
            return False, "未连接"

        need_bytes = points * SAMPLE_BYTES
        result_data = {}
        all_ok = True

        for ch in self.channels:
            raw = self._read_channel_data(ch, need_bytes, max_retries)
            if raw is None:
                all_ok = False
                logger.error(f"通道 {ch} 数据读取失败")
                continue

            key = CHANNEL_KEY_MAP.get(ch, f'ch{ch}')
            result_data[key] = raw

        if not result_data:
            return False, "所有通道数据读取失败"

        # DMA 复位（对齐 NEW DATA.py）
        try:
            self.tcp_client.send("dma_rst 1\n")
            time.sleep(0.02)
            self.tcp_client.receive(max_retries=1, base_timeout=1.0)
        except Exception:
            pass  # DMA 复位失败不阻塞

        return True, result_data

    # =========================================================================
    # 单次采样
    # =========================================================================

    def perform_single_test(self, test_num, sample_number=None):
        """执行单次采样并返回处理后的数据

        Args:
            test_num: 测试序号（日志用）
            sample_number: DMA block 数量（1 block = 81920 样本），为 None 则使用默认值

        Returns:
            (processed_data, error): 成功时 error 为 None
            processed_data 为 {'adc1': np.ndarray, 'adc2': np.ndarray}
        """
        if not self.is_connected():
            return None, "未连接到服务器"

        block_count = sample_number if sample_number is not None else self.sample_number
        points = block_count * SAMPLES_PER_BLOCK

        try:
            # 1. 发送采样命令: sample <block_count> 0x<link_mask>
            link_mask = _build_link_mask(self.channels)
            command = f"sample {block_count} 0x{link_mask:x}"

            logger.info(f"测试 {test_num + 1}: {command} (blocks={block_count}, points={points}, channels={self.channels})")

            success, response = self.send_command(command)
            if not success:
                return None, f"采样指令发送失败: {response}"

            if 'ok' not in response.lower():
                return None, f"采样失败: {response}"

            # 2. 接收数据
            success, data_dict = self.receive_binary_data(points, max_retries=5)
            if not success:
                return None, f"数据接收失败: {data_dict}"

            bytes_info = ", ".join(
                f"{k}={len(v)}B" for k, v in data_dict.items()
            )
            logger.info(f"测试 {test_num + 1}: 接收数据 {bytes_info}")

            # 3. 解码为 numpy 数组
            processed_data = {}
            for key, data in data_dict.items():
                if self.data_type == 'uint32':
                    dtype = '<u4'
                    bytes_per_point = 4
                elif self.data_type == 'float64':
                    dtype = '<f8'
                    bytes_per_point = 8
                else:
                    return None, f"不支持的数据类型: {self.data_type}"

                if len(data) % bytes_per_point != 0:
                    data = data[:len(data) - (len(data) % bytes_per_point)]

                num_values = len(data) // bytes_per_point
                if num_values == 0:
                    logger.warning(f"ADC {key} 未接收到有效数据")
                    processed_data[key] = np.array([], dtype=dtype)
                    continue

                temp_array = np.frombuffer(data, dtype=dtype, count=num_values)
                processed_data[key] = temp_array.copy()
                logger.info(f"测试 {test_num + 1}: {key} 解析 {num_values} 个数据点")

            return processed_data, None

        except Exception as e:
            return None, f"采样异常: {str(e)}"
