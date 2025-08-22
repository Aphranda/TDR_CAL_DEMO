# src/app/windows/MainWindow/Controller.py
from app.widgets.CalibrationPanel import create_calibration_panel
from app.widgets.LogWidget import create_log_widget
from app.widgets.InstrumentPanel import create_instrument_panel
from app.widgets.PlotWidget import create_plot_widget
from app.widgets.VNAControlPanel import create_vna_control_panel
from app.widgets.DataAnalysisPanel import create_data_analysis_panel

class MainWindowController:
    def __init__(self, view, model):
        self.view = view
        self.model = model
        self.sub_controllers = {}  # 存储所有子控制器的引用
        self._initialize()
        self.setup_connections()
    
    def _initialize(self):
        """初始化窗口内容"""
        # 设置窗口基本属性
        self.view.setWindowTitle(self.model.window_title)
        
        # 添加仪表连接面板
        instrument_panel, instrument_controller = create_instrument_panel()
        self.view.set_instrument_widget(instrument_panel)
        self.model.instrument_panel = instrument_panel
        self.sub_controllers['instrument'] = instrument_controller
        
        # 添加校准面板
        calibration_panel, calibration_controller = create_calibration_panel()
        self.view.set_calibration_widget(calibration_panel)
        self.model.calibration_panel = calibration_panel
        self.sub_controllers['calibration'] = calibration_controller
        
        # 添加日志面板 - 现在在单独的标签页中
        log_widget, log_controller = create_log_widget()
        self.view.set_log_widget(log_widget)  # 这会添加到日志标签页
        self.model.log_controller = log_controller
        self.sub_controllers['log'] = log_controller
        self.log_controller = log_controller
        
        # 添加网分控制面板
        vna_control_panel, vna_controller = create_vna_control_panel()
        self.view.set_vna_control_widget(vna_control_panel)
        self.model.vna_control_panel = vna_control_panel
        self.sub_controllers['vna_control'] = vna_controller
        
        # 添加数据分析面板
        data_analysis_panel, data_analysis_controller = create_data_analysis_panel()
        self.view.set_data_analysis_widget(data_analysis_panel)
        self.model.data_analysis_panel = data_analysis_panel
        self.sub_controllers['data_analysis'] = data_analysis_controller
        
        # 设置主窗口控制器引用
        data_analysis_controller.set_main_window_controller(self)
        
        # 添加初始绘图区域
        plot_widget, plot_controller = create_plot_widget("时域响应")
        self.view.add_plot_tab(plot_widget, "时域")
        self.model.plot_widgets["时域"] = plot_widget
        self.sub_controllers['plot_time'] = plot_controller
        
        # 添加频域绘图区域
        freq_plot_widget, freq_plot_controller = create_plot_widget("频域响应")
        self.view.add_plot_tab(freq_plot_widget, "频域")
        self.model.plot_widgets["频域"] = freq_plot_widget
        self.sub_controllers['plot_freq'] = freq_plot_controller
        
        # 初始状态消息
        self.view.show_status_message("就绪", 3000)
        self.log_controller.log("应用程序初始化完成", "INFO")
    
    def setup_connections(self):
        """设置信号槽连接"""
        # 连接错误信号到日志
        if hasattr(self.view, 'errorOccurred'):
            self.view.errorOccurred.connect(
                lambda msg: self.log_controller.log(msg, "ERROR")
            )
        
        # 连接仪表面板的信号到日志
        instrument_controller = self.sub_controllers.get('instrument')
        if instrument_controller and hasattr(instrument_controller, 'instrumentConnected'):
            instrument_controller.instrumentConnected.connect(
                lambda instr: self.log_controller.log(f"仪表 {instr} 已连接", "INFO")
            )
        
        if instrument_controller and hasattr(instrument_controller, 'instrumentDisconnected'):
            instrument_controller.instrumentDisconnected.connect(
                lambda instr: self.log_controller.log(f"仪表 {instr} 已断开", "WARNING")
            )
        
        if instrument_controller and hasattr(instrument_controller, 'log_message'):
            instrument_controller.log_message.connect(
                lambda msg, level: self.log_controller.log(msg, level)
            )
                
        # 连接校准面板的信号到日志
        calibration_controller = self.sub_controllers.get('calibration')
        if calibration_controller and hasattr(calibration_controller, 'calibrationStarted'):
            calibration_controller.calibrationStarted.connect(
                lambda: self.log_controller.log("校准开始", "INFO")
            )
        
        if calibration_controller and hasattr(calibration_controller, 'calibrationCompleted'):
            calibration_controller.calibrationCompleted.connect(
                lambda: self.log_controller.log("校准完成", "INFO")
            )
        
        if calibration_controller and hasattr(calibration_controller, 'calibrationError'):
            calibration_controller.calibrationError.connect(
                lambda msg: self.log_controller.log(f"校准错误: {msg}", "ERROR")
            )
            
        if calibration_controller and hasattr(calibration_controller, 'log_message'):
            calibration_controller.log_message.connect(
                lambda msg, level: self.log_controller.log(msg, level)
            )
        
        # 连接网分控制面板的信号到日志
        vna_controller = self.sub_controllers.get('vna_control')
        if vna_controller and hasattr(vna_controller, 'sweepStarted'):
            vna_controller.sweepStarted.connect(
                lambda: self.log_controller.log("网分扫描开始", "INFO")
            )
        
        if vna_controller and hasattr(vna_controller, 'sweepCompleted'):
            vna_controller.sweepCompleted.connect(
                lambda: self.log_controller.log("网分扫描完成", "INFO")
            )
        
        # 连接数据分析面板的信号 - 这里特别重要！
        data_analysis_controller = self.sub_controllers.get('data_analysis')
        if data_analysis_controller and hasattr(data_analysis_controller, 'dataLoaded'):
            data_analysis_controller.dataLoaded.connect(
                lambda msg: self.log_controller.log(msg, "INFO")
            )
        
        if data_analysis_controller and hasattr(data_analysis_controller, 'analysisStarted'):
            data_analysis_controller.analysisStarted.connect(
                lambda analysis_type: self.log_controller.log(f"开始{analysis_type}分析", "INFO")
            )
        
        if data_analysis_controller and hasattr(data_analysis_controller, 'analysisCompleted'):
            data_analysis_controller.analysisCompleted.connect(
                lambda results: self.log_controller.log("分析完成", "INFO")
            )
        
        if data_analysis_controller and hasattr(data_analysis_controller, 'errorOccurred'):
            data_analysis_controller.errorOccurred.connect(
                lambda msg: self.log_controller.log(msg, "ERROR")
            )
