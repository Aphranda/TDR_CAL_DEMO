# src/main.py
import sys
from PyQt5.QtWidgets import QApplication
from PyQt5.QtCore import QDir
from app.core.TcpClient import TcpClient
from app.utils.ProcessManager import ProcessManager
from app.core.FileManager import FileManager
from app.windows.MainWindow import create_main_window
from app.utils.StyleManager import StyleManager

if __name__ == "__main__":
    # 先检查是否已有实例运行
    process_mgr = ProcessManager()
    if process_mgr.check_duplicate_instance():
        sys.exit(1)
    
    communicator = TcpClient()
    file_manager = FileManager()
    
    # 正常启动主程序
    app = QApplication(sys.argv)

    # 初始化资源系统
    QDir.addSearchPath('resources', 'resources')  # 添加资源搜索路径

    # 加载样式表
    StyleManager.load_style()
    
    # 设置应用程序名称（用于任务管理器识别）
    app.setApplicationName("TDR Calibration System")
    app.setApplicationDisplayName("TDR自动校准系统")
    
    # 创建主窗口
    window = create_main_window()
    window[0].show()
    
    sys.exit(app.exec_())
