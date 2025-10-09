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



    def _create_spectrum_window(self, length: int, window_type: str) -> np.ndarray:
        """创建频谱分析窗函数"""
        if window_type == 'hanning':
            return np.hanning(length)
        elif window_type == 'hamming':
            return np.hamming(length)
        elif window_type == 'blackman':
            return np.blackman(length)
        elif window_type == 'flattop':
            # 平顶窗，幅度精度高
            return np.array([1.0 - 1.93 * np.cos(2*np.pi*i/length) + 
                           1.29 * np.cos(4*np.pi*i/length) - 
                           0.388 * np.cos(6*np.pi*i/length) + 
                           0.032 * np.cos(8*np.pi*i/length) 
                           for i in range(length)])
        elif window_type == 'rectangular':
            return np.ones(length)
        else:
            return np.hanning(length)  # 默认使用汉宁窗
    
    def _compute_coherence(self, spectra: np.ndarray) -> np.ndarray:
        """计算频谱一致性"""
        n_periods = len(spectra)
        if n_periods < 2:
            return np.ones_like(spectra[0])
        
        # 计算平均交叉谱密度和自谱密度
        cross_spectrum = np.sum(spectra * np.conj(spectra), axis=0)
        auto_spectrum1 = np.sum(np.abs(spectra) ** 2, axis=0)
        auto_spectrum2 = auto_spectrum1  # 由于是同一信号，自谱相同
        
        # 计算一致性
        coherence = np.abs(cross_spectrum) ** 2 / (auto_spectrum1 * auto_spectrum2 + 1e-12)
        return np.clip(coherence, 0, 1)
    
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


    def concatenate_data_segments(self, data_segments: List[np.ndarray], 
                                segments_per_group: int = 10) -> List[np.ndarray]:
        """
        将数据段按指定组数进行分组拼接
        
        Parameters:
        -----------
        data_segments : List[np.ndarray]
            数据段列表，每个元素是一个数据段
        segments_per_group : int, optional
            每组包含的段数，默认为10
        
        Returns:
        --------
        List[np.ndarray]
            拼接后的数据组列表
        """
        if not data_segments:
            return []
        
        # 计算组数：data_segments长度除以10
        n_groups = max(1, len(data_segments) // segments_per_group)
        
        concatenated_groups = []
        
        # 计算每组应该包含的段数
        segments_per_group_actual = len(data_segments) // n_groups
        remainder = len(data_segments) % n_groups
        
        logger.info(f"数据段总数: {len(data_segments)}, 分组数: {n_groups}, "
                    f"每组段数: {segments_per_group_actual}, 余数: {remainder}")
        
        start_idx = 0
        for i in range(n_groups):
            # 计算当前组的段数（前remainder组多一个段）
            current_segments = segments_per_group_actual
            if i < remainder:
                current_segments += 1
            
            end_idx = start_idx + current_segments
            
            # 获取当前组的数据段
            group_segments = data_segments[start_idx:end_idx]
            
            # 检查组内所有段长度是否相同
            lengths = [len(segment) for segment in group_segments]
            if len(set(lengths)) > 1:
                logger.warning(f"组 {i+1} 中的数据段长度不一致: {lengths}")
                # 如果长度不同，使用最短长度进行截断
                min_length = min(lengths)
                truncated_segments = [segment[:min_length] for segment in group_segments]
                concatenated_data = np.concatenate(truncated_segments)
            else:
                # 直接拼接当前组的所有段
                concatenated_data = np.concatenate(group_segments)
            
            concatenated_groups.append(concatenated_data)
            start_idx = end_idx
        
        return concatenated_groups


    def compute_long_period_fft(self, 
                            data: np.ndarray, 
                            ts_eff: float,
                            window_type: str = 'hanning',
                            remove_dc: bool = True) -> Tuple[np.ndarray, np.ndarray, Dict[str, Any]]:
        """
        计算长周期FFT，利用长数据提高频率分辨率
        
        Parameters:
        -----------
        data : np.ndarray
            输入的长周期时间序列数据
        ts_eff : float
            有效采样时间间隔（秒）
        window_type : str, optional
            窗函数类型，可选 'hanning', 'hamming', 'blackman', 'flattop'
        remove_dc : bool, optional
            是否移除直流分量，默认为True
        
        Returns:
        --------
        freq : np.ndarray
            频率数组（具有更高的频率分辨率）
        spectrum : np.ndarray
            频谱幅度
        stats : dict
            统计信息
        """
        # 参数验证
        if len(data) == 0:
            raise ValueError("输入数据不能为空")
        
        if ts_eff <= 0:
            raise ValueError("采样时间间隔必须大于0")
        
        # 数据预处理
        data_processed = data.astype(np.float64)
        
        # 移除直流分量
        if remove_dc:
            data_processed = data_processed - np.mean(data_processed)
        
        # 创建窗函数
        window = self._create_spectrum_window(len(data_processed), window_type)
        
        # 应用窗函数
        windowed_data = data_processed * window
        
        # 计算FFT - 使用整个长数据
        fft_result = np.fft.rfft(windowed_data)
        freq = np.fft.rfftfreq(len(data_processed), d=ts_eff)
        
        # 归一化
        scale = (np.sum(window) / len(data_processed)) * len(data_processed)
        magnitude_linear = np.abs(fft_result) / (scale + 1e-12)
        
        # 计算统计信息
        stats = {
            'data_length': len(data_processed),
            'frequency_resolution': freq[1] - freq[0] if len(freq) > 1 else 0,
            'nyquist_frequency': freq[-1] if len(freq) > 0 else 0,
            'window_type': window_type,
            'dc_removed': remove_dc
        }
        
        return freq, magnitude_linear, stats
    

    def compute_multi_period_fft_for_groups(self, 
                                            concatenated_groups: List[np.ndarray],
                                            ts_eff: float,
                                            **kwargs) -> Dict[str, Any]:
        """
        对拼接后的数据组进行FFT分析 - 只使用长周期模式
        
        Parameters:
        -----------
        concatenated_groups : List[np.ndarray]
            拼接后的数据组列表，每个组就是一个完整的周期
        ts_eff : float
            有效采样时间间隔
        **kwargs : dict
            传递给compute_long_period_fft的其他参数
            
        Returns:
        --------
        Dict[str, Any]
            包含所有组的FFT分析结果
        """
        results = {
            'group_spectra': [],
            'group_freqs': [],
            'group_stats': [],
            'group_time_data': [],  # 新增：保存每个组的时域数据
            'average_spectrum': None,
            'average_freq': None,
            'mode': 'long_period'
        }
        
        if not concatenated_groups:
            return results
        
        # 对每个拼接组进行长周期FFT分析
        for i, group_data in enumerate(concatenated_groups):
            try:
                # 保存时域数据
                results['group_time_data'].append(group_data)
                
                # 直接对完整周期进行FFT
                freq, spectrum, stats = self.compute_spectrum(
                    group_data, ts_eff
                )
                
                results['group_spectra'].append(spectrum)
                results['group_freqs'].append(freq)
                results['group_stats'].append(stats)
                
                logger.info(f"组 {i+1} 长周期FFT分析完成: {len(group_data)} 点数据, "
                        f"频率分辨率: {stats['frequency_resolution']:.6f} Hz")
                
            except Exception as e:
                logger.error(f"组 {i+1} 长周期FFT分析失败: {e}")
                continue
        
        # 计算平均频谱
        if results['group_spectra']:
            ref_freq = results['group_freqs'][0]
            aligned_spectra = []
            
            for freq, spectrum in zip(results['group_freqs'], results['group_spectra']):
                if len(freq) == len(ref_freq) and np.allclose(freq, ref_freq):
                    aligned_spectra.append(spectrum)
                else:
                    # 频率轴对齐
                    interp_spectrum = np.interp(ref_freq, freq, spectrum, left=0, right=0)
                    aligned_spectra.append(interp_spectrum)
            
            results['average_spectrum'] = np.mean(aligned_spectra, axis=0)
            results['average_freq'] = ref_freq
        
        return results

    def get_concatenated_data_stats(self, concatenated_groups: List[np.ndarray]) -> Dict[str, Any]:
        """
        获取拼接数据的统计信息
        
        Parameters:
        -----------
        concatenated_groups : List[np.ndarray]
            拼接后的数据组列表
            
        Returns:
        --------
        Dict[str, Any]
            统计信息
        """
        if not concatenated_groups:
            return {'error': '没有可用的拼接数据'}
        
        # 计算每个组的统计信息
        group_stats = []
        for i, group in enumerate(concatenated_groups):
            group_stats.append({
                'group_index': i,
                'length': len(group),
                'mean': float(np.mean(group)),
                'std': float(np.std(group)),
                'min': float(np.min(group)),
                'max': float(np.max(group)),
                'rms': float(np.sqrt(np.mean(group**2)))
            })
        
        stats = {
            'n_groups': len(concatenated_groups),
            'group_lengths': [len(group) for group in concatenated_groups],
            'total_points': sum(len(group) for group in concatenated_groups),
            'avg_group_length': float(np.mean([len(group) for group in concatenated_groups])),
            'max_group_length': max(len(group) for group in concatenated_groups),
            'min_group_length': min(len(group) for group in concatenated_groups),
            'group_stats': group_stats,
            'overall_mean': float(np.mean(np.concatenate(concatenated_groups))),
            'overall_std': float(np.std(np.concatenate(concatenated_groups))),
        }
        
        return stats
