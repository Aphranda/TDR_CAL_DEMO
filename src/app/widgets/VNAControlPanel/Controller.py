# src/app/widgets/VNAControlPanel/Controller.py
class VNAControlController:
    def __init__(self, view, model):
        self.view = view
        self.model = model
        self.setup_connections()
    
    def setup_connections(self):
        """设置信号槽连接"""
        self.view.sweep_button.clicked.connect(self.on_sweep)
        self.view.stop_button.clicked.connect(self.on_stop)
        self.view.save_button.clicked.connect(self.on_save)
        
        # 频率设置变化
        self.view.start_freq_edit.textChanged.connect(self.on_freq_changed)
        self.view.stop_freq_edit.textChanged.connect(self.on_freq_changed)
        self.view.points_spin.valueChanged.connect(self.on_points_changed)
        
        # 功率设置变化
        self.view.power_edit.textChanged.connect(self.on_power_changed)
        
        # IF带宽变化
        self.view.if_bw_combo.currentTextChanged.connect(self.on_if_bw_changed)
    
    def on_sweep(self):
        """开始扫描"""
        print("开始扫描...")
    
    def on_stop(self):
        """停止扫描"""
        print("停止扫描...")
    
    def on_save(self):
        """保存数据"""
        print("保存数据...")
    
    def on_freq_changed(self):
        """频率设置变化"""
        try:
            start_freq = float(self.view.start_freq_edit.text())
            stop_freq = float(self.view.stop_freq_edit.text())
            self.model.frequency_start = start_freq
            self.model.frequency_stop = stop_freq
        except ValueError:
            pass
    
    def on_points_changed(self, value):
        """点数变化"""
        self.model.points = value
    
    def on_power_changed(self):
        """功率变化"""
        try:
            power = float(self.view.power_edit.text())
            self.model.power = power
        except ValueError:
            pass
    
    def on_if_bw_changed(self, value):
        """IF带宽变化"""
        try:
            if_bw = float(value)
            self.model.if_bandwidth = if_bw
        except ValueError:
            pass
