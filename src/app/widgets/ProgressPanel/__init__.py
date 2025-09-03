# src/app/widgets/ProgressPanel/__init__.py
from .View import ProgressPanelView
from .Controller import ProgressPanelController
from .Model import ProgressManager, ProgressBarStyle

def create_progress_panel(title="进度监控", parent=None):
    """创建进度面板的工厂函数"""
    view = ProgressPanelView(title, parent)
    model = ProgressManager()
    controller = ProgressPanelController(view, model)
    return view, controller, model

def create_progress_panel_simple(title="进度监控", parent=None):
    """简化创建函数"""
    view = ProgressPanelView(title, parent)
    model = ProgressManager()
    controller = ProgressPanelController(view, model)
    return controller

# 导出常用类和枚举
__all__ = [
    'ProgressPanelView',
    'ProgressPanelController', 
    'ProgressManager',
    'ProgressBarStyle',
    'create_progress_panel',
    'create_progress_panel_simple'
]
