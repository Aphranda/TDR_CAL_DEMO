# src/app/core/ConfigManager.py
from dataclasses import dataclass
from typing import Optional
import logging

logger = logging.getLogger(__name__)

class SearchMethod:
    RISING = 1
    MAX = 2

class CalibrationMode:
    OPEN = "OPEN"
    SHORT = "SHORT" 
    LOAD = "LOAD"
    THRU = "THRU"

@dataclass
class AnalysisConfig:
    """数据分析配置类"""
    input_dir: str = 'data\\results\\test'
    recursive: bool = True
    clock_freq: float = 39.53858777e6
    trigger_freq: float = 10e6
    n_points: int = 81920
    start_index: int = 70
    use_signed18: bool = True
    show_up_to_GHz: float = 50.0
    skip_first_value: bool = True
    edge_search_start: int = 1
    diff_points: int = 10
    search_method: int = SearchMethod.RISING
    roi_start_tenths: int = 0
    roi_end_tenths: int = 100
    roi_mid_tenths: int = 10
    output_csv: str = 'data\\raw\\calibration\\S_data.csv'
    min_edge_amplitude_ratio: float = 0.1
    min_second_rise_ratio: float = 0.05
    min_second_fall_ratio: float = 0.05
    cal_mode: str = CalibrationMode.LOAD

    @property
    def t_sample(self) -> float:
        return 1.0 / self.clock_freq
  
    @property
    def t_trig(self) -> float:
        return 1.0 / self.trigger_freq
  
    @property
    def fs_eff(self) -> float:
        return self.n_points / self.t_trig
  
    @property
    def ts_eff(self) -> float:
        return 1.0 / self.fs_eff
  
    @property
    def roi_start(self) -> int:
        return int(self.n_points * self.roi_start_tenths / 100)
  
    @property
    def roi_end(self) -> int:
        return int(self.n_points * self.roi_end_tenths / 100)
  
    @property
    def roi_mid(self) -> int:
        return int(self.n_points * self.roi_mid_tenths / 100)
  
    @property
    def l_roi(self) -> int:
        return self.roi_end - self.roi_start
    
 
    def n_roi(self,n) -> int:
        return int(self.n_points * n / 100)

class ConfigValidator:
    """配置验证器"""
    
    @staticmethod
    def validate_config(config: AnalysisConfig) -> None:
        """验证配置参数"""
        valid_modes = [CalibrationMode.OPEN, CalibrationMode.SHORT, 
                      CalibrationMode.LOAD, CalibrationMode.THRU]
        if config.cal_mode not in valid_modes:
            raise ValueError(f"无效的校准模式: {config.cal_mode}。有效模式: {valid_modes}")
      
        if config.roi_start_tenths >= config.roi_end_tenths:
            raise ValueError("ROI起始位置必须小于结束位置")
      
        if config.roi_end_tenths > 100:
            raise ValueError("ROI结束位置不能超过100%")
