# src/app/windows/MainWindow/Model.py
class MainWindowModel:
    def __init__(self):
        self._window_title = "TDR Analyzer Calibration System"
        self._window_size = (1200, 800)
        self.instrument_panel = None
        self.calibration_panel = None
        self.vna_control_panel = None
        self.adc_sampling_panel = None  # 新增ADC采样面板引用
        self.data_analysis_panel = None
        self.log_controller = None
        self.plot_widgets = {}  # 存储绘图部件
    
    @property
    def window_title(self):
        return self._window_title
    
    @property
    def window_size(self):
        return self._window_size
    
    def add_plot_widget(self, name, widget):
        """添加绘图部件"""
        self.plot_widgets[name] = widget
