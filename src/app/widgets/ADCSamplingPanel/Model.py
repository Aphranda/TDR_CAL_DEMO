# src/app/widgets/ADCSamplingPanel/Model.py
from dataclasses import dataclass
from typing import List

class ADCSamplingModel:
    def __init__(self):
        self.adc_connected = False
        self.adc_samples = []
        self.adc_ip = "192.168.1.10"
        self.adc_port = 15000
        self.sample_count = 10
        self.sample_interval = 0.1
        self.output_dir = "data\\results\\test"
        self.filename_prefix = "adc_data"
        self.save_raw_data = True
        
    def set_adc_connection_status(self, connected: bool):
        """设置ADC连接状态"""
        self.adc_connected = connected
        
    def add_adc_sample(self, sample_data):
        """添加ADC采样数据"""
        self.adc_samples.append(sample_data)
        
    def clear_adc_samples(self):
        """清除ADC采样数据"""
        self.adc_samples.clear()
        
    def get_adc_samples_count(self) -> int:
        """获取ADC采样数量"""
        return len(self.adc_samples)
