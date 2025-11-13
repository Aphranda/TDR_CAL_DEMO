# src/app/threads/DataSaverWorker.py
import os
import time
import logging
from PyQt5.QtCore import QObject, pyqtSignal, pyqtSlot, QThread, QMutex, QWaitCondition
from app.core.FileManager import FileManager

logger = logging.getLogger(__name__)

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
        self.completed_tasks = 0
        self.total_tasks = 0
    
    def has_pending_tasks(self):
        """检查是否有待处理的任务"""
        self.mutex.lock()
        has_tasks = len(self.save_queue) > 0
        self.mutex.unlock()
        return has_tasks
    
    def get_pending_task_count(self):
        """获取待处理任务数量"""
        self.mutex.lock()
        count = len(self.save_queue)
        self.mutex.unlock()
        return count
    
    def get_completed_task_count(self):
        """获取已完成任务数量"""
        return self.completed_tasks
    
    def add_save_task(self, data_dict, sample_index, output_dir, filename_prefix):
        """添加保存任务到队列"""
        if not self.running:
            return False
        
        self.mutex.lock()
        
        try:
            # 如果队列已满，等待空间
            while len(self.save_queue) >= self.max_queue_size:
                self.condition.wait(self.mutex)
            
            task = {
                'data_dict': data_dict,
                'sample_index': sample_index,
                'output_dir': output_dir,
                'filename_prefix': filename_prefix,
                'timestamp': time.time()
            }
            
            self.save_queue.append(task)
            self.total_tasks += 1
            self.condition.wakeAll()
            
            logger.debug(f"添加保存任务到队列，当前队列大小: {len(self.save_queue)}")
            return True
            
        except Exception as e:
            logger.error(f"添加保存任务失败: {str(e)}")
            return False
        finally:
            self.mutex.unlock()
    
    @pyqtSlot()
    def run(self):
        """运行保存线程"""
        self.running = True
        logger.info("数据保存线程开始运行")
        
        while self.running or self.save_queue:
            self.mutex.lock()
            
            if not self.save_queue:
                # 如果没有任务，等待新任务
                self.condition.wait(self.mutex, 1000)  # 最多等待1秒
                self.mutex.unlock()
                continue
            
            # 获取保存任务
            task = self.save_queue.pop(0)
            self.mutex.unlock()
            
            # 执行保存
            try:
                success = self._save_data(
                    task['data_dict'], 
                    task['sample_index'], 
                    task['output_dir'], 
                    task['filename_prefix']
                )
                if success:
                    self.completed_tasks += 1
                    
            except Exception as e:
                error_msg = f"保存数据失败: {str(e)}"
                logger.error(error_msg)
                self.errorOccurred.emit(error_msg)
        
        logger.info("数据保存线程结束运行")
        self.finished.emit()
    
    def _save_data(self, data_dict, sample_index, output_dir, filename_prefix):
        """执行数据保存"""
        try:
            # 确保输出目录存在
            self.file_manager.ensure_dir_exists(output_dir)
            
            # 为每个样本创建单独的文件名
            current_filename_prefix = f'{filename_prefix}_{sample_index + 1:04d}'
            success_count = 0
            
            # 保存每个ADC的数据
            for adc_name, data in data_dict.items():
                if data is not None and len(data) > 0:
                    filename = f'{current_filename_prefix}_{adc_name}.bin'
                    filepath = os.path.join(output_dir, filename)
                    
                    try:
                        # 保存为二进制文件
                        if hasattr(data, 'tofile'):
                            # 如果是numpy数组
                            data.tofile(filepath)
                        else:
                            # 如果是其他类型，转换为numpy数组再保存
                            import numpy as np
                            np.array(data, dtype=np.uint32).tofile(filepath)
                        
                        file_size = os.path.getsize(filepath)
                        logger.debug(f"数据已保存: {filename} ({file_size} 字节)")
                        self.dataSaved.emit(filepath, f"数据已保存: {filename}")
                        success_count += 1
                        
                    except Exception as e:
                        error_msg = f"保存文件 {filename} 失败: {str(e)}"
                        logger.error(error_msg)
                        self.errorOccurred.emit(error_msg)
            
            return success_count > 0
            
        except Exception as e:
            error_msg = f"保存数据过程中发生错误: {str(e)}"
            logger.error(error_msg)
            self.errorOccurred.emit(error_msg)
            return False
    
    def stop(self):
        """停止保存线程"""
        logger.info("停止数据保存线程...")
        self.running = False
        self.condition.wakeAll()
    
    def clear_queue(self):
        """清空任务队列"""
        self.mutex.lock()
        self.save_queue.clear()
        self.mutex.unlock()
    
    def get_queue_info(self):
        """获取队列信息"""
        self.mutex.lock()
        info = {
            'queue_size': len(self.save_queue),
            'max_queue_size': self.max_queue_size,
            'completed_tasks': self.completed_tasks,
            'total_tasks': self.total_tasks,
            'running': self.running
        }
        self.mutex.unlock()
        return info
