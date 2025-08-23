# src/app/widgets/CalibrationPanel/Controller.py
from PyQt5.QtCore import QObject, pyqtSignal, QThread, QEventLoop, QMutex, QWaitCondition
from PyQt5.QtWidgets import QMessageBox
from .Model import CalibrationModel, CalibrationType, PortConfig, CalibrationKitType
import os
import numpy as np
import glob

class CalibrationWorker(QThread):
    progress_updated = pyqtSignal(str, int, bool, bool)  # 修改：添加第三个参数表示是否需要用户确认
    finished = pyqtSignal()
    log_message = pyqtSignal(str, str)
    confirmation_result = pyqtSignal(bool)  # 新增：用户确认结果信号
    
    def __init__(self, model, controller):
        super().__init__()
        self.model = model
        self.controller = controller
        self._is_running = False
        self.confirmation_mutex = QMutex()
        self.confirmation_condition = QWaitCondition()
        self.confirmation_result_received = False
        self.last_confirmation_result = False
        
    def run(self):
        self._is_running = True
        self.log_message.emit("开始校准流程", "INFO")
        
        # 获取ADC采样和数据分析控制器
        adc_controller = self.controller.get_adc_controller()
        data_analysis_controller = self.controller.get_data_analysis_controller()
        
        # 获取主窗口控制器
        main_controller = self.controller.get_main_window_controller()
        
        # 创建校准文件夹
        base_path = self.model.create_calibration_folders()
        self.log_message.emit(f"校准文件夹已创建: {base_path}", "INFO")
        
        # 获取校准步骤
        steps = self.model.generate_calibration_steps()
        total_steps = len(steps)
        
        for i, step in enumerate(steps):
            if not self._is_running:
                self.log_message.emit("校准被用户中断", "WARNING")
                break
            
            progress = int((i + 1) / total_steps * 100)
            
            # 判断是否有测量字段
            has_measurement = "测量" in step
            
            # 更新进度
            self.progress_updated.emit(step, progress, False, has_measurement)
            self.log_message.emit(f"执行步骤: {step}", "INFO")
            
            # 如果是测量步骤，执行ADC采样和数据分析
            if has_measurement and self._is_running:
                # 获取当前步骤对应的文件夹
                folder_name = self.model.get_folder_name_from_step(step)
                folder_path = os.path.join(base_path, folder_name)
                
                raw_data_dir = os.path.join(folder_path, "Raw_ADC_Data")
                processed_data_dir = os.path.join(folder_path, "Processed_Data")
                
                # 确保目录存在
                os.makedirs(raw_data_dir, exist_ok=True)
                os.makedirs(processed_data_dir, exist_ok=True)
                
                # 设置ADC采样参数
                adc_controller.view.output_dir_edit.setText(raw_data_dir)
                adc_controller.view.filename_edit.setText(f"step_{i+1}_{folder_name}")
                # adc_controller.view.sample_count_spin.setValue(10)  # 多次采样
                # adc_controller.view.sample_interval_spin.setValue(0.1)  # 短间隔
                
                # 执行ADC采样
                self.log_message.emit(f"开始ADC采样: {step}", "INFO")
                adc_controller.on_sample_adc()
                
                # 等待采样完成
                loop = QEventLoop()
                adc_controller.dataLoaded.connect(loop.quit)
                adc_controller.errorOccurred.connect(loop.quit)
                loop.exec_()
                
                # 检查是否采样成功
                if not adc_controller.model.adc_samples:
                    self.log_message.emit(f"ADC采样失败: {step}", "ERROR")
                    continue
                
                # 获取当前文件夹中的所有数据文件
                data_files = glob.glob(os.path.join(raw_data_dir, "*.csv"))
                if not data_files:
                    self.log_message.emit(f"未找到数据文件: {raw_data_dir}", "ERROR")
                    continue
                
                # 设置数据分析参数
                data_analysis_controller.model.data_files = data_files  # 传入文件列表
                data_analysis_controller.view.file_list.clear()
                
                # 添加文件到列表视图
                for file_path in data_files:
                    data_analysis_controller.view.file_list.addItem(os.path.basename(file_path))
                
                # 执行数据分析
                self.log_message.emit(f"开始数据分析: {step}", "INFO")
                data_analysis_controller.on_analyze()
                
                # 等待分析完成
                loop2 = QEventLoop()
                data_analysis_controller.analysisCompleted.connect(loop2.quit)
                data_analysis_controller.errorOccurred.connect(loop2.quit)
                loop2.exec_()
                
                # 保存分析结果
                if data_analysis_controller.model.results:
                    # 保存处理后的数据
                    processed_filename = f"step_{i+1}_{folder_name}_processed.csv"
                    processed_filepath = os.path.join(processed_data_dir, processed_filename)
                    
                    # 这里应该根据实际分析结果保存数据
                    # 简化处理：保存分析结果的统计信息
                    with open(processed_filepath, 'w') as f:
                        f.write("Analysis Results\n")
                        f.write("=" * 50 + "\n")
                        for key, value in data_analysis_controller.model.results.items():
                            f.write(f"{key}: {value}\n")
                    
                    self.log_message.emit(f"分析结果已保存: {processed_filename}", "INFO")
                # 替换为：
                # 保存分析结果
                if data_analysis_controller.model.results:
                    # 保存处理后的数据
                    processed_filename = f"step_{i+1}_{folder_name}_processed"
                    processed_filepath = os.path.join(processed_data_dir, processed_filename)
                    
                    # 使用数据分析控制器的导出函数保存数据
                    try:
                        # 导出CSV结果
                        data_analysis_controller.export_csv_results(processed_filepath + ".csv")
                        data_analysis_controller.export_plots(processed_filepath)
                        self.log_message.emit(f"分析结果已保存: {processed_filename}*.csv", "INFO")
                    except Exception as e:
                        self.log_message.emit(f"保存分析结果失败: {str(e)}", "ERROR")
            
            # 如果需要用户确认，等待用户响应
            needs_confirmation = (self.model.params.kit_type == CalibrationKitType.MECHANICAL and 
                                ("连接" in step or "更换" in step or has_measurement))
            
            if needs_confirmation and self._is_running:
                self.log_message.emit(f"等待用户确认: {step}", "INFO")
                # 通过控制器请求用户确认
                confirmed = self.request_user_confirmation(step, has_measurement)
                if not confirmed:
                    self.log_message.emit("用户取消了校准", "WARNING")
                    self._is_running = False
                    break
            
            self.msleep(500)  # 模拟耗时操作
        
        if self._is_running:
            self.log_message.emit("校准流程完成", "INFO")
        self.finished.emit()
        
    def request_user_confirmation(self, step_description, has_measurement):
        """请求用户确认（在工作线程中调用）"""
        # 重置确认状态
        self.confirmation_mutex.lock()
        self.confirmation_result_received = False
        self.confirmation_mutex.unlock()
        
        # 在主线程中显示确认对话框
        self.controller.user_confirmation_requested.emit(step_description, has_measurement)
        
        # 等待用户响应
        self.confirmation_mutex.lock()
        while not self.confirmation_result_received and self._is_running:
            self.confirmation_condition.wait(self.confirmation_mutex)
        result = self.last_confirmation_result
        self.confirmation_mutex.unlock()
        
        return result
        
    def wake_up_confirmation(self, result):
        """唤醒等待的确认"""
        self.confirmation_mutex.lock()
        self.confirmation_result_received = True
        self.last_confirmation_result = result
        self.confirmation_condition.wakeAll()
        self.confirmation_mutex.unlock()

    def stop(self):
        self._is_running = False
        self.wake_up_confirmation(False)  # 唤醒等待的确认


class CalibrationController(QObject):
    log_message = pyqtSignal(str, str)
    user_confirmation_requested = pyqtSignal(str, bool)  # 修改：添加第二个参数表示是否有测量字段
    retest_requested = pyqtSignal()  # 新增：重测请求信号
    retest_finished = pyqtSignal()  # 新增：重测完成信号
    
    def __init__(self, view, model):
        super().__init__()
        self.view = view
        self.model = model
        self.worker = None
        self.main_window_controller = None
        self.adc_controller = None
        self.data_analysis_controller = None
        
        # 连接信号槽
        self.connect_signals()
        
        # 初始化视图
        self.update_view_from_model()
        
    def connect_signals(self):
        self.view.kit_type_combo.currentTextChanged.connect(self.on_kit_type_changed)
        self.view.cal_type_combo.currentTextChanged.connect(self.on_cal_type_changed)
        self.view.port_combo.currentTextChanged.connect(self.on_port_config_changed)
        self.view.start_freq_edit.textChanged.connect(self.on_start_freq_changed)
        self.view.stop_freq_edit.textChanged.connect(self.on_stop_freq_changed)
        self.view.step_freq_edit.textChanged.connect(self.on_step_freq_changed)
        self.view.calibration_pow_edit.textChanged.connect(self.on_calibration_pow_changed)
        self.view.calibration_ifbw_edit.textChanged.connect(self.on_calibration_ifbw_changed)
        self.view.start_btn.clicked.connect(self.start_calibration)
        self.view.stop_btn.clicked.connect(self.stop_calibration)
        
        # 连接用户确认信号
        self.user_confirmation_requested.connect(self.handle_user_confirmation)

        # 连接重测信号
        self.view.retest_requested.connect(self.on_retest_requested)
        self.retest_requested.connect(self.on_retest_requested)
        self.retest_finished.connect(self.view.retest_finished)  # 连接重测完成信号
        
    def update_view_from_model(self):
        """从模型更新视图"""
        self.view.kit_type_combo.setCurrentText(self.model.params.kit_type.value)
        self.view.cal_type_combo.setCurrentText(self.model.params.cal_type.value)
        self.view.port_combo.setCurrentText(self.model.params.port_config.value)
        self.view.start_freq_edit.setText(str(self.model.params.start_freq))
        self.view.stop_freq_edit.setText(str(self.model.params.stop_freq))
        self.view.step_freq_edit.setText(str(self.model.params.step_freq))
        self.view.calibration_pow_edit.setText(str(self.model.params.calibration_pow))
        self.view.calibration_ifbw_edit.setText(str(self.model.params.calibration_ifbw))
        self.view.update_calibration_steps(self.model.generate_calibration_steps())
        
    def on_kit_type_changed(self, text):
        """校准件类型改变"""
        try:
            self.model.params.kit_type = CalibrationKitType(text)
            self.log_message.emit(f"校准件类型更改为: {text}", "INFO")
            
            # 根据校准件类型更新UI提示
            if self.model.params.kit_type == CalibrationKitType.ELECTRONIC:
                self.log_message.emit("使用电子校准件，校准将自动进行", "INFO")
            else:
                self.log_message.emit("使用机械校准件，需要人工更换校准件", "WARNING")
                
        except ValueError:
            self.log_message.emit(f"无效的校准件类型: {text}", "ERROR")
            
    def on_cal_type_changed(self, text):
        """校准类型改变"""
        try:
            self.model.params.cal_type = CalibrationType(text)
            self.view.update_calibration_steps(self.model.generate_calibration_steps())
            self.log_message.emit(f"校准类型更改为: {text}", "INFO")
        except ValueError:
            self.log_message.emit(f"无效的校准类型: {text}", "ERROR")
            
    def on_port_config_changed(self, text):
        """端口配置改变"""
        try:
            self.model.params.port_config = PortConfig(text)
            self.view.update_calibration_steps(self.model.generate_calibration_steps())
            self.log_message.emit(f"端口配置更改为: {text}", "INFO")
        except ValueError:
            self.log_message.emit(f"无效的端口配置: {text}", "ERROR")
            
    def on_start_freq_changed(self, text):
        """起始频率改变"""
        try:
            self.model.params.start_freq = float(text)
            self.log_message.emit(f"起始频率设置为: {text} MHz", "INFO")
        except ValueError:
            self.log_message.emit(f"无效的起始频率: {text}", "ERROR")
            
    def on_stop_freq_changed(self, text):
        """终止频率改变"""
        try:
            self.model.params.stop_freq = float(text)
            self.log_message.emit(f"终止频率设置为: {text} MHz", "INFO")
        except ValueError:
            self.log_message.emit(f"无效的终止频率: {text}", "ERROR")
            
    def on_step_freq_changed(self, text):
        """步进频率改变"""
        try:
            self.model.params.step_freq = float(text)
            self.log_message.emit(f"步进频率设置为: {text} MHz", "INFO")
        except ValueError:
            self.log_message.emit(f"无效的步进频率: {text}", "ERROR")
            
    def on_calibration_pow_changed(self, text):
        """校准功率改变"""
        try:
            self.model.params.calibration_pow = float(text)
            self.log_message.emit(f"校准功率设置为: {text} dBm", "INFO")
        except ValueError:
            self.log_message.emit(f"无效的校准功率: {text}", "ERROR")
            
    def on_calibration_ifbw_changed(self, text):
        """校准IF带宽改变"""
        try:
            self.model.params.calibration_ifbw = int(text)
            self.log_message.emit(f"IF带宽设置为: {text} Hz", "INFO")
        except ValueError:
            self.log_message.emit(f"无效的IF带宽: {text}", "ERROR")
            
    def start_calibration(self):
        """开始校准"""
        self.log_message.emit("开始校准流程", "INFO")
        
        # 根据校准件类型显示不同的提示信息
        if self.model.params.kit_type == CalibrationKitType.ELECTRONIC:
            self.log_message.emit("使用电子校准件，校准将自动进行", "INFO")
        else:
            self.log_message.emit("使用机械校准件，请在提示时更换校准件", "WARNING")
            
        self.view.set_calibration_running(True)
        self.worker = CalibrationWorker(self.model, self)
        self.worker.progress_updated.connect(self.on_progress_updated)
        self.worker.finished.connect(self.on_calibration_finished)
        self.worker.log_message.connect(self.log_message)
        self.worker.confirmation_result.connect(self.on_confirmation_result)
        self.worker.start()
        
    def stop_calibration(self):
        """停止校准"""
        self.log_message.emit("用户请求停止校准", "WARNING")
        self.view.reset_scroll_position()
        if self.worker:
            self.worker.stop()
            self.worker.wait()
        self.view.set_calibration_running(False)
        
    def on_progress_updated(self, step, progress, needs_confirmation, has_measurement):
        """更新进度"""
        # 计算当前步骤索引
        current_step_index = -1
        for i, s in enumerate(self.model.steps):
            if s == step:
                current_step_index = i
                break
        
        self.view.update_progress(progress, current_step_index)
        
    def on_calibration_finished(self):
        """校准完成"""
        self.view.set_calibration_running(False)
        self.view.reset_scroll_position()
        self.log_message.emit("校准流程完成", "INFO")
        
    def handle_user_confirmation(self, step_description, has_measurement):
        """处理用户确认请求（在主线程中执行）"""
        confirmed = self.view.show_user_confirmation(step_description, has_measurement)
        
        if not confirmed:
            self.log_message.emit(f"用户取消了步骤: {step_description}", "WARNING")
            if self.worker:
                self.worker.wake_up_confirmation(False)
        else:
            self.log_message.emit(f"用户确认完成: {step_description}", "INFO")
            if self.worker:
                self.worker.wake_up_confirmation(True)
                
    def on_confirmation_result(self, result):
        """处理确认结果"""
        # 这个信号主要用于调试，可以记录确认结果
        if result:
            self.log_message.emit("用户确认继续", "INFO")
        else:
            self.log_message.emit("用户取消操作", "WARNING")

    def on_retest_requested(self):
        """处理重测请求"""
        self.log_message.emit("用户请求重测当前步骤", "INFO")
        
        # 模拟重测操作
        if self.worker and self.worker.isRunning():
            # 可以在这里添加重测逻辑，例如重新发送测量命令
            self.log_message.emit("正在重测当前步骤...", "INFO")
            
            # 使用QTimer来模拟异步重测操作，避免阻塞UI
            from PyQt5.QtCore import QTimer
            QTimer.singleShot(2000, self.on_retest_completed)  # 2秒后完成重测

    def on_retest_completed(self):
        """重测完成"""
        self.log_message.emit("重测完成", "INFO")
        self.retest_finished.emit()  # 发送重测完成信号
        
    def get_calibration_parameters(self):
        """获取当前校准参数"""
        return {
            'kit_type': self.model.params.kit_type.value,
            'cal_type': self.model.params.cal_type.value,
            'port_config': self.model.params.port_config.value,
            'start_freq': self.model.params.start_freq,
            'stop_freq': self.model.params.stop_freq,
            'step_freq': self.model.params.step_freq,
            'calibration_pow': self.model.params.calibration_pow,
            'calibration_ifbw': self.model.params.calibration_ifbw
        }
    
    def set_calibration_parameters(self, params):
        """设置校准参数"""
        try:
            if 'kit_type' in params:
                self.model.params.kit_type = CalibrationKitType(params['kit_type'])
            if 'cal_type' in params:
                self.model.params.cal_type = CalibrationType(params['cal_type'])
            if 'port_config' in params:
                self.model.params.port_config = PortConfig(params['port_config'])
            if 'start_freq' in params:
                self.model.params.start_freq = float(params['start_freq'])
            if 'stop_freq' in params:
                self.model.params.stop_freq = float(params['stop_freq'])
            if 'step_freq' in params:
                self.model.params.step_freq = float(params['step_freq'])
            if 'calibration_pow' in params:
                self.model.params.calibration_pow = float(params['calibration_pow'])
            if 'calibration_ifbw' in params:
                self.model.params.calibration_ifbw = int(params['calibration_ifbw'])
            
            self.update_view_from_model()
            self.log_message.emit("校准参数已更新", "INFO")
            return True
        except (ValueError, KeyError) as e:
            self.log_message.emit(f"设置校准参数失败: {str(e)}", "ERROR")
            return False

    def set_main_window_controller(self, main_window_controller):
        """设置主窗口控制器引用"""
        self.main_window_controller = main_window_controller
        
    def set_adc_controller(self, adc_controller):
        """设置ADC控制器引用"""
        self.adc_controller = adc_controller
        
    def set_data_analysis_controller(self, data_analysis_controller):
        """设置数据分析控制器引用"""
        self.data_analysis_controller = data_analysis_controller
        
    def get_adc_controller(self):
        """获取ADC控制器"""
        return self.adc_controller
        
    def get_data_analysis_controller(self):
        """获取数据分析控制器"""
        return self.data_analysis_controller
        
    def get_main_window_controller(self):
        """获取主窗口控制器"""
        return self.main_window_controller
