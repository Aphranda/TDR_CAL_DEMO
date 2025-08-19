# src/app/windows/MainWindow/__init__.py
from .Model import MainWindowModel
from .View import MainWindowView
from .Controller import MainWindowController

def create_main_window():
    model = MainWindowModel()
    view = MainWindowView()
    controller = MainWindowController(view, model)
    return view, controller, model
