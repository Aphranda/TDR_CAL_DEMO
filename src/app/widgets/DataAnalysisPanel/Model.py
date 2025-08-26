# src/app/widgets/DataAnalysisPanel/Model.py
import os
import numpy as np
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
from ...core.DataAnalyze import AnalysisConfig

@dataclass
class ADCConfig:
    """ADC配置"""
    input_dir: str = ''
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
    search_method: int = 1  # SearchMethod.RISING
    roi_start_tenths: int = 20
    roi_end_tenths: int = 30
    output_csv: str = 'analysis_results.csv'
    min_edge_amplitude_ratio:float = 0.3
    cal_mode: str = "LOAD"  # 新增CAL_Mode参数

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
    def l_roi(self) -> int:
        return self.roi_end - self.roi_start

class DataAnalysisModel:
    def __init__(self):
        self.analysis_type = "ADC数据分析"
        self.data_files = []
        self.current_data = None
        self.results = {}
        self.adc_config = ADCConfig()
        self.adc_connected = False
        self.adc_samples = []
        self.adc_analysis_results = {}
        self.adc_ip = "192.168.1.10"
        self.adc_port = 15000
        self.sample_count = 10
        self.sample_interval = 0.1
        self.output_dir = "data\\results\\test"  # 新增：输出目录
        self.filename_prefix = "adc_data"  # 新增：文件名前缀
        
    def set_adc_connection_status(self, connected: bool):
        """设置ADC连接状态"""
        self.adc_connected = connected
        
    def add_adc_sample(self, sample_data):
        """添加ADC采样数据"""
        self.adc_samples.append(sample_data)
        
    def clear_adc_samples(self):
        """清除ADC采样数据"""
        self.adc_samples.clear()
        
    def get_adc_samples_count(self) -> int:
        """获取ADC采样数量"""
        return len(self.adc_samples)
    
    def get_adc_config_dict(self) -> Dict[str, Any]:
        """获取ADC配置字典"""
        return {
            'input_dir': self.adc_config.input_dir,
            'recursive': self.adc_config.recursive,
            'clock_freq': self.adc_config.clock_freq,
            'trigger_freq': self.adc_config.trigger_freq,
            'n_points': self.adc_config.n_points,
            'start_index': self.adc_config.start_index,
            'use_signed18': self.adc_config.use_signed18,
            'show_up_to_GHz': self.adc_config.show_up_to_GHz,
            'skip_first_value': self.adc_config.skip_first_value,
            'edge_search_start': self.adc_config.edge_search_start,
            'diff_points': self.adc_config.diff_points,
            'search_method': self.adc_config.search_method,
            'roi_start_tenths': self.adc_config.roi_start_tenths,
            'roi_end_tenths': self.adc_config.roi_end_tenths,
            'output_csv': self.adc_config.output_csv
        }
    
    def update_adc_config_from_dict(self, config_dict: Dict[str, Any]):
        """从字典更新ADC配置"""
        for key, value in config_dict.items():
            if hasattr(self.adc_config, key):
                setattr(self.adc_config, key, value)
    
    def convert_to_analysis_config(self) -> AnalysisConfig:
        """转换为DataAnalyze的AnalysisConfig"""
        return AnalysisConfig(
            input_dir=self.adc_config.input_dir,
            recursive=self.adc_config.recursive,
            clock_freq=self.adc_config.clock_freq,
            trigger_freq=self.adc_config.trigger_freq,
            n_points=self.adc_config.n_points,
            start_index=self.adc_config.start_index,
            use_signed18=self.adc_config.use_signed18,
            show_up_to_GHz=self.adc_config.show_up_to_GHz,
            skip_first_value=self.adc_config.skip_first_value,
            edge_search_start=self.adc_config.edge_search_start,
            diff_points=self.adc_config.diff_points,
            search_method=self.adc_config.search_method,
            roi_start_tenths=self.adc_config.roi_start_tenths,
            roi_end_tenths=self.adc_config.roi_end_tenths,
            output_csv=self.adc_config.output_csv
        )
