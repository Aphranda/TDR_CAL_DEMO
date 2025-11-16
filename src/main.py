# src/main.py
import sys
import time
from PyQt5.QtWidgets import QApplication, QSplashScreen
from PyQt5.QtCore import QDir, QTimer, Qt
from PyQt5.QtGui import QPixmap
from app.core.TcpClient import TcpClient
from app.utils.ProcessManager import ProcessManager
from app.core.FileManager import FileManager
from app.windows.MainWindow import create_main_window
from app.utils.StyleManager import StyleManager
from app.core.DataProcessor import DataProcessor

class ApplicationInitializer:
    """应用程序初始化器"""
    
    def __init__(self):
        self.splash = None
        self.data_processor = None
        self.communicator = None
        self.file_manager = None
    
    def show_splash(self):
        """显示启动画面"""
        pixmap = QPixmap("src\\resources\\init\\splash.png")  # 如果有启动图片
        if pixmap.isNull():
            # 如果没有图片，创建一个简单的启动画面
            pixmap = QPixmap(400, 300)
            pixmap.fill(Qt.white)
        
        self.splash = QSplashScreen(pixmap)
        self.splash.show()
        self.splash.showMessage("正在初始化系统...", Qt.AlignBottom | Qt.AlignCenter, Qt.white)
        QApplication.processEvents()
    
    def initialize_components(self):
        """初始化各个组件"""
        # 初始化通信组件
        self.splash.showMessage("初始化通信组件...", Qt.AlignBottom | Qt.AlignCenter, Qt.white)
        QApplication.processEvents()
        self.communicator = TcpClient()
        
        # 初始化文件管理器
        self.splash.showMessage("初始化文件管理器...", Qt.AlignBottom | Qt.AlignCenter, Qt.white)
        QApplication.processEvents()
        self.file_manager = FileManager()
        
        # 初始化数据处理器（开始预编译）
        self.splash.showMessage("预编译数据处理模块...", Qt.AlignBottom | Qt.AlignCenter, Qt.white)
        QApplication.processEvents()
        self.data_processor = DataProcessor({})  # 传入空配置或实际配置
        
        # 等待预编译完成（可选，取决于您对启动速度的要求）
        time.sleep(1)  # 给预编译一些时间
    
    def create_main_window(self):
        """创建主窗口"""
        self.splash.showMessage("加载主界面...", Qt.AlignBottom | Qt.AlignCenter, Qt.white)
        QApplication.processEvents()
        
        return create_main_window()

if __name__ == "__main__":
    # 检查是否已有实例运行
    process_mgr = ProcessManager()
    if process_mgr.check_duplicate_instance():
        sys.exit(1)
    
    # 创建应用
    app = QApplication(sys.argv)
    
    # 初始化资源系统
    QDir.addSearchPath('resources', 'resources')
    
    # 加载样式表
    StyleManager.load_style()
    
    # 设置应用程序信息
    app.setApplicationName("TDR Calibration System")
    app.setApplicationDisplayName("TDR Automatic Calibration System")
    
    # 使用初始化器
    initializer = ApplicationInitializer()
    initializer.show_splash()
    initializer.initialize_components()
    
    # 创建主窗口
    window = initializer.create_main_window()
    
    # 关闭启动画面，显示主窗口
    initializer.splash.finish(window[0])
    window[0].show()
    
    sys.exit(app.exec_())
