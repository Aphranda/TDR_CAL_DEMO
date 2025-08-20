# src/app/widgets/VNAControlPanel/__init__.py
from .Model import VNAControlModel
from .View import VNAControlView
from .Controller import VNAControlController

def create_vna_control_panel():
    model = VNAControlModel()
    view = VNAControlView()
    controller = VNAControlController(view, model)
    return view,controller
