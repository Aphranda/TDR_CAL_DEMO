# src/app/widgets/ADCSamplingPanel/Controller.py
import os
import time
import numpy as np
from PyQt5.QtWidgets import QFileDialog, QMessageBox
from PyQt5.QtCore import QObject, pyqtSignal, QThread, pyqtSlot
from ...core.ADCSample import ADCSample
from ...core.FileManager import FileManager

class ADCWorker(QObject):
    """ADC采样工作线程"""
    progress = pyqtSignal(int, int, str)
    finished = pyqtSignal(bool, str)
    sampleData = pyqtSignal(list)
    dataSaved = pyqtSignal(str, str)  # 数据保存信号 (文件路径, 消息)
    
    def __init__(self, adc_sample, count, interval, save_raw_data=True, output_dir=None, filename_prefix=None):
        super().__init__()
        self.adc_sample = adc_sample
        self.count = count
        self.interval = interval
        self.save_raw_data = save_raw_data
        self.output_dir = output_dir or 'data\\results\\test'
        self.filename_prefix = filename_prefix or 'adc_raw_data'
        self.running = False
    
    @pyqtSlot()
    def run(self):
        """执行ADC采样"""
        self.running = True
        successful_samples = 0
        all_samples = []
        
        try:
            # 确保输出目录存在
            if self.save_raw_data:
                self.adc_sample.file_manager.ensure_dir_exists(self.output_dir)
            
            for i in range(self.count):
                if not self.running:
                    break
                
                self.progress.emit(i + 1, self.count, f"采样 {i + 1}/{self.count}")
                
                # 执行单次采样
                u32_values, error = self.adc_sample.perform_single_test(i)
                if error:
                    self.progress.emit(i + 1, self.count, f"采样失败: {error}")
                    continue
                
                successful_samples += 1
                all_samples.append(u32_values)
                
                # 保存原始数据
                if self.save_raw_data:
                    filename = f'{self.filename_prefix}_{i + 1:04d}.csv'
                    success, message = self.adc_sample.save_test_result(i, u32_values, filename, self.output_dir)
                    if success:
                        self.dataSaved.emit(os.path.join(self.output_dir, filename), f"数据已保存: {filename}")
                    else:
                        self.progress.emit(i + 1, self.count, f"数据保存失败: {message}")
                
                # 等待间隔
                time.sleep(self.interval)
            
            success = successful_samples > 0
            message = f"完成 {successful_samples}/{self.count} 次采样"
            self.sampleData.emit(all_samples)
            self.finished.emit(success, message)
            
        except Exception as e:
            self.finished.emit(False, f"采样过程中发生错误: {str(e)}")
    
    def stop(self):
        """停止采样"""
        self.running = False


class ADCSamplingController(QObject):
    # 定义信号
    dataLoaded = pyqtSignal(str)  # 数据加载完成信号
    errorOccurred = pyqtSignal(str)  # 错误信号
    adcStatusChanged = pyqtSignal(bool, str)  # ADC连接状态变化信号
    samplingProgress = pyqtSignal(int, int, str)  # 采样进度信号
    dataSaved = pyqtSignal(str, str)  # 数据保存信号
    
    def __init__(self, view, model):
        super().__init__()
        self.view = view
        self.model = model
        self.adc_sample = ADCSample()
        self.adc_worker = None
        self.adc_thread = None
        self.setup_connections()

    def setup_connections(self):
        """设置信号槽连接"""
        # ADC连接按钮
        self.view.connect_button.clicked.connect(self.on_connect_adc)
        self.view.disconnect_button.clicked.connect(self.on_disconnect_adc)
        self.view.sample_button.clicked.connect(self.on_sample_adc)
        self.view.browse_dir_button.clicked.connect(self.on_browse_directory)
        
        # 连接状态信号
        self.adcStatusChanged.connect(self.view.update_adc_connection_status)
        self.samplingProgress.connect(self.view.update_sampling_progress)
        
        # 错误和日志信号
        self.errorOccurred.connect(lambda msg: self.log_message(msg, "ERROR"))
        self.dataSaved.connect(lambda path, msg: self.log_message(f"{msg}: {path}", "INFO"))
        self.dataLoaded.connect(lambda msg: self.log_message(msg, "INFO"))

    def log_message(self, message, level="INFO"):
        """记录消息到日志区域"""
        if hasattr(self, 'main_window_controller') and self.main_window_controller:
            self.main_window_controller.log_controller.log(message, level)
    
    def on_connect_adc(self):
        """连接ADC"""
        try:
            ip = self.view.adc_ip_edit.text()
            port_text = self.view.adc_port_edit.text()
            try:
                port = int(port_text)
            except ValueError:
                self.errorOccurred.emit("端口号必须是有效的数字")
                return
            
            # 更新模型
            self.model.adc_ip = ip
            self.model.adc_port = port
            
            self.adc_sample.set_server_config(ip, port)
            success, message = self.adc_sample.connect()
            self.model.set_adc_connection_status(success)
            self.adcStatusChanged.emit(success, message)
            self.log_message(f"ADC连接状态: {message}", "INFO" if success else "WARNING")
        except Exception as e:
            error_msg = f"连接ADC失败: {str(e)}"
            self.errorOccurred.emit(error_msg)
            self.adcStatusChanged.emit(False, str(e))
            self.log_message(error_msg, "ERROR")
    
    def on_disconnect_adc(self):
        """断开ADC连接"""
        try:
            self.adc_sample.disconnect()
            self.model.set_adc_connection_status(False)
            self.adcStatusChanged.emit(False, "手动断开连接")
            self.log_message("ADC已手动断开连接", "INFO")
        except Exception as e:
            error_msg = f"断开连接失败: {str(e)}"
            self.errorOccurred.emit(error_msg)
            self.log_message(error_msg, "ERROR")
    
    def on_sample_adc(self):
        """开始ADC采样"""
        if not self.model.adc_connected:
            error_msg = "请先连接ADC"
            self.errorOccurred.emit(error_msg)
            self.log_message(error_msg, "WARNING")
            return
        
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
        
        # 创建工作线程
        self.adc_thread = QThread()
        self.adc_worker = ADCWorker(self.adc_sample, count, interval, save_raw_data, output_dir, filename_prefix)
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
        self.log_message(f"开始ADC采样，次数: {count}, 间隔: {interval}s", "INFO")
    
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

    def log_message(self, message, level="INFO"):
        """记录消息到日志区域"""
        # 如果已经设置了主窗口控制器引用，使用它来记录日志
        if hasattr(self, 'main_window_controller') and self.main_window_controller:
            self.main_window_controller.log_controller.log(message, level)
        else:
            # 如果没有设置主窗口控制器，直接打印到控制台
            print(f"[{level}] {message}")
