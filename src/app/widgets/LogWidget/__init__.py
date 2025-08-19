# src/app/widgets/LogWidget/__init__.py
from PyQt5.QtWidgets import QWidget, QVBoxLayout
from PyQt5.QtCore import pyqtSignal
from .View import LogWidgetView
from .Controller import LogWidgetController
from .Model import LogWidgetModel

def create_log_widget(parent=None, max_lines=5000, default_level="ALL"):
    """创建完整的日志组件（MVC模式）
    
    Args:
        parent: 父级窗口
        max_lines: 最大日志行数
        default_level: 默认日志级别
        
    Returns:
        Tuple[QWidget, LogWidgetController]: (可视化组件, 控制器实例)
    """
    # 创建容器组件
    container = QWidget(parent)
    layout = QVBoxLayout(container)
    layout.setContentsMargins(0, 0, 0, 0)
    
    # 初始化MVC组件
    model = LogWidgetModel(max_lines=max_lines)
    view = LogWidgetView(container)
    controller = LogWidgetController(view, model)
    
    # 初始化配置
    controller.set_log_level(default_level)
    
    # 设置布局
    layout.addWidget(view)
    
    # 转发控制器的error_logged信号
    container.errorLogged = controller.error_logged
    
    # 添加便捷方法
    def log(message, level="INFO"):
        controller.log(message, level)
    
    container.log = log
    container.clear = controller.clear
    container.set_max_lines = model.max_lines
    
    return container, controller

# 显式导出接口
__all__ = [
    'LogWidgetView',
    'LogWidgetController', 
    'LogWidgetModel',
    'create_log_widget'
]
