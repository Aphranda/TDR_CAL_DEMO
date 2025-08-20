# Title  : ADC Tester Utility
# Author : YEaoqi
# Email  : yeaoqi@foxmail.com
# Time   : 2024-01-15
import sys
import os

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from app.core.ADCSample import ADCSample


def run_adc_test():
    """运行ADC测试的独立工具函数"""
    tester = ADCSample()
    
    # 可配置参数
    server_ip = '192.168.1.10'
    server_port = 15000
    test_count = 10
    output_dir = 'CSV_Data_test_results'
    
    print(f"ADC采样测试工具")
    print(f"服务器: {server_ip}:{server_port}")
    print(f"测试次数: {test_count}")
    print(f"输出目录: {output_dir}")
    print("-" * 50)
    
    # 设置配置
    tester.set_server_config(server_ip, server_port)
    tester.set_output_dir(output_dir)
    
    # 连接
    print("正在连接服务器...")
    success, message = tester.connect(timeout=5)
    if not success:
        print(f"连接失败: {message}")
        return False
    
    print("连接成功!")
    
    # 执行测试
    print("开始执行测试...")
    success, message = tester.perform_multiple_tests(test_count=test_count, delay_between_tests=0.1)
    
    # 断开连接
    tester.disconnect()
    
    print("\n" + "=" * 50)
    if success:
        print(f"✅ 测试完成: {message}")
    else:
        print(f"❌ 测试失败: {message}")
    
    return success


if __name__ == "__main__":
    run_adc_test()
