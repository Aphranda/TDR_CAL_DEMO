# src/app/widgets/LogWidget/Model.py
import os
from pathlib import Path
from datetime import datetime

class LogWidgetModel:
    """日志数据模型（状态管理+持久化存储）"""
    def __init__(self, max_lines=5000):
        # 显示配置
        self._max_lines = max_lines
        self.auto_scroll = True
        self.show_timestamps = True
        
        # 日志级别配置
        self.LEVELS = {
            "DEBUG":    ("#666666", "Debug"),
            "INFO":     ("#000000", "Info"),
            "SUCCESS":  ("#228B22", "Success"),
            "WARNING":  ("#FF8C00", "Warning"),
            "ERROR":    ("#FF0000", "Error"),
            "CRITICAL": ("#8B0000", "Critical"),
            "SEND":     ("#0078D7", "Send"),
            "RECV":     ("#8E44AD", "Receive")
        }
        
        # 文件配置
        self.log_dir = "logs"
        self.max_log_size = 10 * 1024 * 1024  # 10MB
        self._current_log_file = None
        self._ensure_log_dir()
    
    @property
    def max_lines(self):
        return self._max_lines
    
    @max_lines.setter
    def max_lines(self, value):
        self._max_lines = max(100, int(value))
    
    def _ensure_log_dir(self):
        """确保日志目录存在"""
        os.makedirs(self.log_dir, exist_ok=True)
    
    def get_current_log_path(self):
        """获取当日日志文件路径"""
        today = datetime.now().strftime("%Y%m%d")
        return Path(self.log_dir) / f"rnx_{today}.log"
    
    def should_rotate_log(self):
        """检查是否需要日志轮转"""
        log_path = self.get_current_log_path()
        return log_path.exists() and log_path.stat().st_size > self.max_log_size
    
    def get_rotated_log_path(self):
        """生成轮转后的文件名"""
        timestamp = datetime.now().strftime("%H%M%S")
        return self.get_current_log_path().with_name(
            f"rnx_{datetime.now().strftime('%Y%m%d')}_{timestamp}.log"
        )
    
    def open_log_file(self):
        """打开当前日志文件"""
        if self.should_rotate_log():
            os.rename(
                self.get_current_log_path(),
                self.get_rotated_log_path()
            )
        
        self._current_log_file = open(
            self.get_current_log_path(),
            "a",
            encoding="utf-8"
        )
        return self._current_log_file
    
    def close_log_file(self):
        """安全关闭日志文件"""
        if self._current_log_file and not self._current_log_file.closed:
            self._current_log_file.close()
    
    def write_log_entry(self, message, level):
        """写入格式化日志条目"""
        if not self._current_log_file:
            return
        
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
        self._current_log_file.write(
            f"[{timestamp}] [{level}] {message}\n"
        )
        self._current_log_file.flush()
