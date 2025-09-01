# src/app/widgets/ADCSamplingPanel/View.py
from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QGroupBox, 
                             QLabel, QPushButton, QLineEdit, QSpinBox, 
                             QProgressBar, QDoubleSpinBox, QFileDialog, QCheckBox,
                             QRadioButton, QButtonGroup)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QIntValidator, QPalette, QColor

class ADCSamplingView(QWidget):
    def __init__(self):
        super().__init__()
        self.setup_ui()

    def setup_ui(self):
        main_layout = QVBoxLayout()
        main_layout.setSpacing(8)
        main_layout.setContentsMargins(6, 6, 6, 6)
        
        # S参数模式选择部分
        s_mode_group = QGroupBox("S参数时钟控制")
        s_mode_layout = QHBoxLayout()
        s_mode_layout.setSpacing(6)
        s_mode_layout.setContentsMargins(8, 5, 8, 5)
        
        # 创建互斥的按钮组
        self.s_mode_button_group = QButtonGroup(self)
        self.s_mode_button_group.setExclusive(True)
        
        # S11模式
        self.s11_radio = QRadioButton("S11")
        self.s11_radio.setChecked(True)  # 默认选择S11
        self.s11_radio.setToolTip("端口1反射测量")
        self.s_mode_button_group.addButton(self.s11_radio, 0)
        s_mode_layout.addWidget(self.s11_radio)
        
        # S12模式
        self.s12_radio = QRadioButton("S12")
        self.s12_radio.setToolTip("端口1到端口2传输测量")
        self.s_mode_button_group.addButton(self.s12_radio, 1)
        s_mode_layout.addWidget(self.s12_radio)
        
        # S21模式
        self.s21_radio = QRadioButton("S21")
        self.s21_radio.setToolTip("端口2到端口1传输测量")
        self.s_mode_button_group.addButton(self.s21_radio, 2)
        s_mode_layout.addWidget(self.s21_radio)
        
        # S22模式
        self.s22_radio = QRadioButton("S22")
        self.s22_radio.setToolTip("端口2反射测量")
        self.s_mode_button_group.addButton(self.s22_radio, 3)
        s_mode_layout.addWidget(self.s22_radio)
        
        
        s_mode_group.setLayout(s_mode_layout)
        main_layout.addWidget(s_mode_group)
        
        
        # 仪表控制部分
        instrument_group = QGroupBox("ADC采样控制")
        instrument_layout = QVBoxLayout()
        instrument_layout.setSpacing(6)
        instrument_layout.setContentsMargins(8, 12, 8, 12)
        
        # 连接状态显示
        status_layout = QHBoxLayout()
        self.status_label = QLabel("等待主窗口仪表连接...")
        self.status_label.setAlignment(Qt.AlignCenter)
        self.status_label.setMinimumHeight(20)
        self.status_label.setMaximumHeight(50)
        self.status_label.setStyleSheet("""
            QLabel {
                border: 1px solid #cccccc;
                border-radius: 4px;
                padding: 2px;
                background-color: #f0f0f0;
                color: #666666;
            }
        """)
        status_layout.addWidget(self.status_label)
        instrument_layout.addLayout(status_layout)
        
        # 采样设置
        sample_layout = QHBoxLayout()
        sample_layout.setSpacing(4)
        sample_layout.addWidget(QLabel("次数:"))
        self.sample_count_spin = QSpinBox()
        self.sample_count_spin.setRange(1, 1000)
        self.sample_count_spin.setValue(10)
        self.sample_count_spin.setMinimumWidth(70)
        self.sample_count_spin.setMaximumWidth(100)
        sample_layout.addWidget(self.sample_count_spin)
        sample_layout.addWidget(QLabel("间隔(s):"))
        self.sample_interval_spin = QDoubleSpinBox()
        self.sample_interval_spin.setRange(0.1, 10.0)
        self.sample_interval_spin.setValue(0.1)
        self.sample_interval_spin.setMinimumWidth(70)
        self.sample_interval_spin.setMaximumWidth(100)
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
    
    def get_selected_s_mode(self) -> str:
        """获取选中的S参数模式"""
        if self.s11_radio.isChecked():
            return "S11"
        elif self.s12_radio.isChecked():
            return "S12"
        elif self.s21_radio.isChecked():
            return "S21"
        elif self.s22_radio.isChecked():
            return "S22"
        return "S11"  # 默认返回S11
    
    
    def update_adc_connection_status(self, connected: bool, message: str = ""):
        """更新ADC连接状态"""
        status_text = f"{'已连接' if connected else '未连接'} - {message}"
        
        if connected:
            # 已连接状态 - 浅绿色背景
            self.status_label.setStyleSheet("""
                QLabel {
                    border: 1px solid #c3e6cb;
                    border-radius: 4px;
                    padding: 2px;
                    background-color: #d4edda;
                    color: #155724;
                }
            """)
        else:
            # 未连接状态 - 浅黄色背景
            self.status_label.setStyleSheet("""
                QLabel {
                    border: 1px solid #ffeeba;
                    border-radius: 4px;
                    padding: 2px;
                    background-color: #fff3cd;
                    color: #856404;
                }
            """)
            
        self.status_label.setText(status_text)
        self.sample_button.setEnabled(connected)

    
    def update_sampling_progress(self, current: int, total: int, message: str = ""):
        """更新采样进度"""
        self.progress_bar.setVisible(True)
        self.progress_bar.setMaximum(total)
        self.progress_bar.setValue(current)
        if message:
            self.progress_bar.setFormat(f"{message} - %p%")
        else:
            self.progress_bar.setFormat("%p%")
