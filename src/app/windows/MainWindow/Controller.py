# src/app/windows/MainWindow/Controller.py
from app.widgets.CalibrationPanel import create_calibration_panel
from app.widgets.LogWidget import create_log_widget
from app.widgets.InstrumentPanel import create_instrument_panel
from app.widgets.PlotWidget import create_plot_widget

class MainWindowController:
    def __init__(self, view, model):
        self.view = view
        self.model = model
        self._initialize()
        self.setup_connections()
    
    def _initialize(self):
        """初始化窗口内容"""
        # 设置窗口基本属性
        self.view.setWindowTitle(self.model.window_title)
        
        # 添加仪表连接面板
        instrument_panel = create_instrument_panel()
        self.view.set_instrument_widget(instrument_panel)
        self.model.instrument_panel = instrument_panel
        
        # 添加校准面板
        calibration_panel = create_calibration_panel()
        self.view.set_calibration_widget(calibration_panel)
        self.model.calibration_panel = calibration_panel
        
        # 添加日志面板
        log_widget, self.log_controller = create_log_widget()
        self.view.set_log_widget(log_widget)
        self.model.log_controller = self.log_controller
        
        # 添加初始绘图区域
        plot_widget = create_plot_widget("时域响应")
        self.view.add_plot_tab(plot_widget, "时域")
        self.model.plot_widgets["时域"] = plot_widget
        
        # 添加频域绘图区域
        freq_plot_widget = create_plot_widget("频域响应")
        self.view.add_plot_tab(freq_plot_widget, "频域")
        self.model.plot_widgets["频域"] = freq_plot_widget
        
        # 初始状态消息
        self.view.show_status_message("就绪", 3000)
        self.log_controller.log("应用程序初始化完成", "INFO")
    
    def setup_connections(self):
        """设置信号槽连接"""
        # 这里可以添加主窗口级别的信号连接
        # 例如连接错误信号到日志
        if hasattr(self.view, 'errorOccurred'):
            self.view.errorOccurred.connect(
                lambda msg: self.log_controller.log(msg, "ERROR")
            )
        
        # 连接校准面板的信号到日志
        if hasattr(self.model.calibration_panel, 'calibrationStarted'):
            self.model.calibration_panel.calibrationStarted.connect(
                lambda: self.log_controller.log("校准开始", "INFO")
            )
        
        if hasattr(self.model.calibration_panel, 'calibrationCompleted'):
            self.model.calibration_panel.calibrationCompleted.connect(
                lambda: self.log_controller.log("校准完成", "INFO")
            )
