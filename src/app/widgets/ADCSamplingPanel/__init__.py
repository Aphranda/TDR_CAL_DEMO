# src/app/widgets/ADCSamplingPanel/__init__.py
from .Model import ADCSamplingModel
from .View import ADCSamplingView
from .Controller import ADCSamplingController

def create_adc_sampling_panel():
    model = ADCSamplingModel()
    view = ADCSamplingView()
    controller = ADCSamplingController(view, model)
    return view, controller  # 返回视图和控制器
