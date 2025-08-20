# src/app/widgets/VNAControlPanel/Model.py
class VNAControlModel:
    def __init__(self):
        self.frequency_start = 1e6  # 1 MHz
        self.frequency_stop = 3e9   # 3 GHz
        self.points = 201
        self.power = 0  # dBm
        self.if_bandwidth = 1000  # Hz
