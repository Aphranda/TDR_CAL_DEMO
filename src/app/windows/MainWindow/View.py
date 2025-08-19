# src/app/windows/MainWindow/View.py
from PyQt5.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QVBoxLayout, 
    QSplitter, QTabWidget, QStatusBar, QFrame, QSizePolicy
)
from PyQt5.QtCore import Qt

class MainWindowView(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("网络分析仪校准系统")
        self.resize(1200, 800)
        
        self._setup_ui()
        self._apply_styles()
    
    def _setup_ui(self):
        # 创建中心部件
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # 主水平布局
        main_layout = QHBoxLayout()
        main_layout.setContentsMargins(5, 5, 5, 5)
        main_layout.setSpacing(5)
        central_widget.setLayout(main_layout)
        
        # 创建分割器
        splitter = QSplitter(Qt.Horizontal)
        splitter.setHandleWidth(2)
        splitter.setChildrenCollapsible(False)  # 防止子部件被折叠
        main_layout.addWidget(splitter)
        
        # 左侧绘图区域 - 移除最大宽度限制，设置大小策略
        self.plot_area = QTabWidget()
        self.plot_area.setMinimumWidth(400)
        # 移除 setMaximumWidth(800) - 允许拉伸
        self.plot_area.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        splitter.addWidget(self.plot_area)
        
        # 右侧控制区域
        right_widget = QWidget()
        right_layout = QVBoxLayout()
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(5)
        right_widget.setLayout(right_layout)
        right_widget.setMinimumWidth(350)  # 保留最小宽度
        # 移除 setMaximumWidth(450) - 允许拉伸
        right_widget.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Expanding)
        
        # 仪表连接区域
        instrument_frame = QFrame()
        instrument_frame.setFrameStyle(QFrame.StyledPanel | QFrame.Raised)
        instrument_layout = QVBoxLayout()
        instrument_layout.setContentsMargins(5, 5, 5, 5)
        instrument_frame.setLayout(instrument_layout)
        self.instrument_widget = QWidget()
        self.instrument_widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        instrument_layout.addWidget(self.instrument_widget)
        right_layout.addWidget(instrument_frame, 1)
        
        # 校准区域
        calibration_frame = QFrame()
        calibration_frame.setFrameStyle(QFrame.StyledPanel | QFrame.Raised)
        calibration_layout = QVBoxLayout()
        calibration_layout.setContentsMargins(5, 5, 5, 5)
        calibration_frame.setLayout(calibration_layout)
        self.calibration_widget = QWidget()
        self.calibration_widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        calibration_layout.addWidget(self.calibration_widget)
        right_layout.addWidget(calibration_frame, 2)
        
        # 日志区域
        log_frame = QFrame()
        log_frame.setFrameStyle(QFrame.StyledPanel | QFrame.Raised)
        log_layout = QVBoxLayout()
        log_layout.setContentsMargins(5, 5, 5, 5)
        log_frame.setLayout(log_layout)
        self.log_widget = QWidget()
        self.log_widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        log_layout.addWidget(self.log_widget)
        right_layout.addWidget(log_frame, 3)
        
        splitter.addWidget(right_widget)
        
        # 设置初始分割比例
        splitter.setSizes([700, 500])  # 调整初始比例
        
        # 状态栏
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
    
    def _apply_styles(self):
        self.setStyleSheet("""
            QMainWindow {
                background-color: #f0f0f0;
            }
            QFrame {
                background-color: white;
                border-radius: 4px;
                border: 1px solid #d0d0d0;
            }
            QTabWidget::pane {
                border: 1px solid #c4c4c4;
                margin-top: 5px;
            }
            QTabBar::tab {
                padding: 6px;
                min-width: 80px;
                font-size: 11px;
            }
            QTabBar::tab:selected {
                background: #d7d7d7;
                border-bottom: 2px solid #0066cc;
            }
            QSplitter::handle {
                background-color: #c0c0c0;
                width: 2px;
            }
            QSplitter::handle:hover {
                background-color: #a0a0a0;
            }
        """)
    
    def add_plot_tab(self, widget, title):
        """添加绘图标签页"""
        widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.plot_area.addTab(widget, title)
    
    def set_instrument_widget(self, widget):
        """设置仪表连接区域"""
        layout = self.instrument_widget.layout()
        if layout:
            # 清除现有内容
            while layout.count():
                item = layout.takeAt(0)
                if item.widget():
                    item.widget().deleteLater()
        else:
            layout = QVBoxLayout()
            layout.setContentsMargins(2, 2, 2, 2)
            self.instrument_widget.setLayout(layout)
        
        widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        layout.addWidget(widget)
    
    def set_calibration_widget(self, widget):
        """设置校准区域"""
        layout = self.calibration_widget.layout()
        if layout:
            # 清除现有内容
            while layout.count():
                item = layout.takeAt(0)
                if item.widget():
                    item.widget().deleteLater()
        else:
            layout = QVBoxLayout()
            layout.setContentsMargins(2, 2, 2, 2)
            self.calibration_widget.setLayout(layout)
        
        widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        layout.addWidget(widget)
    
    def set_log_widget(self, widget):
        """设置日志区域"""
        layout = self.log_widget.layout()
        if layout:
            # 清除现有内容
            while layout.count():
                item = layout.takeAt(0)
                if item.widget():
                    item.widget().deleteLater()
        else:
            layout = QVBoxLayout()
            layout.setContentsMargins(2, 2, 2, 2)
            self.log_widget.setLayout(layout)
        
        widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        layout.addWidget(widget)
    
    def show_status_message(self, message, timeout=0):
        """显示状态栏消息"""
        self.status_bar.showMessage(message, timeout)
    
    def resizeEvent(self, event):
        """重写resizeEvent以确保布局正确调整"""
        super().resizeEvent(event)
        # 确保分割器比例在窗口大小变化时保持相对稳定
        if hasattr(self, 'plot_area') and hasattr(self, 'centralWidget'):
            # 获取当前窗口大小
            window_width = self.width()
            # 动态调整分割比例（可选）
            # 这里可以根据需要添加动态调整逻辑
            pass
