# src/app/widgets/PlotWidget/__init__.py
from .Model import PlotWidgetModel
from .View import PlotWidgetView
from .Controller import PlotWidgetController

def create_plot_widget(title="Plot"):
    model = PlotWidgetModel(title)
    view = PlotWidgetView(title)
    controller = PlotWidgetController(model, view)
    return view
