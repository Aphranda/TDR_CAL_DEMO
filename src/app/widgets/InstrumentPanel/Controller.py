# src/app/widgets/InstrumentPanel/Controller.py
from PyQt5.QtCore import QObject, pyqtSignal

class InstrumentPanelController(QObject):
    connectionChanged = pyqtSignal(bool)
    instrumentError = pyqtSignal(str)
    
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
            self.model.connected = True
            self.view.update_connection_status(True)
            self.connectionChanged.emit(True)
        except Exception as e:
            self.instrumentError.emit(f"连接失败: {str(e)}")
    
    def disconnect_instrument(self):
        """断开仪器连接"""
        try:
            # 这里实现实际的仪器断开逻辑
            self.model.connected = False
            self.view.update_connection_status(False)
            self.connectionChanged.emit(False)
        except Exception as e:
            self.instrumentError.emit(f"断开连接失败: {str(e)}")
