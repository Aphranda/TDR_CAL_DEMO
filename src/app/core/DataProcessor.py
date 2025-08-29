# src/app/core/DataProcessor.py
import numpy as np
from typing import Tuple, Optional, List, Dict, Any
import logging

logger = logging.getLogger(__name__)

class DataProcessor:
    """数据处理核心类"""
    
    def __init__(self, config):
        self.config = config

    
    def smooth_data(self, 
                    data: np.ndarray, 
                    window_size: int = 5, 
                    window_type: str = 'uniform',
                    mode: str = 'same',
                    sigma: Optional[float] = None,
                    handle_nan: bool = True) -> np.ndarray:
        """
        数据预处理：移动平均滤波
        
        Parameters:
        -----------
        data : np.ndarray
            输入的一维数据数组
        window_size : int, optional
            窗口大小，默认为5。必须是奇数，如果不是奇数会自动调整为奇数
        window_type : str, optional
            窗口类型，可选 'uniform'(均匀), 'gaussian'(高斯), 'triangular'(三角)
        mode : str, optional
            卷积模式，可选 'full', 'same', 'valid'，默认为'same'
        sigma : float, optional
            高斯窗口的标准差，仅当window_type='gaussian'时有效
        handle_nan : bool, optional
            是否处理NaN值，默认为True
        
        Returns:
        --------
        np.ndarray
            平滑后的数据
        
        Raises:
        -------
        ValueError
            如果输入参数无效
        """
        # 参数验证
        if not isinstance(data, np.ndarray):
            data = np.array(data)
        
        if data.ndim != 1:
            raise ValueError("输入数据必须是一维数组")
        
        if len(data) == 0:
            raise ValueError("输入数据不能为空")
        
        if window_size < 1:
            raise ValueError("窗口大小必须大于0")
        
        if window_size > len(data):
            raise ValueError("窗口大小不能大于数据长度")
        
        # 确保窗口大小为奇数
        if window_size % 2 == 0:
            window_size += 1
            print(f"警告：窗口大小调整为奇数 {window_size}")
        
        # 处理NaN值
        if handle_nan and np.any(np.isnan(data)):
            data = self._handle_nan_values(data.copy())
        
        # 创建卷积核
        kernel = self._create_kernel(window_size, window_type, sigma)
        
        try:
            # 执行卷积
            smoothed = np.convolve(data, kernel, mode=mode)
            
            # 对于'same'模式，确保输出长度与输入相同
            if mode == 'same' and len(smoothed) != len(data):
                # 调整输出长度
                if len(smoothed) > len(data):
                    start = (len(smoothed) - len(data)) // 2
                    smoothed = smoothed[start:start + len(data)]
                else:
                    # 填充边界
                    pad_size = (len(data) - len(smoothed)) // 2
                    smoothed = np.pad(smoothed, (pad_size, len(data) - len(smoothed) - pad_size), 
                                    mode='edge')
            
            return smoothed
            
        except Exception as e:
            raise RuntimeError(f"卷积计算失败: {str(e)}")
    def _create_kernel(self, window_size: int, window_type: str, sigma: Optional[float]) -> np.ndarray:
        """创建卷积核"""
        if window_type == 'uniform':
            # 均匀窗口
            kernel = np.ones(window_size) / window_size
            
        elif window_type == 'gaussian':
            # 高斯窗口
            if sigma is None:
                sigma = window_size / 6.0  # 默认标准差
            
            x = np.linspace(-window_size//2, window_size//2, window_size)
            kernel = np.exp(-x**2 / (2 * sigma**2))
            kernel /= np.sum(kernel)  # 归一化
            
        elif window_type == 'triangular':
            # 三角窗口
            kernel = np.concatenate([
                np.linspace(1, window_size//2 + 1, window_size//2 + 1),
                np.linspace(window_size//2, 1, window_size//2)
            ])
            kernel = kernel[:window_size]  # 确保长度正确
            kernel /= np.sum(kernel)
            
        elif window_type == 'hanning':
            # 汉宁窗口
            kernel = np.hanning(window_size)
            kernel /= np.sum(kernel)
            
        else:
            raise ValueError(f"不支持的窗口类型: {window_type}")
        
        return kernel
    def _handle_nan_values(self, data: np.ndarray) -> np.ndarray:
        """处理NaN值"""
        nan_mask = np.isnan(data)
        
        if np.all(nan_mask):
            raise ValueError("所有数据都是NaN")
        
        # 线性插值填充NaN
        if np.any(nan_mask):
            indices = np.arange(len(data))
            data[nan_mask] = np.interp(indices[nan_mask], indices[~nan_mask], data[~nan_mask])
        
        return data
    # 添加一些便捷的包装函数
    def smooth_uniform(self, data: np.ndarray, window_size: int = 5) -> np.ndarray:
        """均匀移动平均"""
        return self.smooth_data(data, window_size, 'uniform')
    def smooth_gaussian(self, data: np.ndarray, window_size: int = 5, sigma: float = None) -> np.ndarray:
        """高斯平滑"""
        return self.smooth_data(data, window_size, 'gaussian', sigma=sigma)
    def smooth_triangular(self, data: np.ndarray, window_size: int = 5) -> np.ndarray:
        """三角平滑"""
        return self.smooth_data(data, window_size, 'triangular')
    
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
