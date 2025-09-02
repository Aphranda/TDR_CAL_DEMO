# src/app/widgets/CalibrationPanel/Model.py
from enum import Enum
from dataclasses import dataclass
from typing import List
import os
import datetime
import numpy as np

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
        """改进的校准步骤生成，添加底噪测试和直通模式确认"""
        self.steps = []
        
        # 添加底噪测试步骤 - 先连接底噪校准件，再测试
        self.steps.append("1. 连接底噪校准件到端口1")
        self.steps.append("2. 测量端口1底噪")
        
        if self.params.cal_type == CalibrationType.SOLT:
            # 单端口或双端口的SOL测量
            self.steps.append("3. 连接短路器到端口1")
            self.steps.append("4. 测量端口1短路标准件")
            self.steps.append("5. 连接开路器到端口1")
            self.steps.append("6. 测量端口1开路标准件")
            self.steps.append("7. 连接负载到端口1")
            self.steps.append("8. 测量端口1负载标准件")
            
            if self.params.port_config == PortConfig.DUAL:
                self.steps.append("9. 连接底噪校准件到端口2")
                self.steps.append("10. 测量端口2底噪")
                self.steps.append("11. 连接短路器到端口2")
                self.steps.append("12. 测量端口2短路标准件")
                self.steps.append("13. 连接开路器到端口2")
                self.steps.append("14. 测量端口2开路标准件")
                self.steps.append("15. 连接负载到端口2")
                self.steps.append("16. 测量端口2负载标准件")
                
                # 直通标件的四种模式，每种模式都需要连接确认
                self.steps.append("17. 连接直通件到端口1-2 (S11模式)")
                self.steps.append("18. 测量直通标准件 S11模式")
                self.steps.append("19. 连接直通件到端口1-2 (S12模式)")
                self.steps.append("20. 测量直通标准件 S12模式")
                self.steps.append("21. 连接直通件到端口1-2 (S21模式)")
                self.steps.append("22. 测量直通标准件 S21模式")
                self.steps.append("23. 连接直通件到端口1-2 (S22模式)")
                self.steps.append("24. 测量直通标准件 S22模式")
                
        elif self.params.cal_type == CalibrationType.TRL:
            self.steps.append("3. 连接直通件到端口1-2")
            self.steps.append("4. 测量直通标准件")
            self.steps.append("5. 连接反射件到端口1")
            self.steps.append("6. 测量端口1反射标准件")
            self.steps.append("7. 连接反射件到端口2")
            self.steps.append("8. 测量端口2反射标准件")
            self.steps.append("9. 连接延迟线到端口1-2")
            self.steps.append("10. 测量延迟线标准件")
            
        self.steps.append("计算误差系数")
        self.steps.append("验证校准质量")
        self.steps.append("保存校准结果")
        
        return self.steps



    def create_calibration_folders(self):
        """创建校准文件夹结构，包含底噪测试文件夹和直通模式子文件夹"""
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
        
        # 添加底噪测试文件夹
        measurement_folders = ["Noise_Port1"]
        analysis_folders = ["ErrorCoefficients", "Verification"]
        
        if self.params.cal_type == CalibrationType.SOLT:
            if self.params.port_config == PortConfig.SINGLE:
                measurement_folders.extend([
                    "Short_Port1",
                    "Open_Port1", 
                    "Load_Port1"
                ])
            else:  # DUAL port
                measurement_folders.extend([
                    "Short_Port1",
                    "Open_Port1",
                    "Load_Port1",
                    "Noise_Port2",  # 添加端口2底噪测试
                    "Short_Port2",
                    "Open_Port2",
                    "Load_Port2"
                ])
                # 为双端口直通测试创建Thru文件夹
                measurement_folders.append("Thru")
        else:  # TRL calibration
            measurement_folders.extend([
                "Thru",
                "Reflect_Port1",
                "Reflect_Port2",
                "Line"
            ])
        
        # 为每个测量文件夹创建Raw_ADC_Data和Processed_Data子文件夹
        for folder in measurement_folders:
            folder_path = os.path.join(self.base_calibration_path, folder)
            os.makedirs(folder_path, exist_ok=True)
            
            # 如果是Thru文件夹，创建S参数子文件夹
            if folder == "Thru" and self.params.port_config == PortConfig.DUAL:
                for s_param in ["S11", "S12", "S21", "S22"]:
                    s_param_path = os.path.join(folder_path, s_param)
                    os.makedirs(s_param_path, exist_ok=True)
                    
                    # 在每个S参数文件夹内创建Raw_ADC_Data和Processed_Data
                    raw_data_path = os.path.join(s_param_path, "Raw_ADC_Data")
                    processed_data_path = os.path.join(s_param_path, "Processed_Data")
                    os.makedirs(raw_data_path, exist_ok=True)
                    os.makedirs(processed_data_path, exist_ok=True)
            else:
                # 其他文件夹正常创建Raw_ADC_Data和Processed_Data
                raw_data_path = os.path.join(folder_path, "Raw_ADC_Data")
                processed_data_path = os.path.join(folder_path, "Processed_Data")
                os.makedirs(raw_data_path, exist_ok=True)
                os.makedirs(processed_data_path, exist_ok=True)
        
        # 创建分析和验证文件夹
        for folder in analysis_folders:
            folder_path = os.path.join(self.base_calibration_path, folder)
            os.makedirs(folder_path, exist_ok=True)
        
        # 返回基础路径
        return self.base_calibration_path


    def get_folder_name_from_step(self, step):
        """根据步骤描述获取文件夹名称"""
        if "底噪" in step:
            if "端口1" in step:
                return "Noise_Port1"
            elif "端口2" in step:
                return "Noise_Port2"
            else:
                return "Noise"
        elif "短路" in step:
            base = "Short"
        elif "开路" in step:
            base = "Open"
        elif "负载" in step:
            base = "Load"
        elif "直通" in step:
            # 检查具体的S参数模式
            if "S11" in step:
                return "Thru\\S11"
            elif "S12" in step:
                return "Thru\\S12"
            elif "S21" in step:
                return "Thru\\S21"
            elif "S22" in step:
                return "Thru\\S22"
            else:
                return "Thru"
        elif "反射" in step:
            base = "Reflect"
        elif "延迟线" in step:
            return "Line"
        elif "误差系数" in step:
            return "ErrorCoefficients"
        elif "验证" in step:
            return "Verification"
        elif "保存" in step:
            return "SaveResults"
        else:
            return "Unknown"

        # 检查端口
        if "端口1" in step:
            return f"{base}_Port1"
        elif "端口2" in step:
            return f"{base}_Port2"
        else:
            return base


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
            
            # 如果是测量步骤，生成并保存模拟数据
            if has_measurement and base_path:
                folder_name = self.get_folder_name_from_step(step)
                
                # 处理嵌套文件夹路径
                if "/" in folder_name:
                    # 对于Thru/S11这样的路径
                    parent_folder, sub_folder = folder_name.split("/")
                    folder_path = os.path.join(self.base_calibration_path, parent_folder, sub_folder)
                    
                    # 确保目录存在
                    os.makedirs(folder_path, exist_ok=True)
                    
                    # 构建Raw和Processed路径
                    raw_data_dir = os.path.join(folder_path, "Raw_ADC_Data")
                    processed_data_dir = os.path.join(folder_path, "Processed_Data")
                else:
                    folder_path = os.path.join(self.base_calibration_path, folder_name)
                    # 确保目录存在
                    os.makedirs(folder_path, exist_ok=True)
                    
                    raw_data_dir = os.path.join(folder_path, "Raw_ADC_Data")
                    processed_data_dir = os.path.join(folder_path, "Processed_Data")
                
                # 确保目录存在
                os.makedirs(raw_data_dir, exist_ok=True)
                os.makedirs(processed_data_dir, exist_ok=True)
                
                # 生成模拟数据
                raw_data = np.random.randint(0, 2**19, 1024, dtype=np.uint32)  # 19位ADC
                
                # 保存原始数据
                if "/" in folder_name:
                    file_base_name = folder_name.replace("/", "_")
                else:
                    file_base_name = folder_name
                
                raw_filename = f"step_{i+1}_{file_base_name}.csv"
                raw_filepath = os.path.join(raw_data_dir, raw_filename)
                np.savetxt(raw_filepath, raw_data, delimiter=',', fmt='%u')
                
                # 模拟数据处理：计算FFT
                processed_data = np.fft.fft(raw_data.astype(np.float64))
                mag = np.abs(processed_data)
                
                # 保存处理后的数据
                processed_filename = f"step_{i+1}_{file_base_name}_fft_mag.csv"
                processed_filepath = os.path.join(processed_data_dir, processed_filename)
                np.savetxt(processed_filepath, mag, delimiter=',')
            
            # 如果是机械校准件且需要人工操作的步骤，发出提示信号
            if (self.params.kit_type == CalibrationKitType.MECHANICAL and 
                ("连接" in step or "更换" in step or has_measurement)):
                yield step, self.progress, True, has_measurement
            else:
                yield step, self.progress, False, False
