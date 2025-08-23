# src/app/windows/MainWindow/Model.py
class MainWindowModel:
    def __init__(self):
        self._window_title = "TDR Analyzer Calibration System"
        self._window_size = (1200, 800)
        self.instrument_panel = None
        self.calibration_panel = None
        self.vna_control_panel = None
        self.adc_sampling_panel = None
        self.data_analysis_panel = None
        self.log_controller = None
        self.plot_widgets = {}
        
        # 新增：存储仪表连接信息
        self.instrument_connected = False
        self.instrument_type = None
        self.instrument_ip = None
        self.instrument_port = None
        self.instrument_controller = None  # 存储仪表控制器
    
    @property
    def window_title(self):
        return self._window_title
    
    @property
    def window_size(self):
        return self._window_size
    
    def add_plot_widget(self, name, widget):
        """添加绘图部件"""
        self.plot_widgets[name] = widget
    
    def set_instrument_info(self, connected, instrument_type, ip, port, controller):
        """设置仪表连接信息"""
        self.instrument_connected = connected
        self.instrument_type = instrument_type
        self.instrument_ip = ip
        self.instrument_port = port
        self.instrument_controller = controller
