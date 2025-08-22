# src/app/widgets/CalibrationPanel/Model.py
from enum import Enum
from dataclasses import dataclass
from typing import List

class CalibrationType(Enum):
    SOLT = "SOLT(Short-Open-Load-Thru)"
    TRL = "TRL(Thru-Reflect-Line)"

class PortConfig(Enum):
    SINGLE = "单端口(1)"
    DUAL = "双端口(1-2)"

class CalibrationKitType(Enum):  # 新增：校准件类型
    ELECTRONIC = "电子校准件"
    MECHANICAL = "机械校准件"

@dataclass
class CalibrationParameters:
    cal_type: CalibrationType = CalibrationType.SOLT
    port_config: PortConfig = PortConfig.SINGLE
    kit_type: CalibrationKitType = CalibrationKitType.MECHANICAL  # 新增：校准件类型
    start_freq: float = 1000.0  # MHz
    stop_freq: float = 35000.0   # MHz
    step_freq: float = 100.0    # MHz
    calibration_pow: float = -20.0  # dBm
    calibration_ifbw: int = 1000    # Hz

class CalibrationModel:
    def __init__(self):
        self.params = CalibrationParameters()
        self.steps = []
        self.progress = 0
        
    def generate_calibration_steps(self):
        """改进的校准步骤生成"""
        self.steps = []
        
        if self.params.cal_type == CalibrationType.SOLT:
            # 单端口或双端口的SOL测量
            self.steps.append("1. 连接短路器到端口1")
            self.steps.append("2. 测量端口1短路标准件")
            self.steps.append("3. 连接开路器到端口1")
            self.steps.append("4. 测量端口1开路标准件")
            self.steps.append("5. 连接负载到端口1")
            self.steps.append("6. 测量端口1负载标准件")
            
            if self.params.port_config == PortConfig.DUAL:
                self.steps.append("7. 连接短路器到端口2")
                self.steps.append("8. 测量端口2短路标准件")
                self.steps.append("9. 连接开路器到端口2")
                self.steps.append("10. 测量端口2开路标准件")
                self.steps.append("11. 连接负载到端口2")
                self.steps.append("12. 测量端口2负载标准件")
                self.steps.append("13. 连接直通件到端口1-2")
                self.steps.append("14. 测量直通标准件")
                
        elif self.params.cal_type == CalibrationType.TRL:
            self.steps.append("1. 连接直通件到端口1-2")
            self.steps.append("2. 测量直通标准件")
            self.steps.append("3. 连接反射件到端口1")
            self.steps.append("4. 测量端口1反射标准件")
            self.steps.append("5. 连接反射件到端口2")
            self.steps.append("6. 测量端口2反射标准件")
            self.steps.append("7. 连接延迟线到端口1-2")
            self.steps.append("8. 测量延迟线标准件")
            
        self.steps.append("计算误差系数")
        self.steps.append("验证校准质量")
        self.steps.append("保存校准结果")
        
        return self.steps

    def simulate_calibration(self):
        """模拟校准过程"""
        self.progress = 0
        total_steps = len(self.steps)
        
        for i, step in enumerate(self.steps):
            # 这里应该替换为实际的仪器操作
            print(f"执行步骤: {step}")
            self.progress = int((i + 1) / total_steps * 100)
            
            # 如果是机械校准件且需要人工操作的步骤，发出提示信号
            if (self.params.kit_type == CalibrationKitType.MECHANICAL and 
                ("连接" in step or "更换" in step)):
                yield step, self.progress, True  # 第三个参数表示需要用户确认
            else:
                yield step, self.progress, False
