from enum import Enum
from dataclasses import dataclass
from typing import List

class CalibrationType(Enum):
    SOLT = "SOLT(Short-Open-Load-Thru)"
    TRL = "TRL(Thru-Reflect-Line)"

class PortConfig(Enum):
    SINGLE = "单端口(1)"
    DUAL = "双端口(1-2)"

@dataclass
class CalibrationParameters:
    cal_type: CalibrationType = CalibrationType.SOLT
    port_config: PortConfig = PortConfig.SINGLE
    start_freq: float = 1e6  # 1MHz
    stop_freq: float = 6e9   # 6GHz

class CalibrationModel:
    def __init__(self):
        self.params = CalibrationParameters()
        self.steps = []
        self.progress = 0
        
    def generate_calibration_steps(self):
        """根据当前配置生成校准步骤"""
        self.steps = []
        
        if self.params.cal_type == CalibrationType.SOLT:
            self.steps.append("1. 连接短路器到端口1")
            self.steps.append("2. 测量短路标准件")
            self.steps.append("3. 连接开路器到端口1")
            self.steps.append("4. 测量开路标准件")
            self.steps.append("5. 连接负载到端口1")
            self.steps.append("6. 测量负载标准件")
            
            if self.params.port_config == PortConfig.DUAL:
                self.steps.append("7. 连接直通件到端口1-2")
                self.steps.append("8. 测量直通标准件")
                
        elif self.params.cal_type == CalibrationType.TRL:
            self.steps.append("1. 连接直通件到端口1-2")
            self.steps.append("2. 测量直通标准件")
            self.steps.append("3. 连接反射件到端口1")
            self.steps.append("4. 测量反射标准件")
            self.steps.append("5. 连接延迟线到端口1-2")
            self.steps.append("6. 测量延迟线标准件")
            
        self.steps.append("7. 计算误差系数")
        self.steps.append("8. 保存校准结果")
        
        return self.steps
    
    def simulate_calibration(self):
        """模拟校准过程"""
        self.progress = 0
        total_steps = len(self.steps)
        
        for i, step in enumerate(self.steps):
            # 这里应该替换为实际的仪器操作
            print(f"执行步骤: {step}")
            self.progress = int((i + 1) / total_steps * 100)
            yield step, self.progress
