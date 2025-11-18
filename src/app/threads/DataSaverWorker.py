# src/app/threads/DataSaverWorker.py
import os
import time
from PyQt5.QtCore import QObject, pyqtSignal, pyqtSlot, QThread, QMutex, QWaitCondition
from app.core.FileManager import FileManager

class DataSaverWorker(QObject):
    """异步数据保存工作线程 - 使用log_message信号"""
    
    finished = pyqtSignal()
    dataSaved = pyqtSignal(str, str)
    errorOccurred = pyqtSignal(str)
    # 新增：日志信号
    log_message = pyqtSignal(str, str)  # (message, level)
    
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
    
    def add_save_task(self, data_dict, sample_index, output_dir, filename_prefix, data_type="uint32"):
        """添加保存任务到队列 - 支持数据类型"""
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
                'data_type': data_type,  # 保存数据类型
                'timestamp': time.time()
            }
            
            self.save_queue.append(task)
            self.total_tasks += 1
            self.condition.wakeAll()
            
            self.log_message.emit(f"添加保存任务到队列，数据类型: {data_type}, 当前队列大小: {len(self.save_queue)}", "DEBUG")
            return True
            
        except Exception as e:
            error_msg = f"添加保存任务失败: {str(e)}"
            self.log_message.emit(error_msg, "ERROR")
            return False
        finally:
            self.mutex.unlock()

    @pyqtSlot()
    def run(self):
        """运行保存线程"""
        self.running = True
        self.log_message.emit("数据保存线程开始运行", "INFO")
        
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
                    task['filename_prefix'],
                    task.get('data_type', 'uint32')  # 传递数据类型，默认为uint32
                )
                if success:
                    self.completed_tasks += 1
                    self.log_message.emit(f"保存任务完成，已完成 {self.completed_tasks} 个任务", "DEBUG")
                    
            except Exception as e:
                error_msg = f"保存数据失败: {str(e)}"
                self.log_message.emit(error_msg, "ERROR")
                self.errorOccurred.emit(error_msg)
        
        self.log_message.emit("数据保存线程结束运行", "INFO")
        self.finished.emit()

    def _save_data(self, data_dict, sample_index, output_dir, filename_prefix, data_type="uint32"):
        """执行数据保存 - 支持数据类型标识"""
        try:
            # 确保输出目录存在
            self.file_manager.ensure_dir_exists(output_dir)
            
            # 为每个样本创建单独的文件名，包含数据类型标识
            current_filename_prefix = f'{filename_prefix}_{sample_index + 1:04d}_{data_type}'  # 在文件名中加入数据类型
            success_count = 0
            
            # 保存每个ADC的数据
            for adc_name, data in data_dict.items():
                if data is not None and len(data) > 0:
                    filename = f'{current_filename_prefix}_{adc_name}.bin'
                    filepath = os.path.join(output_dir, filename)
                    
                    try:
                        # 根据数据类型确定保存方式
                        if data_type == "uint32":
                            # uint32格式，直接保存
                            if hasattr(data, 'tofile'):
                                data.tofile(filepath)
                            else:
                                import numpy as np
                                np.array(data, dtype=np.uint32).tofile(filepath)
                        elif data_type == "float64":
                            # float64格式
                            import numpy as np
                            if hasattr(data, 'tofile'):
                                data.tofile(filepath)
                            else:
                                np.array(data, dtype=np.float64).tofile(filepath)
                        else:
                            error_msg = f"不支持的数据类型: {data_type}"
                            self.log_message.emit(error_msg, "ERROR")
                            self.errorOccurred.emit(error_msg)
                            continue
                        
                        file_size = os.path.getsize(filepath)
                        self.log_message.emit(f"数据已保存: {filename} ({file_size} 字节), 数据类型: {data_type}", "DEBUG")
                        self.dataSaved.emit(filepath, f"数据已保存: {filename} (类型: {data_type})")
                        success_count += 1
                        
                    except Exception as e:
                        error_msg = f"保存文件 {filename} 失败: {str(e)}"
                        self.log_message.emit(error_msg, "ERROR")
                        self.errorOccurred.emit(error_msg)
            
            if success_count > 0:
                self.log_message.emit(f"成功保存 {success_count} 个数据文件", "INFO")
                return True
            else:
                self.log_message.emit("没有成功保存任何数据文件", "WARNING")
                return False
            
        except Exception as e:
            error_msg = f"保存数据过程中发生错误: {str(e)}"
            self.log_message.emit(error_msg, "ERROR")
            self.errorOccurred.emit(error_msg)
            return False

    def stop(self):
        """停止保存线程"""
        self.log_message.emit("停止数据保存线程...", "INFO")
        self.running = False
        self.condition.wakeAll()
    
    def clear_queue(self):
        """清空任务队列"""
        self.mutex.lock()
        queue_size = len(self.save_queue)
        self.save_queue.clear()
        self.mutex.unlock()
        
        if queue_size > 0:
            self.log_message.emit(f"已清空任务队列，移除 {queue_size} 个待处理任务", "INFO")
    
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
