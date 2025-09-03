# src/app/windows/MainWindow/Controller.py
from app.widgets.CalibrationPanel import create_calibration_panel
from app.widgets.LogWidget import create_log_widget
from app.widgets.InstrumentPanel import create_instrument_panel
from app.widgets.PlotWidget import create_plot_widget
from app.widgets.VNAControlPanel import create_vna_control_panel
from app.widgets.ADCSamplingPanel import create_adc_sampling_panel
from app.widgets.DataAnalysisPanel import create_data_analysis_panel
from app.widgets.ProgressPanel import create_progress_panel_simple,ProgressBarStyle

class MainWindowController:
    def __init__(self, view, model):
        self.view = view
        self.model = model
        self.sub_controllers = {}

        # 存储进度面板控制器
        self.progress_controller = None

        self._initialize()
        self.setup_connections()
    
    def _initialize(self):
        """初始化窗口内容"""
        self.view.setWindowTitle(self.model.window_title)
        
        # 添加仪表连接面板到系统功能标签页
        instrument_panel, instrument_controller = create_instrument_panel()
        self.view.set_instrument_widget(instrument_panel)
        self.model.instrument_panel = instrument_panel
        self.sub_controllers['instrument'] = instrument_controller
        
        # 初始化仪表信息
        self.model.set_instrument_info(
            False,  # 初始状态未连接
            instrument_controller.model.instrument_type,
            instrument_controller.model.ip_address,
            instrument_controller.model.port,
            instrument_controller
        )
        
        # 添加日志面板到系统功能标签页
        log_widget, log_controller = create_log_widget()
        self.view.set_log_widget(log_widget)
        self.model.log_controller = log_controller
        self.sub_controllers['log'] = log_controller
        self.log_controller = log_controller
        
        # 添加校准面板到网分校准标签页
        calibration_panel, calibration_controller = create_calibration_panel()
        self.view.set_calibration_widget(calibration_panel)
        self.model.calibration_panel = calibration_panel
        self.sub_controllers['calibration'] = calibration_controller
        
        # 添加网分控制面板
        vna_control_panel, vna_controller = create_vna_control_panel()
        self.view.set_vna_control_widget(vna_control_panel)
        self.model.vna_control_panel = vna_control_panel
        self.sub_controllers['vna_control'] = vna_controller

        # 添加ADC采样面板到数据处理标签页
        adc_sampling_panel, adc_controller = create_adc_sampling_panel()
        self.view.set_adc_sampling_widget(adc_sampling_panel)
        self.model.adc_sampling_panel = adc_sampling_panel
        self.sub_controllers['adc_sampling'] = adc_controller
        
        # 添加数据分析面板
        data_analysis_panel, data_analysis_controller = create_data_analysis_panel()
        self.view.set_data_processing_widget(data_analysis_panel)
        self.model.data_analysis_panel = data_analysis_panel
        self.sub_controllers['data_analysis'] = data_analysis_controller
        
        # 设置主窗口控制器引用
        data_analysis_controller.set_main_window_controller(self)
        adc_controller.set_main_window_controller(self)
        
        # 设置校准控制器的引用
        calibration_controller.set_main_window_controller(self)
        calibration_controller.set_adc_controller(adc_controller)
        calibration_controller.set_data_analysis_controller(data_analysis_controller)
        self.model.calibration_controller = calibration_controller
        
        # 通知ADC采样面板仪表连接状态
        adc_controller.set_instrument_connected(False, None)
        
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

        # 创建进度面板
        self._setup_progress_panel()
    
    
    def setup_connections(self):
        """设置信号槽连接"""
        # 连接错误信号到日志
        if hasattr(self.view, 'errorOccurred'):
            self.view.errorOccurred.connect(
                lambda msg: self.log_controller.log(msg, "ERROR")
            )
        
        # 连接仪表面板的信号到日志和主窗口模型
        instrument_controller = self.sub_controllers.get('instrument')
        if instrument_controller and hasattr(instrument_controller, 'connectionChanged'):
            instrument_controller.connectionChanged.connect(self._handle_instrument_connection_change)
        
        if instrument_controller and hasattr(instrument_controller, 'instrumentError'):
            instrument_controller.instrumentError.connect(
                lambda msg: self.log_controller.log(f"仪表错误: {msg}", "ERROR")
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
        
        # 连接ADC采样面板的信号到日志
        adc_controller = self.sub_controllers.get('adc_sampling')
        if adc_controller and hasattr(adc_controller, 'errorOccurred'):
            adc_controller.errorOccurred.connect(
                lambda msg: self.log_controller.log(f"ADC错误: {msg}", "ERROR")
            )
        
        if adc_controller and hasattr(adc_controller, 'dataLoaded'):
            adc_controller.dataLoaded.connect(
                lambda msg: self.log_controller.log(f"ADC: {msg}", "INFO")
            )
        
        if adc_controller and hasattr(adc_controller, 'adcStatusChanged'):
            adc_controller.adcStatusChanged.connect(
                lambda connected, msg: self.log_controller.log(f"ADC连接状态: {msg}", "INFO" if connected else "WARNING")
            )
        
        # 连接数据分析面板的信号
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

        # 连接进度相关的信号
        self._setup_progress_connections()
    
    def _handle_instrument_connection_change(self, connected):
        """处理仪表连接状态变化"""
        instrument_controller = self.sub_controllers.get('instrument')
        if instrument_controller:
            # 更新主窗口模型中的仪表信息
            self.model.set_instrument_info(
                connected,
                instrument_controller.model.instrument_type,
                instrument_controller.model.ip_address,
                instrument_controller.model.port,
                instrument_controller
            )
            
            # 通知其他面板仪表连接状态变化
            self._notify_instrument_status_change(connected)
            
            # 更新状态栏
            status_msg = f"仪表已连接: {instrument_controller.model.instrument_type} ({instrument_controller.model.ip_address}:{instrument_controller.model.port})" if connected else "仪表已断开"
            self.view.show_status_message(status_msg, 5000)
    
    def _notify_instrument_status_change(self, connected):
        """通知其他面板仪表连接状态变化"""
        # 通知校准面板
        calibration_controller = self.sub_controllers.get('calibration')
        if calibration_controller and hasattr(calibration_controller, 'set_instrument_connected'):
            calibration_controller.set_instrument_connected(connected, self.model.instrument_controller)
        
        # 通知网分控制面板
        vna_controller = self.sub_controllers.get('vna_control')
        if vna_controller and hasattr(vna_controller, 'set_instrument_connected'):
            vna_controller.set_instrument_connected(connected, self.model.instrument_controller)
        
        # 通知ADC采样面板
        adc_controller = self.sub_controllers.get('adc_sampling')
        if adc_controller and hasattr(adc_controller, 'set_instrument_connected'):
            adc_controller.set_instrument_connected(connected, self.model.instrument_controller)
        
        # 通知数据分析面板
        data_analysis_controller = self.sub_controllers.get('data_analysis')
        if data_analysis_controller and hasattr(data_analysis_controller, 'set_instrument_connected'):
            data_analysis_controller.set_instrument_connected(connected, self.model.instrument_controller)
    
    def get_instrument_controller(self):
        """获取仪表控制器"""
        return self.model.instrument_controller
    
    def is_instrument_connected(self):
        """检查仪表是否已连接"""
        return self.model.instrument_connected


    def _setup_progress_panel(self):
        """设置进度面板"""
        # 创建进度面板
        self.progress_controller = create_progress_panel_simple("任务进度监控", self.view)
        
        # 设置到主窗口视图
        self.view.set_progress_panel(self.progress_controller.view)
        
        # 存储到子控制器字典
        self.sub_controllers['progress'] = self.progress_controller
        
        # 初始隐藏进度面板
        self.view.hide_progress_panel()


        
    
    def _setup_progress_connections(self):
        """设置进度相关的信号连接"""
        # 连接ADC采样进度信号
        adc_controller = self.sub_controllers.get('adc_sampling')
        if adc_controller and hasattr(adc_controller, 'samplingProgress'):
            adc_controller.samplingProgress.connect(self._handle_adc_progress)
        
        # 连接数据分析进度信号
        data_analysis_controller = self.sub_controllers.get('data_analysis')
        if data_analysis_controller and hasattr(data_analysis_controller, 'analysisProgress'):
            data_analysis_controller.analysisProgress.connect(self._handle_analysis_progress)
        
        # 连接校准进度信号
        calibration_controller = self.sub_controllers.get('calibration')
        if calibration_controller and hasattr(calibration_controller, 'progress_updated'):
            calibration_controller.progress_updated.connect(self._handle_calibration_progress)
    
    def _handle_adc_progress(self, current, total, message):
        """处理ADC采样进度"""
        progress_id = "adc_sampling"
        label = "ADC数据采集"
        
        # 确保进度条存在
        if not self.progress_controller.get_progress(progress_id):
            self.progress_controller.add_progress_bar(progress_id, label, total)
        
        # 更新进度
        self.progress_controller.update_progress(progress_id, current, total, message)
        
        # 自动显示进度面板
        if not self.view.is_progress_panel_visible():
            self.view.show_progress_panel()
    
    def _handle_analysis_progress(self, current, total, message):
        """处理数据分析进度"""
        progress_id = "data_analysis"
        label = "数据分析处理"
        
        # 确保进度条存在
        if not self.progress_controller.get_progress(progress_id):
            self.progress_controller.add_progress_bar(progress_id, label, total, ProgressBarStyle.GREEN)
        
        # 更新进度
        self.progress_controller.update_progress(progress_id, current, total, message)
        
        # 自动显示进度面板
        if not self.view.is_progress_panel_visible():
            self.view.show_progress_panel()
    
    def _handle_calibration_progress(self, step, progress, needs_confirmation, has_measurement):
        """处理校准进度"""
        progress_id = "calibration"
        label = "网分校准流程"
        
        # 确保进度条存在
        if not self.progress_controller.get_progress(progress_id):
            self.progress_controller.add_progress_bar(progress_id, label, 100, ProgressBarStyle.ORANGE)
        
        # 更新进度
        message = f"执行步骤: {step}"
        if needs_confirmation:
            message += " (等待确认)"
        
        self.progress_controller.update_progress(progress_id, progress, 100, message)
        
        # 自动显示进度面板
        if not self.view.is_progress_panel_visible():
            self.view.show_progress_panel()
    
    def add_custom_progress(self, progress_id, label, total=100, style=ProgressBarStyle.DEFAULT):
        """添加自定义进度条"""
        return self.progress_controller.add_progress_bar(progress_id, label, total, style)
    
    def update_custom_progress(self, progress_id, current, total=None, message=""):
        """更新自定义进度条"""
        success = self.progress_controller.update_progress(progress_id, current, total, message)
        if success and not self.view.is_progress_panel_visible():
            self.view.show_progress_panel()
        return success
    
    def remove_progress(self, progress_id):
        """移除进度条"""
        return self.progress_controller.remove_progress_bar(progress_id)
    
    def clear_all_progress(self):
        """清除所有进度条"""
        self.progress_controller.clear_all()
    
    def show_progress_panel(self):
        """显示进度面板"""
        self.view.show_progress_panel()
    
    def hide_progress_panel(self):
        """隐藏进度面板"""
        self.view.hide_progress_panel()
    
    def toggle_progress_panel(self):
        """切换进度面板显示状态"""
        if self.view.is_progress_panel_visible():
            self.view.hide_progress_panel()
        else:
            self.view.show_progress_panel()