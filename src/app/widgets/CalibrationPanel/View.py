# src/app/widgets/CalibrationPanel/View.py
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGroupBox, 
    QPushButton, QLabel, QComboBox, QProgressBar, QLineEdit,
    QFrame, QSizePolicy, QScrollArea, QGridLayout, QFormLayout
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
        self.setMinimumSize(120, 60)
        self.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        # 设置颜色
        if self.is_current:
            bg_color = QColor(100, 160, 220)
            text_color = QColor(255, 255, 255)
        else:
            bg_color = QColor(240, 240, 240)
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
        
        # 绘制步骤文本
        text_rect = self.rect().adjusted(5, 30, -5, -5)
        painter.drawText(text_rect, Qt.AlignCenter | Qt.TextWordWrap, self.text)

class FlowChartWidget(QWidget):
    """水平流程图控件"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.steps = []
        self.current_step = -1
        self.layout = QHBoxLayout()
        self.layout.setSpacing(5)
        self.layout.setContentsMargins(5, 10, 5, 10)
        self.setLayout(self.layout)
        self.setMinimumHeight(80)
        
    def update_steps(self, steps, current_step=-1):
        """更新流程图步骤"""
        while self.layout.count():
            item = self.layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        
        self.steps = steps
        self.current_step = current_step
        
        for i, step_text in enumerate(steps):
            is_current = (i == current_step)
            step_widget = FlowStepWidget(step_text, i+1, is_current)
            self.layout.addWidget(step_widget)
            
            if i < len(steps) - 1:
                arrow = QLabel("→")
                arrow.setAlignment(Qt.AlignCenter)
                arrow.setStyleSheet("color: #808080; font-size: 16px; font-weight: bold; padding: 0 5px;")
                arrow.setMinimumWidth(20)
                self.layout.addWidget(arrow)
        
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
        
        # 校准配置区域 - 使用表单布局（单行竖向布局）
        config_group = QGroupBox("校准配置")
        config_group.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        config_layout = QFormLayout()
        config_layout.setSpacing(8)
        config_layout.setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow)
        
        # 第一行：校准类型
        self.cal_type_combo = QComboBox()
        self.cal_type_combo.addItems(["SOLT(Short-Open-Load-Thru)", "TRL(Thru-Reflect-Line)"])
        config_layout.addRow("校准类型:", self.cal_type_combo)
        
        # 第二行：端口配置
        self.port_combo = QComboBox()
        self.port_combo.addItems(["单端口(1)", "双端口(1-2)"])
        config_layout.addRow("端口配置:", self.port_combo)
        
        # 第三行：起始频率
        freq_layout = QHBoxLayout()
        self.start_freq_edit = QLineEdit("1000")
        self.start_freq_edit.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        freq_layout.addWidget(self.start_freq_edit)
        freq_layout.addWidget(QLabel("MHz"))
        freq_layout.addStretch()
        config_layout.addRow("起始频率:", freq_layout)
        
        # 第四行：终止频率
        stop_freq_layout = QHBoxLayout()
        self.stop_freq_edit = QLineEdit("6000")
        self.stop_freq_edit.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        stop_freq_layout.addWidget(self.stop_freq_edit)
        stop_freq_layout.addWidget(QLabel("MHz"))
        stop_freq_layout.addStretch()
        config_layout.addRow("终止频率:", stop_freq_layout)
        
        # 第五行：步进频率
        step_freq_layout = QHBoxLayout()
        self.step_freq_edit = QLineEdit("100")
        self.step_freq_edit.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        step_freq_layout.addWidget(self.step_freq_edit)
        step_freq_layout.addWidget(QLabel("MHz"))
        step_freq_layout.addStretch()
        config_layout.addRow("步进频率:", step_freq_layout)
        
        # 第六行：校准功率
        pow_layout = QHBoxLayout()
        self.calibration_pow_edit = QLineEdit("-20")
        self.calibration_pow_edit.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        pow_layout.addWidget(self.calibration_pow_edit)
        pow_layout.addWidget(QLabel("dBm"))
        pow_layout.addStretch()
        config_layout.addRow("校准功率:", pow_layout)
        
        # 第七行：IF带宽
        ifbw_layout = QHBoxLayout()
        self.calibration_ifbw_edit = QLineEdit("1000")
        self.calibration_ifbw_edit.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        ifbw_layout.addWidget(self.calibration_ifbw_edit)
        ifbw_layout.addWidget(QLabel("Hz"))
        ifbw_layout.addStretch()
        config_layout.addRow("IF带宽:", ifbw_layout)
        
        config_group.setLayout(config_layout)
        main_layout.addWidget(config_group)
        
        # 流程图区域
        flow_group = QGroupBox("校准流程")
        flow_group.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        flow_layout = QVBoxLayout()
        
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll_area.setMaximumHeight(120)
        
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
        button_layout.addWidget(self.start_btn)
        button_layout.addWidget(self.stop_btn)
        main_layout.addLayout(button_layout)
        
        self.setLayout(main_layout)
        
    def update_calibration_steps(self, steps):
        """更新校准步骤流程图"""
        self.flow_chart.update_steps(steps)
    
    def update_progress(self, value, current_step=-1):
        """更新进度"""
        self.progress_bar.setValue(value)
        self.flow_chart.update_steps(self.flow_chart.steps, current_step)
    
    def set_calibration_running(self, running):
        """设置校准状态"""
        self.start_btn.setEnabled(not running)
        self.stop_btn.setEnabled(running)
        if not running:
            self.progress_bar.setValue(0)
            self.flow_chart.update_steps(self.flow_chart.steps, -1)
