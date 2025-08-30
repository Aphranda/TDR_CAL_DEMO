# src/app/widgets/CalibrationPanel/View.py
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGroupBox, 
    QPushButton, QLabel, QComboBox, QProgressBar, QLineEdit,
    QFrame, QSizePolicy, QScrollArea, QGridLayout, QFormLayout,
    QMessageBox,QDialog,QApplication  # 新增：用于显示提示框
)
from PyQt5.QtCore import Qt, pyqtSignal,QTimer,QEventLoop
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
            bg_color = QColor(70, 130, 180)  # 更深的蓝色，更醒目
            border_color = QColor(30, 90, 150)
            text_color = QColor(255, 255, 255)
        else:
            bg_color = QColor(240, 240, 240)
            border_color = QColor(180, 180, 180)
            text_color = QColor(80, 80, 80)
        
        # 绘制圆角矩形背景
        painter.setBrush(bg_color)
        painter.setPen(QPen(border_color, 2 if self.is_current else 1))  # 当前步骤边框更粗
        painter.drawRoundedRect(2, 2, self.width()-4, self.height()-4, 10, 10)
        
        # 绘制步骤编号圆圈
        if self.is_current:
            painter.setBrush(QColor(255, 255, 255))
        else:
            painter.setBrush(QColor(255, 255, 255, 200))
        painter.setPen(QPen(QColor(100, 100, 100), 1))
        painter.drawEllipse(self.width()//2 - 10, 8, 20, 20)
        
        # 绘制文本
        painter.setPen(text_color)
        font = QFont()
        font.setPointSize(8)
        if self.is_current:
            font.setBold(True)  # 当前步骤文本加粗
        painter.setFont(font)
        
        # 绘制步骤编号
        painter.drawText(self.width()//2 - 10, 8, 20, 20, Qt.AlignCenter, str(self.step_number))
        
        # 绘制步骤文本
        text_rect = self.rect().adjusted(5, 30, -5, -5)
        painter.drawText(text_rect, Qt.AlignCenter | Qt.TextWordWrap, self.text)


# src/app/widgets/CalibrationPanel/View.py (部分修改)
class FlowChartWidget(QWidget):
    """水平流程图控件，支持自动滚动"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.steps = []
        self.current_step = -1
        self.step_widgets = []  # 存储步骤控件的引用
        self.arrow_widgets = []  # 存储箭头控件的引用
        self.layout = QHBoxLayout()
        self.layout.setSpacing(5)
        self.layout.setContentsMargins(5, 10, 5, 10)
        self.setLayout(self.layout)
        self.setMinimumHeight(80)
        self._scroll_area = None  # 存储滚动区域的引用
        self._last_scroll_position = 0  # 记录上一次的滚动位置
        self.step_target_positions = []  # 存储每个步骤的目标滚动位置

    def reset_scroll_position(self):
        """重置滚动位置到初始位置"""
        if self._scroll_area:
            self._scroll_area.horizontalScrollBar().setValue(0)
            self._last_scroll_position = 0
        
    def set_scroll_area(self, scroll_area):
        """设置滚动区域引用"""
        self._scroll_area = scroll_area
        
    def update_steps(self, steps, current_step=-1):
        """更新流程图步骤 - 只更新必要的内容，避免完全重建"""
        # 检查步骤是否真的改变了
        if self.steps == steps and self.current_step == current_step:
            return  # 没有变化，不需要更新
            
        # 保存当前滚动位置
        scroll_pos = self.get_scroll_position()
            
        # 如果步骤数量或内容改变了，需要重新创建
        if len(self.steps) != len(steps) or self.steps != steps:
            # 清除现有控件
            self.clear_widgets()
            
            self.steps = steps
            self.step_widgets = []
            self.arrow_widgets = []
            
            for i, step_text in enumerate(steps):
                is_current = (i == current_step)
                step_widget = FlowStepWidget(step_text, i+1, is_current)
                self.step_widgets.append(step_widget)
                self.layout.addWidget(step_widget)
                
                if i < len(steps) - 1:
                    arrow = QLabel("→")
                    arrow.setAlignment(Qt.AlignCenter)
                    arrow.setStyleSheet("color: #808080; font-size: 16px; font-weight: bold; padding: 0 5px;")
                    arrow.setMinimumWidth(20)
                    self.arrow_widgets.append(arrow)
                    self.layout.addWidget(arrow)
            
            self.layout.addStretch()
            
            # 更新最小宽度，确保内容可以正确计算
            self.update_minimum_width()
            
            # 预先计算所有步骤的目标位置
            QTimer.singleShot(100, self.precalculate_step_positions)
            
            # 恢复滚动位置
            QTimer.singleShot(50, lambda: self.restore_scroll_position(scroll_pos))
        else:
            # 只是当前步骤改变了，更新样式即可
            self.current_step = current_step
            for i, widget in enumerate(self.step_widgets):
                widget.is_current = (i == current_step)
                widget.update()  # 触发重绘
        
        # 如果当前步骤有效，确保它可见
        if 0 <= current_step < len(self.step_widgets):
            # 使用定时器延迟滚动，确保布局已经完成
            QTimer.singleShot(100, lambda: self.ensure_step_visible(current_step))
    
    def precalculate_step_positions(self):
        """预先计算所有步骤的目标滚动位置"""
        if not self._scroll_area or not self.step_widgets:
            return
            
        self.step_target_positions = []
        
        # 确保布局已经完成
        QApplication.processEvents()
        
        # 获取滚动区域的视口尺寸
        viewport_width = self._scroll_area.viewport().width()
        
        for i, step_widget in enumerate(self.step_widgets):
            # 计算步骤控件在滚动区域中的位置
            step_pos = step_widget.mapTo(self._scroll_area, step_widget.rect().topLeft())
            
            # 计算需要滚动的距离
            step_center_x = step_pos.x() + step_widget.width() // 2
            target_scroll_x = step_center_x - viewport_width // 2
            
            # 确保滚动位置在有效范围内
            max_scroll = self._scroll_area.horizontalScrollBar().maximum()
            target_scroll_x = max(0, min(target_scroll_x, max_scroll))
            
            self.step_target_positions.append(target_scroll_x)
    
    def get_scroll_position(self):
        """获取当前滚动位置"""
        if self._scroll_area:
            position = self._scroll_area.horizontalScrollBar().value()
            max_scroll = self._scroll_area.horizontalScrollBar().maximum()
            return position
        return 0
    
    def restore_scroll_position(self, position):
        """恢复滚动位置"""
        if self._scroll_area:
            # 确保位置在有效范围内
            max_scroll = self._scroll_area.horizontalScrollBar().maximum()
            position = min(position, max_scroll)
            self._scroll_area.horizontalScrollBar().setValue(position)
            self._last_scroll_position = position  # 记录最后的滚动位置
    
    def clear_widgets(self):
        """清除所有控件"""
        while self.layout.count():
            item = self.layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self.step_widgets = []
        self.arrow_widgets = []
        self.step_target_positions = []  # 清空预计算的位置
    
    def update_minimum_width(self):
        """更新最小宽度，确保内容可以正确计算"""
        total_width = 0
        for i in range(len(self.step_widgets)):
            total_width += self.step_widgets[i].minimumWidth()
            if i < len(self.step_widgets) - 1:
                total_width += 20  # 箭头宽度
        
        # 设置最小宽度，确保滚动区域可以正确计算内容大小
        self.setMinimumWidth(total_width + 20)  # 添加一些边距
    
    def ensure_step_visible(self, step_index):
        """确保指定步骤在可视区域内 - 使用预计算的位置"""
        if not 0 <= step_index < len(self.step_widgets) or not self._scroll_area:
            return
            
        # 确保预计算的位置可用
        if step_index >= len(self.step_target_positions):
            print(f"警告: 步骤 {step_index} 的预计算位置不可用")
            return
            
        target_scroll_x = self.step_target_positions[step_index]
        self._scroll_area.horizontalScrollBar().setValue(target_scroll_x)
        self._last_scroll_position = target_scroll_x  # 记录最后的滚动位置

class CalibrationView(QWidget):
    calibration_started = pyqtSignal()
    calibration_stopped = pyqtSignal()
    user_confirmation_needed = pyqtSignal(str)  # 新增：需要用户确认的信号
    retest_requested = pyqtSignal()  # 新增：重测请求信号
    retest_finished = pyqtSignal()  # 新增：重测完成信号
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setup_ui()
        self.retest_button = None  # 存储重测按钮的引用
        self.is_retesting = False  # 重测状态标志
        
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
        
        # 第一行：校准件类型
        self.kit_type_combo = QComboBox()
        self.kit_type_combo.addItems(["电子校准件", "机械校准件"])
        config_layout.addRow("校准件类型:", self.kit_type_combo)
        
        # 第二行：校准类型
        self.cal_type_combo = QComboBox()
        self.cal_type_combo.addItems(["SOLT(Short-Open-Load-Thru)", "TRL(Thru-Reflect-Line)"])
        config_layout.addRow("校准类型:", self.cal_type_combo)
        
        # 第三行：端口配置
        self.port_combo = QComboBox()
        self.port_combo.addItems(["单端口(1)", "双端口(1-2)"])
        config_layout.addRow("端口配置:", self.port_combo)
        
        # 第四行：起始频率
        freq_layout = QHBoxLayout()
        self.start_freq_edit = QLineEdit("1000")
        self.start_freq_edit.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        freq_layout.addWidget(self.start_freq_edit)
        freq_layout.addWidget(QLabel("MHz"))
        freq_layout.addStretch()
        config_layout.addRow("起始频率:", freq_layout)
        
        # 第五行：终止频率
        stop_freq_layout = QHBoxLayout()
        self.stop_freq_edit = QLineEdit("6000")
        self.stop_freq_edit.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        stop_freq_layout.addWidget(self.stop_freq_edit)
        stop_freq_layout.addWidget(QLabel("MHz"))
        stop_freq_layout.addStretch()
        config_layout.addRow("终止频率:", stop_freq_layout)
        
        # 第六行：步进频率
        step_freq_layout = QHBoxLayout()
        self.step_freq_edit = QLineEdit("100")
        self.step_freq_edit.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        step_freq_layout.addWidget(self.step_freq_edit)
        step_freq_layout.addWidget(QLabel("MHz"))
        step_freq_layout.addStretch()
        config_layout.addRow("步进频率:", step_freq_layout)
        
        # 第七行：校准功率
        pow_layout = QHBoxLayout()
        self.calibration_pow_edit = QLineEdit("-20")
        self.calibration_pow_edit.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        pow_layout.addWidget(self.calibration_pow_edit)
        pow_layout.addWidget(QLabel("dBm"))
        pow_layout.addStretch()
        config_layout.addRow("校准功率:", pow_layout)
        
        # 第八行：IF带宽
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
        
        self.flow_chart = FlowChartWidget()
        self.flow_chart.set_scroll_area(scroll_area)  # 设置滚动区域引用
        scroll_area.setWidget(self.flow_chart)
        
        flow_layout.addWidget(scroll_area)
        flow_group.setLayout(flow_layout)
        main_layout.addWidget(flow_group)
        
        




        # 进度条区域 - 新增：用于显示ADC采集和数据分析进度
        progress_group = QGroupBox("操作进度")
        progress_layout = QVBoxLayout()
        
        # ADC采样进度
        adc_progress_layout = QHBoxLayout()
        self.adc_progress_bar = QProgressBar()
        self.adc_progress_bar.setRange(0, 100)
        self.adc_progress_bar.setTextVisible(True)
        self.adc_progress_bar.setVisible(False)  # 初始隐藏
        adc_progress_layout.addWidget(self.adc_progress_bar)
        progress_layout.addLayout(adc_progress_layout)
        
        # 数据分析进度
        analysis_progress_layout = QHBoxLayout()
        self.analysis_progress_bar = QProgressBar()
        self.analysis_progress_bar.setRange(0, 100)
        self.analysis_progress_bar.setTextVisible(True)
        self.analysis_progress_bar.setVisible(False)  # 初始隐藏
        analysis_progress_layout.addWidget(self.analysis_progress_bar)
        progress_layout.addLayout(analysis_progress_layout)

        # 进度条
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setTextVisible(True)
        progress_layout.addWidget(self.progress_bar)

        progress_group.setLayout(progress_layout)
        main_layout.addWidget(progress_group)
        
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

    def reset_scroll_position(self):
        """重置滚动位置到初始位置"""
        self.flow_chart.reset_scroll_position()
    
    def update_progress(self, value, current_step=-1):
        """更新进度"""
        self.progress_bar.setValue(value)
        self.flow_chart.update_steps(self.flow_chart.steps, current_step)
        
        # 确保当前步骤可见
        if current_step >= 0:
            self.flow_chart.ensure_step_visible(current_step)

    def update_adc_progress(self, current, total, message):
        """更新ADC采样进度"""
        self.adc_progress_bar.setVisible(True)
        self.adc_progress_bar.setMaximum(total)
        self.adc_progress_bar.setValue(current)
        self.status_label.setText(f"ADC采样: {message}")
    
    def update_analysis_progress(self, current, total, message):
        """更新数据分析进度"""
        self.analysis_progress_bar.setVisible(True)
        self.analysis_progress_bar.setMaximum(total)
        self.analysis_progress_bar.setValue(current)
        self.status_label.setText(f"数据分析: {message}")
    
    def reset_progress_bars(self):
        """重置进度条"""
        self.adc_progress_bar.setVisible(False)
        self.analysis_progress_bar.setVisible(False)
        self.adc_progress_bar.setValue(0)
        self.analysis_progress_bar.setValue(0)
        self.status_label.setText("就绪")
    
    def set_calibration_running(self, running):
        """设置校准状态"""
        self.start_btn.setEnabled(not running)
        self.stop_btn.setEnabled(running)
        if not running:
            self.progress_bar.setValue(0)
            self.flow_chart.update_steps(self.flow_chart.steps, -1)
    
    # 修改 show_user_confirmation 方法
    def show_user_confirmation(self, step_description, has_measurement=False):
        """显示用户确认对话框 - 修改为使用非模态对话框"""
        # 获取应用程序的主窗口
        from PyQt5.QtWidgets import QApplication
        main_window = QApplication.activeWindow()
        if main_window is None:
            main_window = self.window()  # 如果获取不到活动窗口，则使用当前窗口的顶级窗口

        # 创建自定义对话框
        self.confirmation_dialog = QDialog(main_window)  # 使用主窗口作为父窗口
        self.confirmation_dialog.setWindowTitle("请确认操作")
        self.confirmation_dialog.setModal(False)  # 修改为非模态对话框
        self.confirmation_dialog.setWindowFlags(
            self.confirmation_dialog.windowFlags() | Qt.WindowStaysOnTopHint
        )  # 添加窗口置顶标志
        
        layout = QVBoxLayout(self.confirmation_dialog)
        
        # 添加说明文本
        label = QLabel(f"请确认已完成: {step_description}\n\n完成后请点击'确定'继续")
        layout.addWidget(label)
        
        # 添加按钮
        button_layout = QHBoxLayout()
        ok_button = QPushButton("确定")
        cancel_button = QPushButton("取消")
        
        button_layout.addWidget(ok_button)
        button_layout.addWidget(cancel_button)
        
        # 如果有测量字段，添加重测按钮
        if has_measurement:
            self.retest_button = QPushButton("重测")
            button_layout.addWidget(self.retest_button)
            self.retest_button.clicked.connect(lambda: self.on_retest_clicked(step_description))
            # 设置初始样式
            self.update_retest_button_style()
        
        layout.addLayout(button_layout)
        
        # 连接按钮信号
        ok_button.clicked.connect(self.on_confirmation_ok)
        cancel_button.clicked.connect(self.on_confirmation_cancel)
        
        # 连接重测完成信号
        self.retest_finished.connect(self.on_retest_finished)
        
        # 显示对话框但不阻塞
        self.confirmation_dialog.show()
        
        # 创建事件循环等待用户响应
        self.confirmation_loop = QEventLoop()
        return self.confirmation_loop.exec_() == QDialog.Accepted

    
    def on_confirmation_ok(self):
        """处理确认确定按钮"""
        if hasattr(self, 'confirmation_loop'):
            self.confirmation_loop.exit(QDialog.Accepted)
        if self.confirmation_dialog:
            self.confirmation_dialog.deleteLater()
            self.confirmation_dialog = None
        self.retest_button = None
        self.is_retesting = False
    
    def on_confirmation_cancel(self):
        """处理确认取消按钮"""
        if hasattr(self, 'confirmation_loop'):
            self.confirmation_loop.exit(QDialog.Rejected)
        if self.confirmation_dialog:
            self.confirmation_dialog.deleteLater()
            self.confirmation_dialog = None
        self.retest_button = None
        self.is_retesting = False
    
    def on_retest_clicked(self, step_description):
        """处理重测按钮点击"""
        if not self.is_retesting:
            self.is_retesting = True
            self.update_retest_button_style()
            # 发送重测信号
            self.retest_requested.emit()
    
    def on_retest_finished(self):
        """处理重测完成"""
        self.is_retesting = False
        self.update_retest_button_style()
    
    def update_retest_button_style(self):
        """更新重测按钮样式"""
        if self.retest_button:
            if self.is_retesting:
                self.retest_button.setText("正在重测")
                self.retest_button.setEnabled(False)
            else:
                self.retest_button.setText("重测")
                self.retest_button.setEnabled(True)
