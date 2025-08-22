# src/app/widgets/CalibrationPanel/Controller.py
from PyQt5.QtCore import QObject, pyqtSignal, QThread
from .Model import CalibrationModel, CalibrationType, PortConfig

class CalibrationWorker(QThread):
    progress_updated = pyqtSignal(str, int)
    finished = pyqtSignal()
    log_message = pyqtSignal(str, str)  # 新增：日志信号
    
    def __init__(self, model):
        super().__init__()
        self.model = model
        self._is_running = False
        
    def run(self):
        self._is_running = True
        self.log_message.emit("开始校准流程", "INFO")  # 新增：记录开始日志
        
        for step, progress in self.model.simulate_calibration():
            if not self._is_running:
                self.log_message.emit("校准被用户中断", "WARNING")  # 新增：记录中断日志
                break
            self.progress_updated.emit(step, progress)
            self.log_message.emit(f"执行步骤: {step}", "INFO")  # 新增：记录步骤日志
            self.msleep(500)  # 模拟耗时操作
        
        if self._is_running:
            self.log_message.emit("校准流程完成", "INFO")  # 新增：记录完成日志
        self.finished.emit()
        
    def stop(self):
        self._is_running = False

class CalibrationController(QObject):
    # 新增：定义日志信号
    log_message = pyqtSignal(str, str)  # (message, level)
    
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
        self.view.cal_type_combo.currentTextChanged.connect(self.on_cal_type_changed)
        self.view.port_combo.currentTextChanged.connect(self.on_port_config_changed)
        self.view.start_freq_edit.textChanged.connect(self.on_start_freq_changed)
        self.view.stop_freq_edit.textChanged.connect(self.on_stop_freq_changed)
        self.view.step_freq_edit.textChanged.connect(self.on_step_freq_changed)
        self.view.calibration_pow_edit.textChanged.connect(self.on_calibration_pow_changed)
        self.view.calibration_ifbw_edit.textChanged.connect(self.on_calibration_ifbw_changed)
        self.view.start_btn.clicked.connect(self.start_calibration)
        self.view.stop_btn.clicked.connect(self.stop_calibration)
        
    def update_view_from_model(self):
        """从模型更新视图"""
        self.view.cal_type_combo.setCurrentText(self.model.params.cal_type.value)
        self.view.port_combo.setCurrentText(self.model.params.port_config.value)
        self.view.start_freq_edit.setText(str(self.model.params.start_freq))
        self.view.stop_freq_edit.setText(str(self.model.params.stop_freq))
        self.view.step_freq_edit.setText(str(self.model.params.step_freq))
        self.view.calibration_pow_edit.setText(str(self.model.params.calibration_pow))
        self.view.calibration_ifbw_edit.setText(str(self.model.params.calibration_ifbw))
        self.view.update_calibration_steps(self.model.generate_calibration_steps())
        
    def on_cal_type_changed(self, text):
        """校准类型改变"""
        try:
            self.model.params.cal_type = CalibrationType(text)
            self.view.update_calibration_steps(self.model.generate_calibration_steps())
            self.log_message.emit(f"校准类型更改为: {text}", "INFO")  # 新增：记录类型变更
        except ValueError:
            self.log_message.emit(f"无效的校准类型: {text}", "ERROR")  # 新增：记录错误
            
    def on_port_config_changed(self, text):
        """端口配置改变"""
        try:
            self.model.params.port_config = PortConfig(text)
            self.view.update_calibration_steps(self.model.generate_calibration_steps())
            self.log_message.emit(f"端口配置更改为: {text}", "INFO")  # 新增：记录配置变更
        except ValueError:
            self.log_message.emit(f"无效的端口配置: {text}", "ERROR")  # 新增：记录错误
            
    def on_start_freq_changed(self, text):
        """起始频率改变"""
        try:
            self.model.params.start_freq = float(text)
            self.log_message.emit(f"起始频率设置为: {text} MHz", "INFO")  # 新增：记录频率设置
        except ValueError:
            self.log_message.emit(f"无效的起始频率: {text}", "ERROR")  # 新增：记录错误
            
    def on_stop_freq_changed(self, text):
        """终止频率改变"""
        try:
            self.model.params.stop_freq = float(text)
            self.log_message.emit(f"终止频率设置为: {text} MHz", "INFO")  # 新增：记录频率设置
        except ValueError:
            self.log_message.emit(f"无效的终止频率: {text}", "ERROR")  # 新增：记录错误
            
    def on_step_freq_changed(self, text):
        """步进频率改变"""
        try:
            self.model.params.step_freq = float(text)
            self.log_message.emit(f"步进频率设置为: {text} MHz", "INFO")  # 新增：记录频率设置
        except ValueError:
            self.log_message.emit(f"无效的步进频率: {text}", "ERROR")  # 新增：记录错误
            
    def on_calibration_pow_changed(self, text):
        """校准功率改变"""
        try:
            self.model.params.calibration_pow = float(text)
            self.log_message.emit(f"校准功率设置为: {text} dBm", "INFO")  # 新增：记录功率设置
        except ValueError:
            self.log_message.emit(f"无效的校准功率: {text}", "ERROR")  # 新增：记录错误
            
    def on_calibration_ifbw_changed(self, text):
        """校准IF带宽改变"""
        try:
            self.model.params.calibration_ifbw = int(text)
            self.log_message.emit(f"IF带宽设置为: {text} Hz", "INFO")  # 新增：记录带宽设置
        except ValueError:
            self.log_message.emit(f"无效的IF带宽: {text}", "ERROR")  # 新增：记录错误
            
    def start_calibration(self):
        """开始校准"""
        self.log_message.emit("开始校准流程", "INFO")  # 新增：记录开始校准
        self.view.set_calibration_running(True)
        self.worker = CalibrationWorker(self.model)
        self.worker.progress_updated.connect(self.on_progress_updated)
        self.worker.finished.connect(self.on_calibration_finished)
        self.worker.log_message.connect(self.log_message)  # 新增：连接工作线程的日志信号
        self.worker.start()
        
    def stop_calibration(self):
        """停止校准"""
        self.log_message.emit("用户请求停止校准", "WARNING")  # 新增：记录停止请求
        if self.worker:
            self.worker.stop()
            self.worker.wait()
        self.view.set_calibration_running(False)
        
    def on_progress_updated(self, step, progress):
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
        self.log_message.emit("校准流程完成", "INFO")  # 新增：记录完成
        
    def get_calibration_parameters(self):
        """获取当前校准参数"""
        return {
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
            self.log_message.emit("校准参数已更新", "INFO")  # 新增：记录参数更新
            return True
        except (ValueError, KeyError) as e:
            self.log_message.emit(f"设置校准参数失败: {str(e)}", "ERROR")  # 新增：记录错误
            return False
