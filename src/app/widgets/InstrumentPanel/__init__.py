# src/app/widgets/InstrumentPanel/__init__.py
from .Model import InstrumentPanelModel
from .View import InstrumentPanelView
from .Controller import InstrumentPanelController

def create_instrument_panel():
    model = InstrumentPanelModel()
    view = InstrumentPanelView()
    controller = InstrumentPanelController(model, view)
    return view, controller  # 返回视图和控制器
