# src/app/widgets/InstrumentPanel/Controller.py
from PyQt5.QtCore import QObject, pyqtSignal

class InstrumentPanelController(QObject):
    connectionChanged = pyqtSignal(bool)
    instrumentError = pyqtSignal(str)
    log_message = pyqtSignal(str, str)  # 添加日志信号
    
    def __init__(self, model, view):
        super().__init__()
        self.model = model
        self.view = view
        self.setup_connections()
    
    def setup_connections(self):
        """设置信号连接"""
        self.view.connectButton.clicked.connect(self.toggle_connection)
    
    def toggle_connection(self):
        """切换仪器连接状态"""
        if self.model.connected:
            self.disconnect_instrument()
        else:
            self.connect_instrument()
    
    def connect_instrument(self):
        """连接仪器"""
        try:
            # 这里实现实际的仪器连接逻辑
            connection_info = self.view.get_connection_info()
            
            # 模拟连接成功
            self.model.connected = True
            self.view.update_connection_status(True)
            self.connectionChanged.emit(True)
            
            # 通过日志输出连接信息
            self.log_message.emit(
                f"仪器连接成功 - 类型: {connection_info['instrument_type']}, "
                f"IP: {connection_info['ip_address']}, 端口: {connection_info['port']}",
                "INFO"
            )
            
        except Exception as e:
            error_msg = f"连接失败: {str(e)}"
            self.instrumentError.emit(error_msg)
            self.log_message.emit(error_msg, "ERROR")
    
    def disconnect_instrument(self):
        """断开仪器连接"""
        try:
            # 这里实现实际的仪器断开逻辑
            self.model.connected = False
            self.view.update_connection_status(False)
            self.connectionChanged.emit(False)
            
            # 通过日志输出断开信息
            self.log_message.emit("仪器已断开连接", "INFO")
            
        except Exception as e:
            error_msg = f"断开连接失败: {str(e)}"
            self.instrumentError.emit(error_msg)
            self.log_message.emit(error_msg, "ERROR")
