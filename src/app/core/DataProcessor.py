# src/app/core/DataProcessor.py
import numpy as np
from typing import Tuple, Optional, List, Dict, Any
import logging

try:
    from .PerformanceMonitor import timeit, performance_monitor
except ImportError:
    from PerformanceMonitor import timeit, performance_monitor

logger = logging.getLogger(__name__)

class DataProcessor:
    """数据处理核心类"""
    
    def __init__(self, config):
        self.config = config

        # 缓存排序索引
        self._BIT31_MASK = np.uint32(0x80000000)
        self._ADC_MASK = np.uint32(0x000FFFFF)
        self._SIGN_OFFSET = np.uint32(1 << 19)
        self._SIGN_THRESHOLD = np.uint32(1 << 19)
        self._FULL_SIGN = np.uint32(1 << 20)

        # 性能监控
        self._adc_call_count = 0
        self._adc_slow_threshold = 100

        self._sort_cache = {}  # 键为 (data_length, t_sample, t_trig)，值为排序索引
        self._hanning_cache = {}
        self._fft_plan_cache = {}
        self._spectrum_cache = {}
        self._window_cache = {}
        self._cache_hits = 0
        self._cache_misses = 0

    
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
        """从uint32数组中提取bit31和ADC数据 - 紧急修复版本"""
        try:
            # 优化1: 使用最简化的位操作
            bit31 = (u32_arr >> 31).astype(np.uint8)
            
            # 优化2: 直接提取低20位
            adc_18u = u32_arr & self._ADC_MASK
            
            if use_signed18:
                # 优化3: 使用向量化的符号转换
                # 创建有符号数组
                adc_data = adc_18u.astype(np.int32)
                # 批量处理符号转换
                sign_mask = adc_18u >= self._SIGN_THRESHOLD
                adc_data[sign_mask] = adc_data[sign_mask] - self._FULL_SIGN
            else:
                adc_data = adc_18u.astype(np.int32)
            
            # 性能监控和自动恢复
            self._adc_call_count += 1
            if self._adc_call_count > self._adc_slow_threshold:
                self._adc_call_count = 0
                # 强制内存清理
                import gc
                gc.collect()
            
            return bit31, adc_data
            
        except Exception as e:
            logger.error(f"extract_adc_data出错: {e}")
            # 回退到简单实现
            bit31 = ((u32_arr >> 31) & 0x1).astype(np.uint8)
            adc_18u = (u32_arr & 0x000FFFFF).astype(np.uint32)
            if use_signed18:
                adc_18s = ((adc_18u + (1 << 19)) & 0x000FFFFF) - (1 << 19)
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
        data_length = len(segment_data)
        cache_key = (data_length, t_sample, t_trig)
        
        if cache_key in self._sort_cache:
            sort_idx = self._sort_cache[cache_key]
            sorted_data = segment_data[sort_idx]
            return sorted_data, sort_idx
        else:
            # 计算周期内时间
            t_within_period = (np.arange(data_length, dtype=np.float64) * t_sample) % t_trig
            # 按时间排序
            sort_idx = np.argsort(t_within_period)
            sorted_data = segment_data[sort_idx]
            # 缓存排序索引
            self._sort_cache[cache_key] = sort_idx
            return sorted_data, sort_idx
    
   
    def compute_spectrum(self, data: np.ndarray, ts_eff: float) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        """计算数据的频谱 - 优化版本"""
        data_length = len(data)
        
        # 优化1: 数据长度检查
        if data_length < 10:
            freq = np.array([])
            mag_linear = np.array([])
            fft_result = np.array([])
            return freq, mag_linear, fft_result
        
        # 优化2: 智能缓存策略
        cache_key = self._generate_spectrum_cache_key(data, ts_eff)
        
        if cache_key in self._spectrum_cache:
            self._cache_hits += 1
            return self._spectrum_cache[cache_key]
        
        self._cache_misses += 1
        
        try:
            # 优化3: 使用更高效的均值计算
            data_mean = np.mean(data, dtype=np.float64)
            data_centered = data.astype(np.float64) - data_mean
            
            # 优化4: 预计算窗函数
            window = self._get_cached_window(data_length)
            
            # 优化5: 高效加窗
            windowed_data = data_centered * window
            
            # 优化6: 计算FFT
            fft_result = np.fft.rfft(windowed_data)
            freq = np.fft.rfftfreq(data_length, d=ts_eff)
            
            # 优化7: 高效归一化
            scale = np.sum(window)
            magnitude_linear = np.abs(fft_result) / (scale + 1e-12)
            
            result = (freq, magnitude_linear, fft_result)
            
            # 优化8: 智能缓存（只缓存小数据）
            if data_length <= 10000:  # 只缓存合理大小的数据
                self._spectrum_cache[cache_key] = result
                # 限制缓存大小
                if len(self._spectrum_cache) > 100:
                    self._spectrum_cache.pop(next(iter(self._spectrum_cache)))
            
            return result
            
        except Exception as e:
            logger.error(f"compute_spectrum计算失败: {e}")
            # 返回空结果
            freq = np.array([])
            mag_linear = np.array([])
            fft_result = np.array([])
            return freq, mag_linear, fft_result
    
    def _generate_spectrum_cache_key(self, data: np.ndarray, ts_eff: float) -> str:
        """生成频谱缓存键"""
        data_length = len(data)
        # 使用数据的统计特征作为缓存键的一部分
        data_hash = hash((data_length, ts_eff, np.mean(data), np.std(data)))
        return f"spectrum_{data_hash}"
    
    def _get_cached_window(self, data_length: int) -> np.ndarray:
        """获取缓存的窗函数"""
        if data_length not in self._window_cache:
            self._window_cache[data_length] = np.hanning(data_length)
        return self._window_cache[data_length]
    
    def clear_spectrum_cache(self):
        """清空频谱缓存"""
        self._spectrum_cache.clear()
        logger.info(f"频谱缓存已清空，命中率: {self._cache_hits}/{self._cache_hits + self._cache_misses}")

    def clear_cache(self):
        """清空缓存，防止内存泄漏"""
        self._hanning_cache.clear()
        self._fft_plan_cache.clear()
    
    
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




    def remove_spikes_robust(self, data: np.ndarray, method: str = "Hampel", 
                            window_size: int = 5, threshold: float = 3.0) -> Tuple[np.ndarray, List[int]]:
        """
        使用稳健方法去除奇异点
        
        Args:
            data: 输入数据
            method: 检测方法 ("Hampel", "Z-score", "IQR")
            threshold: 阈值（标准差倍数）
            window_size: 窗口大小
            
        Returns:
            Tuple[清理后的数据, 奇异点位置列表]
        """
        if len(data) < window_size * 2 + 1:
            return data, []
        
        spikes_detected = []
        cleaned_data = data.copy().astype(np.float64)
        
        for i in range(window_size, len(data) - window_size):
            # 获取窗口数据（排除当前点）
            window_indices = list(range(i - window_size, i)) + list(range(i + 1, i + window_size + 1))
            window_data = data[window_indices]
            
            if method == "Hampel":
                # Hampel标识器：基于中位数绝对偏差（对异常值更鲁棒）
                median = np.median(window_data)
                mad = np.median(np.abs(window_data - median))
                
                if mad > 0:
                    # 使用一致估计量缩放
                    z_score = 0.6745 * (data[i] - median) / mad
                    if abs(z_score) > threshold:
                        spikes_detected.append(i)
                        # 使用窗口的中位数代替奇异点
                        cleaned_data[i] = median
                        
            elif method == "Z-score":
                # 基于Z-score的方法（对高斯分布数据效果好）
                mean = np.mean(window_data)
                std = np.std(window_data)
                
                if std > 0:
                    z_score = (data[i] - mean) / std
                    if abs(z_score) > threshold:
                        spikes_detected.append(i)
                        cleaned_data[i] = mean
                        
            elif method == "IQR":
                # 基于四分位距的方法（对偏态分布鲁棒）
                q75, q25 = np.percentile(window_data, [75, 25])
                iqr = q75 - q25
                
                if iqr > 0:
                    lower_bound = q25 - threshold * iqr
                    upper_bound = q75 + threshold * iqr
                    
                    if data[i] < lower_bound or data[i] > upper_bound:
                        spikes_detected.append(i)
                        cleaned_data[i] = np.median(window_data)
        
        return cleaned_data, spikes_detected

    def remove_spikes_simple(self, data: np.ndarray, threshold_ratio: float = 2.0, 
                            window_size: int = 5) -> np.ndarray:
        """
        简单的奇异点去除方法
        
        Args:
            data: 输入数据
            threshold_ratio: 阈值比例
            window_size: 窗口大小
            
        Returns:
            清理后的数据
        """
        try:
            if len(data) < window_size * 2 + 1:
                return data
                
            cleaned_data = data.copy().astype(np.float64)
            
            for i in range(window_size, len(data) - window_size):
                # 获取周围数据
                left_window = data[i - window_size:i]
                right_window = data[i + 1:i + window_size + 1]
                surrounding_data = np.concatenate([left_window, right_window])
                
                # 计算统计信息
                surrounding_mean = np.mean(surrounding_data)
                surrounding_std = np.std(surrounding_data)
                
                if surrounding_std > 0:
                    z_score = abs(data[i] - surrounding_mean) / surrounding_std
                    
                    if z_score > threshold_ratio:
                        # 使用中位数代替（对异常值更鲁棒）
                        cleaned_data[i] = np.median(surrounding_data)
            
            return cleaned_data
            
        except Exception as e:
            logger.error(f"去除奇异点时出错: {e}")
            return data
