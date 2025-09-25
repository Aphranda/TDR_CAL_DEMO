# src/app/threads/ADCSampleWorker.py
import os
import time
from matplotlib.pylab import f
import numpy as np
from PyQt5.QtCore import QObject, pyqtSignal, QThread,pyqtSlot
from app.core.ADCSample import ADCSample
from app.core.FileManager import FileManager
from .DataSaverWorker import DataSaverWorker

class ADCSampleWorker(QObject):
    """ADC采样工作线程 - 使用异步保存优化性能"""
    progress = pyqtSignal(int, int, str)
    finished = pyqtSignal(bool, str)
    sampleData = pyqtSignal(dict)  # 发送字典，包含两个ADC的数据
    dataSaved = pyqtSignal(str, str)
    saveError = pyqtSignal(str)
    
    def __init__(self, tcp_client, count, interval, save_raw_data=True, output_dir=None, filename_prefix=None,sample_number = 10):
        super().__init__()
        self.adc_sample = ADCSample()
        self.adc_sample.set_tcp_client(tcp_client)
        self.count = count
        self.interval = interval
        self.save_raw_data = save_raw_data
        self.output_dir = output_dir or 'data\\results\\test'
        self.filename_prefix = filename_prefix or 'adc_raw_data'
        self.sample_number = sample_number  # 新增：保存单次采样数量
        self.running = False
        self._should_stop = False
        
        # 创建异步保存线程
        self.saver_thread = QThread()
        self.data_saver = DataSaverWorker(max_queue_size=5)  # 限制队列大小防止内存占用过高
        self.data_saver.moveToThread(self.saver_thread)
        
        # 连接信号槽
        self.data_saver.dataSaved.connect(self.dataSaved)
        self.data_saver.errorOccurred.connect(self.saveError)
        self.saver_thread.started.connect(self.data_saver.run)
        self.data_saver.finished.connect(self.saver_thread.quit)
        self.data_saver.finished.connect(self.data_saver.deleteLater)
        self.saver_thread.finished.connect(self.saver_thread.deleteLater)
    
    def _initialize_sampling(self):
        """初始化采样环境"""
        self.running = True
        self._should_stop = False
        
        # 启动保存线程
        self.saver_thread.start()
        
        # 确保输出目录存在
        if self.save_raw_data:
            self.data_saver.file_manager.ensure_dir_exists(self.output_dir)
        
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
            processed_data, error = self.adc_sample.perform_single_test(sample_index,self.sample_number)
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
    
    def _async_save_sample_data(self, sample_data, sample_index):
        """异步保存采样数据"""
        if not self.save_raw_data:
            return True
        
        try:
            # 复制数据以避免在异步保存过程中被修改
            data_copy = {}
            for adc_name, data in sample_data.items():
                data_copy[adc_name] = data.copy()
            
            # 添加到保存队列
            self.data_saver.add_save_task(
                data_copy, sample_index, self.output_dir, self.filename_prefix
            )
            return True
        except Exception as e:
            self.saveError.emit(f"添加到保存队列失败: {str(e)}")
            return False
    
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
                
                # 异步保存原始数据
                if self.save_raw_data:
                    self._async_save_sample_data(sample_data, sample_index)
                
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
            # 停止保存线程
            if hasattr(self, 'data_saver') and self.data_saver:
                self.data_saver.stop()
            
            if hasattr(self, 'saver_thread') and self.saver_thread.isRunning():
                self.saver_thread.quit()
                self.saver_thread.wait(5000)  # 等待5秒
            
            if hasattr(self, 'adc_sample') and self.adc_sample:
                if hasattr(self.adc_sample, 'file_manager'):
                    self.adc_sample.file_manager = None
                if hasattr(self.adc_sample, 'tcp_client'):
                    self.adc_sample.tcp_client = None
                self.adc_sample = None
            
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
        self.cleanup_resources()