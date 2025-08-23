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
        self.portEdit.setValidator(QIntValidator(0, 32768))  # 端口号验证
        self.portEdit.setMinimumWidth(100)
        self.portEdit.setMaximumWidth(120)
        connect_layout.addWidget(self.portEdit)
        config_layout.addLayout(connect_layout)
        
        # 连接按钮和断开按钮 - 参考数据分析界面的样式
        button_layout = QHBoxLayout()
        self.connectButton = QPushButton("连接仪器")
        self.connectButton.setMinimumHeight(32)
        self.disconnectButton = QPushButton("断开连接")
        self.disconnectButton.setMinimumHeight(32)
        self.disconnectButton.setEnabled(False)  # 初始状态禁用断开按钮
        
        button_layout.addWidget(self.connectButton)
        button_layout.addWidget(self.disconnectButton)
        
        config_layout.addLayout(button_layout)
        
        config_group.setLayout(config_layout)
        main_layout.addWidget(config_group)
        
        # 添加弹性空间
        main_layout.addStretch()
        
        self.setLayout(main_layout)
    
    def update_connection_status(self, connected, instrument_info=None):
        """更新连接状态显示"""
        if connected:
            self.connectButton.setEnabled(False)  # 连接后禁用连接按钮
            self.disconnectButton.setEnabled(True)  # 启用断开按钮
            self.connectButton.setText("已连接")
            self.disconnectButton.setText("断开连接")
            
            # 连接后禁用输入框，防止修改
            self.ipEdit.setEnabled(False)
            self.portEdit.setEnabled(False)
            self.instrumentCombo.setEnabled(False)
        else:
            self.connectButton.setEnabled(True)  # 断开后启用连接按钮
            self.disconnectButton.setEnabled(False)  # 禁用断开按钮
            self.connectButton.setText("连接仪器")
            self.disconnectButton.setText("断开连接")
            
            # 断开后启用输入框，允许修改
            self.ipEdit.setEnabled(True)
            self.portEdit.setEnabled(True)
            self.instrumentCombo.setEnabled(True)
    
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
