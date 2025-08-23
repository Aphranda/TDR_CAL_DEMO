# src/app/widgets/ADCSamplingPanel/View.py
from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QGroupBox, 
                             QLabel, QPushButton, QLineEdit, QSpinBox, 
                             QProgressBar, QDoubleSpinBox, QFileDialog)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QIntValidator

class ADCSamplingView(QWidget):
    def __init__(self):
        super().__init__()
        self.setup_ui()

    def setup_ui(self):
        main_layout = QVBoxLayout()
        main_layout.setSpacing(8)
        main_layout.setContentsMargins(6, 6, 6, 6)
        
        # 仪表控制部分
        instrument_group = QGroupBox("ADC采样控制")
        instrument_layout = QVBoxLayout()
        instrument_layout.setSpacing(6)
        instrument_layout.setContentsMargins(8, 12, 8, 12)
        
        # 连接设置
        connect_layout = QHBoxLayout()
        connect_layout.setSpacing(4)
        connect_layout.addWidget(QLabel("IP地址:"))
        self.adc_ip_edit = QLineEdit("192.168.1.10")
        self.adc_ip_edit.setPlaceholderText("输入ADC IP地址")
        connect_layout.addWidget(self.adc_ip_edit)

        connect_layout.addWidget(QLabel("端口:"))
        self.adc_port_edit = QLineEdit("15000")
        self.adc_port_edit.setValidator(QIntValidator(0, 32768))
        self.adc_port_edit.setMinimumWidth(100)
        self.adc_port_edit.setMaximumWidth(120)
        connect_layout.addWidget(self.adc_port_edit)
        instrument_layout.addLayout(connect_layout)
        
        # 连接按钮
        button_layout = QHBoxLayout()
        button_layout.setSpacing(4)
        self.connect_button = QPushButton("连接ADC")
        self.disconnect_button = QPushButton("断开连接")
        self.disconnect_button.setEnabled(False)
        button_layout.addWidget(self.connect_button)
        button_layout.addWidget(self.disconnect_button)
        instrument_layout.addLayout(button_layout)
        
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
        instrument_layout.addLayout(sample_layout)
          
        # 文件名设置
        filename_layout = QHBoxLayout()
        filename_layout.setSpacing(4)
        filename_layout.addWidget(QLabel("文件名称:"))
        self.filename_edit = QLineEdit("adc_data")
        self.filename_edit.setPlaceholderText("输入保存的文件名（不含扩展名）")
        filename_layout.addWidget(self.filename_edit)
        instrument_layout.addLayout(filename_layout)

        # 输出目录设置
        output_dir_layout = QHBoxLayout()
        output_dir_layout.setSpacing(4)
        output_dir_layout.addWidget(QLabel("输出目录:"))
        self.output_dir_edit = QLineEdit("data\\results\\test")
        self.output_dir_edit.setPlaceholderText("选择输出目录")
        output_dir_layout.addWidget(self.output_dir_edit)
        
        self.browse_dir_button = QPushButton("浏览")
        self.browse_dir_button.setMinimumWidth(60)
        output_dir_layout.addWidget(self.browse_dir_button)
        instrument_layout.addLayout(output_dir_layout)

        # 采样按钮
        self.sample_button = QPushButton("开始采样")
        self.sample_button.setEnabled(False)
        instrument_layout.addWidget(self.sample_button)
        
        instrument_group.setLayout(instrument_layout)
        main_layout.addWidget(instrument_group)
        
        # 进度条
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        main_layout.addWidget(self.progress_bar)
        
        self.setLayout(main_layout)
    
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
