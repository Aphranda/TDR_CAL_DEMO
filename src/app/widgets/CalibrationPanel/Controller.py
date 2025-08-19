from PyQt5.QtCore import QObject, pyqtSignal, QThread
from .Model import CalibrationModel, CalibrationType, PortConfig

class CalibrationWorker(QThread):
    progress_updated = pyqtSignal(str, int)
    finished = pyqtSignal()
    
    def __init__(self, model):
        super().__init__()
        self.model = model
        self._is_running = False
        
    def run(self):
        self._is_running = True
        for step, progress in self.model.simulate_calibration():
            if not self._is_running:
                break
            self.progress_updated.emit(step, progress)
            self.msleep(500)  # 模拟耗时操作
        self.finished.emit()
        
    def stop(self):
        self._is_running = False

class CalibrationController(QObject):
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
        self.view.start_btn.clicked.connect(self.start_calibration)
        self.view.stop_btn.clicked.connect(self.stop_calibration)
        
    def update_view_from_model(self):
        """从模型更新视图"""
        self.view.cal_type_combo.setCurrentText(self.model.params.cal_type.value)
        self.view.port_combo.setCurrentText(self.model.params.port_config.value)
        self.view.start_freq_edit.setText(str(self.model.params.start_freq))
        self.view.stop_freq_edit.setText(str(self.model.params.stop_freq))
        self.view.update_calibration_steps(self.model.generate_calibration_steps())
        
    def on_cal_type_changed(self, text):
        """校准类型改变"""
        self.model.params.cal_type = CalibrationType(text)
        self.view.update_calibration_steps(self.model.generate_calibration_steps())
        
    def on_port_config_changed(self, text):
        """端口配置改变"""
        self.model.params.port_config = PortConfig(text)
        self.view.update_calibration_steps(self.model.generate_calibration_steps())
        
    def on_start_freq_changed(self, text):
        """起始频率改变"""
        try:
            self.model.params.start_freq = float(text)
        except ValueError:
            pass
        
    def on_stop_freq_changed(self, text):
        """终止频率改变"""
        try:
            self.model.params.stop_freq = float(text)
        except ValueError:
            pass
        
    def start_calibration(self):
        """开始校准"""
        self.view.set_calibration_running(True)
        self.worker = CalibrationWorker(self.model)
        self.worker.progress_updated.connect(self.on_progress_updated)
        self.worker.finished.connect(self.on_calibration_finished)
        self.worker.start()
        
    def stop_calibration(self):
        """停止校准"""
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
