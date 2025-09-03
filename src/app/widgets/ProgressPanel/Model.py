# src/app/widgets/ProgressPanel/Model.py
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, Optional
from PyQt5.QtCore import QObject, pyqtSignal

class ProgressBarStyle(Enum):
    DEFAULT = "default"
    BLUE = "blue"
    GREEN = "green"
    ORANGE = "orange"
    RED = "red"
    PURPLE = "purple"
    CYAN = "cyan"
    PINK = "pink"

@dataclass
class ProgressBarData:
    id: str
    label: str
    current: int = 0
    total: int = 100
    visible: bool = True
    style: ProgressBarStyle = ProgressBarStyle.DEFAULT
    format_string: str = "{label}: {value}% - {current}/{total}"
    extra_info: Dict = field(default_factory=dict)

class ProgressManager(QObject):
    """进度管理器模型 - 现在完全在ProgressPanel中管理"""
    progress_added = pyqtSignal(str, str)  # (progress_id, label)
    progress_updated = pyqtSignal(str, int, int, str)  # (progress_id, current, total, message)
    progress_removed = pyqtSignal(str)  # progress_id
    progress_visibility_changed = pyqtSignal(str, bool)  # (progress_id, visible)
    progress_style_changed = pyqtSignal(str, ProgressBarStyle)  # (progress_id, style)
    all_progress_cleared = pyqtSignal()  # 所有进度条已清除
    
    def __init__(self):
        super().__init__()
        self.progress_bars: Dict[str, ProgressBarData] = {}
    
    def add_progress_bar(self, progress_id: str, label: str, total: int = 100, 
                        style: ProgressBarStyle = ProgressBarStyle.DEFAULT) -> bool:
        """添加进度条"""
        if progress_id in self.progress_bars:
            return False
        
        self.progress_bars[progress_id] = ProgressBarData(
            id=progress_id,
            label=label,
            total=total,
            style=style
        )
        self.progress_added.emit(progress_id, label)
        return True
    
    def update_progress(self, progress_id: str, current: int, total: Optional[int] = None, 
                       message: str = "") -> bool:
        """更新进度"""
        if progress_id not in self.progress_bars:
            return False
        
        progress = self.progress_bars[progress_id]
        progress.current = current
        if total is not None:
            progress.total = total
        
        self.progress_updated.emit(progress_id, current, progress.total, message)
        return True
    
    def set_visibility(self, progress_id: str, visible: bool) -> bool:
        """设置可见性"""
        if progress_id not in self.progress_bars:
            return False
        
        self.progress_bars[progress_id].visible = visible
        self.progress_visibility_changed.emit(progress_id, visible)
        return True
    
    def set_style(self, progress_id: str, style: ProgressBarStyle) -> bool:
        """设置样式"""
        if progress_id not in self.progress_bars:
            return False
        
        self.progress_bars[progress_id].style = style
        self.progress_style_changed.emit(progress_id, style)
        return True
    
    def remove_progress_bar(self, progress_id: str) -> bool:
        """移除进度条"""
        if progress_id not in self.progress_bars:
            return False
        
        del self.progress_bars[progress_id]
        self.progress_removed.emit(progress_id)
        return True
    
    def get_progress(self, progress_id: str) -> Optional[ProgressBarData]:
        """获取进度条数据"""
        return self.progress_bars.get(progress_id)
    
    def get_all_progress_ids(self) -> list:
        """获取所有进度条ID"""
        return list(self.progress_bars.keys())
    
    def clear_all(self):
        """清除所有进度条"""
        for progress_id in list(self.progress_bars.keys()):
            self.remove_progress_bar(progress_id)
        self.all_progress_cleared.emit()
    
    def get_progress_count(self) -> int:
        """获取进度条数量"""
        return len(self.progress_bars)
