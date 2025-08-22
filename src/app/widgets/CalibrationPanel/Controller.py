# src/app/widgets/CalibrationPanel/Controller.py
from PyQt5.QtCore import QObject, pyqtSignal, QThread, QEventLoop, QMutex, QWaitCondition
from PyQt5.QtWidgets import QMessageBox
from .Model import CalibrationModel, CalibrationType, PortConfig, CalibrationKitType

class CalibrationWorker(QThread):
    progress_updated = pyqtSignal(str, int, bool)  # 修改：添加第三个参数表示是否需要用户确认
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
        
        for step, progress, needs_confirmation in self.model.simulate_calibration():
            if not self._is_running:
                self.log_message.emit("校准被用户中断", "WARNING")
                break
            
            self.progress_updated.emit(step, progress, needs_confirmation)
            self.log_message.emit(f"执行步骤: {step}", "INFO")
            
            # 如果需要用户确认，等待用户响应
            if needs_confirmation and self._is_running:
                self.log_message.emit(f"等待用户确认: {step}", "INFO")
                # 通过控制器请求用户确认
                confirmed = self.request_user_confirmation(step)
                if not confirmed:
                    self.log_message.emit("用户取消了校准", "WARNING")
                    self._is_running = False
                    break
            
            self.msleep(500)  # 模拟耗时操作
        
        if self._is_running:
            self.log_message.emit("校准流程完成", "INFO")
        self.finished.emit()
        
    def stop(self):
        self._is_running = False
        self.wake_up_confirmation(False)  # 唤醒等待的确认
        
    def request_user_confirmation(self, step_description):
        """请求用户确认（在工作线程中调用）"""
        # 重置确认状态
        self.confirmation_mutex.lock()
        self.confirmation_result_received = False
        self.confirmation_mutex.unlock()
        
        # 在主线程中显示确认对话框
        self.controller.user_confirmation_requested.emit(step_description)
        
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

class CalibrationController(QObject):
    log_message = pyqtSignal(str, str)
    user_confirmation_requested = pyqtSignal(str)  # 请求用户确认的信号
    
    def __init__(self, view, model):
        super().__init__()
        self.view = view
        self.model = model
        self.worker = None
        
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
        
    def on_progress_updated(self, step, progress, needs_confirmation):
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
        
    def handle_user_confirmation(self, step_description):
        """处理用户确认请求（在主线程中执行）"""
        confirmed = self.view.show_user_confirmation(step_description)
        
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
