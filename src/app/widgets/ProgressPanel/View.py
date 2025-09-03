# src/app/widgets/ProgressPanel/View.py
from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QGroupBox, 
                            QProgressBar, QLabel, QScrollArea, QFrame, QPushButton, QToolButton,QSizePolicy)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont
from .Model import ProgressBarStyle

class StyledProgressBar(QFrame):
    """带标签的样式化进度条 - 所有信息在同一行"""
    def __init__(self, progress_id: str, label: str, parent=None):
        super().__init__(parent)
        self.progress_id = progress_id
        self.setup_ui(label)
        self.apply_style(ProgressBarStyle.DEFAULT)
        self.setMinimumHeight(40)  # 降低高度以适应单行布局
    
    def setup_ui(self, label):
        # 使用水平布局将所有元素放在同一行
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 5, 8, 5)
        layout.setSpacing(8)
        
        # 标签（左侧）- 固定宽度
        self.label = QLabel(label)
        self.label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self.label.setStyleSheet("""
            font-weight: bold; 
            min-width: 120px; 
            max-width: 120px;
            padding: 2px;
        """)
        self.label.setFixedWidth(120)  # 固定宽度
        layout.addWidget(self.label)
        
        # 进度条（中间）- 固定比例
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setTextVisible(True)
        self.progress_bar.setFormat("%p% (%v/%m)")
        self.progress_bar.setStyleSheet("""
            QProgressBar {
                min-height: 20px;
                max-height: 20px;
                border: 1px solid #ccc;
                border-radius: 3px;
                text-align: center;
                background-color: #f8f9fa;
            }
            QProgressBar::chunk {
                background-color: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                stop:0 #007acc, stop:1 #005a9e);
                border-radius: 2px;
            }
        """)
        layout.addWidget(self.progress_bar, 2)  # 添加拉伸因子，比例2
        
        # ID标签（右侧）- 固定宽度
        self.id_label = QLabel(f"ID: {self.progress_id}")
        self.id_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.id_label.setStyleSheet("""
            color: #888; 
            font-size: 9px; 
            min-width: 100px; 
            max-width: 100px;
            padding: 2px;
        """)
        self.id_label.setFixedWidth(100)  # 固定宽度
        layout.addWidget(self.id_label)
        
        # 状态信息（最右侧）- 固定宽度
        self.status_label = QLabel("就绪")
        self.status_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.status_label.setStyleSheet("""
            color: #666; 
            font-size: 10px; 
            min-width: 150px; 
            max-width: 150px;
            padding: 2px;
        """)
        self.status_label.setFixedWidth(200)  # 固定宽度
        layout.addWidget(self.status_label)
        
        # 设置整个进度条的固定尺寸策略
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
    
    def apply_style(self, style: ProgressBarStyle):
        """应用样式"""
        style_sheet = self.get_style_sheet(style)
        self.progress_bar.setStyleSheet(style_sheet)
        
        # 根据样式设置边框颜色
        border_colors = {
            ProgressBarStyle.DEFAULT: "#ccc",
            ProgressBarStyle.BLUE: "#1e90ff",
            ProgressBarStyle.GREEN: "#32cd32",
            ProgressBarStyle.ORANGE: "#ff8c00",
            ProgressBarStyle.RED: "#dc143c",
            ProgressBarStyle.PURPLE: "#9370db",
            ProgressBarStyle.CYAN: "#20b2aa",
            ProgressBarStyle.PINK: "#ff69b4"
        }
        border_color = border_colors.get(style, "#ccc")
        self.setStyleSheet(f"border: 1px solid {border_color}; border-radius: 5px; padding: 2px;")
    
    def get_style_sheet(self, style: ProgressBarStyle) -> str:
        """获取样式表"""
        styles = {
            ProgressBarStyle.DEFAULT: """
                QProgressBar {
                    border: 1px solid #ccc;
                    border-radius: 3px;
                    text-align: center;
                    background-color: #f8f9fa;
                    height: 20px;
                }
                QProgressBar::chunk {
                    background-color: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #007acc, stop:1 #005a9e);
                    border-radius: 2px;
                }
            """,
            ProgressBarStyle.BLUE: """
                QProgressBar {
                    border: 1px solid #1e90ff;
                    border-radius: 3px;
                    text-align: center;
                    background-color: #e6f2ff;
                    height: 20px;
                }
                QProgressBar::chunk {
                    background-color: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #1e90ff, stop:1 #0066cc);
                    border-radius: 2px;
                }
            """,
            ProgressBarStyle.GREEN: """
                QProgressBar {
                    border: 1px solid #32cd32;
                    border-radius: 3px;
                    text-align: center;
                    background-color: #f0fff0;
                    height: 20px;
                }
                QProgressBar::chunk {
                    background-color: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #32cd32, stop:1 #228b22);
                    border-radius: 2px;
                }
            """,
            ProgressBarStyle.ORANGE: """
                QProgressBar {
                    border: 1px solid #ff8c00;
                    border-radius: 3px;
                    text-align: center;
                    background-color: #fff5e6;
                    height: 20px;
                }
                QProgressBar::chunk {
                    background-color: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #ff8c00, stop:1 #cc7000);
                    border-radius: 2px;
                }
            """,
            ProgressBarStyle.RED: """
                QProgressBar {
                    border: 1px solid #dc143c;
                    border-radius: 3px;
                    text-align: center;
                    background-color: #ffe6e6;
                    height: 20px;
                }
                QProgressBar::chunk {
                    background-color: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #dc143c, stop:1 #a50d2d);
                    border-radius: 2px;
                }
            """,
            ProgressBarStyle.PURPLE: """
                QProgressBar {
                    border: 1px solid #9370db;
                    border-radius: 3px;
                    text-align: center;
                    background-color: #f0e6ff;
                    height: 20px;
                }
                QProgressBar::chunk {
                    background-color: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #9370db, stop:1 #6a5acd);
                    border-radius: 2px;
                }
            """,
            ProgressBarStyle.CYAN: """
                QProgressBar {
                    border: 1px solid #20b2aa;
                    border-radius: 3px;
                    text-align: center;
                    background-color: #e0ffff;
                    height: 20px;
                }
                QProgressBar::chunk {
                    background-color: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #20b2aa, stop:1 #008b8b);
                    border-radius: 2px;
                }
            """,
            ProgressBarStyle.PINK: """
                QProgressBar {
                    border: 1px solid #ff69b4;
                    border-radius: 3px;
                    text-align: center;
                    background-color: #ffe6f2;
                    height: 20px;
                }
                QProgressBar::chunk {
                    background-color: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #ff69b4, stop:1 #ff1493);
                    border-radius: 2px;
                }
            """
        }
        return styles.get(style, styles[ProgressBarStyle.DEFAULT])
    
    def update_progress(self, current: int, total: int, message: str = ""):
        """更新进度"""
        self.progress_bar.setMaximum(total)
        self.progress_bar.setValue(current)
        
        # 更新状态信息
        if message:
            self.status_label.setText(message)
        
        # 动态更新格式字符串显示百分比
        percentage = (current / total * 100) if total > 0 else 0
        display_text = f"{percentage:.1f}% ({current}/{total})"
        self.progress_bar.setFormat(display_text)

class ProgressPanelView(QWidget):
    """进度面板视图"""
    def __init__(self, title="进度监控", parent=None):
        super().__init__(parent)
        self.progress_bars = {}  # progress_id -> StyledProgressBar
        self.setup_ui(title)
    
    def setup_ui(self, title):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(5, 5, 5, 5)
        main_layout.setSpacing(8)
        
        # 标题和控制按钮区域 - 所有按钮在同一行
        header_layout = QHBoxLayout()
        header_layout.setSpacing(10)
        
        # 标题
        self.title_label = QLabel(title)
        self.title_label.setStyleSheet("font-size: 14px; font-weight: bold;")
        header_layout.addWidget(self.title_label)
        
        # 添加拉伸因子，将按钮推到右侧
        header_layout.addStretch()
        
        # 控制按钮 - 全部放在同一行
        self.clear_button = QToolButton()
        self.clear_button.setText("清除所有")
        self.clear_button.setToolTip("清除所有进度条")
        self.clear_button.setStyleSheet("QToolButton { padding: 3px 8px; }")
        header_layout.addWidget(self.clear_button)
        
        self.collapse_button = QToolButton()
        self.collapse_button.setText("折叠/展开")
        self.collapse_button.setToolTip("折叠或展开所有进度条")
        self.collapse_button.setStyleSheet("QToolButton { padding: 3px 8px; }")
        header_layout.addWidget(self.collapse_button)
        
        self.auto_scroll_button = QToolButton()
        self.auto_scroll_button.setText("自动滚动")
        self.auto_scroll_button.setToolTip("启用/禁用自动滚动到最新进度")
        self.auto_scroll_button.setCheckable(True)
        self.auto_scroll_button.setChecked(True)
        self.auto_scroll_button.setStyleSheet("QToolButton { padding: 3px 8px; }")
        header_layout.addWidget(self.auto_scroll_button)
        
        main_layout.addLayout(header_layout)
        
        # 统计信息
        self.stats_label = QLabel("进度条数量: 0")
        self.stats_label.setStyleSheet("color: #666; font-size: 11px;")
        main_layout.addWidget(self.stats_label)
        
        # 滚动区域
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        
        # 进度条容器
        self.container = QWidget()
        self.container_layout = QVBoxLayout(self.container)
        self.container_layout.setContentsMargins(5, 5, 5, 5)
        self.container_layout.setSpacing(5)  # 减少间距以适应单行布局
        self.container_layout.addStretch()
        
        scroll_area.setWidget(self.container)
        main_layout.addWidget(scroll_area)
    
    def add_progress_bar(self, progress_id: str, label: str, style: ProgressBarStyle = ProgressBarStyle.DEFAULT):
        """添加进度条"""
        if progress_id in self.progress_bars:
            return False
        
        progress_bar = StyledProgressBar(progress_id, label)
        progress_bar.apply_style(style)
        
        # 插入到布局中（在拉伸项之前）
        count = self.container_layout.count()
        self.container_layout.insertWidget(count - 1, progress_bar)
        
        self.progress_bars[progress_id] = progress_bar
        progress_bar.show()
        
        # 更新统计信息
        self.update_stats()
        
        # 如果启用了自动滚动，滚动到底部
        if self.auto_scroll_button.isChecked():
            self.scroll_to_bottom()
        
        return True
    
    def scroll_to_bottom(self):
        """滚动到底部"""
        # 需要获取滚动区域并滚动到底部
        scroll_area = self.findChild(QScrollArea)
        if scroll_area:
            scroll_bar = scroll_area.verticalScrollBar()
            scroll_bar.setValue(scroll_bar.maximum())
    
    def update_progress(self, progress_id: str, current: int, total: int, message: str = ""):
        """更新进度"""
        if progress_id not in self.progress_bars:
            return False
        
        self.progress_bars[progress_id].update_progress(current, total, message)
        
        # 如果启用了自动滚动，确保进度条可见
        if self.auto_scroll_button.isChecked():
            self.ensure_progress_visible(progress_id)
        
        return True
    
    def ensure_progress_visible(self, progress_id):
        """确保指定进度条在可视区域内"""
        if progress_id not in self.progress_bars:
            return
        
        progress_bar = self.progress_bars[progress_id]
        scroll_area = self.findChild(QScrollArea)
        if scroll_area:
            # 计算进度条在滚动区域中的位置
            progress_pos = progress_bar.mapTo(scroll_area, progress_bar.rect().topLeft())
            
            # 如果进度条不在可视区域内，滚动到它
            viewport = scroll_area.viewport()
            if (progress_pos.y() < 0 or 
                progress_pos.y() + progress_bar.height() > viewport.height()):
                scroll_bar = scroll_area.verticalScrollBar()
                target_value = scroll_bar.value() + progress_pos.y()
                scroll_bar.setValue(target_value)
    
    def set_visibility(self, progress_id: str, visible: bool):
        """设置可见性"""
        if progress_id not in self.progress_bars:
            return False
        
        self.progress_bars[progress_id].setVisible(visible)
        return True
    
    def set_style(self, progress_id: str, style: ProgressBarStyle):
        """设置样式"""
        if progress_id not in self.progress_bars:
            return False
        
        self.progress_bars[progress_id].apply_style(style)
        return True
    
    def remove_progress_bar(self, progress_id: str):
        """移除进度条"""
        if progress_id not in self.progress_bars:
            return False
        
        progress_bar = self.progress_bars[progress_id]
        self.container_layout.removeWidget(progress_bar)
        progress_bar.deleteLater()
        del self.progress_bars[progress_id]
        
        # 更新统计信息
        self.update_stats()
        return True
    
    def clear_all(self):
        """清除所有进度条"""
        for progress_id in list(self.progress_bars.keys()):
            self.remove_progress_bar(progress_id)
    
    def toggle_collapse(self):
        """切换折叠/展开状态"""
        for progress_bar in self.progress_bars.values():
            current_visibility = progress_bar.isVisible()
            progress_bar.setVisible(not current_visibility)
    
    def update_stats(self):
        """更新统计信息"""
        count = len(self.progress_bars)
        self.stats_label.setText(f"进度条数量: {count}")
    
    def get_progress_bar_count(self) -> int:
        """获取进度条数量"""
        return len(self.progress_bars)
