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
        
        # 文件载入部分
        file_group = QGroupBox("文件载入")
        file_layout = QVBoxLayout()
        file_layout.setSpacing(6)
        file_layout.setContentsMargins(8, 12, 8, 12)
        
        # 文件操作按钮
        file_control_layout = QHBoxLayout()
        file_control_layout.setSpacing(4)
        self.load_button = QPushButton("加载文件")
        self.clear_button = QPushButton("清除列表")
        self.clear_plot = QPushButton("清除绘图")
        file_control_layout.addWidget(self.load_button)
        file_control_layout.addWidget(self.clear_button)
        file_control_layout.addWidget(self.clear_plot)
        file_layout.addLayout(file_control_layout)
        
        # 文件列表
        self.file_list = QListWidget()
        self.file_list.setMaximumHeight(100)
        file_layout.addWidget(self.file_list)
        
        file_group.setLayout(file_layout)
        main_layout.addWidget(file_group)
        
        # 分析设置部分
        analysis_group = QGroupBox("分析设置")
        analysis_layout = QVBoxLayout()
        analysis_layout.setSpacing(6)
        analysis_layout.setContentsMargins(8, 12, 8, 12)
        
        # 添加ADC数据分析选项
        adc_analysis_widget = self.create_adc_analysis_options()
        analysis_layout.addWidget(adc_analysis_widget)
        
        # 分析按钮
        button_layout = QHBoxLayout()
        button_layout.setSpacing(4)
        self.analyze_button = QPushButton("开始分析")
        self.export_button = QPushButton("导出结果")
        button_layout.addWidget(self.analyze_button)
        button_layout.addWidget(self.export_button)
        analysis_layout.addLayout(button_layout)
        
        analysis_group.setLayout(analysis_layout)
        main_layout.addWidget(analysis_group)
        
        self.setLayout(main_layout)

    
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
        
        # 新增：最大读取大小设置
        max_read_layout = QHBoxLayout()
        max_read_layout.setSpacing(4)
        max_read_layout.addWidget(QLabel("读取段数:"))
        self.adc_max_read_size = QSpinBox()
        self.adc_max_read_size.setRange(1, 1000)
        self.adc_max_read_size.setValue(100)
        self.adc_max_read_size.setSingleStep(1)
        self.adc_max_read_size.setMaximumWidth(120)
        max_read_layout.addWidget(self.adc_max_read_size)
        
        # 添加读取位数选择
        max_read_layout.addWidget(QLabel("读取位数:"))
        self.adc_bit_width_combo = QComboBox()
        self.adc_bit_width_combo.addItems(["20", "18", "16", "14"])
        self.adc_bit_width_combo.setCurrentText("20")
        self.adc_bit_width_combo.setToolTip("选择ADC数据的有效位数")
        self.adc_bit_width_combo.setMaximumWidth(100)
        max_read_layout.addWidget(self.adc_bit_width_combo)
        
        layout.addLayout(max_read_layout)
        
        # ROI设置
        roi_layout = QHBoxLayout()
        roi_layout.setSpacing(4)
        roi_layout.addWidget(QLabel("ROI:"))
        
        self.adc_roi_start = QDoubleSpinBox()
        self.adc_roi_start.setRange(0.0, 100.0)
        self.adc_roi_start.setValue(24)
        self.adc_roi_start.setSingleStep(0.1)
        self.adc_roi_start.setDecimals(1)
        self.adc_roi_start.setSuffix(" %")
        self.adc_roi_start.setMinimumWidth(100)
        self.adc_roi_start.setMaximumWidth(120)
        roi_layout.addWidget(self.adc_roi_start)
        
        self.adc_roi_mid = QDoubleSpinBox()
        self.adc_roi_mid.setRange(0.0, 100.0)
        self.adc_roi_mid.setValue(25.0)
        self.adc_roi_mid.setSingleStep(0.1)
        self.adc_roi_mid.setDecimals(1)
        self.adc_roi_mid.setSuffix(" %")
        self.adc_roi_mid.setMinimumWidth(100)
        self.adc_roi_mid.setMaximumWidth(120)
        roi_layout.addWidget(self.adc_roi_mid)
        
        self.adc_roi_end = QDoubleSpinBox()
        self.adc_roi_end.setRange(0.0, 100.0)
        self.adc_roi_end.setValue(26.0)
        self.adc_roi_end.setSingleStep(0.1)
        self.adc_roi_end.setDecimals(1)
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
        
        # 第二行：AlignMode 和 AlignPos
        grid_layout.addWidget(QLabel("AlignMode:"), 1, 0)
        self.alignment_combo = QComboBox()
        self.alignment_combo.addItems(["ADC1", "ADC2"])
        self.alignment_combo.setCurrentText("ADC1")
        self.alignment_combo.setToolTip("选择双通道重新对齐的参考通道")
        self.alignment_combo.setMaximumWidth(120)
        grid_layout.addWidget(self.alignment_combo, 1, 1)
        
        grid_layout.addWidget(QLabel("AlignPos:"), 1, 2)
        self.align_pos_spin = QDoubleSpinBox()
        self.align_pos_spin.setRange(0.0, 100.0)
        self.align_pos_spin.setValue(25.0)  # 默认值25%
        self.align_pos_spin.setSingleStep(0.1)
        self.align_pos_spin.setDecimals(1)
        self.align_pos_spin.setSuffix(" %")
        self.align_pos_spin.setMaximumWidth(120)
        self.align_pos_spin.setToolTip("设置对齐位置百分比")
        grid_layout.addWidget(self.align_pos_spin, 1, 3)
        
        # 添加拉伸因子使控件均匀分布
        grid_layout.setColumnStretch(0, 1)
        grid_layout.setColumnStretch(1, 2)
        grid_layout.setColumnStretch(2, 1)
        grid_layout.setColumnStretch(3, 2)
        
        layout.addLayout(grid_layout)
        
        widget.setLayout(layout)
        return widget

    def get_alignment_reference(self) -> str:
        """获取对齐参考通道"""
        return self.alignment_combo.currentText().lower()

    def get_selected_bit_width(self) -> int:
        """获取选中的读取位数"""
        bit_width_text = self.adc_bit_width_combo.currentText()
        if bit_width_text == "20":
            return 20
        elif bit_width_text == "18":
            return 18
        elif bit_width_text == "16":
            return 16
        elif bit_width_text == "14":
            return 14
        return 20  # 默认返回20位
