# src/app/core/DataProcessor.py
import numpy as np
from typing import Tuple, Optional, List, Dict, Any
import logging
import threading
from concurrent.futures import ThreadPoolExecutor
from numba import jit, prange
from numba.core.errors import NumbaWarning
import warnings
from .PerformanceMonitor import timeit, performance_monitor
logger = logging.getLogger(__name__)
warnings.filterwarnings("ignore", category=NumbaWarning)


# 预编译函数 - 使用最常见的参数组合
@jit(nopython=True, cache=True, parallel=True)
def hampel_filter_precompiled(data: np.ndarray, window_size: int, threshold: float) -> Tuple[np.ndarray, np.ndarray]:
    """
    预编译的Numba并行版本 - 使用最常用的参数
    """
    n = len(data)
    cleaned_data = data.copy()
    spikes = np.zeros(n, dtype=np.int32)
    spike_count = 0
    
    window_size_total = 2 * window_size
    
    # 并行处理所有中心点
    for i in prange(window_size, n - window_size):
        # 构建窗口数据
        window_data = np.empty(window_size_total, dtype=data.dtype)
        
        # 填充左侧窗口
        for j in range(window_size):
            window_data[j] = data[i - window_size + j]
        
        # 填充右侧窗口  
        for j in range(window_size):
            window_data[window_size + j] = data[i + 1 + j]
        
        # 快速计算中位数和MAD
        window_sorted = np.sort(window_data)
        
        # 计算中位数
        mid = window_size_total // 2
        if window_size_total % 2 == 1:
            median = window_sorted[mid]
        else:
            median = (window_sorted[mid - 1] + window_sorted[mid]) * 0.5
        
        # 计算MAD
        abs_devs = np.empty(window_size_total, dtype=data.dtype)
        for j in range(window_size_total):
            abs_devs[j] = np.abs(window_data[j] - median)
        
        abs_devs_sorted = np.sort(abs_devs)
        
        if window_size_total % 2 == 1:
            mad = abs_devs_sorted[mid]
        else:
            mad = (abs_devs_sorted[mid - 1] + abs_devs_sorted[mid]) * 0.5
        
        # 检测奇异点
        if mad > 1e-10:
            z_score = 0.6745 * (data[i] - median) / mad
            if np.abs(z_score) > threshold:
                spikes[spike_count] = i
                spike_count += 1
                cleaned_data[i] = median
    
    return cleaned_data, spikes[:spike_count]

# 预编译函数 - 简化版本（用于小数据集）
@jit(nopython=True, cache=True)
def hampel_filter_simple(data: np.ndarray, window_size: int, threshold: float) -> Tuple[np.ndarray, np.ndarray]:
    """简化版本，编译更快"""
    n = len(data)
    cleaned_data = data.copy()
    spikes = np.zeros(n, dtype=np.int32)
    spike_count = 0
    
    for i in range(window_size, n - window_size):
        # 构建窗口
        window_data = np.concatenate((
            data[i-window_size:i], 
            data[i+1:i+window_size+1]
        ))
        
        median = np.median(window_data)
        abs_devs = np.abs(window_data - median)
        mad = np.median(abs_devs)
        
        if mad > 1e-10:
            z_score = 0.6745 * (data[i] - median) / mad
            if np.abs(z_score) > threshold:
                spikes[spike_count] = i
                spike_count += 1
                cleaned_data[i] = median
    
    return cleaned_data, spikes[:spike_count]

@jit(nopython=True, cache=True)
def hampel_filter_optimized(data: np.ndarray, window_size: int, threshold: float) -> Tuple[np.ndarray, np.ndarray]:
    """
    内存访问优化的Numba版本
    """
    n = len(data)
    cleaned_data = data.copy()
    spikes = np.zeros(n, dtype=np.int32)
    spike_count = 0
    
    # 预分配工作数组，避免重复分配
    window_size_total = 2 * window_size
    window_buffer = np.empty(window_size_total, dtype=data.dtype)
    abs_devs_buffer = np.empty(window_size_total, dtype=data.dtype)
    
    for i in range(window_size, n - window_size):
        # 高效填充窗口缓冲区
        idx = 0
        for j in range(i - window_size, i):
            window_buffer[idx] = data[j]
            idx += 1
        for j in range(i + 1, i + window_size + 1):
            window_buffer[idx] = data[j]
            idx += 1
        
        # 快速排序计算中位数
        window_buffer_sorted = np.sort(window_buffer)
        
        # 计算中位数
        mid = window_size_total // 2
        if window_size_total % 2 == 1:
            median = window_buffer_sorted[mid]
        else:
            median = (window_buffer_sorted[mid - 1] + window_buffer_sorted[mid]) * 0.5
        
        # 计算绝对偏差
        for j in range(window_size_total):
            abs_devs_buffer[j] = abs(window_buffer[j] - median)
        
        # 排序计算MAD
        abs_devs_sorted = np.sort(abs_devs_buffer)
        
        if window_size_total % 2 == 1:
            mad = abs_devs_sorted[mid]
        else:
            mad = (abs_devs_sorted[mid - 1] + abs_devs_sorted[mid]) * 0.5
        
        # 检测奇异点
        if mad > 1e-10:
            z_score = 0.6745 * (data[i] - median) / mad
            if abs(z_score) > threshold:
                spikes[spike_count] = i
                spike_count += 1
                cleaned_data[i] = median
    
    return cleaned_data, spikes[:spike_count]

class DataProcessor:
    """数据处理核心类"""
    
    def __init__(self, config):
        self.config = config

        self._compilation_done = False
        self._compilation_thread = None
        
        # 启动预编译
        self._start_precompilation()


    def _start_precompilation(self):
        """在后台线程中启动预编译"""
        def precompile():
            try:
                logger.info("开始预编译Numba函数...")
                
                # 使用典型数据进行预编译
                typical_data = np.random.randn(1000).astype(np.float64)
                
                # 预编译常用参数组合
                hampel_filter_precompiled(typical_data, 5, 3.0)
                hampel_filter_simple(typical_data, 5, 3.0)
                
                self._compilation_done = True
                logger.info("Numba函数预编译完成")
                
            except Exception as e:
                logger.warning(f"预编译失败: {e}")
        
        self._compilation_thread = threading.Thread(target=precompile, daemon=True)
        self._compilation_thread.start()
    
    def wait_for_compilation(self, timeout: float = 5.0):
        """等待预编译完成（可选）"""
        if self._compilation_thread and self._compilation_thread.is_alive():
            self._compilation_thread.join(timeout=timeout)

    
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
    
    def extract_adc_data(self, u32_arr: np.ndarray, use_signed18: bool = True, N: int = 20) -> Tuple[np.ndarray, np.ndarray]:
        """从uint32数组中提取bit31和ADC数据
        
        Parameters:
        -----------
        u32_arr : np.ndarray
            输入的uint32数组
        use_signed18 : bool, optional
            是否使用18位有符号格式，默认为True
        N : int, optional
            提取的位数（高位），范围1-20，默认为20（全位）
        
        Returns:
        --------
        Tuple[np.ndarray, np.ndarray]
            bit31数组和ADC数据数组
        """
        # 参数验证
        if N < 1 or N > 20:
            raise ValueError("N必须在1到20之间")
        
        # 提取bit31
        bit31 = ((u32_arr >> 31) & 0x1).astype(np.uint8)
        
        # 提取ADC数据 - 只取前N位高位
        if N == 20:
            # 如果取全位，保持原有逻辑
            adc_18u = (u32_arr & ((1 << 20) - 1)).astype(np.uint32)
        else:
            # 取前N位高位：右移(20-N)位，然后取低N位
            shift_bits = 20 - N
            adc_18u = ((u32_arr >> shift_bits) & ((1 << N) - 1)).astype(np.uint32)
        
        # 转换为有符号或无符号
        if use_signed18:
            # 对于N位有符号数，符号位是第N-1位
            sign_bit_mask = 1 << (N - 1)
            offset = 1 << (N - 1)
            mask = (1 << N) - 1
            
            adc_18s = ((adc_18u + offset) & mask) - offset
            adc_data = adc_18s.astype(np.int32)
        else:
            adc_data = adc_18u.astype(np.int32)
        
        return bit31, adc_data

    
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



    # @timeit
    def remove_spikes_robust(self, data: np.ndarray, window_size: int = 5, threshold: float = 3.0) -> Tuple[np.ndarray, List[int]]:
        """
        结合多种优化技术的最终版本
        """
        n = len(data)
        if n < 2 * window_size + 1:
            return data, []
        
        cleaned_data = data.copy().astype(np.float64)
        spikes_detected = []
        
        # 使用更高效的窗口处理
        total_window_size = 2 * window_size
        
        # 预计算基础索引
        left_template = np.arange(-window_size, 0)
        right_template = np.arange(1, window_size + 1)
        
        # 处理所有中心点
        for i in range(window_size, n - window_size):
            # 直接计算窗口索引，避免创建临时数组
            left_start = i + left_template[0]
            left_end = i + left_template[-1] + 1
            right_start = i + right_template[0]
            right_end = i + right_template[-1] + 1
            
            # 直接使用切片，避免concatenate
            window_data = np.empty(total_window_size, dtype=data.dtype)
            window_data[:window_size] = data[left_start:left_end]
            window_data[window_size:] = data[right_start:right_end]
            
            # 快速计算中位数（部分排序）
            sorted_window = np.partition(window_data, total_window_size // 2)
            median = sorted_window[total_window_size // 2]
            
            # 如果数组长度是偶数，需要调整中位数
            if total_window_size % 2 == 0:
                median2 = np.partition(window_data, total_window_size // 2 - 1)[total_window_size // 2 - 1]
                median = (median + median2) / 2.0
            
            # 计算MAD
            abs_dev = np.abs(window_data - median)
            sorted_abs_dev = np.partition(abs_dev, total_window_size // 2)
            mad = sorted_abs_dev[total_window_size // 2]
            
            if mad > 1e-10:
                z_score = 0.6745 * (data[i] - median) / mad
                if abs(z_score) > threshold:
                    spikes_detected.append(i)
                    cleaned_data[i] = median
        
        return cleaned_data, spikes_detected




    # @timeit
    def remove_spikes_robust_final(self,data: np.ndarray, window_size: int = 5, threshold: float = 3.0) -> Tuple[np.ndarray, List[int]]:
        """
        最终优化的Numba版本
        """
        if len(data) < 2 * window_size + 1:
            return data, []
        
        data_float = data.astype(np.float64)
        cleaned_data, spike_indices = hampel_filter_optimized(data_float, window_size, threshold)
        
        return cleaned_data, spike_indices.tolist()
