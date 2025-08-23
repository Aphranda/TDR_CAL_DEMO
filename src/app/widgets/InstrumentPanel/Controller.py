# src/app/widgets/InstrumentPanel/Controller.py
from PyQt5.QtCore import QObject, pyqtSignal
from app.core.TcpClient import TcpClient  # 导入TcpClient类
class InstrumentPanelController(QObject):
    connectionChanged = pyqtSignal(bool)
    instrumentError = pyqtSignal(str)
    log_message = pyqtSignal(str, str)
    
    def __init__(self, model, view):
        super().__init__()
        self.model = model
        self.view = view
        self.tcp_client = TcpClient()  # 创建TcpClient实例
        self.setup_connections()
    
    def setup_connections(self):
        """设置信号连接"""
        self.view.connectButton.clicked.connect(self.connect_instrument)
        self.view.disconnectButton.clicked.connect(self.disconnect_instrument)
    
    def connect_instrument(self):
        """连接仪器"""
        try:
            connection_info = self.view.get_connection_info()
            ip = connection_info['ip_address']
            port = connection_info['port']
            
            # 使用TcpClient进行真实连接
            success, message = self.tcp_client.connect(ip, port, timeout=3)
            
            if success:
                self.model.connected = True
                self.model.ip_address = ip
                self.model.port = port
                self.model.instrument_type = connection_info['instrument_type']
                
                self.view.update_connection_status(True)
                self.connectionChanged.emit(True)  # 发出连接状态变化信号
                
                # 通过日志输出连接信息
                self.log_message.emit(
                    f"仪器连接成功 - 类型: {connection_info['instrument_type']}, "
                    f"IP: {ip}, 端口: {port}",
                    "INFO"
                )
            else:
                # 连接失败
                error_msg = f"连接失败: {message}"
                self.instrumentError.emit(error_msg)
                self.log_message.emit(error_msg, "ERROR")
                self.view.update_connection_status(False)  # 确保界面状态正确
            
        except Exception as e:
            error_msg = f"连接异常: {str(e)}"
            self.instrumentError.emit(error_msg)
            self.log_message.emit(error_msg, "ERROR")
            self.view.update_connection_status(False)
    
    def disconnect_instrument(self):
        """断开仪器连接"""
        try:
            # 使用TcpClient断开连接
            self.tcp_client.close()
            self.model.connected = False
            self.view.update_connection_status(False)
            self.connectionChanged.emit(False)  # 发出连接状态变化信号
            
            # 通过日志输出断开信息
            self.log_message.emit("仪器已断开连接", "INFO")
            
        except Exception as e:
            error_msg = f"断开连接失败: {str(e)}"
            self.instrumentError.emit(error_msg)
            self.log_message.emit(error_msg, "ERROR")
    
    def check_connection_status(self):
        """检查连接状态，用于定时检测网络是否断开"""
        if self.model.connected:
            # 尝试发送一个简单的查询命令来检测连接状态
            try:
                # 根据仪器类型发送不同的查询命令
                if self.model.instrument_type == "VNA":
                    # VNA常用的查询命令
                    success, response = self.tcp_client.send("*IDN?", max_retries=1, base_timeout=1.0)
                    if success:
                        success, response = self.tcp_client.receive(max_retries=1, base_timeout=1.0)
                elif self.model.instrument_type == "ADC":
                    # ADC常用的查询命令
                    success, response = self.tcp_client.send("STATUS?", max_retries=1, base_timeout=1.0)
                    if success:
                        success, response = self.tcp_client.receive(max_retries=1, base_timeout=1.0)
                else:
                    # 其他仪器类型
                    success, response = self.tcp_client.send("*IDN?", max_retries=1, base_timeout=1.0)
                    if success:
                        success, response = self.tcp_client.receive(max_retries=1, base_timeout=1.0)
                
                # 如果发送或接收失败，说明连接已断开
                if not success:
                    self._handle_connection_lost()
                    
            except Exception as e:
                # 任何异常都认为连接已断开
                self._handle_connection_lost()
    
    def _handle_connection_lost(self):
        """处理连接断开的情况"""
        if self.model.connected:
            self.model.connected = False
            self.view.update_connection_status(False)
            self.connectionChanged.emit(False)
            self.tcp_client.close()
            
            # 记录连接断开日志
            self.log_message.emit(
                f"检测到网络连接断开 - 类型: {self.model.instrument_type}, "
                f"IP: {self.model.ip_address}, 端口: {self.model.port}",
                "WARNING"
            )
    
    def send_command(self, command, max_retries=3, base_timeout=1.0):
        """发送命令到仪器"""
        if not self.model.connected:
            return False, "未连接"
        
        try:
            success, message = self.tcp_client.send(command, max_retries, base_timeout)
            if not success:
                # 发送失败，可能连接已断开
                self._handle_connection_lost()
            return success, message
        except Exception as e:
            self._handle_connection_lost()
            return False, f"发送命令异常: {str(e)}"
    
    def receive_response(self, max_retries=3, base_timeout=1.0):
        """接收仪器响应"""
        if not self.model.connected:
            return False, "未连接"
        
        try:
            success, response = self.tcp_client.receive(max_retries, base_timeout)
            if not success:
                # 接收失败，可能连接已断开
                self._handle_connection_lost()
            return success, response
        except Exception as e:
            self._handle_connection_lost()
            return False, f"接收响应异常: {str(e)}"
    
    def query_instrument(self, command, max_retries=3, base_timeout=1.0):
        """查询仪器（发送命令并接收响应）"""
        if not self.model.connected:
            return False, "未连接"
        
        try:
            # 发送命令
            success, message = self.send_command(command, max_retries, base_timeout)
            if not success:
                return False, message
            
            # 接收响应
            success, response = self.receive_response(max_retries, base_timeout)
            return success, response
            
        except Exception as e:
            self._handle_connection_lost()
            return False, f"查询仪器异常: {str(e)}"
