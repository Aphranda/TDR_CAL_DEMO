# src/app/widgets/CalibrationPanel/__init__.py
from .View import CalibrationView
from .Model import CalibrationModel
from .Controller import CalibrationController

def create_calibration_panel(parent=None):
    """创建校准面板的工厂函数"""
    view = CalibrationView(parent)
    model = CalibrationModel()
    controller = CalibrationController(view, model)
    return view, controller
