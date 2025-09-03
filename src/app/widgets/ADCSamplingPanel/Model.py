# src/app/widgets/ADCSamplingPanel/Model.py
import gc
import numpy as np
from collections import deque

class ADCSamplingModel:
    def __init__(self):
        self.adc_connected = False
        self.adc_samples = deque(maxlen=50)  # 使用双端队列，自动限制大小
        self.sample_references = []
        self.adc_ip = "192.168.1.10"
        self.adc_port = 15000
        self.sample_count = 10
        self.sample_interval = 0.1
        self.output_dir = "data\\results\\test"
        self.filename_prefix = "adc_data"
        self.save_raw_data = True
        self.max_samples_in_memory = 50
        
        # 内存监控
        self.memory_usage = 0

    def set_adc_connection_status(self, connected: bool):
        self.adc_connected = connected

    def add_adc_sample(self, sample_data):
        """添加ADC采样数据，使用内存友好的方式"""
        # 如果数据很大，使用更高效的数据类型
        if isinstance(sample_data, np.ndarray) and sample_data.nbytes > 1024 * 1024:
            sample_data = self._optimize_array_memory(sample_data)
        
        # 添加到队列（自动管理大小）
        self.adc_samples.append(sample_data)
        
        # 更新内存使用
        self._update_memory_usage()

    def _optimize_array_memory(self, array):
        """优化数组内存使用"""
        if array.dtype == np.uint32 and np.max(array) < 65536:
            return array.astype(np.uint16)
        elif array.dtype == np.float64:
            return array.astype(np.float32)
        return array

    def _update_memory_usage(self):
        """更新内存使用统计"""
        total_memory = 0
        for sample in self.adc_samples:
            if hasattr(sample, 'nbytes'):
                total_memory += sample.nbytes
            elif isinstance(sample, list):
                total_memory += len(sample) * 4
        self.memory_usage = total_memory

    def get_samples_generator(self):
        """返回样本数据的生成器"""
        for sample in self.adc_samples:
            yield sample

    def get_recent_samples(self, count=10):
        """获取最近的样本（生成器方式）"""
        for i in range(max(0, len(self.adc_samples) - count), len(self.adc_samples)):
            yield self.adc_samples[i]

    def clear_adc_samples(self):
        """清除ADC采样数据"""
        for sample in self.adc_samples:
            self._release_sample_memory(sample)
        
        self.adc_samples.clear()
        self.memory_usage = 0
        gc.collect()

    def _release_sample_memory(self, sample):
        """释放单个样本的内存"""
        if isinstance(sample, np.ndarray):
            sample.setflags(write=True)
            sample.resize(0, refcheck=False)
        del sample

    def get_memory_info(self):
        return {
            'samples_count': len(self.adc_samples),
            'memory_usage_bytes': self.memory_usage,
            'memory_usage_mb': self.memory_usage / (1024 * 1024),
            'max_samples': self.max_samples_in_memory
        }
