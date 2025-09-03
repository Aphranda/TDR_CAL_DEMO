# src/app/windows/MainWindow/View.py
from PyQt5.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QVBoxLayout, 
    QSplitter, QTabWidget, QStatusBar, QFrame, QSizePolicy,
    QToolButton, QLabel
)
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QIcon
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
        self.plot_progress_splitter = None
        
        # 标记是否已经设置过分割器比例
        self._splitter_ratios_set = False

        # 存储进度条面板引用
        self.progress_panel = None
        self.progress_container = None
        
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
        
        # 左侧绘图区域（现在包含绘图和进度条）
        self._setup_left_plot_area()
        
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
        
        # 在状态栏添加进度控制按钮
        self._add_statusbar_progress_button()
    
    def _add_statusbar_progress_button(self):
        """在状态栏添加进度控制按钮"""
        # 创建进度控制按钮
        self.status_progress_button = QToolButton()
        self.status_progress_button.setText("显示进度")
        self.status_progress_button.setCheckable(True)
        self.status_progress_button.setChecked(False)
        self.status_progress_button.clicked.connect(self._handle_status_progress_button)
        
        # 添加到状态栏
        self.status_bar.addPermanentWidget(self.status_progress_button)
    
    def _handle_status_progress_button(self, checked):
        """处理状态栏进度按钮点击"""
        if checked:
            self.show_progress_panel()
        else:
            self.hide_progress_panel()
    
    def _setup_left_plot_area(self):
        """设置左侧绘图区域（包含绘图和进度条）"""
        # 创建垂直分割器来分割绘图区域和进度条
        self.plot_progress_splitter = QSplitter(Qt.Vertical)
        self.plot_progress_splitter.setHandleWidth(2)
        self.plot_progress_splitter.setChildrenCollapsible(False)
        
        # 绘图区域
        self.plot_area = QTabWidget()
        self.plot_area.setMinimumWidth(400)
        self.plot_area.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.plot_progress_splitter.addWidget(self.plot_area)
        
        # 进度条容器（初始隐藏）
        self.progress_container = QWidget()
        self.progress_container.setVisible(False)
        self.progress_container.setMinimumHeight(150)
        self.progress_container.setMaximumHeight(300)
        
        progress_layout = QVBoxLayout(self.progress_container)
        progress_layout.setContentsMargins(5, 5, 5, 5)
        progress_layout.setSpacing(5)
        
        # 进度条标题和控制按钮
        progress_header = QWidget()
        header_layout = QHBoxLayout(progress_header)
        header_layout.setContentsMargins(0, 0, 0, 0)
        
        self.progress_title = QLabel("进度监控")
        self.progress_title.setStyleSheet("font-weight: bold; font-size: 12px;")
        header_layout.addWidget(self.progress_title)
        
        header_layout.addStretch()
        
        self.progress_toggle_button = QToolButton()
        self.progress_toggle_button.setText("隐藏进度")
        self.progress_toggle_button.setCheckable(True)
        self.progress_toggle_button.setChecked(True)
        self.progress_toggle_button.clicked.connect(lambda checked: self.toggle_progress_panel(checked))
        header_layout.addWidget(self.progress_toggle_button)
        
        progress_layout.addWidget(progress_header)
        
        # 占位符，稍后通过 set_progress_panel 设置实际内容
        self.progress_placeholder = QWidget()
        progress_layout.addWidget(self.progress_placeholder)
        
        # 将进度容器添加到分割器下部
        self.plot_progress_splitter.addWidget(self.progress_container)
        
        # 初始分割比例：全部给绘图区域，进度区域为0
        self.plot_progress_splitter.setSizes([100, 0])
        
        # 添加到主分割器
        self.main_splitter.addWidget(self.plot_progress_splitter)
    
    def showEvent(self, event):
        """重写show事件，在窗口显示后设置分割器比例"""
        super().showEvent(event)
        if not self._splitter_ratios_set:
            QTimer.singleShot(100, self._setup_splitter_ratios)
            self._splitter_ratios_set = True
    
    def _setup_splitter_ratios(self):
        """设置所有分割器的初始比例"""
        MAIN_SPLITTER_RATIO = 0.7
        INSTRUMENT_PANEL_RATIO = 0.2
        LOG_PANEL_RATIO = 0.8
        ADC_SAMPLING_RATIO = 0.4
        DATA_ANALYSIS_RATIO = 0.6
        
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
            self.sys_splitter.setSizes([100, 600])
        
        # 设置数据处理垂直分割器比例
        data_processing_tab_height = self.data_processing_tab.height()
        if data_processing_tab_height > 0:
            adc_height = int(data_processing_tab_height * ADC_SAMPLING_RATIO)
            analysis_height = data_processing_tab_height - adc_height
            self.data_processing_splitter.setSizes([adc_height, analysis_height])
        else:
            self.data_processing_splitter.setSizes([250, 450])
    
    def resizeEvent(self, event):
        """重写resize事件，保持分割器比例"""
        super().resizeEvent(event)
        if self._splitter_ratios_set:
            self._setup_splitter_ratios()
    
    def set_splitter_ratio(self, splitter_name, ratios):
        """设置分割器比例"""
        if splitter_name == 'main' and self.main_splitter:
            self.main_splitter.setSizes(ratios)
        elif splitter_name == 'sys' and self.sys_splitter:
            self.sys_splitter.setSizes(ratios)
        elif splitter_name == 'data_processing' and self.data_processing_splitter:
            self.data_processing_splitter.setSizes(ratios)
    
    def get_splitter_ratio(self, splitter_name):
        """获取分割器当前比例"""
        if splitter_name == 'main' and self.main_splitter:
            return self.main_splitter.sizes()
        elif splitter_name == 'sys' and self.sys_splitter:
            return self.sys_splitter.sizes()
        elif splitter_name == 'data_processing' and self.data_processing_splitter:
            return self.data_processing_splitter.sizes()
        return []
    
    def set_adc_sampling_widget(self, widget):
        """设置ADC采样区域"""
        widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        widget.setMinimumHeight(200)
        self.data_processing_splitter.addWidget(widget)
    
    def set_data_processing_widget(self, widget):
        """设置数据分析区域"""
        widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        widget.setMinimumHeight(300)
        self.data_processing_splitter.addWidget(widget)
    
    def add_plot_tab(self, widget, title):
        """添加绘图标签页"""
        widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.plot_area.addTab(widget, title)

    def clear_plot_tabs(self):
        """清除所有绘图标签页"""
        self.plot_area.clear()
    
    def set_instrument_widget(self, widget):
        """设置仪表连接区域"""
        widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        widget.setMinimumHeight(100)
        self.sys_splitter.addWidget(widget)

    def set_log_widget(self, widget):
        """设置日志区域"""
        widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        widget.setMinimumHeight(400)
        self.sys_splitter.addWidget(widget)
    
    def set_calibration_widget(self, widget):
        """设置校准区域"""
        widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.calibration_tab_layout.addWidget(widget)
    
    def set_vna_control_widget(self, widget):
        """设置网分控制区域"""
        layout = self.vna_control_layout
        while layout.count():
            item = layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        
        widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        layout.addWidget(widget)
    
    def show_status_message(self, message, timeout=0):
        """显示状态栏消息"""
        self.status_bar.showMessage(message, timeout)
    
    def set_progress_panel(self, progress_widget):
        """设置进度条面板内容"""
        if self.progress_container:
            old_widget = self.progress_placeholder
            if old_widget:
                progress_layout = self.progress_container.layout()
                progress_layout.removeWidget(old_widget)
                old_widget.deleteLater()
            
            progress_widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
            progress_layout.addWidget(progress_widget)
            self.progress_panel = progress_widget
    
    def toggle_progress_panel(self, checked):
        """切换进度面板的显示/隐藏"""
        if self.progress_container:
            self.progress_container.setVisible(checked)
            self.progress_toggle_button.setText("隐藏进度" if checked else "显示进度")
            self.status_progress_button.setChecked(checked)
            self.status_progress_button.setText("隐藏进度" if checked else "显示进度")
            
            if checked:
                total_height = self.plot_progress_splitter.height()
                plot_height = int(total_height * 0.8)
                progress_height = total_height - plot_height
                self.plot_progress_splitter.setSizes([plot_height, progress_height])
            else:
                total_height = self.plot_progress_splitter.height()
                self.plot_progress_splitter.setSizes([total_height, 0])
    
    def show_progress_panel(self):
        """显示进度面板"""
        self.toggle_progress_panel(True)
    
    def hide_progress_panel(self):
        """隐藏进度面板"""
        self.toggle_progress_panel(False)
    
    def is_progress_panel_visible(self):
        """检查进度面板是否可见"""
        return self.progress_container.isVisible() if self.progress_container else False
    
    def update_progress_panel_title(self, title):
        """更新进度面板标题"""
        if self.progress_title:
            self.progress_title.setText(title)
