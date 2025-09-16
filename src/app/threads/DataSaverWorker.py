# src/app/threads/ADCSampleWorker.py
import os
from PyQt5.QtCore import QObject, pyqtSignal, pyqtSlot, QThread, QMutex, QWaitCondition
from app.core.FileManager import FileManager
from memory_profiler import profile
class DataSaverWorker(QObject):
    """异步数据保存工作线程"""
    finished = pyqtSignal()
    dataSaved = pyqtSignal(str, str)
    errorOccurred = pyqtSignal(str)
    
    def __init__(self, max_queue_size=10):
        super().__init__()
        self.file_manager = FileManager()
        self.save_queue = []
        self.mutex = QMutex()
        self.condition = QWaitCondition()
        self.running = False
        self.max_queue_size = max_queue_size
    
    @pyqtSlot()
    def run(self):
        """运行保存线程"""
        self.running = True
        while self.running or self.save_queue:
            self.mutex.lock()
            if not self.save_queue:
                self.condition.wait(self.mutex)
            
            if self.save_queue:
                # 获取保存任务
                data_dict, sample_index, output_dir, filename_prefix = self.save_queue.pop(0)
                self.mutex.unlock()
                
                # 执行保存
                try:
                    self._save_data(data_dict, sample_index, output_dir, filename_prefix)
                except Exception as e:
                    self.errorOccurred.emit(f"保存数据失败: {str(e)}")
            else:
                self.mutex.unlock()
        
        self.finished.emit()
    
    def add_save_task(self, data_dict, sample_index, output_dir, filename_prefix):
        """添加保存任务到队列"""
        self.mutex.lock()
        
        # 如果队列已满，等待空间
        while len(self.save_queue) >= self.max_queue_size:
            self.condition.wait(self.mutex)
        
        self.save_queue.append((data_dict, sample_index, output_dir, filename_prefix))
        self.condition.wakeAll()
        self.mutex.unlock()
    
    def _save_data(self, data_dict, sample_index, output_dir, filename_prefix):
        """执行数据保存"""
        filename_prefix = f'{filename_prefix}_{sample_index + 1:04d}'
        
        # 确保输出目录存在
        self.file_manager.ensure_dir_exists(output_dir)
        
        # 保存每个ADC的数据
        for adc_name, data in data_dict.items():
            if data is not None and len(data) > 0:
                filename = f'{filename_prefix}_{adc_name}.bin'
                filepath = os.path.join(output_dir, filename)
                
                try:
                    # 保存为二进制文件
                    data.tofile(filepath)
                    self.dataSaved.emit(filepath, f"数据已保存: {filename}")
                except Exception as e:
                    self.errorOccurred.emit(f"保存文件 {filename} 失败: {str(e)}")
    
    def stop(self):
        """停止保存线程"""
        self.running = False
        self.condition.wakeAll()