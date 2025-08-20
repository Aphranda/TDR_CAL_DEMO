# src/app/widgets/InstrumentPanel/View.py
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGroupBox,
    QLabel, QPushButton, QComboBox, QLineEdit, QSizePolicy
)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QIntValidator

class InstrumentPanelView(QWidget):
    def __init__(self):
        super().__init__()
        self.setup_ui()
    
    def setup_ui(self):
        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(5, 5, 5, 5)
        main_layout.setSpacing(8)

        # 仪器信息显示组
        info_group = QGroupBox("仪器信息")
        info_group.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        info_layout = QVBoxLayout()
        
        self.infoLabel = QLabel("请先连接仪器...")
        self.infoLabel.setStyleSheet("color: gray; font-style: italic;")
        self.infoLabel.setWordWrap(True)
        info_layout.addWidget(self.infoLabel)
        
        info_group.setLayout(info_layout)
        main_layout.addWidget(info_group)
        
        # 仪器连接配置组
        config_group = QGroupBox("仪器连接配置")
        config_group.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        config_layout = QVBoxLayout()
        config_layout.setSpacing(10)
        
        # 仪器类型选择
        type_layout = QHBoxLayout()
        type_layout.addWidget(QLabel("仪器类型:"))
        self.instrumentCombo = QComboBox()
        self.instrumentCombo.addItems(["VNA", "TDR", "ADC"])
        self.instrumentCombo.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        type_layout.addWidget(self.instrumentCombo)
        config_layout.addLayout(type_layout)
        
        # 连接设置
        connect_layout = QHBoxLayout()
        connect_layout.addWidget(QLabel("IP地址:"))
        self.ipEdit = QLineEdit("192.168.1.10")
        self.ipEdit.setPlaceholderText("输入仪器IP地址")
        connect_layout.addWidget(self.ipEdit)
        
        connect_layout.addWidget(QLabel("端口:"))
        self.portEdit = QLineEdit("15000")
        self.portEdit.setValidator(QIntValidator(1000, 65535))  # 端口号验证
        self.portEdit.setMaximumWidth(80)
        connect_layout.addWidget(self.portEdit)
        config_layout.addLayout(connect_layout)
        
        # 连接按钮和状态
        button_layout = QHBoxLayout()
        self.connectButton = QPushButton("连接仪器")
        self.connectButton.setMinimumHeight(32)
        button_layout.addWidget(self.connectButton)
        
        # 状态指示灯
        self.statusIndicator = QLabel("●")
        self.statusIndicator.setAlignment(Qt.AlignCenter)
        self.statusIndicator.setStyleSheet("""
            font-size: 16px;
            font-weight: bold;
            color: red;
            padding: 2px 6px;
        """)
        button_layout.addWidget(self.statusIndicator)
        
        self.statusLabel = QLabel("未连接")
        self.statusLabel.setStyleSheet("color: gray; font-size: 11px;")
        button_layout.addWidget(self.statusLabel)
        
        button_layout.addStretch()
        config_layout.addLayout(button_layout)
        
        config_group.setLayout(config_layout)
        main_layout.addWidget(config_group)
        
        
        # 添加弹性空间
        main_layout.addStretch()
        
        self.setLayout(main_layout)
    
    def update_connection_status(self, connected, instrument_info=None):
        """更新连接状态显示"""
        if connected:
            self.connectButton.setText("断开连接")
            self.statusIndicator.setStyleSheet("""
                font-size: 16px;
                font-weight: bold;
                color: green;
                padding: 2px 6px;
            """)
            self.statusLabel.setText("已连接")
            self.statusLabel.setStyleSheet("color: green; font-size: 11px;")
            
            # 显示仪器信息
            if instrument_info:
                info_text = f"型号: {instrument_info.get('model', '未知')}\n"
                info_text += f"序列号: {instrument_info.get('serial', '未知')}\n"
                info_text += f"固件版本: {instrument_info.get('firmware', '未知')}"
                self.infoLabel.setText(info_text)
                self.infoLabel.setStyleSheet("color: black;")
        else:
            self.connectButton.setText("连接仪器")
            self.statusIndicator.setStyleSheet("""
                font-size: 16px;
                font-weight: bold;
                color: red;
                padding: 2px 6px;
            """)
            self.statusLabel.setText("未连接")
            self.statusLabel.setStyleSheet("color: gray; font-size: 11px;")
            self.infoLabel.setText("请先连接仪器...")
            self.infoLabel.setStyleSheet("color: gray; font-style: italic;")
    
    def get_connection_info(self):
        """获取连接信息"""
        return {
            'instrument_type': self.instrumentCombo.currentText(),
            'ip_address': self.ipEdit.text().strip(),
            'port': int(self.portEdit.text()) if self.portEdit.text().isdigit() else 15000
        }
    
    def set_connection_info(self, instrument_type, ip_address, port):
        """设置连接信息"""
        index = self.instrumentCombo.findText(instrument_type)
        if index >= 0:
            self.instrumentCombo.setCurrentIndex(index)
        self.ipEdit.setText(ip_address)
        self.portEdit.setText(str(port))
    
    def set_connect_button_enabled(self, enabled):
        """设置连接按钮状态"""
        self.connectButton.setEnabled(enabled)
