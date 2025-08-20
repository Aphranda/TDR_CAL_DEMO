# src/app/widgets/DataAnalysisPanel/View.py
from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QGroupBox, 
                             QLabel, QPushButton, QComboBox, QListWidget,
                             QCheckBox, QLineEdit, QTextEdit, QSpinBox, 
                             QProgressBar, QSplitter, QTabWidget, QDoubleSpinBox, 
                             QStackedWidget, QFileDialog)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QIntValidator

class DataAnalysisView(QWidget):
    def __init__(self):
        super().__init__()
        self.setup_ui()
    
    def setup_ui(self):
        main_layout = QHBoxLayout()
        
        # 左侧控制面板
        control_panel = QWidget()
        control_layout = QVBoxLayout()
        control_layout.setSpacing(8)  # 减小整体间距
        
        # ADC控制部分
        adc_group = QGroupBox("ADC采样控制")
        adc_layout = QVBoxLayout()
        adc_layout.setSpacing(6)  # 减小组内间距
        
        # 连接设置
        connect_layout = QHBoxLayout()
        connect_layout.addWidget(QLabel("IP地址:"))
        self.adc_ip_edit = QLineEdit("192.168.1.10")
        self.adc_ip_edit.setPlaceholderText("输入ADC IP地址")
        connect_layout.addWidget(self.adc_ip_edit)

        connect_layout.addWidget(QLabel("端口:"))
        self.adc_port_edit = QLineEdit("15000")
        self.adc_port_edit.setValidator(QIntValidator(1000, 65535))
        self.adc_port_edit.setMaximumWidth(80)
        connect_layout.addWidget(self.adc_port_edit)
        adc_layout.addLayout(connect_layout)
        
        # 连接按钮
        button_layout = QHBoxLayout()
        self.connect_button = QPushButton("连接ADC")
        self.disconnect_button = QPushButton("断开连接")
        self.disconnect_button.setEnabled(False)
        button_layout.addWidget(self.connect_button)
        button_layout.addWidget(self.disconnect_button)
        adc_layout.addLayout(button_layout)
        
        # 采样设置
        sample_layout = QHBoxLayout()
        sample_layout.addWidget(QLabel("采样次数:"))
        self.sample_count_spin = QSpinBox()
        self.sample_count_spin.setRange(1, 1000)
        self.sample_count_spin.setValue(10)
        sample_layout.addWidget(self.sample_count_spin)
        sample_layout.addWidget(QLabel("间隔(s):"))
        self.sample_interval_spin = QDoubleSpinBox()
        self.sample_interval_spin.setRange(0.1, 10.0)
        self.sample_interval_spin.setValue(0.1)
        sample_layout.addWidget(self.sample_interval_spin)
        adc_layout.addLayout(sample_layout)
        
        # 采样按钮
        self.sample_button = QPushButton("开始采样")
        self.sample_button.setEnabled(False)
        adc_layout.addWidget(self.sample_button)
        
        # 进度条
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        adc_layout.addWidget(self.progress_bar)
        
        adc_group.setLayout(adc_layout)
        control_layout.addWidget(adc_group)
        
        # 数据文件选择 - 修改这个GroupBox
        file_group = QGroupBox("数据文件")
        file_layout = QVBoxLayout()
        file_layout.setSpacing(6)  # 减小组内间距
        
        # 文件操作按钮
        file_control_layout = QHBoxLayout()
        self.load_button = QPushButton("加载文件")
        self.clear_button = QPushButton("清除列表")
        file_control_layout.addWidget(self.load_button)
        file_control_layout.addWidget(self.clear_button)
        file_layout.addLayout(file_control_layout)
        
        # 文件列表
        self.file_list = QListWidget()
        self.file_list.setMaximumHeight(100)
        file_layout.addWidget(self.file_list)
        
        # 新增：数据保存选项
        save_layout = QHBoxLayout()
        self.save_raw_check = QCheckBox("保存原始数据")
        self.save_raw_check.setChecked(True)
        save_layout.addWidget(self.save_raw_check)
        file_layout.addLayout(save_layout)
        
        # 新增：输出目录设置
        output_dir_layout = QHBoxLayout()
        output_dir_layout.addWidget(QLabel("输出目录:"))
        self.output_dir_edit = QLineEdit("CSV_Data_test_results")
        self.output_dir_edit.setPlaceholderText("选择输出目录")
        output_dir_layout.addWidget(self.output_dir_edit)
        
        self.browse_dir_button = QPushButton("浏览")
        self.browse_dir_button.setMinimumWidth(80)
        output_dir_layout.addWidget(self.browse_dir_button)
        file_layout.addLayout(output_dir_layout)
        
        file_group.setLayout(file_layout)
        control_layout.addWidget(file_group)
        
        # 数据分析类型选择
        type_group = QGroupBox("分析类型")
        type_layout = QVBoxLayout()
        type_layout.setSpacing(6)  # 减小组内间距
        
        self.analysis_combo = QComboBox()
        self.analysis_combo.addItems(["S参数", "TDR", "ADC数据分析"])
        type_layout.addWidget(self.analysis_combo)
        
        # 分析选项堆叠窗口
        self.options_stack = QStackedWidget()
        type_layout.addWidget(self.options_stack)
        
        type_group.setLayout(type_layout)
        control_layout.addWidget(type_group)

        # S参数选项
        s_param_widget = self.create_s_parameter_options()
        self.options_stack.addWidget(s_param_widget)
        
        # TDR选项
        tdr_widget = self.create_tdr_options()
        self.options_stack.addWidget(tdr_widget)
        
        # ADC数据分析选项
        adc_analysis_widget = self.create_adc_analysis_options()
        self.options_stack.addWidget(adc_analysis_widget)
        
        # 分析按钮
        button_layout = QHBoxLayout()
        self.analyze_button = QPushButton("开始分析")
        self.export_button = QPushButton("导出结果")
        button_layout.addWidget(self.analyze_button)
        button_layout.addWidget(self.export_button)
        control_layout.addLayout(button_layout)
        
        control_panel.setLayout(control_layout)
        
        # 右侧结果显示区域
        result_tabs = QTabWidget()
        
        # 文本结果标签
        self.result_text = QTextEdit()
        self.result_text.setReadOnly(True)
        result_tabs.addTab(self.result_text, "分析结果")
        
        # 统计信息标签
        self.stats_text = QTextEdit()
        self.stats_text.setReadOnly(True)
        result_tabs.addTab(self.stats_text, "统计信息")
        
        # 配置信息标签
        self.config_text = QTextEdit()
        self.config_text.setReadOnly(True)
        result_tabs.addTab(self.config_text, "配置信息")
        
        # 使用垂直分割器
        splitter = QSplitter(Qt.Vertical)
        splitter.addWidget(control_panel)
        splitter.addWidget(result_tabs)
        splitter.setSizes([400, 600])  # 调整分割比例
        
        main_layout.addWidget(splitter)
        self.setLayout(main_layout)
        
        # 初始显示S参数选项
        self.options_stack.setCurrentIndex(0)
        
        # 连接浏览目录按钮
        self.browse_dir_button.clicked.connect(self.on_browse_directory)
    
    def on_browse_directory(self):
        """浏览选择输出目录"""
        directory = QFileDialog.getExistingDirectory(
            self, 
            "选择输出目录",
            self.output_dir_edit.text() or "."
        )
        if directory:
            self.output_dir_edit.setText(directory)
    
    def create_s_parameter_options(self):
        """创建S参数选项"""
        widget = QWidget()
        layout = QVBoxLayout()
        layout.setSpacing(6)  # 减小组间间距
        
        # 频率范围设置
        freq_layout = QHBoxLayout()
        freq_layout.addWidget(QLabel("起始频率:"))
        self.s_start_freq = QDoubleSpinBox()
        self.s_start_freq.setRange(0.1, 50.0)
        self.s_start_freq.setValue(0.1)
        self.s_start_freq.setSuffix(" GHz")
        freq_layout.addWidget(self.s_start_freq)
        
        freq_layout.addWidget(QLabel("终止频率:"))
        self.s_stop_freq = QDoubleSpinBox()
        self.s_stop_freq.setRange(0.1, 50.0)
        self.s_stop_freq.setValue(10.0)
        self.s_stop_freq.setSuffix(" GHz")
        freq_layout.addWidget(self.s_stop_freq)
        layout.addLayout(freq_layout)
        
        # 点数设置
        points_layout = QHBoxLayout()
        points_layout.addWidget(QLabel("扫描点数:"))
        self.s_points = QSpinBox()
        self.s_points.setRange(101, 10001)
        self.s_points.setValue(201)
        points_layout.addWidget(self.s_points)
        
        points_layout.addStretch()
        
        # 添加IF带宽设置
        points_layout.addWidget(QLabel("IF带宽:"))
        self.s_if_bw = QDoubleSpinBox()
        self.s_if_bw.setRange(1.0, 10000.0)
        self.s_if_bw.setValue(1000.0)
        self.s_if_bw.setSuffix(" Hz")
        self.s_if_bw.setMaximumWidth(100)
        points_layout.addWidget(self.s_if_bw)
        
        layout.addLayout(points_layout)
        
        # 校准设置
        cal_layout = QHBoxLayout()
        self.s_use_calibration = QCheckBox("使用校准文件")
        self.s_use_calibration.setChecked(True)
        cal_layout.addWidget(self.s_use_calibration)
        
        self.s_cal_file_button = QPushButton("选择校准文件")
        self.s_cal_file_button.setMaximumWidth(120)
        cal_layout.addWidget(self.s_cal_file_button)
        
        layout.addLayout(cal_layout)
        
        widget.setLayout(layout)
        return widget
    
    def create_tdr_options(self):
        """创建TDR选项"""
        widget = QWidget()
        layout = QVBoxLayout()
        layout.setSpacing(6)  # 减小组间间距
        
        # 时间范围设置
        time_layout = QHBoxLayout()
        time_layout.addWidget(QLabel("时间范围:"))
        self.tdr_time_range = QDoubleSpinBox()
        self.tdr_time_range.setRange(1.0, 1000.0)
        self.tdr_time_range.setValue(10.0)
        self.tdr_time_range.setSuffix(" ns")
        time_layout.addWidget(self.tdr_time_range)
        layout.addLayout(time_layout)
        
        # 阻抗设置
        imp_layout = QHBoxLayout()
        imp_layout.addWidget(QLabel("参考阻抗:"))
        self.tdr_ref_impedance = QDoubleSpinBox()
        self.tdr_ref_impedance.setRange(1.0, 1000.0)
        self.tdr_ref_impedance.setValue(50.0)
        self.tdr_ref_impedance.setSuffix(" Ω")
        imp_layout.addWidget(self.tdr_ref_impedance)
        layout.addLayout(imp_layout)
        
        widget.setLayout(layout)
        return widget
    
    def create_adc_analysis_options(self):
        """创建ADC数据分析选项"""
        widget = QWidget()
        layout = QVBoxLayout()
        layout.setSpacing(6)  # 减小组间间距
        
        # 频率设置
        clock_layout = QHBoxLayout()
        clock_layout.addWidget(QLabel("时钟频率:"))
        self.adc_clock_freq = QDoubleSpinBox()
        self.adc_clock_freq.setRange(1.0, 1000.0)
        self.adc_clock_freq.setValue(39.54)
        self.adc_clock_freq.setSuffix(" MHz")
        clock_layout.addWidget(self.adc_clock_freq)
        layout.addLayout(clock_layout)
        
        trigger_layout = QHBoxLayout()
        trigger_layout.addWidget(QLabel("触发频率:"))
        self.adc_trigger_freq = QDoubleSpinBox()
        self.adc_trigger_freq.setRange(0.1, 100.0)
        self.adc_trigger_freq.setValue(10.0)
        self.adc_trigger_freq.setSuffix(" MHz")
        trigger_layout.addWidget(self.adc_trigger_freq)
        layout.addLayout(trigger_layout)
        
        # ROI设置
        roi_layout = QHBoxLayout()
        roi_layout.addWidget(QLabel("ROI范围:"))
        self.adc_roi_start = QSpinBox()
        self.adc_roi_start.setRange(0, 100)
        self.adc_roi_start.setValue(20)
        self.adc_roi_start.setSuffix(" %")
        roi_layout.addWidget(self.adc_roi_start)
        
        roi_layout.addWidget(QLabel("-"))
        
        self.adc_roi_end = QSpinBox()
        self.adc_roi_end.setRange(0, 100)
        self.adc_roi_end.setValue(30)
        self.adc_roi_end.setSuffix(" %")
        roi_layout.addWidget(self.adc_roi_end)
        layout.addLayout(roi_layout)
        
        # 选项
        options_layout = QHBoxLayout()
        self.adc_recursive_check = QCheckBox("递归搜索子目录")
        self.adc_recursive_check.setChecked(True)
        options_layout.addWidget(self.adc_recursive_check)
        
        self.adc_signed_check = QCheckBox("使用有符号18位")
        self.adc_signed_check.setChecked(True)
        options_layout.addWidget(self.adc_signed_check)
        layout.addLayout(options_layout)
        
        widget.setLayout(layout)
        return widget
    
    def show_s_parameter_options(self):
        """显示S参数选项"""
        self.options_stack.setCurrentIndex(0)
    
    def show_tdr_options(self):
        """显示TDR选项"""
        self.options_stack.setCurrentIndex(1)
    
    def show_adc_analysis_options(self):
        """显示ADC数据分析选项"""
        self.options_stack.setCurrentIndex(2)
    
    def update_adc_connection_status(self, connected: bool, message: str = ""):
        """更新ADC连接状态"""
        self.connect_button.setEnabled(not connected)
        self.disconnect_button.setEnabled(connected)
        self.sample_button.setEnabled(connected)
        
        if connected:
            self.connect_button.setText("已连接")
            status_text = f"ADC连接成功: {message}"
        else:
            self.connect_button.setText("连接ADC")
            status_text = f"ADC断开连接: {message}"
        
        self.append_result_text(status_text)
    
    def update_sampling_progress(self, current: int, total: int, message: str = ""):
        """更新采样进度"""
        self.progress_bar.setVisible(True)
        self.progress_bar.setMaximum(total)
        self.progress_bar.setValue(current)
        
        if message:
            self.append_result_text(f"采样进度: {current}/{total} - {message}")
    
    def append_result_text(self, text: str):
        """添加结果文本"""
        self.result_text.append(text)
    
    def append_stats_text(self, text: str):
        """添加统计文本"""
        self.stats_text.append(text)
    
    def append_config_text(self, text: str):
        """添加配置文本"""
        self.config_text.append(text)
    
    def clear_all_text(self):
        """清除所有文本"""
        self.result_text.clear()
        self.stats_text.clear()
        self.config_text.clear()
    
    def display_analysis_results(self, results: dict):
        """显示分析结果"""
        self.clear_all_text()
        
        # 显示结果
        self.result_text.append("分析结果:")
        self.result_text.append("=" * 50)
        for key, value in results.items():
            self.result_text.append(f"{key}: {value}")
    
    def display_adc_analysis_results(self, results: dict, stats: dict):
        """显示ADC分析结果"""
        self.clear_all_text()
        
        # 显示结果
        self.result_text.append("ADC数据分析结果:")
        self.result_text.append("=" * 50)
        for key, value in results.items():
            self.result_text.append(f"{key}: {value}")
        
        # 显示统计信息
        self.stats_text.append("统计信息:")
        self.stats_text.append("=" * 50)
        for key, value in stats.items():
            if isinstance(value, dict):
                self.stats_text.append(f"{key}:")
                for k, v in value.items():
                    self.stats_text.append(f"  {k}: {v}")
            else:
                self.stats_text.append(f"{key}: {value}")
        
        # 显示配置信息
        self.config_text.append("分析配置:")
        self.config_text.append("=" * 50)
        self.config_text.append(f"时钟频率: {self.adc_clock_freq.value()} MHz")
        self.config_text.append(f"触发频率: {self.adc_trigger_freq.value()} MHz")
        self.config_text.append(f"ROI范围: {self.adc_roi_start.value()}%-{self.adc_roi_end.value()}%")
        self.config_text.append(f"递归搜索: {'是' if self.adc_recursive_check.isChecked() else '否'}")
        self.config_text.append(f"有符号18位: {'是' if self.adc_signed_check.isChecked() else '否'}")
