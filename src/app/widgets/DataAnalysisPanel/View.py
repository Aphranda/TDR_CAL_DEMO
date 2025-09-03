# src/app/widgets/DataAnalysisPanel/View.py
from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QGroupBox, 
                             QLabel, QPushButton, QComboBox, QListWidget,
                             QCheckBox, QLineEdit, QTextEdit, QSpinBox, 
                             QProgressBar, QSplitter, QTabWidget, QDoubleSpinBox, 
                             QStackedWidget, QFileDialog, QGridLayout)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QIntValidator

class DataAnalysisView(QWidget):
    def __init__(self):
        super().__init__()
        self.setup_ui()

    def setup_ui(self):
        main_layout = QVBoxLayout()
        main_layout.setSpacing(8)
        main_layout.setContentsMargins(6, 6, 6, 6)

        # # 设置窗口属性以避免递归重绘
        # self.setAttribute(Qt.WA_OpaquePaintEvent)
        # self.setAttribute(Qt.WA_PaintOnScreen)
        
        # 数据文件选择
        file_group = QGroupBox("数据分析")
        file_layout = QVBoxLayout()
        file_layout.setSpacing(6)
        file_layout.setContentsMargins(8, 12, 8, 12)
        
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
        self.analysis_combo.addItems(["ADC数据分析", "S参数", "TDR"])
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
        main_layout.addWidget(file_group)

        # S参数选项
        s_param_widget = self.create_s_parameter_options()
        self.options_stack.addWidget(s_param_widget)
        
        # TDR选项
        tdr_widget = self.create_tdr_options()
        self.options_stack.addWidget(tdr_widget)
        
        # ADC数据分析选项
        adc_analysis_widget = self.create_adc_analysis_options()
        self.options_stack.addWidget(adc_analysis_widget)
        
        # # 进度条
        # self.progress_bar = QProgressBar()
        # self.progress_bar.setVisible(False)
        # main_layout.addWidget(self.progress_bar)
        
        self.setLayout(main_layout)
        
        # 初始显示ADC数据分析选项
        self.options_stack.setCurrentIndex(2)
    
    def create_s_parameter_options(self):
        """创建S参数选项"""
        widget = QWidget()
        layout = QVBoxLayout()
        layout.setSpacing(6)
        layout.setContentsMargins(0, 0, 0, 0)
        
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
        layout.setSpacing(6)
        layout.setContentsMargins(0, 0, 0, 0)
        
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
        layout.setSpacing(5)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # 频率设置
        clock_layout = QHBoxLayout()
        clock_layout.setSpacing(4)
        clock_layout.addWidget(QLabel("时钟频率:"))
        self.adc_clock_freq = QDoubleSpinBox()
        self.adc_clock_freq.setRange(1.0, 1000.0*1e6)
        self.adc_clock_freq.setValue(39538587.77)
        self.adc_clock_freq.setSuffix(" Hz")
        self.adc_clock_freq.setMaximumWidth(250)
        clock_layout.addWidget(self.adc_clock_freq)
        layout.addLayout(clock_layout)
        
        trigger_layout = QHBoxLayout()
        trigger_layout.setSpacing(4)
        trigger_layout.addWidget(QLabel("触发频率:"))
        self.adc_trigger_freq = QDoubleSpinBox()
        self.adc_trigger_freq.setRange(0.1, 100.0*1e6)
        self.adc_trigger_freq.setValue(10000000.0)
        self.adc_trigger_freq.setSuffix(" Hz")
        self.adc_trigger_freq.setMaximumWidth(250)
        trigger_layout.addWidget(self.adc_trigger_freq)
        layout.addLayout(trigger_layout)


        
        # ROI设置 - 修改为QDoubleSpinBox以支持0.1%步进
        roi_layout = QHBoxLayout()
        roi_layout.setSpacing(4)
        roi_layout.addWidget(QLabel("ROI:"))
        
        self.adc_roi_start = QDoubleSpinBox()
        self.adc_roi_start.setRange(0.0, 100.0)
        self.adc_roi_start.setValue(0.0)
        self.adc_roi_start.setSingleStep(0.1)  # 设置最小步进为0.1%
        self.adc_roi_start.setDecimals(1)      # 设置小数位数为1位
        self.adc_roi_start.setSuffix(" %")
        self.adc_roi_start.setMinimumWidth(100)
        self.adc_roi_start.setMaximumWidth(120)
        roi_layout.addWidget(self.adc_roi_start)
        
        self.adc_roi_mid = QDoubleSpinBox()
        self.adc_roi_mid.setRange(0.0, 100.0)
        self.adc_roi_mid.setValue(27.0)
        self.adc_roi_mid.setSingleStep(0.1)    # 设置最小步进为0.1%
        self.adc_roi_mid.setDecimals(1)        # 设置小数位数为1位
        self.adc_roi_mid.setSuffix(" %")
        self.adc_roi_mid.setMinimumWidth(100)
        self.adc_roi_mid.setMaximumWidth(120)
        roi_layout.addWidget(self.adc_roi_mid)
        
        self.adc_roi_end = QDoubleSpinBox()
        self.adc_roi_end.setRange(0.0, 100.0)
        self.adc_roi_end.setValue(100.0)
        self.adc_roi_end.setSingleStep(0.1)    # 设置最小步进为0.1%
        self.adc_roi_end.setDecimals(1)        # 设置小数位数为1位
        self.adc_roi_end.setSuffix(" %")
        self.adc_roi_end.setMinimumWidth(100)
        self.adc_roi_end.setMaximumWidth(120)
        roi_layout.addWidget(self.adc_roi_end)
        layout.addLayout(roi_layout)
        
        # 创建两行网格布局来放置四个控件
        grid_layout = QGridLayout()
        grid_layout.setSpacing(4)
        
        # 第一行：DIFFP 和 SMOTP
        grid_layout.addWidget(QLabel("DIFFP:"), 0, 0)
        self.adc_diff_points = QSpinBox()
        self.adc_diff_points.setRange(1, 1000)
        self.adc_diff_points.setValue(10)
        grid_layout.addWidget(self.adc_diff_points, 0, 1)
        
        grid_layout.addWidget(QLabel("SMOTP:"), 0, 2)
        self.adc_average_points = QSpinBox()
        self.adc_average_points.setRange(1, 1000)
        self.adc_average_points.setValue(1)
        grid_layout.addWidget(self.adc_average_points, 0, 3)
        
        # 第二行：Mode 和 CAL
        grid_layout.addWidget(QLabel("Mode:"), 1, 0)
        self.search_method_combo = QComboBox()
        self.search_method_combo.addItem("Raise", 1)
        self.search_method_combo.addItem("MAX", 2)
        self.search_method_combo.setCurrentIndex(0)
        grid_layout.addWidget(self.search_method_combo, 1, 1)
        
        grid_layout.addWidget(QLabel("CAL:"), 1, 2)
        self.cal_type_combo = QComboBox()
        self.cal_type_combo.addItems(["SHORT", "OPEN", "LOAD", "THRU"])
        self.cal_type_combo.setCurrentIndex(0)
        grid_layout.addWidget(self.cal_type_combo, 1, 3)
        
        # 添加拉伸因子使控件均匀分布
        grid_layout.setColumnStretch(0, 1)
        grid_layout.setColumnStretch(1, 2)
        grid_layout.setColumnStretch(2, 1)
        grid_layout.setColumnStretch(3, 2)
        
        layout.addLayout(grid_layout)
        
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

    
