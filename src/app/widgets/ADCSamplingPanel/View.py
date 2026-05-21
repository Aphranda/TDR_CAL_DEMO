# src/app/widgets/ADCSamplingPanel/View.py
from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QGroupBox, 
                             QLabel, QPushButton, QLineEdit, QSpinBox, 
                             QDoubleSpinBox, QFileDialog, QRadioButton, QButtonGroup)
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


        # S21模式
        self.s21_radio = QRadioButton("S21")
        self.s21_radio.setToolTip("端口2到端口1传输测量")
        self.s_mode_button_group.addButton(self.s21_radio, 2)
        s_mode_layout.addWidget(self.s21_radio)
        
        # S12模式
        self.s12_radio = QRadioButton("S12")
        self.s12_radio.setToolTip("端口1到端口2传输测量")
        self.s_mode_button_group.addButton(self.s12_radio, 1)
        s_mode_layout.addWidget(self.s12_radio)
        

        
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
        
        # 采样设置 - 修改这里：添加单次采样数量
        sample_layout = QHBoxLayout()
        sample_layout.setSpacing(4)
        
        # 采样次数
        sample_layout.addWidget(QLabel("NSa"))
        self.sample_count_spin = QSpinBox()
        self.sample_count_spin.setRange(1, 1000)
        self.sample_count_spin.setValue(10)
        self.sample_count_spin.setMinimumWidth(70)
        self.sample_count_spin.setMaximumWidth(100)
        self.sample_count_spin.setToolTip("每次采样命令发送的样本数量0")
        sample_layout.addWidget(self.sample_count_spin)
        
        # 单次采样数量 - 新增控件
        sample_layout.addWidget(QLabel("SaN:"))
        self.sample_number_spin = QSpinBox()
        self.sample_number_spin.setRange(1, 1000)  # block 数量，1 block = 81920 样本
        self.sample_number_spin.setValue(1)  # 默认 1 个 block
        self.sample_number_spin.setMinimumWidth(70)
        self.sample_number_spin.setMaximumWidth(100)
        self.sample_number_spin.setToolTip("采样 block 数量 (1 block = 81920 样本)")
        sample_layout.addWidget(self.sample_number_spin)
        
        # 采样间隔
        sample_layout.addWidget(QLabel("间隔(s):"))
        self.sample_interval_spin = QDoubleSpinBox()
        self.sample_interval_spin.setRange(0.1, 10.0)
        self.sample_interval_spin.setValue(0.1)
        self.sample_interval_spin.setMinimumWidth(70)
        self.sample_interval_spin.setMaximumWidth(100)
        sample_layout.addWidget(self.sample_interval_spin)
        
        instrument_layout.addLayout(sample_layout)

        # 数据类型和ADC采集模式选择部分 - 修改这里：合并到同一行
        data_type_adc_layout = QHBoxLayout()
        data_type_adc_layout.setSpacing(6)
        
        # 左侧：数据类型选择
        data_type_layout = QHBoxLayout()
        data_type_layout.setSpacing(4)
        
        # 创建数据类型互斥按钮组
        self.data_type_button_group = QButtonGroup(self)
        self.data_type_button_group.setExclusive(True)
        
        # uint32 选项
        self.uint32_radio = QRadioButton("u32")
        self.uint32_radio.setChecked(True)  # 默认选择uint32
        self.uint32_radio.setToolTip("32位无符号整数格式，文件较小")
        self.data_type_button_group.addButton(self.uint32_radio, 0)
        data_type_layout.addWidget(self.uint32_radio)
        
        # float64 选项
        self.float64_radio = QRadioButton("f64")
        self.float64_radio.setToolTip("64位浮点数格式，精度更高")
        self.data_type_button_group.addButton(self.float64_radio, 1)
        data_type_layout.addWidget(self.float64_radio)
        
        
        # 右侧：ADC采集模式选择
        adc_mode_layout = QHBoxLayout()
        adc_mode_layout.setSpacing(4)
        
   
        # 创建ADC采集模式互斥按钮组
        self.adc_mode_button_group = QButtonGroup(self)
        self.adc_mode_button_group.setExclusive(True)
        
        # ADC1 选项
        self.adc1_radio = QRadioButton("AD1")
        self.adc1_radio.setChecked(True)  # 默认选择adc1通道
        self.adc1_radio.setToolTip("只采集ADC1通道")
        self.adc_mode_button_group.addButton(self.adc1_radio, 0)
        adc_mode_layout.addWidget(self.adc1_radio)
        
        # ADC2 选项
        self.adc2_radio = QRadioButton("AD2")
        self.adc2_radio.setToolTip("只采集ADC2通道")
        self.adc_mode_button_group.addButton(self.adc2_radio, 1)
        adc_mode_layout.addWidget(self.adc2_radio)
        
        # 双通道 选项
        self.both_adc_radio = QRadioButton("BOTH")
        
        self.both_adc_radio.setToolTip("同时采集ADC1和ADC2通道")
        self.adc_mode_button_group.addButton(self.both_adc_radio, 2)
        adc_mode_layout.addWidget(self.both_adc_radio)
        
        # 将数据类型和ADC采集模式布局添加到主布局
        data_type_adc_layout.addLayout(data_type_layout)
        data_type_adc_layout.addLayout(adc_mode_layout)
        
        instrument_layout.addLayout(data_type_adc_layout)
          
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
    
    def get_selected_data_type(self) -> str:
        """获取选中的数据类型"""
        if self.uint32_radio.isChecked():
            return "uint32"
        elif self.float64_radio.isChecked():
            return "float64"
        return "uint32"  # 默认返回uint32
    
    def get_selected_adc_mode(self) -> str:
        """获取选中的ADC采集模式"""
        if self.adc1_radio.isChecked():
            return "AD1"
        elif self.adc2_radio.isChecked():
            return "AD2"
        elif self.both_adc_radio.isChecked():
            return "BOTH"
        return "BOTH"  # 默认返回双通道

    
    def get_sample_number(self) -> int:
        """获取单次采样数量"""
        return self.sample_number_spin.value()
    
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
