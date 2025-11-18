# src/app/threads/ADCSampleWorker.py
import os
import time
import numpy as np
import logging
from PyQt5.QtCore import QObject, pyqtSignal, QThread, pyqtSlot
from app.core.ADCSample import ADCSample
from app.core.FileManager import FileManager
from app.core.ConfigManager import ADCMode
from .DataSaverWorker import DataSaverWorker

logger = logging.getLogger(__name__)

class ADCSampleWorker(QObject):
    """ADC采样工作线程 - 支持双进度条（采样进度和保存进度）和日志信号"""
    
    # 采样进度信号
    samplingProgress = pyqtSignal(int, int, str)  # (current, total, message)
    # 保存进度信号
    savingProgress = pyqtSignal(int, int, str)    # (current, total, message)
    finished = pyqtSignal(bool, str)
    sampleData = pyqtSignal(dict)  # 发送字典，包含ADC数据
    dataSaved = pyqtSignal(str, str)
    saveError = pyqtSignal(str)
    # 新增：日志信号
    log_message = pyqtSignal(str, str)  # (message, level)
    
    def __init__(self, tcp_client, count, interval, save_raw_data=True, 
                 output_dir=None, filename_prefix=None, sample_number=10, 
                 adc_mode=ADCMode.ADC1_ONLY, data_type="uint32"):
        super().__init__()
        self.adc_sample = ADCSample()
        self.adc_sample.set_tcp_client(tcp_client)
        self.adc_sample.set_adc_mode(adc_mode)  # 设置ADC模式
        self.adc_sample.set_data_type(data_type)  # 设置数据类型
        self.count = count
        self.interval = interval
        self.save_raw_data = save_raw_data
        self.output_dir = output_dir or 'data\\results\\test'
        self.filename_prefix = filename_prefix or 'adc_raw_data'
        self.sample_number = sample_number
        self.adc_mode = adc_mode
        self.data_type = data_type  # 保存数据类型
        self.running = False
        self._should_stop = False
        
        # 根据ADC模式计算保存任务数量
        if adc_mode == ADCMode.BOTH_ADCS:
            self.save_tasks_total = count * 2  # 需要保存ADC1和ADC2的数据
        else:
            self.save_tasks_total = count  # 只保存一个ADC的数据
        
        self.save_tasks_completed = 0
        
        # 创建异步保存线程
        self.saver_thread = QThread()
        self.data_saver = DataSaverWorker(max_queue_size=5)
        self.data_saver.moveToThread(self.saver_thread)
        
        # 连接信号槽
        self.data_saver.dataSaved.connect(self._on_data_saved)
        self.data_saver.errorOccurred.connect(self.saveError)
        self.saver_thread.started.connect(self.data_saver.run)
        self.data_saver.finished.connect(self.saver_thread.quit)
        self.data_saver.finished.connect(self.data_saver.deleteLater)
        self.saver_thread.finished.connect(self.saver_thread.deleteLater)
        self.data_saver.log_message.connect(self.log_message)
    
    def _on_data_saved(self, filepath, message):
        """处理数据保存完成事件"""
        self.save_tasks_completed += 1
        # 发射保存进度信号
        self.savingProgress.emit(
            self.save_tasks_completed, 
            self.save_tasks_total, 
            f"已保存 {self.save_tasks_completed}/{self.save_tasks_total} 个文件"
        )
        self.dataSaved.emit(filepath, message)
    
    def _initialize_sampling(self):
        """初始化采样环境"""
        self.running = True
        self._should_stop = False
        self.save_tasks_completed = 0
        
        # 启动保存线程
        self.saver_thread.start()
        
        # 确保输出目录存在
        if self.save_raw_data:
            self.data_saver.file_manager.ensure_dir_exists(self.output_dir)
        
        # 初始化保存进度条
        self.savingProgress.emit(0, self.save_tasks_total, "等待数据保存...")
        
        self.log_message.emit(f"ADC采样模式: {self.adc_mode.value}, 总保存任务: {self.save_tasks_total}", "INFO")
        
        return True
    
    def _create_sample_generator(self):
        """创建采样数据生成器"""
        for i in range(self.count):
            if not self.running or self._should_stop:
                break
            
            # 发射采样进度信号
            self.samplingProgress.emit(i + 1, self.count, f"采样 {i + 1}/{self.count}")
            
            # 执行单次采样
            processed_data, error = self._perform_single_sample(i)
            if error:
                self.log_message.emit(f"采样失败: {error}", "WARNING")
                self.samplingProgress.emit(i + 1, self.count, f"采样失败: {error}")
                continue
            
            yield processed_data, i
            
            # 等待间隔
            if self.interval > 0:
                time.sleep(self.interval)

    def _perform_single_sample(self, sample_index):
        """执行单次采样操作"""
        try:
            self.log_message.emit(f"开始第 {sample_index + 1} 次采样，采样点数: {self.sample_number}", "DEBUG")
            processed_data, error = self.adc_sample.perform_single_test(sample_index, self.sample_number)
            
            if error:
                self.log_message.emit(f"第 {sample_index + 1} 次采样失败: {error}", "ERROR")
            else:
                self.log_message.emit(f"第 {sample_index + 1} 次采样完成", "INFO")
                
            return processed_data, error
        except Exception as e:
            error_msg = f"第 {sample_index + 1} 次采样过程中发生异常: {str(e)}"
            self.log_message.emit(error_msg, "ERROR")
            logger.error(error_msg)
            return None, f"采样异常: {str(e)}"
    
    def _process_sample_data(self, data_dict):
        """处理采样数据，优化内存使用"""
        processed_dict = {}
        
        for adc_name, u32_values in data_dict.items():
            # 根据ADC模式过滤不需要的数据
            if (adc_name == 'adc1' and self.adc_mode not in [ADCMode.ADC1_ONLY, ADCMode.BOTH_ADCS]) or \
               (adc_name == 'adc2' and self.adc_mode not in [ADCMode.ADC2_ONLY, ADCMode.BOTH_ADCS]):
                continue
                
            if u32_values is None or len(u32_values) == 0:
                processed_dict[adc_name] = np.array([], dtype=np.uint16)
                self.log_message.emit(f"通道 {adc_name} 数据为空", "WARNING")
                continue
            
            # 使用更高效的数据类型
            if np.max(u32_values) < 65536:
                processed_dict[adc_name] = np.array(u32_values, dtype=np.uint16)
            else:
                processed_dict[adc_name] = np.array(u32_values, dtype=np.uint32)
            
            self.log_message.emit(f"通道 {adc_name} 数据处理完成，数据点数量: {len(u32_values)}", "DEBUG")
        
        return processed_dict
    
    def _async_save_sample_data(self, sample_data, sample_index):
        """异步保存采样数据 - 传递数据类型"""
        if not self.save_raw_data:
            return True
        
        try:
            # 复制数据以避免在异步保存过程中被修改
            data_copy = {}
            for adc_name, data in sample_data.items():
                # 根据ADC模式过滤不需要保存的数据
                if (adc_name == 'adc1' and self.adc_mode not in [ADCMode.ADC1_ONLY, ADCMode.BOTH_ADCS]) or \
                (adc_name == 'adc2' and self.adc_mode not in [ADCMode.ADC2_ONLY, ADCMode.BOTH_ADCS]):
                    continue
                data_copy[adc_name] = data.copy()
            
            # 添加到保存队列，传递数据类型
            success = self.data_saver.add_save_task(
                data_copy, sample_index, self.output_dir, self.filename_prefix, self.data_type  # 传递data_type
            )
            
            if success:
                self.log_message.emit(f"第 {sample_index + 1} 次采样数据已加入保存队列", "DEBUG")
            else:
                self.log_message.emit(f"第 {sample_index + 1} 次采样数据加入保存队列失败", "WARNING")
                
            return success
        except Exception as e:
            error_msg = f"添加到保存队列失败: {str(e)}"
            logger.error(error_msg)
            self.log_message.emit(error_msg, "ERROR")
            self.saveError.emit(error_msg)
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
        # 等待所有保存任务完成
        if self.save_raw_data and self.data_saver:
            self._wait_for_save_completion()
        
        success = successful_samples > 0
        message = f"完成 {successful_samples}/{self.count} 次采样，保存 {self.save_tasks_completed} 个文件"
        
        if success:
            self.log_message.emit(message, "INFO")
        else:
            self.log_message.emit(message, "WARNING")
            
        self.finished.emit(success, message)
    
    def _wait_for_save_completion(self):
        """等待所有保存任务完成"""
        max_wait_time = 30  # 最大等待时间30秒
        wait_interval = 0.5  # 检查间隔0.5秒
        total_waited = 0
        
        # 检查DataSaverWorker是否有has_pending_tasks方法
        if not hasattr(self.data_saver, 'has_pending_tasks'):
            self.log_message.emit("DataSaverWorker没有has_pending_tasks方法，跳过等待", "WARNING")
            return
        
        while (self.data_saver.has_pending_tasks() and 
               total_waited < max_wait_time and 
               self.running and not self._should_stop):
            time.sleep(wait_interval)
            total_waited += wait_interval
            
            # 更新保存进度
            pending = self.data_saver.get_pending_task_count()
            completed = self.save_tasks_completed
            total = completed + pending
            
            self.savingProgress.emit(
                completed, 
                total, 
                f"等待保存完成... ({pending}个任务待处理)"
            )
            
            if total_waited % 5 == 0:  # 每5秒记录一次等待状态
                self.log_message.emit(f"等待保存任务完成... 已等待 {total_waited} 秒，剩余 {pending} 个任务", "INFO")
    
    @pyqtSlot()
    def run(self):
        """执行ADC采样 - 主运行函数"""
        # 初始化
        if not self._initialize_sampling():
            self.log_message.emit("ADC采样初始化失败", "ERROR")
            self.finished.emit(False, "初始化失败")
            return
        
        successful_samples = 0
        
        try:
            self.log_message.emit("开始ADC采样流程", "INFO")
            
            # 使用生成器逐次处理数据
            sample_gen = self._create_sample_generator()
            
            for sample_data, sample_index in sample_gen:
                successful_samples += 1
                
                # 发送ADC数据字典
                self.sampleData.emit(sample_data)
                
                # 异步保存原始数据
                if self.save_raw_data:
                    self._async_save_sample_data(sample_data, sample_index)
                
                # 清理当前采样数据
                self._cleanup_sample_resources(sample_data)
            
            # 完成采样
            self._finalize_sampling(successful_samples)
            
        except Exception as e:
            error_msg = f"采样过程中发生错误: {str(e)}"
            self.log_message.emit(error_msg, "ERROR")
            logger.error(error_msg)
            self.finished.emit(False, error_msg)
        finally:
            self.cleanup_resources()
    
    def cleanup_resources(self):
        """清理工作线程资源"""
        try:
            self.log_message.emit("开始清理工作线程资源", "INFO")
            
            # 停止保存线程
            if hasattr(self, 'data_saver') and self.data_saver:
                self.data_saver.stop()
                self.log_message.emit("DataSaverWorker已停止", "DEBUG")
            
            if hasattr(self, 'saver_thread') and self.saver_thread.isRunning():
                self.saver_thread.quit()
                self.saver_thread.wait(5000)  # 等待5秒
                self.log_message.emit("保存线程已停止", "DEBUG")
            
            if hasattr(self, 'adc_sample') and self.adc_sample:
                if hasattr(self.adc_sample, 'file_manager'):
                    self.adc_sample.file_manager = None
                if hasattr(self.adc_sample, 'tcp_client'):
                    self.adc_sample.tcp_client = None
                self.adc_sample = None
                self.log_message.emit("ADC采样实例已清理", "DEBUG")
            
            self.running = False
            self._should_stop = False
            
            import gc
            gc.collect()
            gc.collect()
            
            self.log_message.emit("工作线程资源清理完成", "INFO")
            
        except Exception as e:
            error_msg = f"清理工作线程资源失败: {e}"
            self.log_message.emit(error_msg, "ERROR")
            logger.error(error_msg)
    
    def stop(self):
        """停止采样"""
        self.log_message.emit("停止ADC采样工作线程...", "INFO")
        self.running = False
        self._should_stop = True
        self.cleanup_resources()
