# src/app/widgets/VNAControlPanel/View.py
from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QGroupBox, 
                             QLabel, QLineEdit, QPushButton, QComboBox, QSpinBox,
                             QDoubleSpinBox)
from PyQt5.QtCore import Qt

class VNAControlView(QWidget):
    def __init__(self):
        super().__init__()
        self.setup_ui()
    
    def setup_ui(self):
        layout = QVBoxLayout()
        layout.setSpacing(8)  # 减小整体间距
        layout.setContentsMargins(6, 6, 6, 6)  # 减小主布局边距
        
        # 频率设置组
        freq_group = QGroupBox("频率设置")
        freq_layout = QVBoxLayout()
        freq_layout.setSpacing(6)  # 减小组内间距
        freq_layout.setContentsMargins(8, 12, 8, 12)  # 减小GroupBox内部边距
        
        # 起始频率
        start_freq_layout = QHBoxLayout()
        start_freq_layout.setSpacing(4)  # 减小水平布局间距
        start_freq_layout.addWidget(QLabel("起始频率:"))
        self.start_freq_edit = QLineEdit("1e6")
        self.start_freq_edit.setPlaceholderText("Hz")
        self.start_freq_edit.setMaximumWidth(120)  # 限制输入框宽度
        start_freq_layout.addWidget(self.start_freq_edit)
        start_freq_layout.addWidget(QLabel("Hz"))
        freq_layout.addLayout(start_freq_layout)
        
        # 终止频率
        stop_freq_layout = QHBoxLayout()
        stop_freq_layout.setSpacing(4)
        stop_freq_layout.addWidget(QLabel("终止频率:"))
        self.stop_freq_edit = QLineEdit("3e9")
        self.stop_freq_edit.setPlaceholderText("Hz")
        self.stop_freq_edit.setMaximumWidth(120)
        stop_freq_layout.addWidget(self.stop_freq_edit)
        stop_freq_layout.addWidget(QLabel("Hz"))
        freq_layout.addLayout(stop_freq_layout)
        
        # 点数
        points_layout = QHBoxLayout()
        points_layout.setSpacing(4)
        points_layout.addWidget(QLabel("点数:"))
        self.points_spin = QSpinBox()
        self.points_spin.setRange(2, 10001)
        self.points_spin.setValue(201)
        self.points_spin.setMaximumWidth(80)  # 限制下拉框宽度
        points_layout.addWidget(self.points_spin)
        freq_layout.addLayout(points_layout)
        
        freq_group.setLayout(freq_layout)
        layout.addWidget(freq_group)
        
        # 功率设置组
        power_group = QGroupBox("功率设置")
        power_layout = QVBoxLayout()
        power_layout.setSpacing(6)
        power_layout.setContentsMargins(8, 12, 8, 12)
        
        power_set_layout = QHBoxLayout()
        power_set_layout.setSpacing(4)
        power_set_layout.addWidget(QLabel("输出功率:"))
        self.power_edit = QLineEdit("0")
        self.power_edit.setPlaceholderText("dBm")
        self.power_edit.setMaximumWidth(80)
        power_set_layout.addWidget(self.power_edit)
        power_set_layout.addWidget(QLabel("dBm"))
        power_layout.addLayout(power_set_layout)
        
        power_group.setLayout(power_layout)
        layout.addWidget(power_group)
        
        # IF带宽设置
        if_group = QGroupBox("IF带宽")
        if_layout = QVBoxLayout()
        if_layout.setSpacing(6)
        if_layout.setContentsMargins(8, 12, 8, 12)
        
        if_set_layout = QHBoxLayout()
        if_set_layout.setSpacing(4)
        if_set_layout.addWidget(QLabel("IF带宽:"))
        self.if_bw_combo = QComboBox()
        self.if_bw_combo.addItems(["10", "100", "1000", "10000"])
        self.if_bw_combo.setCurrentText("1000")
        self.if_bw_combo.setMaximumWidth(80)  # 限制下拉框宽度
        if_set_layout.addWidget(self.if_bw_combo)
        if_set_layout.addWidget(QLabel("Hz"))
        if_layout.addLayout(if_set_layout)
        
        if_group.setLayout(if_layout)
        layout.addWidget(if_group)
        
        # 控制按钮
        button_layout = QHBoxLayout()
        button_layout.setSpacing(4)
        self.sweep_button = QPushButton("开始扫描")
        self.stop_button = QPushButton("停止扫描")
        self.save_button = QPushButton("保存数据")
        
        button_layout.addWidget(self.sweep_button)
        button_layout.addWidget(self.stop_button)
        button_layout.addWidget(self.save_button)
        
        layout.addLayout(button_layout)
        layout.addStretch()
        
        self.setLayout(layout)
