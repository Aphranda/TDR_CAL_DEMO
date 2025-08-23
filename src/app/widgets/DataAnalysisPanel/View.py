# src/app/widgets/DataAnalysisPanel/View.py
from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QGroupBox, 
                             QLabel, QPushButton, QComboBox, QListWidget,
                             QCheckBox, QLineEdit, QTextEdit, QSpinBox, 
                             QProgressBar, QSplitter, QTabWidget, QDoubleSpinBox, 
                             QStackedWidget, QFileDialog, QGridLayout)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QIntValidator
from ...widgets.PlotWidget import create_plot_widget
import numpy as np

class DataAnalysisView(QWidget):
    def __init__(self):
        super().__init__()
        self.plot_widgets = {}  # 存储绘图部件
        self.plot_controllers = {}  # 新增：存储绘图控制器
        self.main_window_view = None  # 添加main_window_view属性，初始为None
        self.setup_ui()

    def setup_ui(self):
        main_layout = QVBoxLayout()  # 修改：使用垂直布局
        main_layout.setSpacing(8)
        main_layout.setContentsMargins(6, 6, 6, 6)  # 减小主布局边距
        
        # 左侧控制面板
        control_panel = QWidget()
        control_layout = QVBoxLayout()
        control_layout.setSpacing(8)  # 减小整体间距
        control_layout.setContentsMargins(4, 4, 4, 4)  # 减小控制面板边距
        
        # ADC控制部分
        adc_group = QGroupBox("ADC采样控制")
        adc_layout = QVBoxLayout()
        adc_layout.setSpacing(6)  # 减小组内间距
        adc_layout.setContentsMargins(8, 12, 8, 12)  # 减小GroupBox内部边距
        
        # 连接设置
        connect_layout = QHBoxLayout()
        connect_layout.setSpacing(4)  # 减小水平布局间距
        connect_layout.addWidget(QLabel("IP地址:"))
        self.adc_ip_edit = QLineEdit("192.168.1.10")
        self.adc_ip_edit.setPlaceholderText("输入ADC IP地址")
        connect_layout.addWidget(self.adc_ip_edit)

        connect_layout.addWidget(QLabel("端口:"))
        self.adc_port_edit = QLineEdit("15000")
        self.adc_port_edit.setValidator(QIntValidator(0, 32768))
        self.adc_port_edit.setMinimumWidth(100)  # 减小端口输入框宽度
        self.adc_port_edit.setMaximumWidth(120)
        connect_layout.addWidget(self.adc_port_edit)
        adc_layout.addLayout(connect_layout)
        
        # 连接按钮
        button_layout = QHBoxLayout()
        button_layout.setSpacing(4)
        self.connect_button = QPushButton("连接ADC")
        self.disconnect_button = QPushButton("断开连接")
        self.disconnect_button.setEnabled(False)
        button_layout.addWidget(self.connect_button)
        button_layout.addWidget(self.disconnect_button)
        adc_layout.addLayout(button_layout)
        
        # 采样设置
        sample_layout = QHBoxLayout()
        sample_layout.setSpacing(4)
        sample_layout.addWidget(QLabel("采样次数:"))
        self.sample_count_spin = QSpinBox()
        self.sample_count_spin.setRange(1, 1000)
        self.sample_count_spin.setValue(10)
        self.sample_count_spin.setMaximumWidth(70)
        sample_layout.addWidget(self.sample_count_spin)
        sample_layout.addWidget(QLabel("间隔(s):"))
        self.sample_interval_spin = QDoubleSpinBox()
        self.sample_interval_spin.setRange(0.1, 10.0)
        self.sample_interval_spin.setValue(0.1)
        self.sample_interval_spin.setMaximumWidth(70)
        sample_layout.addWidget(self.sample_interval_spin)
        adc_layout.addLayout(sample_layout)
          
        # 新增：文件名设置
        filename_layout = QHBoxLayout()
        filename_layout.setSpacing(4)
        filename_layout.addWidget(QLabel("文件名称:"))
        self.filename_edit = QLineEdit("adc_data")
        self.filename_edit.setPlaceholderText("输入保存的文件名（不含扩展名）")
        filename_layout.addWidget(self.filename_edit)
        adc_layout.addLayout(filename_layout)

        # 新增：输出目录设置
        output_dir_layout = QHBoxLayout()
        output_dir_layout.setSpacing(4)
        output_dir_layout.addWidget(QLabel("输出目录:"))
        self.output_dir_edit = QLineEdit("data\\results\\test")
        self.output_dir_edit.setPlaceholderText("选择输出目录")
        output_dir_layout.addWidget(self.output_dir_edit)
        
        self.browse_dir_button = QPushButton("浏览")
        self.browse_dir_button.setMinimumWidth(60)
        output_dir_layout.addWidget(self.browse_dir_button)
        adc_layout.addLayout(output_dir_layout)

        # 采样按钮
        self.sample_button = QPushButton("开始采样")
        self.sample_button.setEnabled(False)
        adc_layout.addWidget(self.sample_button)
        
        adc_group.setLayout(adc_layout)
        control_layout.addWidget(adc_group)
        
        # 数据文件选择 - 修改这个GroupBox
        file_group = QGroupBox("数据分析")
        file_layout = QVBoxLayout()
        file_layout.setSpacing(6)  # 减小组内间距
        file_layout.setContentsMargins(8, 12, 8, 12)  # 减小GroupBox内部边距
        
        # 文件操作按钮
        file_control_layout = QHBoxLayout()
        file_control_layout.setSpacing(4)
        self.load_button = QPushButton("加载文件")
        self.clear_button = QPushButton("清除列表")
        file_control_layout.addWidget(self.load_button)
        file_control_layout.addWidget(self.clear_button)
        file_layout.addLayout(file_control_layout)
        
        # 文件列表
        self.file_list = QListWidget()
        self.file_list.setMaximumHeight(100)
        file_layout.addWidget(self.file_list)
        
        # 分析类型选择
        file_layout.addWidget(QLabel("分析类型:"))
        self.analysis_combo = QComboBox()
        self.analysis_combo.addItems(["ADC数据分析","S参数", "TDR"])
        file_layout.addWidget(self.analysis_combo)
        
        # 分析选项堆叠窗口
        self.options_stack = QStackedWidget()
        file_layout.addWidget(self.options_stack)
        
        # 分析按钮
        button_layout = QHBoxLayout()
        button_layout.setSpacing(4)
        self.analyze_button = QPushButton("开始分析")
        self.export_button = QPushButton("导出结果")
        button_layout.addWidget(self.analyze_button)
        button_layout.addWidget(self.export_button)
        file_layout.addLayout(button_layout)
        
        file_group.setLayout(file_layout)
        control_layout.addWidget(file_group)

        # S参数选项
        s_param_widget = self.create_s_parameter_options()
        self.options_stack.addWidget(s_param_widget)
        
        # TDR选项
        tdr_widget = self.create_tdr_options()
        self.options_stack.addWidget(tdr_widget)
        
        # ADC数据分析选项
        adc_analysis_widget = self.create_adc_analysis_options()
        self.options_stack.addWidget(adc_analysis_widget)
        
        control_panel.setLayout(control_layout)
        
        # 删除右侧结果显示区域，只保留控制面板
        main_layout.addWidget(control_panel)
        
        # 添加公用进度条到最外层底部
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        main_layout.addWidget(self.progress_bar)
        
        self.setLayout(main_layout)
        
        # 初始显示ADC数据分析选项
        self.options_stack.setCurrentIndex(2)
        
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
        layout.setContentsMargins(0, 0, 0, 0)  # 移除内部边距
        
        # 频率范围设置
        freq_layout = QHBoxLayout()
        freq_layout.setSpacing(4)
        freq_layout.addWidget(QLabel("起始频率:"))
        self.s_start_freq = QDoubleSpinBox()
        self.s_start_freq.setRange(0.1, 50.0)
        self.s_start_freq.setValue(0.1)
        self.s_start_freq.setSuffix(" GHz")
        self.s_start_freq.setMaximumWidth(100)
        freq_layout.addWidget(self.s_start_freq)
        
        freq_layout.addWidget(QLabel("终止频率:"))
        self.s_stop_freq = QDoubleSpinBox()
        self.s_stop_freq.setRange(0.1, 50.0)
        self.s_stop_freq.setValue(10.0)
        self.s_stop_freq.setSuffix(" GHz")
        self.s_stop_freq.setMaximumWidth(100)
        freq_layout.addWidget(self.s_stop_freq)
        layout.addLayout(freq_layout)
        
        # 点数设置
        points_layout = QHBoxLayout()
        points_layout.setSpacing(4)
        points_layout.addWidget(QLabel("扫描点数:"))
        self.s_points = QSpinBox()
        self.s_points.setRange(101, 10001)
        self.s_points.setValue(201)
        self.s_points.setMaximumWidth(80)
        points_layout.addWidget(self.s_points)
        
        points_layout.addStretch()
        
        # 添加IF带宽设置
        points_layout.addWidget(QLabel("IF带宽:"))
        self.s_if_bw = QDoubleSpinBox()
        self.s_if_bw.setRange(1.0, 10000.0)
        self.s_if_bw.setValue(1000.0)
        self.s_if_bw.setSuffix(" Hz")
        self.s_if_bw.setMaximumWidth(80)
        points_layout.addWidget(self.s_if_bw)
        
        layout.addLayout(points_layout)
        
        # 校准设置
        cal_layout = QHBoxLayout()
        cal_layout.setSpacing(4)
        self.s_use_calibration = QCheckBox("使用校准文件")
        self.s_use_calibration.setChecked(True)
        cal_layout.addWidget(self.s_use_calibration)
        
        self.s_cal_file_button = QPushButton("选择校准文件")
        self.s_cal_file_button.setMaximumWidth(100)
        cal_layout.addWidget(self.s_cal_file_button)
        
        layout.addLayout(cal_layout)
        
        widget.setLayout(layout)
        return widget
    
    def create_tdr_options(self):
        """创建TDR选项"""
        widget = QWidget()
        layout = QVBoxLayout()
        layout.setSpacing(6)  # 减小组间间距
        layout.setContentsMargins(0, 0, 0, 0)  # 移除内部边距
        
        # 时间范围设置
        time_layout = QHBoxLayout()
        time_layout.setSpacing(4)
        time_layout.addWidget(QLabel("时间范围:"))
        self.tdr_time_range = QDoubleSpinBox()
        self.tdr_time_range.setRange(1.0, 1000.0)
        self.tdr_time_range.setValue(10.0)
        self.tdr_time_range.setSuffix(" ns")
        self.tdr_time_range.setMaximumWidth(100)
        time_layout.addWidget(self.tdr_time_range)
        layout.addLayout(time_layout)
        
        # 阻抗设置
        imp_layout = QHBoxLayout()
        imp_layout.setSpacing(4)
        imp_layout.addWidget(QLabel("参考阻抗:"))
        self.tdr_ref_impedance = QDoubleSpinBox()
        self.tdr_ref_impedance.setRange(1.0, 1000.0)
        self.tdr_ref_impedance.setValue(50.0)
        self.tdr_ref_impedance.setSuffix(" Ω")
        self.tdr_ref_impedance.setMaximumWidth(100)
        imp_layout.addWidget(self.tdr_ref_impedance)
        layout.addLayout(imp_layout)
        
        widget.setLayout(layout)
        return widget
    
    def create_adc_analysis_options(self):
        """创建ADC数据分析选项"""
        widget = QWidget()
        layout = QVBoxLayout()
        layout.setSpacing(6)  # 减小组间间距
        layout.setContentsMargins(0, 0, 0, 0)  # 移除内部边距
        
        # 频率设置
        clock_layout = QHBoxLayout()
        clock_layout.setSpacing(4)
        clock_layout.addWidget(QLabel("时钟频率:"))
        self.adc_clock_freq = QDoubleSpinBox()
        self.adc_clock_freq.setRange(1.0, 1000.0*1e6)
        self.adc_clock_freq.setValue(39538587.77)
        self.adc_clock_freq.setSuffix(" Hz")
        self.adc_clock_freq.setMaximumWidth(120)
        clock_layout.addWidget(self.adc_clock_freq)
        layout.addLayout(clock_layout)
        
        trigger_layout = QHBoxLayout()
        trigger_layout.setSpacing(4)
        trigger_layout.addWidget(QLabel("触发频率:"))
        self.adc_trigger_freq = QDoubleSpinBox()
        self.adc_trigger_freq.setRange(0.1, 100.0*1e6)
        self.adc_trigger_freq.setValue(10000000.0)
        self.adc_trigger_freq.setSuffix(" Hz")
        self.adc_trigger_freq.setMaximumWidth(120)
        trigger_layout.addWidget(self.adc_trigger_freq)
        layout.addLayout(trigger_layout)
        
        # ROI设置
        roi_layout = QHBoxLayout()
        roi_layout.setSpacing(4)
        roi_layout.addWidget(QLabel("ROI范围:"))
        self.adc_roi_start = QSpinBox()
        self.adc_roi_start.setRange(0, 100)
        self.adc_roi_start.setValue(20)
        self.adc_roi_start.setSuffix(" %")
        self.adc_roi_start.setMaximumWidth(60)
        roi_layout.addWidget(self.adc_roi_start)
        
        roi_layout.addWidget(QLabel("-"))
        
        self.adc_roi_end = QSpinBox()
        self.adc_roi_end.setRange(0, 100)
        self.adc_roi_end.setValue(30)
        self.adc_roi_end.setSuffix(" %")
        self.adc_roi_end.setMaximumWidth(60)
        roi_layout.addWidget(self.adc_roi_end)
        layout.addLayout(roi_layout)
        
        # 选项
        options_layout = QHBoxLayout()
        options_layout.setSpacing(4)

        # 添加SearchMethod下拉框
        options_layout.addWidget(QLabel("Mode:"))
        self.search_method_combo = QComboBox()
        self.search_method_combo.addItem("Raise", 1)
        self.search_method_combo.addItem("MAX", 2)
        self.search_method_combo.setCurrentIndex(0)
        options_layout.addWidget(self.search_method_combo)
        
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
        else:
            self.connect_button.setText("连接ADC")
    
    def update_sampling_progress(self, current: int, total: int, message: str = ""):
        """更新采样进度"""
        self.progress_bar.setVisible(True)
        self.progress_bar.setMaximum(total)
        self.progress_bar.setValue(current)
