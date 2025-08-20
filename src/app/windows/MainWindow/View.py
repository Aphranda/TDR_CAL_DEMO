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
        self.resize(1600, 1000)
        
        self._setup_ui()
    
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
        splitter.setChildrenCollapsible(False)
        main_layout.addWidget(splitter)
        
        # 左侧绘图区域
        self.plot_area = QTabWidget()
        self.plot_area.setMinimumWidth(400)
        self.plot_area.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        splitter.addWidget(self.plot_area)
        
        # 右侧控制区域 - TabWidget
        self.right_tab_widget = QTabWidget()
        self.right_tab_widget.setMinimumWidth(350)
        self.right_tab_widget.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Expanding)
        
        # 创建三个标签页
        # 网分校准标签页（包含仪表连接、校准、日志）
        self.calibration_tab = QWidget()
        self.calibration_tab_layout = QVBoxLayout()
        self.calibration_tab_layout.setContentsMargins(5, 5, 5, 5)
        self.calibration_tab.setLayout(self.calibration_tab_layout)
        self.right_tab_widget.addTab(self.calibration_tab, "网分校准")
        
        # 网分控制标签页
        self.vna_control_tab = QWidget()
        self.vna_control_layout = QVBoxLayout()
        self.vna_control_layout.setContentsMargins(5, 5, 5, 5)
        self.vna_control_tab.setLayout(self.vna_control_layout)
        self.right_tab_widget.addTab(self.vna_control_tab, "网分控制")
        
        # 数据分析标签页
        self.data_analysis_tab = QWidget()
        self.data_analysis_layout = QVBoxLayout()
        self.data_analysis_layout.setContentsMargins(5, 5, 5, 5)
        self.data_analysis_tab.setLayout(self.data_analysis_layout)
        self.right_tab_widget.addTab(self.data_analysis_tab, "数据分析")
        
        splitter.addWidget(self.right_tab_widget)
        
        # 设置初始分割比例
        splitter.setSizes([1100, 500])
        
        # 状态栏
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        
        # 在网分校准标签页中创建垂直分割器
        self.calibration_splitter = QSplitter(Qt.Vertical)
        self.calibration_splitter.setHandleWidth(2)
        self.calibration_splitter.setChildrenCollapsible(False)
        self.calibration_tab_layout.addWidget(self.calibration_splitter)

    
    def add_plot_tab(self, widget, title):
        """添加绘图标签页"""
        widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.plot_area.addTab(widget, title)
    
    def set_instrument_widget(self, widget):
        """设置仪表连接区域（在网分校准标签页中）"""
        widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        widget.setMinimumHeight(150)  # 设置最小高度
        self.calibration_splitter.addWidget(widget)
        
        # 设置分割比例
        if self.calibration_splitter.count() == 1:
            self.calibration_splitter.setSizes([150])
    
    def set_calibration_widget(self, widget):
        """设置校准区域（在网分校准标签页中）"""
        widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        widget.setMinimumHeight(200)  # 设置最小高度
        self.calibration_splitter.addWidget(widget)
        
        # 设置分割比例
        if self.calibration_splitter.count() == 2:
            self.calibration_splitter.setSizes([150, 200])
    
    def set_log_widget(self, widget):
        """设置日志区域（在网分校准标签页中）"""
        widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        widget.setMinimumHeight(150)  # 设置最小高度
        self.calibration_splitter.addWidget(widget)
        
        # 设置分割比例
        if self.calibration_splitter.count() == 3:
            self.calibration_splitter.setSizes([150, 200, 150])
    
    def set_vna_control_widget(self, widget):
        """设置网分控制区域"""
        layout = self.vna_control_layout
        # 清除现有内容
        while layout.count():
            item = layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        
        widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        layout.addWidget(widget)
    
    def set_data_analysis_widget(self, widget):
        """设置数据分析区域"""
        layout = self.data_analysis_layout
        # 清除现有内容
        while layout.count():
            item = layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        
        widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        layout.addWidget(widget)
    
    def show_status_message(self, message, timeout=0):
        """显示状态栏消息"""
        self.status_bar.showMessage(message, timeout)
