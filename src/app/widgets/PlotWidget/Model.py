# src/app/widgets/PlotWidget/Model.py
class PlotWidgetModel:
    def __init__(self, title):
        self.title = title
        self.x_data = []
        self.y_data = []
        self.x_label = "X"
        self.y_label = "Y"
