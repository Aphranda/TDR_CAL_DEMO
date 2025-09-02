# src/app/core/ADCSample.py
import struct
import os
import time
import socket


import logging
import gc  # 添加垃圾回收模块

try:
    from .TcpClient import TcpClient
    from .FileManager import FileManager
except ImportError:
    from TcpClient import TcpClient
    from FileManager import FileManager

logger = logging.getLogger(__name__)

class ADCSample:
    """使用外部TcpClient实例的ADC采样类，优化内存使用"""
    
    def __init__(self, tcp_client=None, file_manager=None):
        # 使用外部传入的TcpClient实例
        self.tcp_client = tcp_client or TcpClient()
        self.file_manager = file_manager or FileManager()
        self.connected = self.tcp_client.connected if self.tcp_client else False
        self.server_ip = self.tcp_client.server_ip if self.tcp_client and self.tcp_client.server_ip else '192.168.1.10'
        self.server_port = self.tcp_client.server_port if self.tcp_client and self.tcp_client.server_port else 15000
        self.chunk_size = 32768  # 32KB chunks
        self.output_dir = 'data\\results\\test'
    
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
    
    def send_command(self, command, max_retries=3):
        """发送命令并获取响应"""
        if not self.is_connected():
            return False, "未连接到服务器"
        
        success, response = self.tcp_client.send(command, max_retries)
        if not success:
            return False, response
        
        # 如果需要接收响应
        success, response_data = self.tcp_client.receive(max_retries=max_retries)
        return success, response_data
    
    def receive_binary_data(self, max_retries=3, base_timeout=1.0):
        """
        专门用于接收二进制数据的方法，优化内存使用
        返回: (是否成功, 字节数据或错误信息)
        """
        if not self.is_connected() or not self.tcp_client.sock:
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
                
                # 使用固定大小的缓冲区来避免无限增长的bytearray
                chunk_buffer = bytearray(self.chunk_size)
                bytes_received = self.tcp_client.sock.recv_into(chunk_buffer)
                
                if bytes_received == 0:
                    retry_count += 1
                    continue
                
                # 只添加实际接收到的数据
                received_data = chunk_buffer[:bytes_received]
                
                # 检查结束标记
                if received_data == b'\x00':
                    break
                
                # 使用extend而不是+=来避免创建临时对象
                data.extend(received_data)
                retry_count = 0  # 重置重试计数
                
                # 立即释放临时变量内存
                del chunk_buffer, received_data
                gc.collect()
                
            except (socket.timeout, ConnectionError) as e:
                retry_count += 1
                time.sleep(0.2 * retry_count)
            except Exception as e:
                # 确保在异常时释放内存
                del data
                gc.collect()
                return False, f"接收数据错误: {str(e)}"
        
        if retry_count >= max_retries:
            # 超时时释放内存
            del data
            gc.collect()
            return False, "接收数据超时"
        
        # 返回前进行内存整理
        if hasattr(data, 'shrink_to_fit'):
            data.shrink_to_fit()
        
        return True, bytes(data)  # 返回不可变的bytes对象而不是bytearray

    
    def perform_single_test(self, test_num):
        """执行单次测试并返回数据，优化内存使用"""
        if not self.is_connected():
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
                # 使用内存视图避免数据复制
                data_view = memoryview(data)
                u32_values = []
                
                # 分批处理数据以避免一次性分配大内存
                batch_size = 1024 * 256  # 每批处理256KB数据
                for i in range(0, len(data), batch_size):
                    end_idx = min(i + batch_size, len(data))
                    batch_data = data_view[i:end_idx]
                    batch_num_values = len(batch_data) // 4
                    
                    if batch_num_values > 0:
                        batch_u32 = struct.unpack('<' + 'I' * batch_num_values, batch_data)
                        u32_values.extend(batch_u32)
                    
                    # 释放批次内存
                    del batch_data, batch_u32
                    gc.collect()
                
                logger.info(f"测试 {test_num + 1}: 成功解析 {num_values} 个32位数据点")
                
                # 释放大内存对象
                del data, data_view
                gc.collect()

                # 测试完成后再次清空TCP缓存
                bytes_cleared = self.tcp_client.clear_receive_buffer()
                if bytes_cleared > 0:
                    logger.debug(f"测试后清空了 {bytes_cleared} 字节的TCP缓存")
                
                return u32_values, None
                
            except struct.error as e:
                return None, f"数据解析错误: {str(e)}"
            
        except Exception as e:
            return None, f"测试过程中发生错误: {str(e)}"
    
    def perform_multiple_tests(self, test_count=10, delay_between_tests=0.1):
        """执行多次测试，优化内存使用"""
        if not self.is_connected():
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
                
                # 立即释放测试数据内存
                del u32_values
                gc.collect()
                
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
        
        # 最终垃圾回收
        gc.collect()
        
        return successful_tests > 0, f"完成 {successful_tests}/{test_count} 次测试"

    def save_test_result(self, test_num, u32_values, filename=None, output_dir=None):
        """保存测试结果到文件，优化内存使用"""
        if filename is None:
            filename = f'test_result_{test_num + 1:04d}.csv'
        if output_dir is None:
            output_dir = self.output_dir
        
        # 保存CSV文件
        csv_success, csv_message = self.file_manager.save_adc_csv_data(u32_values, filename, output_dir)
        
        # 同时保存原始二进制数据
        bin_filename = f'{filename.replace(".csv","")}.bin'
        bin_success, bin_message = self.save_binary_data(u32_values, bin_filename, output_dir)
        
        return csv_success, f"CSV: {csv_message}, BIN: {bin_message}"
    
    def save_binary_data(self, u32_values, filename, output_dir):
        """保存原始二进制数据，优化内存使用"""
        self.file_manager.ensure_dir_exists(output_dir)
        filepath = os.path.join(output_dir, filename)
        
        try:
            # 分批处理大数组以避免一次性分配大内存
            batch_size = 1024 * 256  # 每批处理256KB数据
            total_values = len(u32_values)
            
            with open(filepath, 'wb') as f:
                for i in range(0, total_values, batch_size):
                    end_idx = min(i + batch_size, total_values)
                    batch_data = u32_values[i:end_idx]
                    
                    # 将uint32数组转换为字节数据
                    binary_data = struct.pack('<' + 'I' * len(batch_data), *batch_data)
                    f.write(binary_data)
                    
                    # 释放批次内存
                    del batch_data, binary_data
                    gc.collect()
            
            logger.info(f"二进制数据已保存到 {filepath}，共{total_values * 4}字节")
            return True, f"二进制数据保存成功: {filepath}"
            
        except Exception as e:
            logger.error(f"二进制数据保存失败: {str(e)}")
            return False, f"二进制数据保存失败: {str(e)}"

    def cleanup(self):
        """清理资源，释放内存"""
        if hasattr(self, 'tcp_client') and self.tcp_client:
            self.tcp_client.close()
        
        # 强制垃圾回收
        gc.collect()
        gc.collect()  # 两次调用以确保完全回收


# 保持向后兼容的独立函数
def main():
    """独立运行的主函数"""
    tcpClient = TcpClient()
    tcpClient.connect(ip='192.168.1.10',port=15000)
    adc_sample = ADCSample(tcpClient)

    
    try:
        # 连接到服务器
        success, message = adc_sample.perform_single_test(1)
        print(f"连接失败: {message}")
        return
        
        print("连接成功，开始测试...")
        
        # 执行多次测试
        success, message = adc_sample.perform_multiple_tests(test_count=10)
        
        if success:
            print(f"测试完成: {message}")
        else:
            print(f"测试失败: {message}")
            
    finally:
        # 确保资源清理
        adc_sample.cleanup()


if __name__ == "__main__":
    main()
