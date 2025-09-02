# src/app/widgets/ADCSamplingPanel/Controller.py
import os
import time
import numpy as np
from PyQt5.QtWidgets import QFileDialog, QMessageBox
from PyQt5.QtCore import QObject, pyqtSignal, QThread, pyqtSlot
from ...core.ADCSample import ADCSample
from ...core.FileManager import FileManager
from ...core.ClockController import ClockController  # 导入时钟控制类
from memory_profiler import profile

class ADCWorker(QObject):
    """ADC采样工作线程"""
    progress = pyqtSignal(int, int, str)
    finished = pyqtSignal(bool, str)
    sampleData = pyqtSignal(list)
    dataSaved = pyqtSignal(str, str)  # 数据保存信号 (文件路径, 消息)
    
    def __init__(self, tcp_client, count, interval, save_raw_data=True, output_dir=None, filename_prefix=None):
        super().__init__()
        # 使用传入的tcp_client实例化ADCSample
        self.adc_sample = ADCSample()
        self.adc_sample.set_tcp_client(tcp_client)  # 设置TCP客户端
        self.count = count
        self.interval = interval
        self.save_raw_data = save_raw_data
        self.output_dir = output_dir or 'data\\results\\test'
        self.filename_prefix = filename_prefix or 'adc_raw_data'
        self.running = False
        self._should_stop = False


    @pyqtSlot()
    def run(self):
        """执行ADC采样"""
        self.running = True
        successful_samples = 0
        
        try:
            # 确保输出目录存在
            if self.save_raw_data:
                self.adc_sample.file_manager.ensure_dir_exists(self.output_dir)
            
            for i in range(self.count):
                if not self.running or self._should_stop:
                    break
                
                self.progress.emit(i + 1, self.count, f"采样 {i + 1}/{self.count}")
                
                # 执行单次采样 - 使用上下文管理器确保资源释放
                u32_values, error = None, None
                try:
                    u32_values, error = self.adc_sample.perform_single_test(i)
                    if error:
                        self.progress.emit(i + 1, self.count, f"采样失败: {error}")
                        continue
                    
                    successful_samples += 1
                    
                    # 处理采样数据 - 优化内存使用
                    sample_data = self._process_sample_data(u32_values)
                    
                    # 立即发送数据
                    self.sampleData.emit([sample_data])
                    
                    # 保存原始数据
                    if self.save_raw_data:
                        filename = f'{self.filename_prefix}_{i + 1:04d}.csv'
                        success, message = self.adc_sample.save_test_result(i, u32_values, filename, self.output_dir)
                        if success:
                            self.dataSaved.emit(os.path.join(self.output_dir, filename), f"数据已保存: {filename}")
                        else:
                            self.progress.emit(i + 1, self.count, f"数据保存失败: {message}")
                    
                finally:
                    # 强制释放采样数据内存
                    self._force_release_memory(u32_values)
                    u32_values = None
                    del u32_values
                
                # 等待间隔
                time.sleep(self.interval)
            
            success = successful_samples > 0
            message = f"完成 {successful_samples}/{self.count} 次采样"
            self.finished.emit(success, message)
            
        except Exception as e:
            self.finished.emit(False, f"采样过程中发生错误: {str(e)}")
        finally:
            # 彻底清理资源
            self.cleanup_resources()

    def _process_sample_data(self, u32_values):
        """处理采样数据，优化内存使用"""
        if u32_values is None:
            return []
        
        # 如果是numpy数组，转换为更小的数据类型
        if isinstance(u32_values, np.ndarray):
            # 根据数据范围选择合适的数据类型
            if np.max(u32_values) < 65536:  # 如果数据在uint16范围内
                return u32_values.astype(np.uint16)
            else:
                return u32_values.astype(np.uint32)
        elif isinstance(u32_values, tuple):
            return list(u32_values)
        else:
            try:
                return u32_values.copy()
            except AttributeError:
                return u32_values

    def _force_release_memory(self, obj):
        """强制释放对象内存"""
        if obj is None:
            return
        
        # 对于numpy数组，使用特殊方法释放内存
        if isinstance(obj, np.ndarray):
            # 设置数组为None并调用gc
            obj.setflags(write=True)
            obj.resize(0, refcheck=False)
        elif hasattr(obj, 'clear'):
            obj.clear()
        
        # 删除引用
        del obj

    
    def cleanup_resources(self):
        """清理工作线程资源"""
        try:
            # 清理ADCSample实例
            if hasattr(self, 'adc_sample') and self.adc_sample:
                if hasattr(self.adc_sample, 'file_manager'):
                    self.adc_sample.file_manager = None
                if hasattr(self.adc_sample, 'tcp_client'):
                    self.adc_sample.tcp_client = None
                self.adc_sample = None
            
            # 清理其他引用
            self.running = False
            self._should_stop = False
            
            # 强制垃圾回收
            import gc
            gc.collect()
            
        except Exception as e:
            print(f"清理工作线程资源失败: {e}")
    
    def stop(self):
        """停止采样"""
        self.running = False
        self._should_stop = True




class ADCSamplingController(QObject):
    # 定义信号
    dataLoaded = pyqtSignal(str)  # 数据加载完成信号
    errorOccurred = pyqtSignal(str)  # 错误信号
    adcStatusChanged = pyqtSignal(bool, str)  # ADC连接状态变化信号
    samplingProgress = pyqtSignal(int, int, str)  # 采样进度信号
    dataSaved = pyqtSignal(str, str)  # 数据保存信号
    clockModeChanged = pyqtSignal(str, str)  # 时钟模式变化信号 (模式, 消息)
    
    def __init__(self, view, model):
        super().__init__()
        self.view = view
        self.model = model
        self.tcp_client = None  # 存储TCP客户端引用
        self.clock_controller = ClockController()  # 创建时钟控制器实例
        self.adc_worker = None
        self.adc_thread = None
        self.main_window_controller = None
        self.setup_connections()

    def setup_connections(self):
        """设置信号槽连接"""
        # 连接采样控制按钮
        self.view.sample_button.clicked.connect(self.on_sample_adc)
        self.view.browse_dir_button.clicked.connect(self.on_browse_directory)
        
        # 连接S参数模式单选按钮
        self.view.s11_radio.toggled.connect(lambda checked: self.on_s_mode_changed("S11", checked))
        self.view.s12_radio.toggled.connect(lambda checked: self.on_s_mode_changed("S12", checked))
        self.view.s21_radio.toggled.connect(lambda checked: self.on_s_mode_changed("S21", checked))
        self.view.s22_radio.toggled.connect(lambda checked: self.on_s_mode_changed("S22", checked))
        
        # 连接状态信号
        self.adcStatusChanged.connect(self.view.update_adc_connection_status)
        self.samplingProgress.connect(self.view.update_sampling_progress)
        self.clockModeChanged.connect(self.on_clock_mode_changed)
        
        # 错误和日志信号
        self.errorOccurred.connect(lambda msg: self.log_message(msg, "ERROR"))
        self.dataSaved.connect(lambda path, msg: self.log_message(f"{msg}: {path}", "INFO"))
        self.dataLoaded.connect(lambda msg: self.log_message(msg, "INFO"))

    def set_instrument_connected(self, connected, instrument_controller):
        """设置仪器连接状态，由主窗口调用"""
        if connected and instrument_controller and instrument_controller.tcp_client:
            # 保存TCP客户端引用，供ADCWorker和时钟控制器使用
            self.tcp_client = instrument_controller.tcp_client
            self.clock_controller.set_tcp_client(self.tcp_client)
            self.model.set_adc_connection_status(True)
            self.adcStatusChanged.emit(True, "使用主窗口仪表连接")
            self.log_message("ADC采样使用主窗口仪表连接", "INFO")
            
            # 默认设置S11模式
            self.set_s_mode("S11")
        else:
            self.tcp_client = None
            self.clock_controller.set_tcp_client(None)
            self.model.set_adc_connection_status(False)
            self.adcStatusChanged.emit(False, "仪表未连接")
            self.log_message("仪表未连接，无法进行ADC采样", "WARNING")

    def on_s_mode_changed(self, mode: str, checked: bool):
        """S参数模式切换事件"""
        if checked and self.tcp_client and self.tcp_client.connected:
            self.set_s_mode(mode)

    def set_s_mode(self, mode: str):
        """设置S参数模式"""
        if not self.tcp_client or not self.tcp_client.connected:
            self.log_message(f"无法设置 {mode} 模式: 仪表未连接", "WARNING")
            return
        
        try:
            success, message = None, None
            
            # 根据模式调用相应的时钟控制方法
            if mode == "S11":
                success, message = self.clock_controller.set_s11_mode()
            elif mode == "S12":
                success, message = self.clock_controller.set_s12_mode()
            elif mode == "S21":
                success, message = self.clock_controller.set_s21_mode()
            elif mode == "S22":
                success, message = self.clock_controller.set_s22_mode()
            else:
                self.log_message(f"不支持的S参数模式: {mode}", "ERROR")
                return
            
            if success:
                self.clockModeChanged.emit(mode, message)
                self.log_message(message, "INFO")
                
            else:
                self.errorOccurred.emit(message)
                self.log_message(message, "ERROR")
                
        except Exception as e:
            error_msg = f"设置 {mode} 模式时发生错误: {str(e)}"
            self.errorOccurred.emit(error_msg)
            self.log_message(error_msg, "ERROR")

    def on_clock_mode_changed(self, mode: str, message: str):
        """时钟模式变化事件"""
        # 可以在这里添加额外的处理逻辑
        pass

    def log_message(self, message, level="INFO"):
        """记录消息到日志区域"""
        if hasattr(self, 'main_window_controller') and self.main_window_controller:
            self.main_window_controller.log_controller.log(message, level)
        else:
            # 如果没有设置主窗口控制器，直接打印到控制台
            print(f"[{level}] {message}")
    
    def on_sample_adc(self):
        """开始ADC采样"""
        if not self.model.adc_connected or not self.tcp_client:
            error_msg = "仪表未连接，请先连接仪表"
            self.errorOccurred.emit(error_msg)
            self.log_message(error_msg, "WARNING")
            return
        
        # 获取当前选中的S参数模式
        current_mode = self.view.get_selected_s_mode()
        
        
        # 获取采样参数
        count = self.view.sample_count_spin.value()
        interval = self.view.sample_interval_spin.value()
        save_raw_data = True
        output_dir = self.view.output_dir_edit.text() or 'data\\results\\test'
        filename_prefix = self.view.filename_edit.text() or 'adc_raw_data'
        
        # 更新模型
        self.model.sample_count = count
        self.model.sample_interval = interval
        self.model.save_raw_data = save_raw_data
        self.model.output_dir = output_dir
        self.model.filename_prefix = filename_prefix
        
        # 创建工作线程，传入TCP客户端
        self.adc_thread = QThread()
        self.adc_worker = ADCWorker(self.tcp_client, count, interval, save_raw_data, output_dir, filename_prefix)
        self.adc_worker.moveToThread(self.adc_thread)
        
        # 连接信号
        self.adc_thread.started.connect(self.adc_worker.run)
        self.adc_worker.progress.connect(self.samplingProgress)
        self.adc_worker.finished.connect(self.on_sampling_finished)
        self.adc_worker.finished.connect(self.adc_thread.quit)
        self.adc_worker.finished.connect(self.adc_worker.deleteLater)
        self.adc_thread.finished.connect(self.adc_thread.deleteLater)
        self.adc_worker.sampleData.connect(self.on_sample_data_received)
        self.adc_worker.dataSaved.connect(self.dataSaved)
        
        # 启动线程
        self.adc_thread.start()
        self.log_message(f"开始ADC采样，模式: {current_mode}, 次数: {count}, 间隔: {interval}s", "INFO")
    
    def on_sampling_finished(self, success, message):
        """采样完成"""
        if success:
            self.dataLoaded.emit(message)
            self.log_message(message, "INFO")
        else:
            self.errorOccurred.emit(message)
            self.log_message(message, "ERROR")
    
    def on_sample_data_received(self, sample_data):
        """接收到采样数据"""
        for data in sample_data:
            self.model.add_adc_sample(data)
        msg = f"接收到 {len(sample_data)} 组采样数据"
        self.dataLoaded.emit(msg)
        self.log_message(msg, "INFO")
    
    def on_browse_directory(self):
        """浏览选择输出目录"""
        directory = QFileDialog.getExistingDirectory(
            self.view, 
            "选择输出目录",
            self.view.output_dir_edit.text() or "."
        )
        if directory:
            self.view.output_dir_edit.setText(directory)
    
    def set_main_window_controller(self, main_window_controller):
        """设置主窗口控制器引用"""
        self.main_window_controller = main_window_controller
    
    def cleanup(self):
        """清理控制器资源"""
        try:
            # 停止采样线程
            if hasattr(self, 'adc_worker') and self.adc_worker:
                self.adc_worker.stop()
            
            # 清理时钟控制器
            if hasattr(self, 'clock_controller'):
                self.clock_controller.cleanup()
            
            # 清理其他资源
            self.tcp_client = None
            self.main_window_controller = None
            
            # 强制垃圾回收
            import gc
            gc.collect()
            
        except Exception as e:
            print(f"清理ADC采样控制器失败: {e}")
