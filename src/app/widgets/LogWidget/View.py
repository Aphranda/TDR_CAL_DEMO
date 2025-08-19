# src/app/widgets/LogWidget/View.py
from PyQt5.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QTextEdit,
    QToolBar,
    QComboBox,
    QAction,
    QLineEdit,
    QMenu,
    QLabel
)
from PyQt5.QtGui import (
    QTextCursor,
    QTextCharFormat,
    QColor,
    QFont,
    QIcon
)
from PyQt5.QtCore import Qt, pyqtSignal

class LogWidgetView(QWidget):
    """日志显示视图（纯UI组件）"""
    content_appended = pyqtSignal()

    # UI交互信号
    level_changed = pyqtSignal(str)
    font_size_changed = pyqtSignal(int)
    word_wrap_toggled = pyqtSignal(bool)
    timestamp_toggled = pyqtSignal(bool)
    search_requested = pyqtSignal(str)
    clear_requested = pyqtSignal()
    export_requested = pyqtSignal(str)
    copy_requested = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()
        self._connect_signals()
        self._load_stylesheet()

    def _setup_ui(self):
        """初始化所有UI组件"""
        # 主布局
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.layout.setSpacing(2)

        # 工具栏
        self.toolbar = QToolBar()
        self.toolbar.setMovable(False)

        # 日志级别选择
        self.level_combo = QComboBox()
        self.toolbar.addWidget(QLabel("级别:"))
        self.toolbar.addWidget(self.level_combo)

        # 字体大小选择
        self.font_combo = QComboBox()
        self.font_combo.addItems(map(str, range(8, 16)))
        self.font_combo.setCurrentText("10")
        self.toolbar.addWidget(QLabel("字体:"))
        self.toolbar.addWidget(self.font_combo)

        # 工具栏按钮
        self.wrap_action = QAction("自动换行", self)
        self.wrap_action.setCheckable(True)
        self.toolbar.addAction(self.wrap_action)

        self.timestamp_action = QAction("时间戳", self)
        self.timestamp_action.setCheckable(True)
        self.timestamp_action.setChecked(True)
        self.toolbar.addAction(self.timestamp_action)

        # 搜索框
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("搜索...")
        self.search_edit.setMaximumWidth(200)
        self.toolbar.addWidget(self.search_edit)

        self.search_action = QAction("搜索", self)
        self.toolbar.addAction(self.search_action)

        # 清空按钮
        self.clear_action = QAction("清空", self)
        self.toolbar.addAction(self.clear_action)

        # 日志显示区域
        self.text_edit = QTextEdit()
        self.text_edit.setReadOnly(True)
        self.text_edit.setLineWrapMode(QTextEdit.NoWrap)
        self.text_edit.setFont(QFont("Consolas", 10))
        self.text_edit.setContextMenuPolicy(Qt.CustomContextMenu)

        # 组装布局
        self.layout.addWidget(self.toolbar)
        self.layout.addWidget(self.text_edit)

    def _connect_signals(self):
        """连接内部信号"""
        self.level_combo.currentTextChanged.connect(self.level_changed)
        self.font_combo.currentTextChanged.connect(
            lambda: self.font_size_changed.emit(int(self.font_combo.currentText()))
        )
        self.wrap_action.toggled.connect(self.word_wrap_toggled)
        self.timestamp_action.toggled.connect(self.timestamp_toggled)
        self.search_action.triggered.connect(self._emit_search)
        self.search_edit.returnPressed.connect(self._emit_search)
        self.clear_action.triggered.connect(self.clear_requested)
        self.text_edit.customContextMenuRequested.connect(self._show_context_menu)

    def _emit_search(self):
        """触发搜索信号"""
        text = self.search_edit.text().strip()
        if text:
            self.search_requested.emit(text)

    def _show_context_menu(self, pos):
        """显示右键菜单"""
        menu = QMenu(self)
        
        copy_action = menu.addAction("复制")
        copy_action.triggered.connect(self.copy_requested)
        
        select_all_action = menu.addAction("全选")
        select_all_action.triggered.connect(self.text_edit.selectAll)
        
        menu.addSeparator()
        
        export_action = menu.addAction("导出日志...")
        export_action.triggered.connect(lambda: self.export_requested.emit(""))
        
        menu.exec_(self.text_edit.mapToGlobal(pos))

    def _load_stylesheet(self):
        """加载样式表"""
        self.setStyleSheet("""
            QTextEdit {
                font-family: Consolas;
                font-size: 10pt;
                background-color: #f8f8f8;
            }
            QToolBar {
                background: #e0e0e0;
                padding: 2px;
                border-bottom: 1px solid #ccc;
            }
        """)

    # 公共接口
    def append_html(self, html):
        cursor = self.text_edit.textCursor()
        cursor.movePosition(QTextCursor.End)
        cursor.insertHtml(html + "<br>")
        self.content_appended.emit()

    def clear_content(self):
        """清空内容"""
        self.text_edit.clear()

    def scroll_to_bottom(self):
        """滚动到底部"""
        self.text_edit.ensureCursorVisible()

    def set_levels(self, levels):
        """设置可选的日志级别"""
        self.level_combo.clear()
        self.level_combo.addItem("ALL", "ALL")
        for level, (_, display_name) in levels.items():
            self.level_combo.addItem(display_name, level)

    def set_word_wrap(self, enabled):
        """设置自动换行"""
        self.text_edit.setLineWrapMode(
            QTextEdit.WidgetWidth if enabled else QTextEdit.NoWrap
        )

    def set_font_size(self, size):
        """设置字体大小"""
        font = self.text_edit.font()
        font.setPointSize(size)
        self.text_edit.setFont(font)

    def highlight_text(self, text):
        """高亮搜索文本"""
        self.clear_highlights()
        
        if not text:
            return
            
        doc = self.text_edit.document()
        cursor = QTextCursor(doc)
        format = QTextCharFormat()
        format.setBackground(QColor(255, 255, 0, 100))
        
        while True:
            cursor = doc.find(text, cursor)
            if cursor.isNull():
                break
            cursor.mergeCharFormat(format)

    def clear_highlights(self):
        """清除所有高亮"""
        cursor = self.text_edit.textCursor()
        cursor.select(QTextCursor.Document)
        format = QTextCharFormat()
        format.setBackground(Qt.transparent)
        cursor.mergeCharFormat(format)
