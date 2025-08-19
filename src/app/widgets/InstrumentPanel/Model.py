# src/app/widgets/InstrumentPanel/Model.py
class InstrumentPanelModel:
    def __init__(self):
        self.connected = False
        self.instrument_type = "VNA"
        self.ip_address = "192.168.1.100"
        self.port = 5025
