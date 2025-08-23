# src/app/windows/MainWindow/View.py
from PyQt5.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QVBoxLayout, 
    QSplitter, QTabWidget, QStatusBar, QFrame, QSizePolicy
)
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import  QIcon
from pathlib import Path

class MainWindowView(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("TDR Analyzer Calibration System")
        self.resize(1600, 1000)

        # 设置窗口图标
        icon_path = "src\\resources\\icon\\icon_TDR_01.ico"
        if Path(icon_path).exists():
            self.setWindowIcon(QIcon(icon_path))
        else:
            print(f"警告: 图标文件未找到 - {icon_path}")
        
        # 存储分割器引用
        self.main_splitter = None
        self.sys_splitter = None
        self.data_processing_splitter = None
        
        # 标记是否已经设置过分割器比例
        self._splitter_ratios_set = False
        
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
        
        # 创建主水平分割器
        self.main_splitter = QSplitter(Qt.Horizontal)
        self.main_splitter.setHandleWidth(2)
        self.main_splitter.setChildrenCollapsible(False)
        main_layout.addWidget(self.main_splitter)
        
        # 左侧绘图区域
        self.plot_area = QTabWidget()
        self.plot_area.setMinimumWidth(400)
        self.plot_area.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.main_splitter.addWidget(self.plot_area)
        
        # 右侧控制区域 - TabWidget
        self.right_tab_widget = QTabWidget()
        self.right_tab_widget.setMinimumWidth(350)
        self.right_tab_widget.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Expanding)
        
        # 创建四个标签页
        # 系统标签页 - 现在包含仪表连接和日志
        self.sys_tab = QWidget()
        self.sys_layout = QVBoxLayout()
        self.sys_layout.setContentsMargins(0, 0, 0, 0)
        self.sys_layout.setSpacing(0)
        self.sys_tab.setLayout(self.sys_layout)
        self.right_tab_widget.addTab(self.sys_tab, "系统功能")
        
        # 创建系统功能标签页内的垂直分割器
        self.sys_splitter = QSplitter(Qt.Vertical)
        self.sys_splitter.setHandleWidth(2)
        self.sys_splitter.setChildrenCollapsible(False)
        self.sys_layout.addWidget(self.sys_splitter)
        
        # 网分校准标签页（只包含校准配置）
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
        
        # 数据处理标签页 - 现在包含ADC采样和数据分析
        self.data_processing_tab = QWidget()
        self.data_processing_layout = QVBoxLayout()
        self.data_processing_layout.setContentsMargins(0, 0, 0, 0)
        self.data_processing_layout.setSpacing(0)
        self.data_processing_tab.setLayout(self.data_processing_layout)
        self.right_tab_widget.addTab(self.data_processing_tab, "数据处理")
        
        # 创建数据处理标签页内的垂直分割器
        self.data_processing_splitter = QSplitter(Qt.Vertical)
        self.data_processing_splitter.setHandleWidth(2)
        self.data_processing_splitter.setChildrenCollapsible(False)
        self.data_processing_layout.addWidget(self.data_processing_splitter)
        
        self.main_splitter.addWidget(self.right_tab_widget)
        
        # 状态栏
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
    
    def showEvent(self, event):
        """重写show事件，在窗口显示后设置分割器比例"""
        super().showEvent(event)
        if not self._splitter_ratios_set:
            # 使用定时器延迟设置分割器比例，确保窗口已经完全显示
            QTimer.singleShot(100, self._setup_splitter_ratios)
            self._splitter_ratios_set = True
    
    def _setup_splitter_ratios(self):
        """
        设置所有分割器的初始比例
        
        主水平分割器：左侧绘图区域占70%，右侧控制区域占30%
        系统功能垂直分割器：仪表面板占20%，日志面板占80%
        数据处理垂直分割器：ADC采样面板占40%，数据分析面板占60%
        """
        # 配置主水平分割器比例
        MAIN_SPLITTER_RATIO = 0.7  # 左侧绘图区域占比
        
        # 配置系统功能分割器比例
        INSTRUMENT_PANEL_RATIO = 0.2  # 仪表面板占比
        LOG_PANEL_RATIO = 0.8         # 日志面板占比
        
        # 配置数据处理分割器比例
        ADC_SAMPLING_RATIO = 0.4      # ADC采样面板占比
        DATA_ANALYSIS_RATIO = 0.6     # 数据分析面板占比
        
        # 设置主水平分割器比例
        total_width = self.main_splitter.width()
        if total_width > 0:
            left_width = int(total_width * MAIN_SPLITTER_RATIO)
            right_width = total_width - left_width
            self.main_splitter.setSizes([left_width, right_width])
        
        # 设置系统功能垂直分割器比例
        sys_tab_height = self.sys_tab.height()
        if sys_tab_height > 0:
            instrument_height = int(sys_tab_height * INSTRUMENT_PANEL_RATIO)
            log_height = sys_tab_height - instrument_height
            self.sys_splitter.setSizes([instrument_height, log_height])
        else:
            # 使用默认像素值作为后备方案
            DEFAULT_INSTRUMENT_HEIGHT = 100
            DEFAULT_LOG_HEIGHT = 600
            self.sys_splitter.setSizes([DEFAULT_INSTRUMENT_HEIGHT, DEFAULT_LOG_HEIGHT])
        
        # 设置数据处理垂直分割器比例
        data_processing_tab_height = self.data_processing_tab.height()
        if data_processing_tab_height > 0:
            adc_height = int(data_processing_tab_height * ADC_SAMPLING_RATIO)
            analysis_height = data_processing_tab_height - adc_height
            self.data_processing_splitter.setSizes([adc_height, analysis_height])
        else:
            # 使用默认像素值作为后备方案
            DEFAULT_ADC_HEIGHT = 300
            DEFAULT_ANALYSIS_HEIGHT = 400
            self.data_processing_splitter.setSizes([DEFAULT_ADC_HEIGHT, DEFAULT_ANALYSIS_HEIGHT])
    
    def resizeEvent(self, event):
        """重写resize事件，保持分割器比例"""
        super().resizeEvent(event)
        # 如果需要保持固定比例，可以在窗口大小改变时重新调整
        if self._splitter_ratios_set:
            self._setup_splitter_ratios()
    
    def set_splitter_ratio(self, splitter_name, ratios):
        """
        设置分割器比例
        
        Args:
            splitter_name: 分割器名称，'main' 或 'sys' 或 'data_processing'
            ratios: 比例列表，如 [700, 300]
        """
        if splitter_name == 'main' and self.main_splitter:
            self.main_splitter.setSizes(ratios)
        elif splitter_name == 'sys' and self.sys_splitter:
            self.sys_splitter.setSizes(ratios)
        elif splitter_name == 'data_processing' and self.data_processing_splitter:
            self.data_processing_splitter.setSizes(ratios)
    
    def get_splitter_ratio(self, splitter_name):
        """
        获取分割器当前比例
        
        Args:
            splitter_name: 分割器名称，'main' 或 'sys' 或 'data_processing'
        
        Returns:
            list: 当前比例列表
        """
        if splitter_name == 'main' and self.main_splitter:
            return self.main_splitter.sizes()
        elif splitter_name == 'sys' and self.sys_splitter:
            return self.sys_splitter.sizes()
        elif splitter_name == 'data_processing' and self.data_processing_splitter:
            return self.data_processing_splitter.sizes()
        return []
    
    def set_adc_sampling_widget(self, widget):
        """设置ADC采样区域（在数据处理标签页中）"""
        widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        widget.setMinimumHeight(200)  # 设置最小高度
        self.data_processing_splitter.addWidget(widget)
    
    def set_data_processing_widget(self, widget):
        """设置数据分析区域（在数据处理标签页中）"""
        widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        widget.setMinimumHeight(300)  # 设置最小高度
        self.data_processing_splitter.addWidget(widget)
    
    def add_plot_tab(self, widget, title):
        """添加绘图标签页"""
        widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.plot_area.addTab(widget, title)

    def clear_plot_tabs(self):
        """清除所有绘图标签页"""
        self.plot_area.clear()
    
    def set_instrument_widget(self, widget):
        """设置仪表连接区域（在系统功能标签页中）"""
        widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        widget.setMinimumHeight(100)  # 设置最小高度
        self.sys_splitter.addWidget(widget)

    def set_log_widget(self, widget):
        """设置日志区域（在系统功能标签页中）"""
        widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        widget.setMinimumHeight(400)  # 设置最小高度
        self.sys_splitter.addWidget(widget)
    
    def set_calibration_widget(self, widget):
        """设置校准区域（在网分校准标签页中）"""
        widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.calibration_tab_layout.addWidget(widget)
    
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
    
    def show_status_message(self, message, timeout=0):
        """显示状态栏消息"""
        self.status_bar.showMessage(message, timeout)
