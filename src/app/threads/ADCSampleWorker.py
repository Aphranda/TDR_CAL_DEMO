# src/app/threads/ADCSampleWorker.py
import os
import time
import numpy as np
from PyQt5.QtCore import QObject, pyqtSignal, pyqtSlot
from app.core.ADCSample import ADCSample
from app.core.FileManager import FileManager
from memory_profiler import profile

class ADCSampleWorker(QObject):
    """ADC采样工作线程 - 使用生成器优化内存"""
    progress = pyqtSignal(int, int, str)
    finished = pyqtSignal(bool, str)
    sampleData = pyqtSignal(dict)  # 发送字典，包含两个ADC的数据
    dataSaved = pyqtSignal(str, str)
    
    def __init__(self, tcp_client, count, interval, save_raw_data=True, output_dir=None, filename_prefix=None):
        super().__init__()
        self.adc_sample = ADCSample()
        self.file_manager = FileManager()
        self.adc_sample.set_tcp_client(tcp_client)
        self.count = count
        self.interval = interval
        self.save_raw_data = save_raw_data
        self.output_dir = output_dir or 'data\\results\\test'
        self.filename_prefix = filename_prefix or 'adc_raw_data'
        self.running = False
        self._should_stop = False
    
    def _initialize_sampling(self):
        """初始化采样环境"""
        self.running = True
        self._should_stop = False
        
        # 确保输出目录存在
        if self.save_raw_data:
            self.file_manager.ensure_dir_exists(self.output_dir)
        
        return True
    
    def _create_sample_generator(self):
        """创建采样数据生成器"""
        for i in range(self.count):
            if not self.running or self._should_stop:
                break
            
            self.progress.emit(i + 1, self.count, f"采样 {i + 1}/{self.count}")
            
            # 执行单次采样
            processed_data, error = self._perform_single_sample(i)
            if error:
                self.progress.emit(i + 1, self.count, f"采样失败: {error}")
                continue
            
            yield processed_data, i
            
            # 等待间隔
            time.sleep(self.interval)
    
    def _perform_single_sample(self, sample_index):
        """执行单次采样操作"""
        try:
            # ADCSample.perform_single_test 返回 (processed_data, error)
            processed_data, error = self.adc_sample.perform_single_test(sample_index)
            return processed_data, error
        except Exception as e:
            return None, f"采样异常: {str(e)}"
    
    def _process_sample_data(self, data_dict):
        """处理采样数据，优化内存使用"""
        processed_dict = {}
        
        for adc_name, u32_values in data_dict.items():
            if u32_values is None or len(u32_values) == 0:
                processed_dict[adc_name] = np.array([], dtype=np.uint16)
                continue
            
            # 使用更高效的数据类型
            if np.max(u32_values) < 65536:
                processed_dict[adc_name] = np.array(u32_values, dtype=np.uint16)
            else:
                processed_dict[adc_name] = np.array(u32_values, dtype=np.uint32)
        
        return processed_dict
    
    def _save_sample_data(self, sample_data, sample_index):
        """保存采样数据"""
        filename_prefix = f'{self.filename_prefix}_{sample_index + 1:04d}'
        success, message = self.adc_sample.save_test_result(
            sample_index, sample_data, filename_prefix, self.output_dir
        )
        
        if success:
            # 发送两个ADC文件的保存消息
            for adc_name in sample_data.keys():
                filename = f'{filename_prefix}_{adc_name}.bin'  # 修改为.bin文件
                self.dataSaved.emit(os.path.join(self.output_dir, filename), 
                                   f"数据已保存: {filename}")
        else:
            self.progress.emit(sample_index + 1, self.count, 
                              f"数据保存失败: {message}")
        
        return success
    
    def _force_release_memory(self, obj):
        """强制释放对象内存"""
        if obj is None:
            return
        
        if isinstance(obj, dict):
            for key, value in obj.items():
                self._force_release_memory(value)
            obj.clear()
        elif isinstance(obj, np.ndarray):
            obj.setflags(write=True)
            obj.resize(0, refcheck=False)
        elif hasattr(obj, 'clear'):
            obj.clear()
        
        del obj
    
    def _cleanup_sample_resources(self, data_dict):
        """清理采样过程中的资源"""
        self._force_release_memory(data_dict)
    
    def _finalize_sampling(self, successful_samples):
        """完成采样过程"""
        success = successful_samples > 0
        message = f"完成 {successful_samples}/{self.count} 次采样"
        self.finished.emit(success, message)
    
    @pyqtSlot()
    def run(self):
        """执行ADC采样 - 主运行函数"""
        # 初始化
        if not self._initialize_sampling():
            self.finished.emit(False, "初始化失败")
            return
        
        successful_samples = 0
        
        try:
            # 使用生成器逐次处理数据
            sample_gen = self._create_sample_generator()
            
            for sample_data, sample_index in sample_gen:
                successful_samples += 1
                
                # 发送双ADC数据字典
                self.sampleData.emit(sample_data)
                
                # 保存原始数据
                if self.save_raw_data:
                    self._save_sample_data(sample_data, sample_index)
                
                # 清理当前采样数据
                self._cleanup_sample_resources(sample_data)
            
            # 完成采样
            self._finalize_sampling(successful_samples)
            
        except Exception as e:
            self.finished.emit(False, f"采样过程中发生错误: {str(e)}")
        finally:
            self.cleanup_resources()
    
    def cleanup_resources(self):
        """清理工作线程资源"""
        try:
            if hasattr(self, 'adc_sample') and self.adc_sample:
                if hasattr(self.adc_sample, 'file_manager'):
                    self.adc_sample.file_manager = None
                if hasattr(self.adc_sample, 'tcp_client'):
                    self.adc_sample.tcp_client = None
                self.adc_sample = None
            
            if hasattr(self, 'file_manager'):
                self.file_manager = None
            
            self.running = False
            self._should_stop = False
            self.save_raw_data = None
            
            import gc
            gc.collect()
            gc.collect()
            
        except Exception as e:
            print(f"清理工作线程资源失败: {e}")
    
    def stop(self):
        """停止采样"""
        self.running = False
        self._should_stop = True
