# src/app/core/ADCSample.py
import struct
import os
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

class ADCSample:
    """使用外部TcpClient实例的ADC采样类"""
    
    def __init__(self, tcp_client=None, file_manager=None):
        # 使用外部传入的TcpClient实例
        self.tcp_client = tcp_client or TcpClient()
        self.file_manager = file_manager or FileManager()
        self.connected = self.tcp_client.connected if self.tcp_client else False
        self.server_ip = self.tcp_client.server_ip if self.tcp_client and self.tcp_client.server_ip else '192.168.1.10'
        self.server_port = self.tcp_client.server_port if self.tcp_client and self.tcp_client.server_port else 15000
        self.chunk_size = 65530
        self.output_dir = 'data\\results\\test'
        self.sample_number = 10  # 新增：默认单次采样数量为10
        self.adc_mode = ADCMode.ADC1_ONLY  # 默认采集两个ADC
        self.data_type = 'uint32'  # 默认数据类型

    def set_data_type(self, data_type):
        """设置ADC输出数据类型"""
        self.data_type = data_type
        logger.info(f"ADC输出数据类型设置为: {data_type}")

    def set_adc_mode(self, adc_mode: ADCMode):
        """设置ADC采集模式"""
        self.adc_mode = adc_mode
        logger.info(f"ADC采集模式设置为: {adc_mode.value}")

    def set_sample_number(self, sample_number: int):
        """设置单次采样数量"""
        self.sample_number = sample_number
    
    def set_tcp_client(self, tcp_client):
        """设置外部TcpClient实例"""
        self.tcp_client = tcp_client
        self.connected = tcp_client.connected if tcp_client else False
        if tcp_client:
            self.server_ip = tcp_client.server_ip
            self.server_port = tcp_client.server_port
    
    def set_server_config(self, ip, port):
        """设置服务器配置"""
        self.server_ip = ip
        self.server_port = port
    
    def set_output_dir(self, output_dir):
        """设置输出目录"""
        self.output_dir = output_dir
    
    def is_connected(self):
        """检查是否已连接"""
        return self.tcp_client and self.tcp_client.connected
    
    # @timeit
    def send_command(self, command, max_retries=3):
        """发送命令并获取响应"""
        if not self.is_connected():
            return False, "未连接到服务器"
        
        success, response = self.tcp_client.send(command, max_retries)
        if not success:
            return False, response
        
 
        success, response_data = self.tcp_client.receive(max_retries=max_retries)
        return success, response_data
    
    # @timeit
    def receive_binary_data(self, max_retries=3, base_timeout=2.0):
        """
        专门用于接收二进制数据的方法
        根据ADC模式读取数据，使用字典返回
        返回: (是否成功, {'adc1': adc1_data, 'adc2': adc2_data} 或错误信息)
        """
        if not self.is_connected() or not self.tcp_client.sock:
            return False, "未连接"
        
        
        adc1_data = bytearray()
        adc2_data = bytearray()
        #ToDo 清空TCP接收缓冲区
        if self.adc_mode in [ADCMode.ADC1_ONLY, ADCMode.BOTH_ADCS]:
            retry_count = 0
            while retry_count < max_retries:
                try:
                    # 根据ADC模式决定读取哪些数据
                    # 发送read1命令读取第一个ADC
                    success, _ = self.tcp_client.send('read1', max_retries)
                    if not success:
                        retry_count += 1
                        continue
                    time.sleep(0.02)
                    # 接收第一个ADC的二进制数据
                    self.tcp_client.sock.settimeout(base_timeout)
                    chunk1 = self.tcp_client.sock.recv(self.chunk_size)
                    
                    if not chunk1:
                        retry_count += 1
                        continue
                    # 检查结束标记
                    if chunk1 == b'\x00':
                        break

                    adc1_data.extend(chunk1)            
                    retry_count = 0  # 重置重试计数
                    
                except (socket.timeout, ConnectionError) as e:
                    retry_count += 1
                    time.sleep(0.2 * retry_count)
                except Exception as e:
                    return False, f"接收数据错误: {str(e)}"
        
        
        if self.adc_mode in [ADCMode.ADC2_ONLY, ADCMode.BOTH_ADCS]:
            retry_count = 0
            while retry_count < max_retries:
                try:
                    # 发送read2命令读取第二个ADC
                    success, _ = self.tcp_client.send('read2', max_retries)
                    if not success:
                        retry_count += 1
                        continue
                    time.sleep(0.02)
                    # 接收第二个ADC的二进制数据
                    chunk2 = self.tcp_client.sock.recv(self.chunk_size)
                    
                    if not chunk2:
                        retry_count += 1
                        continue
                    
                    # 检查结束标记
                    if chunk2 == b'\x00':
                        break
                    adc2_data.extend(chunk2)
                    
                    retry_count = 0  # 重置重试计数
                    
                except (socket.timeout, ConnectionError) as e:
                    retry_count += 1
                    time.sleep(0.2 * retry_count)
                except Exception as e:
                    return False, f"接收数据错误: {str(e)}"
        
        if retry_count >= max_retries:
            return False, "接收数据超时"
        
        # 根据ADC模式返回相应的数据字典
        result_data = {}
        if self.adc_mode in [ADCMode.ADC1_ONLY, ADCMode.BOTH_ADCS]:
            result_data['adc1'] = adc1_data
        if self.adc_mode in [ADCMode.ADC2_ONLY, ADCMode.BOTH_ADCS]:
            result_data['adc2'] = adc2_data
            
        return True, result_data
    


    # @timeit
    def perform_single_test(self, test_num, sample_number=None):
        """执行单次测试并返回数据"""
        if not self.is_connected():
            return None, "未连接到服务器"

        # 使用传入的sample_number或默认值
        current_sample_number = sample_number if sample_number is not None else self.sample_number

        try:
            # 根据数据类型选择采样命令
            if self.data_type == 'uint32':
                command = f'sample {current_sample_number}'
            elif self.data_type == 'float64':
                print("current_sample_number",current_sample_number)
                command = f'caclu_sample {current_sample_number}'
            else:
                return None, f"不支持的数据类型: {self.data_type}"

            success, response = self.send_command(command)
            if not success:
                return None, f"采样指令发送失败: {response}"

            logger.info(f"测试 {test_num + 1}: {command} 响应: {response.strip()}")

            if 'ok' not in response.lower():
                return None, f"采样失败: {response}"

            # 接收采样数据
            success, data_dict = self.receive_binary_data(max_retries=5)
            if not success:
                return None, f"数据接收失败: {data_dict}"

            logger.info(f"测试 {test_num + 1}: 接收 ADC1 {len(data_dict.get('adc1', []))} 字节, ADC2 {len(data_dict.get('adc2', []))} 字节")

            # 根据数据类型处理数据
            processed_data = {}
            for adc_name, data in data_dict.items():
                # 根据数据类型确定每个数据点的字节数和numpy类型
                if self.data_type == 'uint32':
                    bytes_per_point = 4
                    dtype = '<u4'  # 小端无符号32位整数
                elif self.data_type == 'float64':
                    bytes_per_point = 8
                    dtype = '<f8'  # 小端64位浮点数
                else:
                    return None, f"不支持的数据类型: {self.data_type}"

                if len(data) % bytes_per_point != 0:
                    data = data[:len(data) - (len(data) % bytes_per_point)]

                num_values = len(data) // bytes_per_point
                if num_values == 0:
                    logger.warning(f"ADC {adc_name} 未接收到有效数据")
                    processed_data[adc_name] = np.array([], dtype=dtype)
                    continue

                temp_array = np.frombuffer(data, dtype=dtype, count=num_values)
                processed_data[adc_name] = temp_array.copy()
                logger.info(f"测试 {test_num + 1}: ADC {adc_name} 成功解析 {num_values} 个{self.data_type}数据点")
            
            return processed_data, None

        except Exception as e:
            return None, f"测试过程中发生错误: {str(e)}"


