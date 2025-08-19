# src/app/widgets/LogWidget/Controller.py
import os
import time
from pathlib import Path
from PyQt5.QtCore import QObject, pyqtSignal, QTimer
from PyQt5.QtWidgets import QFileDialog, QMessageBox
from PyQt5.QtGui import QIcon
from datetime import datetime

class LogWidgetController(QObject):
    """日志业务逻辑控制器"""
    
    error_logged = pyqtSignal(str)
    
    def __init__(self, view, model):
        super().__init__()
        self.view = view
        self.model = model
        self._log_file = None
        
        self._init_ui()
        self._connect_signals()
        self._open_log_file()
    
    def _init_ui(self):
        """初始化UI状态"""
        self.view.set_levels(self.model.LEVELS)
        self.view.set_word_wrap(False)
        self.view.set_font_size(10)
    
    def _connect_signals(self):
        """连接所有信号槽"""
        # UI交互信号
        self.view.content_appended.connect(self._handle_content_appended)
        self.view.level_changed.connect(self.set_log_level)
        self.view.font_size_changed.connect(self.view.set_font_size)
        self.view.word_wrap_toggled.connect(self.view.set_word_wrap)
        self.view.timestamp_toggled.connect(
            lambda x: setattr(self.model, "show_timestamps", x)
        )
        self.view.search_requested.connect(self.search)
        self.view.clear_requested.connect(self.clear)
        self.view.export_requested.connect(self.export_log)
        self.view.copy_requested.connect(self.view.text_edit.copy)
        
        # 自动滚动检测
        scroll_bar = self.view.text_edit.verticalScrollBar()
        scroll_bar.valueChanged.connect(
            lambda: setattr(
                self.model, 
                "auto_scroll",
                abs(scroll_bar.value() - scroll_bar.maximum()) < 10
            )
        )
    
    def _open_log_file(self):
        """打开日志文件"""
        self._log_file = self.model.open_log_file()
    
    def log(self, message, level="INFO"):
        """记录日志主方法"""
        if level not in self.model.LEVELS:
            return
            
        # 生成带样式的HTML
        timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
        color = self.model.LEVELS[level][0]
        
        html_parts = []
        if self.model.show_timestamps:
            html_parts.append(f'<span style="color:gray;">[{timestamp}]</span>')
        html_parts.append(f'<span style="color:{color};font-weight:bold;">[{level}]</span>')
        html_parts.append(f'<span style="color:{color};">{message}</span>')
        
        # 更新UI
        self.view.append_html(" ".join(html_parts))
        
        # 写入文件
        self.model.write_log_entry(message, level)
        
        # 触发错误信号
        if level in ("ERROR", "CRITICAL"):
            self.error_logged.emit(message)
    
    def _handle_content_appended(self):
        """处理内容追加事件"""
        if self.model.auto_scroll:
            self.view.scroll_to_bottom()

    def set_log_level(self, level):
        """设置日志显示级别"""
        if level == "ALL":
            self.model.enabled_levels = set(self.model.LEVELS.keys())
        else:
            self.model.enabled_levels = {level}
    
    def search(self, text):
        """搜索日志内容"""
        self.view.highlight_text(text)
        if text:
            self.view.search_edit.setStyleSheet("background: #fffacd;")
            QTimer.singleShot(1000, lambda: self.view.search_edit.setStyleSheet(""))
    
    def clear(self):
        """清空日志"""
        self.view.clear_content()
    
    def export_log(self, file_path=None):
        """导出日志到文件"""
        if not file_path:
            file_path, _ = QFileDialog.getSaveFileName(
                self.view,
                "导出日志",
                "",
                "文本文件 (*.txt);;HTML文件 (*.html)"
            )
            if not file_path:
                return
        
        try:
            if file_path.endswith(".html"):
                content = self.view.text_edit.toHtml()
            else:
                content = self.view.text_edit.toPlainText()
            
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(content)
            
            self.log(f"日志已导出到: {file_path}", "SUCCESS")
        except Exception as e:
            self.log(f"导出失败: {str(e)}", "ERROR")
    
    def cleanup(self):
        """清理资源"""
        self.model.close_log_file()
    
    def clean_old_logs(self, log_dir="logs", days_to_keep=7):
        """清理过期日志，添加确认对话框"""
        now = time.time()
        cutoff = now - days_to_keep * 86400
        
        # 先扫描过期文件
        old_logs = []
        for filename in os.listdir(log_dir):
            path = os.path.join(log_dir, filename)
            if os.path.isfile(path) and filename.startswith("rnx_"):
                stat = os.stat(path)
                if stat.st_mtime < cutoff:
                    old_logs.append((path, stat.st_size,time.strftime('%Y-%m-%d', time.localtime(stat.st_mtime))))
        
        if not old_logs:
            self.log("系统日志更新", "INFO")
            return
        
        # 创建消息框并应用样式
        msg = QMessageBox()
        msg.setStyleSheet(self.view.styleSheet())

        # 设置窗口图标
        icon_path = "src/resources/icons/icon_RNX_01.ico"
        if Path(icon_path).exists():
            msg.setWindowIcon(QIcon(icon_path))
        else:
            print(f"警告: 图标文件未找到 - {icon_path}")


        # 设置消息框属性
        msg.setIcon(QMessageBox.Question)
        msg.setWindowTitle("确认删除过期日志")
        
        # 显示前5个文件作为示例
        sample_files = "\n".join([f"{date} - {os.path.basename(path)}" 
                                for path, _, date in old_logs[:5]])
        if len(old_logs) > 5:
            sample_files += f"\n...及其他{len(old_logs)-5}个文件"
        
        total_size = sum(size for _, size, _ in old_logs)
        msg.setText(f"检测到{len(old_logs)}个过期日志文件(共{total_size/1024:.1f}KB)\n\n"
                f"示例文件:\n{sample_files}\n\n"
                f"确定要删除这些文件吗?")
        
        msg.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
        msg.setDefaultButton(QMessageBox.No)
        
        # 添加详情按钮
        detail_button = msg.addButton("查看详情", QMessageBox.ActionRole)
        

        ret = msg.exec_()
        
        if msg.clickedButton() == detail_button:
            # 显示完整文件列表
            detail_msg = QMessageBox()
            detail_msg.setWindowTitle("过期日志详情")
            detail_msg.setText("以下文件将被删除:")
            detail_msg.setDetailedText("\n".join(
                f"{date} - {os.path.basename(path)} ({size/1024:.1f}KB)"
                for path, size, date in old_logs
            ))
            

            detail_msg.exec_()
            
            # 再次显示确认对话框
            ret = msg.exec_()
        
        if ret == QMessageBox.No:
            self.log("用户取消了日志清理操作", "INFO")
            return
        
        # 执行删除
        deleted_count = 0
        deleted_size = 0
        for path, size, _ in old_logs:
            try:
                os.remove(path)
                deleted_count += 1
                deleted_size += size
            except Exception as e:
                self.log(f"删除日志文件失败 {path}: {e}", "ERROR")
        
        if deleted_count > 0:
            self.log(f"已清理{deleted_count}个过期日志文件, 释放空间{deleted_size/1024:.1f}KB", "SUCCESS")


    def _update_log_level(self, level=None):
        """更新显示的日志级别
        
        Args:
            level (str, optional): 要设置的级别。如果为None则从UI获取
        """
        if level is None:
            level = self.view.level_combo.currentData()
        
        if level == "ALL":
            self.enabled_levels = set(self.LEVELS.keys())
        else:
            self.enabled_levels = {level}
        
        # 更新UI显示
        if level and level != "ALL":
            index = self.view.level_combo.findData(level)
            if index >= 0:
                self.view.level_combo.setCurrentIndex(index)


    def _search_text(self, search_str):
        """搜索文本并高亮"""
        self.view.clear_highlights()
        
        doc = self.view.text_edit.document()
        cursor = self.view.text_edit.textCursor()
        options = QTextDocument.FindCaseSensitively
        
        # 第一次搜索：从当前位置到文档末尾
        found_cursor = doc.find(search_str, cursor, options)
        
        # 第二次搜索：如果没找到，从文档开头再搜索
        if found_cursor.isNull():
            cursor = QTextCursor(doc)
            found_cursor = doc.find(search_str, cursor, options)
            if found_cursor.isNull():
                self.log(f"未找到: {search_str}", "WARNING")
                return
        
        # 高亮所有匹配项
        self.view.highlight_text(search_str, options)
        
        # 精确定位到匹配项
        self.view.text_edit.setTextCursor(found_cursor)
        self.view.text_edit.ensureCursorVisible()

    def _export_log(self, file_path):
        """导出日志到文件"""
        if not file_path:
            file_path, _ = QFileDialog.getSaveFileName(
                self.view, "导出日志", "", "文本文件 (*.txt);;HTML文件 (*.html)"
            )
            if not file_path:
                return
        
        try:
            if file_path.endswith(".html"):
                content = self.view.text_edit.toHtml()
            else:
                content = self.view.text_edit.toPlainText()
            
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(content)
            
            self.log(f"日志已导出到: {file_path}", "SUCCESS")
        except Exception as e:
            self.log(f"导出失败: {str(e)}", "ERROR")

    def set_max_lines(self, max_lines):
        """设置最大日志行数"""
        self.max_lines = max(100, int(max_lines))

    def set_auto_scroll(self, enabled):
        """设置是否自动滚动到底部"""
        self._auto_scroll = bool(enabled)
        if enabled:
            self.view.scroll_to_bottom()

