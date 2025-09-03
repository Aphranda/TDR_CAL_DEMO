# src/app/widgets/ProgressPanel/Controller.py
from PyQt5.QtCore import QObject
from .Model import ProgressManager, ProgressBarStyle
from .View import ProgressPanelView

class ProgressPanelController(QObject):
    """进度面板控制器"""
    def __init__(self, view: ProgressPanelView, model: ProgressManager):
        super().__init__()
        self.view = view
        self.model = model
        self.setup_connections()
    
    def setup_connections(self):
        """设置信号连接"""
        self.model.progress_added.connect(self.on_progress_added)
        self.model.progress_updated.connect(self.on_progress_updated)
        self.model.progress_removed.connect(self.on_progress_removed)
        self.model.progress_visibility_changed.connect(self.on_visibility_changed)
        self.model.progress_style_changed.connect(self.on_style_changed)
        self.model.all_progress_cleared.connect(self.on_all_cleared)
        
        # 连接视图按钮信号
        self.view.clear_button.clicked.connect(self.clear_all)
    
    def on_progress_added(self, progress_id: str, label: str):
        """处理进度条添加"""
        progress_data = self.model.get_progress(progress_id)
        if progress_data:
            self.view.add_progress_bar(progress_id, label, progress_data.style)
            self.view.set_visibility(progress_id, progress_data.visible)
    
    def on_progress_updated(self, progress_id: str, current: int, total: int, message: str):
        """处理进度更新"""
        self.view.update_progress(progress_id, current, total, message)
    
    def on_progress_removed(self, progress_id: str):
        """处理进度条移除"""
        self.view.remove_progress_bar(progress_id)
    
    def on_visibility_changed(self, progress_id: str, visible: bool):
        """处理可见性变化"""
        self.view.set_visibility(progress_id, visible)
    
    def on_style_changed(self, progress_id: str, style: ProgressBarStyle):
        """处理样式变化"""
        self.view.set_style(progress_id, style)
    
    def on_all_cleared(self):
        """处理所有进度条清除"""
        self.view.clear_all()
    
    def add_progress_bar(self, progress_id: str, label: str, total: int = 100, 
                        style: ProgressBarStyle = ProgressBarStyle.DEFAULT) -> bool:
        """添加进度条"""
        return self.model.add_progress_bar(progress_id, label, total, style)
    
    def update_progress(self, progress_id: str, current: int, total: int = None, 
                       message: str = "") -> bool:
        """更新进度"""
        return self.model.update_progress(progress_id, current, total, message)
    
    def set_visibility(self, progress_id: str, visible: bool) -> bool:
        """设置可见性"""
        return self.model.set_visibility(progress_id, visible)
    
    def set_style(self, progress_id: str, style: ProgressBarStyle) -> bool:
        """设置样式"""
        return self.model.set_style(progress_id, style)
    
    def remove_progress_bar(self, progress_id: str) -> bool:
        """移除进度条"""
        return self.model.remove_progress_bar(progress_id)
    
    def clear_all(self):
        """清除所有进度条"""
        self.model.clear_all()
    
    def get_progress(self, progress_id: str):
        """获取进度数据"""
        return self.model.get_progress(progress_id)
    
    def get_all_progress_ids(self) -> list:
        """获取所有进度条ID"""
        return self.model.get_all_progress_ids()
    
    def get_progress_count(self) -> int:
        """获取进度条数量"""
        return self.model.get_progress_count()
