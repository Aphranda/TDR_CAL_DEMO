# src/app/core/ADCSample.py
import struct
import os
import time
import socket
from .TcpClient import TcpClient
from .FileManager import FileManager
import logging

logger = logging.getLogger(__name__)

class ADCSample:
    """使用TcpClient优化的ADC采样类"""
    
    def __init__(self, file_manager=None):
        self.tcp_client = TcpClient()
        self.file_manager = file_manager or FileManager()
        self.connected = False
        self.server_ip = '192.168.1.10'
        self.server_port = 15000
        self.chunk_size = 32768
        self.output_dir = 'data\\results\\test'
    
    def set_server_config(self, ip, port):
        """设置服务器配置"""
        self.server_ip = ip
        self.server_port = port
    
    def set_output_dir(self, output_dir):
        """设置输出目录"""
        self.output_dir = output_dir
    
    def connect(self, timeout=3):
        """连接到ADC服务器"""
        success, message = self.tcp_client.connect(self.server_ip, self.server_port, timeout)
        self.connected = success
        return success, message
    
    def disconnect(self):
        """断开连接"""
        self.tcp_client.close()
        self.connected = False
    
    def send_command(self, command, max_retries=3):
        """发送命令并获取响应"""
        if not self.connected:
            return False, "未连接到服务器"
        
        success, response = self.tcp_client.send(command, max_retries)
        if not success:
            return False, response
        
        # 如果需要接收响应
        success, response_data = self.tcp_client.receive(max_retries=max_retries)
        return success, response_data
    
    def receive_binary_data(self, max_retries=3, base_timeout=1.0):
        """
        专门用于接收二进制数据的方法
        返回: (是否成功, 字节数据或错误信息)
        """
        if not self.connected or not self.tcp_client.sock:
            return False, "未连接"
        
        retry_count = 0
        data = bytearray()
        
        while retry_count < max_retries:
            try:
                # 发送read命令
                success, _ = self.tcp_client.send('read', max_retries)
                if not success:
                    retry_count += 1
                    continue
                
                # 直接接收二进制数据
                self.tcp_client.sock.settimeout(base_timeout)
                chunk = self.tcp_client.sock.recv(self.chunk_size)
                
                if not chunk:
                    retry_count += 1
                    continue
                
                # 检查结束标记
                if chunk == b'\x00':
                    break
                
                data.extend(chunk)
                retry_count = 0  # 重置重试计数
                
            except (socket.timeout, ConnectionError) as e:
                retry_count += 1
                time.sleep(0.2 * retry_count)
            except Exception as e:
                return False, f"接收数据错误: {str(e)}"
        
        if retry_count >= max_retries:
            return False, "接收数据超时"
        
        return True, data
    
    def perform_single_test(self, test_num):
        """执行单次测试并返回数据"""
        if not self.connected:
            return None, "未连接到服务器"
        
        try:
            # 发送sample指令
            success, response = self.send_command('sample')
            if not success:
                return None, f"采样指令发送失败: {response}"
            
            logger.info(f"测试 {test_num + 1}: sample 响应: {response.strip()}")
            
            if 'ok' not in response.lower():
                return None, f"采样失败: {response}"
            
            # 接收采样数据 - 使用专门的二进制接收方法
            success, data = self.receive_binary_data(max_retries=5)
            if not success:
                return None, f"数据接收失败: {data}"
            
            logger.info(f"测试 {test_num + 1}: 接收 {len(data)} 字节原始数据")
            
            # 检查数据长度是否为4的倍数
            if len(data) % 4 != 0:
                # 截断到最近的4的倍数
                data = data[:len(data) - (len(data) % 4)]
            
            # 将数据解析为小端 uint32
            num_values = len(data) // 4
            if num_values == 0:
                return None, "未接收到有效数据"
            
            try:
                u32_values = struct.unpack('<' + 'I' * num_values, data)
                logger.info(f"测试 {test_num + 1}: 成功解析 {num_values} 个32位数据点")
                return u32_values, None
            except struct.error as e:
                return None, f"数据解析错误: {str(e)}"
            
        except Exception as e:
            return None, f"测试过程中发生错误: {str(e)}"
    
    def perform_multiple_tests(self, test_count=10, delay_between_tests=0.1):
        """执行多次测试"""
        if not self.connected:
            return False, "未连接到服务器"
        
        self.file_manager.ensure_dir_exists(self.output_dir)
        start_time = time.time()
        successful_tests = 0
        
        for i in range(test_count):
            try:
                logger.info(f"\n开始测试 {i + 1}/{test_count}")
                
                # 执行单次测试
                u32_values, error = self.perform_single_test(i)
                if error:
                    logger.error(f"测试 {i + 1} 失败: {error}")
                    continue
                
                # 保存结果
                success, message = self.save_test_result(i, u32_values)
                if success:
                    successful_tests += 1
                    logger.info(f"测试 {i + 1} 完成: {message}")
                else:
                    logger.error(f"测试 {i + 1} 保存失败: {message}")
                
                # 每次测试后短暂暂停
                time.sleep(delay_between_tests)
                
            except Exception as e:
                logger.error(f"测试 {i + 1} 发生异常: {str(e)}")
                continue
        
        # 计算并显示总耗时
        total_time = time.time() - start_time
        logger.info(f"\n所有测试完成! 共进行 {test_count} 次测试，成功 {successful_tests} 次")
        logger.info(f"总耗时: {total_time:.2f} 秒")
        if successful_tests > 0:
            logger.info(f"平均每次成功测试耗时: {total_time / successful_tests:.2f} 秒")
        logger.info(f"结果文件保存在: {os.path.abspath(self.output_dir)}")
        
        return successful_tests > 0, f"完成 {successful_tests}/{test_count} 次测试"

    def save_test_result(self, test_num, u32_values, filename=None, output_dir=None):
        """保存测试结果到文件"""
        if filename is None:
            filename = f'test_result_{test_num + 1:04d}.csv'
        if output_dir is None:
            output_dir = self.output_dir
        
        # 保存CSV文件
        csv_success, csv_message = self.file_manager.save_adc_csv_data(u32_values, filename, output_dir)
        
        # 同时保存原始二进制数据
        bin_filename = f'adc_raw_binary_{test_num + 1:04d}.bin'
        bin_success, bin_message = self.save_binary_data(u32_values, bin_filename, output_dir)
        
        return csv_success, f"CSV: {csv_message}, BIN: {bin_message}"
    
    def save_binary_data(self, u32_values, filename, output_dir):
        """保存原始二进制数据"""
        self.file_manager.ensure_dir_exists(output_dir)
        filepath = os.path.join(output_dir, filename)
        
        try:
            # 将uint32数组转换为字节数据
            binary_data = struct.pack('<' + 'I' * len(u32_values), *u32_values)
            
            with open(filepath, 'wb') as f:
                f.write(binary_data)
            
            logger.info(f"二进制数据已保存到 {filepath}，共{len(binary_data)}字节")
            return True, f"二进制数据保存成功: {filepath}"
            
        except Exception as e:
            logger.error(f"二进制数据保存失败: {str(e)}")
            return False, f"二进制数据保存失败: {str(e)}"


# 保持向后兼容的独立函数
def main():
    """独立运行的主函数"""
    adc_sample = ADCSample()
    
    # 连接到服务器
    success, message = adc_sample.connect()
    if not success:
        print(f"连接失败: {message}")
        return
    
    print("连接成功，开始测试...")
    
    # 执行多次测试
    success, message = adc_sample.perform_multiple_tests(test_count=10)
    
    # 断开连接
    adc_sample.disconnect()
    
    if success:
        print(f"测试完成: {message}")
    else:
        print(f"测试失败: {message}")


if __name__ == "__main__":
    main()
