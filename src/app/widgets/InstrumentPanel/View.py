# src/app/widgets/InstrumentPanel/View.py
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGroupBox,
    QLabel, QPushButton, QComboBox, QLineEdit, QSizePolicy
)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont

class InstrumentPanelView(QWidget):
    def __init__(self):
        super().__init__()
        self.setup_ui()
    
    def setup_ui(self):
        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(5, 5, 5, 5)
        main_layout.setSpacing(8)
        
        # 使用GroupBox包含所有控件，样式与校准界面保持一致
        config_group = QGroupBox("仪器连接")
        config_group.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        config_layout = QVBoxLayout()
        config_layout.setSpacing(6)
        
        # 第一行：仪器类型选择和状态显示
        row1_layout = QHBoxLayout()
        row1_layout.addWidget(QLabel("类型:"))
        self.instrumentCombo = QComboBox()
        self.instrumentCombo.addItems(["VNA", "TDR", "Signal Generator"])
        self.instrumentCombo.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        row1_layout.addWidget(self.instrumentCombo)
        
        row1_layout.addSpacing(10)
        
        # 状态显示放在第一行右侧
        self.statusLabel = QLabel("未连接")
        self.statusLabel.setAlignment(Qt.AlignCenter)
        self.statusLabel.setStyleSheet("""
            color: red; 
            font-size: 11px; 
            padding: 4px 8px; 
            background-color: #fff0f0; 
            border: 1px solid #ffc0c0; 
            border-radius: 4px;
            font-weight: bold;
        """)
        row1_layout.addWidget(self.statusLabel)
        row1_layout.addStretch()
        config_layout.addLayout(row1_layout)
        
        # 第二行：IP地址、端口设置和连接按钮
        row2_layout = QHBoxLayout()
        row2_layout.addWidget(QLabel("IP地址:"))
        self.ipEdit = QLineEdit("192.168.1.100")
        self.ipEdit.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        row2_layout.addWidget(self.ipEdit)
        
        row2_layout.addSpacing(10)
        row2_layout.addWidget(QLabel("端口:"))
        self.portEdit = QLineEdit("5025")
        self.portEdit.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.portEdit.setMaximumWidth(80)  # 端口输入框稍窄一些
        row2_layout.addWidget(self.portEdit)
        
        row2_layout.addSpacing(10)
        
        # 连接按钮放在第二行
        self.connectButton = QPushButton("连接")
        self.connectButton.setMinimumHeight(30)
        row2_layout.addWidget(self.connectButton)
        
        row2_layout.addStretch()
        config_layout.addLayout(row2_layout)
        
        config_group.setLayout(config_layout)
        main_layout.addWidget(config_group)
        
        # 添加弹性空间使内容靠上显示
        main_layout.addStretch()
        
        self.setLayout(main_layout)
    
    def update_connection_status(self, connected):
        """更新连接状态显示"""
        if connected:
            self.connectButton.setText("断开")
            self.statusLabel.setText("已连接")
            self.statusLabel.setStyleSheet("""
                color: green; 
                font-size: 11px; 
                padding: 4px 8px; 
                background-color: #f0fff0; 
                border: 1px solid #c0e0c0; 
                border-radius: 4px;
                font-weight: bold;
            """)
        else:
            self.connectButton.setText("连接")
            self.statusLabel.setText("未连接")
            self.statusLabel.setStyleSheet("""
                color: red; 
                font-size: 11px; 
                padding: 4px 8px; 
                background-color: #fff0f0; 
                border: 1px solid #ffc0c0; 
                border-radius: 4px;
                font-weight: bold;
            """)
    
    def get_connection_info(self):
        """获取连接信息"""
        return {
            'instrument_type': self.instrumentCombo.currentText(),
            'ip_address': self.ipEdit.text(),
            'port': int(self.portEdit.text())
        }
