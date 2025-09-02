import gc
import numpy as np
class ADCSamplingModel:
    def __init__(self):
        self.adc_connected = False
        self.adc_samples = []  # 存储采样数据的引用
        self.sample_references = []  # 跟踪所有数据引用
        self.adc_ip = "192.168.1.10"
        self.adc_port = 15000
        self.sample_count = 10
        self.sample_interval = 0.1
        self.output_dir = "data\\results\\test"
        self.filename_prefix = "adc_data"
        self.save_raw_data = True
        self.max_samples_in_memory = 50  # 内存中最多保留的样本数
        
        # 添加内存监控
        self.memory_usage = 0
        
    def set_adc_connection_status(self, connected: bool):
        """设置ADC连接状态"""
        self.adc_connected = connected

    def add_adc_sample(self, sample_data):
        """添加ADC采样数据，自动管理内存"""
        # 如果超过最大内存限制，移除最早的样本
        if len(self.adc_samples) >= self.max_samples_in_memory:
            oldest_sample = self.adc_samples.pop(0)
            self._release_sample_memory(oldest_sample)
        
        # 添加新样本
        self.adc_samples.append(sample_data)
        
        # 更新内存使用统计
        self._update_memory_usage()
        
        # 如果是numpy数组，确保使用高效的数据类型
        if isinstance(sample_data, np.ndarray):
            # 如果数据很大，考虑使用更小的数据类型
            if sample_data.nbytes > 1024 * 1024:  # 大于1MB
                sample_data = sample_data.astype(np.float32)  # 使用单精度浮点数
    
    def _release_sample_memory(self, sample):
        """释放单个样本的内存"""
        if hasattr(sample, 'shape'):
            del sample
        elif isinstance(sample, list):
            sample.clear()
        elif hasattr(sample, 'close'):
            sample.close()
    
    def _update_memory_usage(self):
        """更新内存使用统计"""
        total_memory = 0
        for sample in self.adc_samples:
            if hasattr(sample, 'nbytes'):
                total_memory += sample.nbytes
            elif isinstance(sample, list):
                total_memory += len(sample) * 4  # 假设每个整数4字节
        self.memory_usage = total_memory
    
    def clear_adc_samples(self):
        """清除ADC采样数据，彻底释放内存"""
        for sample in self.adc_samples:
            self._release_sample_memory(sample)
        
        self.adc_samples.clear()
        self.memory_usage = 0
        
        # 强制垃圾回收
        gc.collect()
    
    def get_memory_info(self):
        """获取内存使用信息"""
        return {
            'samples_count': len(self.adc_samples),
            'memory_usage_bytes': self.memory_usage,
            'memory_usage_mb': self.memory_usage / (1024 * 1024),
            'max_samples': self.max_samples_in_memory
        }
