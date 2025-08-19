# src/app/widgets/CalibrationPanel/View.py
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGroupBox, 
    QPushButton, QLabel, QComboBox, QProgressBar, QLineEdit,
    QFrame, QSizePolicy, QScrollArea
)
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QPainter, QColor, QPen, QFont

class FlowStepWidget(QWidget):
    """流程图步骤控件"""
    def __init__(self, text, step_number, is_current=False, parent=None):
        super().__init__(parent)
        self.text = text
        self.step_number = step_number
        self.is_current = is_current
        self.setMinimumSize(120, 60)  # 设置最小尺寸以适应水平布局
        self.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        # 设置颜色
        if self.is_current:
            bg_color = QColor(100, 160, 220)  # 当前步骤蓝色
            text_color = QColor(255, 255, 255)
        else:
            bg_color = QColor(240, 240, 240)  # 默认灰色
            text_color = QColor(80, 80, 80)
        
        # 绘制圆角矩形背景
        painter.setBrush(bg_color)
        painter.setPen(QPen(QColor(180, 180, 180), 1))
        painter.drawRoundedRect(2, 2, self.width()-4, self.height()-4, 10, 10)
        
        # 绘制步骤编号圆圈
        painter.setBrush(QColor(255, 255, 255, 200))
        painter.setPen(QPen(QColor(100, 100, 100), 1))
        painter.drawEllipse(self.width()//2 - 10, 8, 20, 20)
        
        # 绘制文本
        painter.setPen(text_color)
        font = QFont()
        font.setPointSize(8)
        painter.setFont(font)
        
        # 绘制步骤编号
        painter.drawText(self.width()//2 - 10, 8, 20, 20, Qt.AlignCenter, str(self.step_number))
        
        # 绘制步骤文本（自动换行）
        text_rect = self.rect().adjusted(5, 30, -5, -5)
        painter.drawText(text_rect, Qt.AlignCenter | Qt.TextWordWrap, self.text)

class FlowChartWidget(QWidget):
    """水平流程图控件"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.steps = []
        self.current_step = -1
        self.layout = QHBoxLayout()
        self.layout.setSpacing(5)  # 步骤间距
        self.layout.setContentsMargins(5, 10, 5, 10)
        self.setLayout(self.layout)
        self.setMinimumHeight(80)
        
    def update_steps(self, steps, current_step=-1):
        """更新流程图步骤"""
        # 清除现有步骤
        while self.layout.count():
            item = self.layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        
        # 添加新步骤
        self.steps = steps
        self.current_step = current_step
        
        for i, step_text in enumerate(steps):
            is_current = (i == current_step)
            step_widget = FlowStepWidget(step_text, i+1, is_current)
            self.layout.addWidget(step_widget)
            
            # 如果不是最后一步，添加右箭头
            if i < len(steps) - 1:
                arrow = QLabel("→")
                arrow.setAlignment(Qt.AlignCenter)
                arrow.setStyleSheet("color: #808080; font-size: 16px; font-weight: bold; padding: 0 5px;")
                arrow.setMinimumWidth(20)
                self.layout.addWidget(arrow)
        
        # 添加弹性空间使内容居中
        self.layout.addStretch()

class CalibrationView(QWidget):
    calibration_started = pyqtSignal()
    calibration_stopped = pyqtSignal()
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setup_ui()
        
    def setup_ui(self):
        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(5, 5, 5, 5)
        main_layout.setSpacing(8)
        
        # 校准配置区域 - 使用紧凑布局
        config_group = QGroupBox("校准配置")
        config_group.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        config_layout = QVBoxLayout()
        config_layout.setSpacing(4)
        
        # 第一行：校准类型和端口选择 - 修改为Expanding大小策略
        row1_layout = QHBoxLayout()
        row1_layout.addWidget(QLabel("类型:"))
        self.cal_type_combo = QComboBox()
        self.cal_type_combo.addItems(["SOLT", "TRL"])
        # 移除 setMaximumWidth(120) 限制，改为Expanding策略
        self.cal_type_combo.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        row1_layout.addWidget(self.cal_type_combo)
        
        row1_layout.addSpacing(10)
        row1_layout.addWidget(QLabel("端口:"))
        self.port_combo = QComboBox()
        self.port_combo.addItems(["单端口", "双端口"])
        # 移除 setMaximumWidth(80) 限制，改为Expanding策略
        self.port_combo.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        row1_layout.addWidget(self.port_combo)
        row1_layout.addStretch()
        config_layout.addLayout(row1_layout)
        
        # 第二行：频率设置 - 修改为Expanding大小策略
        row2_layout = QHBoxLayout()
        row2_layout.addWidget(QLabel("起始:"))
        self.start_freq_edit = QLineEdit("1e6")
        # 移除 setMaximumWidth(80) 限制，改为Expanding策略
        self.start_freq_edit.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        row2_layout.addWidget(self.start_freq_edit)
        
        row2_layout.addSpacing(5)
        row2_layout.addWidget(QLabel("Hz"))
        row2_layout.addSpacing(10)
        
        row2_layout.addWidget(QLabel("终止:"))
        self.stop_freq_edit = QLineEdit("6e9")
        # 移除 setMaximumWidth(80) 限制，改为Expanding策略
        self.stop_freq_edit.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        row2_layout.addWidget(self.stop_freq_edit)
        row2_layout.addWidget(QLabel("Hz"))
        row2_layout.addStretch()
        config_layout.addLayout(row2_layout)
        
        config_group.setLayout(config_layout)
        main_layout.addWidget(config_group)
        
        # 流程图区域 - 使用滚动区域以适应长流程
        flow_group = QGroupBox("校准流程")
        flow_group.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        flow_layout = QVBoxLayout()
        
        # 创建滚动区域
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll_area.setMaximumHeight(100)  # 限制高度
        
        self.flow_chart = FlowChartWidget()
        scroll_area.setWidget(self.flow_chart)
        
        flow_layout.addWidget(scroll_area)
        flow_group.setLayout(flow_layout)
        main_layout.addWidget(flow_group)
        
        # 进度条
        progress_layout = QHBoxLayout()
        progress_layout.addWidget(QLabel("进度:"))
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setTextVisible(True)
        progress_layout.addWidget(self.progress_bar)
        main_layout.addLayout(progress_layout)
        
        # 按钮区域
        button_layout = QHBoxLayout()
        self.start_btn = QPushButton("开始校准")
        self.stop_btn = QPushButton("停止")
        self.stop_btn.setEnabled(False)
        self.stop_btn.setMaximumWidth(60)
        button_layout.addWidget(self.start_btn)
        button_layout.addWidget(self.stop_btn)
        button_layout.addStretch()
        main_layout.addLayout(button_layout)
        
        self.setLayout(main_layout)
        
    def update_calibration_steps(self, steps):
        """更新校准步骤流程图"""
        self.flow_chart.update_steps(steps)
    
    def update_progress(self, value, current_step=-1):
        """更新进度"""
        self.progress_bar.setValue(value)
        # 高亮显示当前步骤
        self.flow_chart.update_steps(self.flow_chart.steps, current_step)
    
    def set_calibration_running(self, running):
        """设置校准状态"""
        self.start_btn.setEnabled(not running)
        self.stop_btn.setEnabled(running)
        if not running:
            self.progress_bar.setValue(0)
            # 重置流程图高亮
            self.flow_chart.update_steps(self.flow_chart.steps, -1)
