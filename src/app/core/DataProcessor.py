# src/app/core/DataProcessor.py
import numpy as np
from typing import Tuple, Optional, List, Dict, Any
import logging

logger = logging.getLogger(__name__)

class DataProcessor:
    """数据处理核心类"""
    
    def __init__(self, config):
        self.config = config
    
    def extract_adc_data(self, u32_arr: np.ndarray, use_signed18: bool = True) -> Tuple[np.ndarray, np.ndarray]:
        """从uint32数组中提取bit31和ADC数据"""
        # 提取bit31
        bit31 = ((u32_arr >> 31) & 0x1).astype(np.uint8)
      
        # 提取ADC数据
        adc_18u = (u32_arr & ((1 << 20) - 1)).astype(np.uint32)
      
        # 转换为有符号或无符号
        if use_signed18:
            adc_18s = ((adc_18u + (1 << 19)) & ((1 << 20) - 1)) - (1 << 19)
            adc_data = adc_18s.astype(np.int32)
        else:
            adc_data = adc_18u.astype(np.int32)
      
        return bit31, adc_data
    
    def detect_valid_data(self, bit31: np.ndarray, edge_search_start: int = 1) -> Optional[int]:
        """检测bit31数组中的上升沿位置"""
        # 检测上升沿 (0->1转换)
        edge_idx = np.flatnonzero((bit31[1:] == 1) & (bit31[:-1] == 0))
        # 过滤起始位置
        edge_idx = edge_idx[edge_idx >= edge_search_start]
      
        if edge_idx.size == 0:
            logger.warning("未找到上升沿")
            return None
      
        return edge_idx[0] + 1
    
    def extract_data_segment(self, adc_data: np.ndarray, rise_idx: int, 
                           start_index: int, n_points: int) -> Optional[np.ndarray]:
        """从ADC数据中截取指定长度的数据段"""
        start_capture = rise_idx + start_index
      
        # 检查数据长度是否足够
        if start_capture + n_points > adc_data.size:
            logger.warning("数据长度不足")
            return None
      
        # 截取数据段
        return adc_data[start_capture : start_capture + n_points]
    
    def sort_data_by_period(self, segment_data: np.ndarray, 
                          t_sample: float, t_trig: float) -> Tuple[np.ndarray, np.ndarray]:
        """按周期时间对数据进行排序"""
        # 计算周期内时间
        t_within_period = (np.arange(len(segment_data), dtype=np.float64) * t_sample) % t_trig
      
        # 按时间排序
        sort_idx = np.argsort(t_within_period)
        sorted_data = segment_data[sort_idx]
      
        return sorted_data, sort_idx
    
    def compute_spectrum(self, data: np.ndarray, ts_eff: float) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        """计算数据的频谱"""
        # 去均值
        data_centered = data.astype(np.float64) - np.mean(data)
      
        # 加窗
        window = np.hanning(len(data))
        windowed_data = data_centered * window
      
        # 计算FFT
        fft_result = np.fft.rfft(windowed_data)
        freq = np.fft.rfftfreq(len(data), d=ts_eff)
      
        # 归一化
        scale = (np.sum(window) / len(data)) * len(data)
        magnitude_linear = np.abs(fft_result) / (scale + 1e-12)
      
        return freq, magnitude_linear, fft_result
    
    def compute_difference(self, data: np.ndarray, diff_points: int) -> np.ndarray:
        """计算数据的差分"""
        return data[diff_points:] - data[:-diff_points]
    
    def align_data(self, sorted_data: np.ndarray, rise_pos: int, target_position: int) -> np.ndarray:
        """对齐数据，使上升沿位于目标位置"""
        shift = (target_position - rise_pos) % len(sorted_data)
        return np.roll(sorted_data, shift)
    
    def extract_roi(self, aligned_data: np.ndarray, roi_start: int, roi_end: int) -> np.ndarray:
        """从对齐后的数据中提取感兴趣区域(ROI)"""
        return aligned_data[roi_start:roi_end]
