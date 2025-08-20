# src/app/widgets/DataAnalysisPanel/__init__.py
from .Model import DataAnalysisModel
from .View import DataAnalysisView
from .Controller import DataAnalysisController

def create_data_analysis_panel():
    model = DataAnalysisModel()
    view = DataAnalysisView()
    controller = DataAnalysisController(view, model)
    return view, controller  # 返回视图和控制器
