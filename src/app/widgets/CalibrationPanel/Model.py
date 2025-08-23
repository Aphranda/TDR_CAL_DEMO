# src/app/widgets/CalibrationPanel/Model.py
from enum import Enum
from dataclasses import dataclass
from typing import List
import os
import datetime

class CalibrationType(Enum):
    SOLT = "SOLT(Short-Open-Load-Thru)"
    TRL = "TRL(Thru-Reflect-Line)"

class PortConfig(Enum):
    SINGLE = "单端口(1)"
    DUAL = "双端口(1-2)"

class CalibrationKitType(Enum):
    ELECTRONIC = "电子校准件"
    MECHANICAL = "机械校准件"

@dataclass
class CalibrationParameters:
    cal_type: CalibrationType = CalibrationType.SOLT
    port_config: PortConfig = PortConfig.SINGLE
    kit_type: CalibrationKitType = CalibrationKitType.MECHANICAL
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
        self.base_calibration_path = None
        
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

    def create_calibration_folders(self):
        """创建校准文件夹结构，每个测量步骤下包含Raw_ADC_Data和Processed_Data子文件夹"""
        # 确保data/calibration目录存在
        calibration_base_dir = os.path.join("data", "calibration")
        os.makedirs(calibration_base_dir, exist_ok=True)
        
        # 创建基础校准目录
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        cal_type = "SOLT" if self.params.cal_type == CalibrationType.SOLT else "TRL"
        port_config = "SinglePort" if self.params.port_config == PortConfig.SINGLE else "DualPort"
        
        base_dir_name = f"Calibration_{cal_type}_{port_config}_{timestamp}"
        self.base_calibration_path = os.path.join(calibration_base_dir, base_dir_name)
        
        # 创建基础目录
        os.makedirs(self.base_calibration_path, exist_ok=True)
        
        # 根据校准类型创建子文件夹
        if self.params.cal_type == CalibrationType.SOLT:
            if self.params.port_config == PortConfig.SINGLE:
                measurement_folders = [
                    "Short_Port1",
                    "Open_Port1", 
                    "Load_Port1"
                ]
                analysis_folders = [
                    "ErrorCoefficients",
                    "Verification"
                ]
            else:  # DUAL port
                measurement_folders = [
                    "Short_Port1",
                    "Open_Port1",
                    "Load_Port1",
                    "Short_Port2",
                    "Open_Port2",
                    "Load_Port2",
                    "Thru"
                ]
                analysis_folders = [
                    "ErrorCoefficients",
                    "Verification"
                ]
        else:  # TRL calibration
            measurement_folders = [
                "Thru",
                "Reflect_Port1",
                "Reflect_Port2",
                "Line"
            ]
            analysis_folders = [
                "ErrorCoefficients",
                "Verification"
            ]
        
        # 为每个测量文件夹创建Raw_ADC_Data和Processed_Data子文件夹
        for folder in measurement_folders:
            folder_path = os.path.join(self.base_calibration_path, folder)
            os.makedirs(folder_path, exist_ok=True)
            
            # 创建数据子文件夹
            raw_data_path = os.path.join(folder_path, "Raw_ADC_Data")
            processed_data_path = os.path.join(folder_path, "Processed_Data")
            os.makedirs(raw_data_path, exist_ok=True)
            os.makedirs(processed_data_path, exist_ok=True)
        
        # 创建分析和验证文件夹
        for folder in analysis_folders:
            folder_path = os.path.join(self.base_calibration_path, folder)
            os.makedirs(folder_path, exist_ok=True)
            
        return self.base_calibration_path

    def simulate_calibration(self):
        """模拟校准过程"""
        # 首先创建文件夹
        base_path = self.create_calibration_folders()
        print(f"校准文件夹已创建: {base_path}")
        
        self.progress = 0
        total_steps = len(self.steps)
        
        for i, step in enumerate(self.steps):
            # 这里应该替换为实际的仪器操作
            print(f"执行步骤: {step}")
            self.progress = int((i + 1) / total_steps * 100)
            
            # 判断是否有测量字段
            has_measurement = "测量" in step
            
            # 如果是机械校准件且需要人工操作的步骤，发出提示信号
            if (self.params.kit_type == CalibrationKitType.MECHANICAL and 
                ("连接" in step or "更换" in step or has_measurement)):
                yield step, self.progress, True, has_measurement
            else:
                yield step, self.progress, False, False
