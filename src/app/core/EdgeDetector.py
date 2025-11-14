# src/app/core/EdgeDetector.py
import matplotlib.pyplot as plt
from scipy.signal import savgol_filter
import numpy as np
from typing import Optional, Dict, Any, List, Tuple
import logging
logger = logging.getLogger(__name__)
class EdgeDetector:
    """边沿检测器类"""
    
    def __init__(self, config):
        self.config = config


    def smooth_10ps_edge(self,data: np.ndarray, window_length: int = 7, polyorder: int = 3) -> np.ndarray:
        """Savitzky-Golay滤波，保留边沿特性"""
        return savgol_filter(data, window_length, polyorder)
    
    def _preprocess_data(self, data: np.ndarray, window_size: int = 5) -> np.ndarray:
        """数据预处理：移动平均滤波"""
        return np.convolve(data, np.ones(window_size)/window_size, mode='same')
    
    def _is_spike_noise(self, data: np.ndarray, candidate_pos: int, window_size: int = 3) -> bool:
        """
        检测是否为毛刺噪声（中间高两边低的异常点）
        
        Args:
            data: 原始数据
            candidate_pos: 候选点位置
            window_size: 检测窗口大小
            
        Returns:
            True如果是毛刺噪声，False如果不是
        """
        if candidate_pos < window_size or candidate_pos >= len(data) - window_size:
            return False
        
        # 获取候选点前后窗口的数据
        left_window = data[candidate_pos - window_size:candidate_pos]
        right_window = data[candidate_pos + 1:candidate_pos + window_size + 1]
        candidate_value = data[candidate_pos]
        
        # 计算左右窗口的平均值
        left_avg = np.mean(left_window)
        right_avg = np.mean(right_window)
        
        # 如果候选点值远高于左右平均值，且左右平均值相近，则认为是毛刺
        if (candidate_value > left_avg * 1.5 and 
            candidate_value > right_avg * 1.5 and
            abs(left_avg - right_avg) < (left_avg + right_avg) * 0.2):
            return True
        
        return False
    
    def _is_noise_floor(self, data: np.ndarray, noise_threshold_ratio: float = 0.3) -> bool:
        """
        判断是否为底噪
        
        Args:
            data: 输入数据
            noise_threshold_ratio: 底噪判断阈值比例（默认0.3）
            
        Returns:
            True如果是底噪，False如果不是
        """
        if len(data) < 10:
            return False
            
        # 计算数据的峰峰值
        p2p = np.ptp(data)
        if p2p > 550000:
            return True
        # 计算数据的平均值
        mean_val = np.mean(data)
        
        # 计算峰峰值与平均值的差值
        p2p_minus_mean = p2p - mean_val
        
        # 判断条件：峰峰值减平均值不超过峰峰值的0.3倍
        if p2p_minus_mean <= p2p * noise_threshold_ratio:
            logger.info(f"Detected noise floor - p2p: {p2p:.2f}, mean: {mean_val:.2f}, "
                    f"p2p_minus_mean: {p2p_minus_mean:.2f}, threshold: {p2p * noise_threshold_ratio:.2f}")
            return True
            
        logger.debug(f"Noise floor not detected - p2p: {p2p:.2f}, mean: {mean_val:.2f}, "
                    f"p2p_minus_mean: {p2p_minus_mean:.2f}, threshold: {p2p * noise_threshold_ratio:.2f}")
        return False


    def _find_edges_by_differential(self, smoothed_data: np.ndarray, 
                                  is_rising: bool = True,
                                  min_amplitude_ratio: float = 0.3) -> List[Tuple[int, float]]:
        """
        使用差分法查找边沿候选点（用于底噪情况）
        
        Args:
            smoothed_data: 平滑后的数据
            is_rising: True为上升沿，False为下降沿
            min_amplitude_ratio: 最小幅度比例阈值
            
        Returns:
            候选点列表，每个元素为(位置, 幅度)
        """
        if len(smoothed_data) < 20:
            return []
        
        # 计算差分
        dy = np.diff(smoothed_data)
        
        # 设置差分阈值
        threshold = np.ptp(smoothed_data) * min_amplitude_ratio
        
        if is_rising:
            # 寻找上升沿：差分大于阈值的位置
            candidate_indices = np.flatnonzero(dy > threshold * 0.5) + 1
        else:
            # 寻找下降沿：差分小于阈值的位置
            candidate_indices = np.flatnonzero(dy < -threshold * 0.5) + 1
        
        # 计算每个候选点的幅度
        valid_candidates = []
        for candidate in candidate_indices:
            if 10 <= candidate < len(smoothed_data) - 10:
                # 计算前后窗口的平均值
                pre_window = smoothed_data[max(0, candidate-5):candidate]
                post_window = smoothed_data[candidate:min(len(smoothed_data), candidate+5)]
                
                pre_avg = np.mean(pre_window)
                post_avg = np.mean(post_window)
                
                if is_rising and post_avg > pre_avg:
                    amplitude = post_avg - pre_avg
                    if amplitude > threshold:
                        valid_candidates.append((candidate, amplitude))
                elif not is_rising and post_avg < pre_avg:
                    amplitude = pre_avg - post_avg
                    if amplitude > threshold:
                        valid_candidates.append((candidate, amplitude))
        
        return valid_candidates
    
    def _find_edge_candidates(self, smoothed_data: np.ndarray, 
                            is_rising: bool = True, 
                            min_amplitude_ratio: float = 0.3, use_fast_mode = False) -> List[Tuple[int, float]]:
        """
        使用窗口移动方法找到所有可能的边沿候选区间，然后对候选区间做平均值处理，
        去掉平均值最小的异常点，最后再用差分法搜索上升沿位置
        
        Args:
            smoothed_data: 平滑后的数据
            is_rising: True为上升沿，False为下降沿
            min_amplitude_ratio: 最小幅度比例阈值
            
        Returns:
            候选点列表，每个元素为(位置, 幅度)
        """
        if use_fast_mode:
            return self._find_edges_by_differential(smoothed_data, is_rising, min_amplitude_ratio)
        # 第一步：判断是否为底噪
        if self._is_noise_floor(smoothed_data, noise_threshold_ratio=0.05):
            # 如果是底噪，直接使用差分法
            return self._find_edges_by_differential(smoothed_data, is_rising, min_amplitude_ratio)
        
        # 第二步：窗口移动检测候选区间
        window_size = max(10, int(len(smoothed_data) * 0.05))  # 5%的窗口大小，最小10个点
        step_size = max(5, int(len(smoothed_data) * 0.03))    # 3%的步进大小，最小5个点
        
        # 确保步长不为0
        if step_size == 0:
            step_size = 1
            
        threshold = np.ptp(smoothed_data) * min_amplitude_ratio  # 峰峰值阈值
        
        candidate_windows = []
        
        # 滑动窗口检测
        for start in range(0, len(smoothed_data) - window_size, step_size):
            end = start + window_size
            window_data = smoothed_data[start:end]
            window_p2p = np.ptp(window_data)  # 计算窗口内的峰峰值
            
            if window_p2p > threshold:
                candidate_windows.append((start, end, window_p2p))
        
        if not candidate_windows:
            return []
        
        # 第三步：对候选区间做平均值处理，去掉平均值最小的异常点
        valid_windows = []
        window_means = []
        
        for start, end, p2p in candidate_windows:
            window_mean = np.mean(smoothed_data[start:end])
            window_means.append(window_mean)
        
        # 计算平均值的均值和标准差
        mean_of_means = np.mean(window_means)
        std_of_means = np.std(window_means)
        
        # 筛选有效的窗口（去掉平均值异常的点）
        for i, (start, end, p2p) in enumerate(candidate_windows):
            if abs(window_means[i] - mean_of_means) < 2 * std_of_means:
                valid_windows.append((start, end, p2p))
        
        if not valid_windows:
            return []
        
        # 第四步：在有效窗口内使用差分法搜索精确的边沿位置
        valid_candidates = []
        
        for start, end, p2p in valid_windows:
            window_data = smoothed_data[start:end]
            
            # 计算差分
            dy = np.diff(window_data)
            
            # 设置差分阈值
            if is_rising:
                dy_threshold = np.max(dy) * 0.3 if len(dy) > 0 else 0
                candidate_indices = np.flatnonzero(dy > dy_threshold) + 1
            else:
                dy_threshold = np.min(dy) * 0.3 if len(dy) > 0 else 0
                candidate_indices = np.flatnonzero(dy < dy_threshold) + 1
            
            # 转换回全局坐标并计算幅度
            for candidate in candidate_indices:
                global_pos = start + candidate
                if 20 <= global_pos < len(smoothed_data) - 20:
                    # 新增：过滤毛刺噪声点
                    if self._is_spike_noise(smoothed_data, global_pos, 3):
                        continue  # 跳过毛刺噪声点
                    
                    # 计算候选点前后±5%窗口的平均值
                    window_size_5pct = max(5, int(len(smoothed_data) * 0.02))
                    pre_window_start = max(0, global_pos - window_size_5pct)
                    pre_window_end = global_pos
                    post_window_start = global_pos
                    post_window_end = min(len(smoothed_data), global_pos + window_size_5pct)
                    
                    pre_avg = np.mean(smoothed_data[pre_window_start:pre_window_end])
                    post_avg = np.mean(smoothed_data[post_window_start:post_window_end])
                    
                    # 判断是否为毛刺信号：如果两边平均值差距很小，说明是毛刺
                    if abs(pre_avg - post_avg) < threshold * 0.1:
                        continue  # 跳过毛刺信号
                    
                    # 通过两边大小判断边沿类型
                    if is_rising and post_avg > pre_avg:
                        amplitude = post_avg - pre_avg
                        valid_candidates.append((global_pos, amplitude))
                    elif not is_rising and post_avg < pre_avg:
                        amplitude = pre_avg - post_avg
                        valid_candidates.append((global_pos, amplitude))
        
        return valid_candidates

    def find_rise_position(self, sorted_data: np.ndarray, search_method: int, 
                         adc_full_mean: Optional[float] = None,
                         min_edge_amplitude_ratio: float = 0.5) -> int:
        """在排序后的数据中搜索上升沿位置"""
        # 预处理数据
 
        if search_method == 1:  # RISING
            if adc_full_mean is None:
                adc_full_mean = np.mean(sorted_data)

            # 预处理数据
            sorted_data = self.smooth_10ps_edge(sorted_data)
            
            # 找到所有上升沿候选点
            candidates = self._find_edge_candidates(sorted_data, True, min_edge_amplitude_ratio)
            
            if candidates:
                # 选择幅度最大的候选点
                candidates.sort(key=lambda x: x[1], reverse=True)
                return candidates[0][0]
            else:
                # 回退到差分方法
                if len(sorted_data) > 1:
                    max_dy_idx = np.argmax(np.diff(sorted_data))
                    return max_dy_idx + 1
                else:
                    return 0
        else:
            # 最大值方法
            return np.argmax(sorted_data)
    
    def find_second_edge_position(self, sorted_data: np.ndarray, 
                                first_edge_pos: int, 
                                is_rising: bool = True,
                                min_amplitude_ratio: float = 0.1,
                                search_start_offset: int = 50,
                                search_range_ratio: float = 0.5) -> Optional[int]:
        """
        查找第二个边沿位置（上升沿或下降沿）
        
        Args:
            sorted_data: 排序后的数据
            first_edge_pos: 第一个边沿位置
            is_rising: True为上升沿，False为下降沿
            min_amplitude_ratio: 最小幅度比例
            search_start_offset: 搜索起始偏移量
            search_range_ratio: 搜索范围比例
            
        Returns:
            第二个边沿位置或None
        """
        if first_edge_pos >= len(sorted_data) - 20:
            return None
        
        # 预处理数据
        smoothed_data = self._preprocess_data(sorted_data)
        
        # 计算第一个边沿的幅度作为参考
        if is_rising:
            first_baseline = np.median(smoothed_data[max(0, first_edge_pos-15):first_edge_pos])
            first_peak_search_end = min(first_edge_pos + 50, len(smoothed_data))
            first_peak_val = np.max(smoothed_data[first_edge_pos:first_peak_search_end])
            first_amplitude = first_peak_val - first_baseline
        else:
            first_baseline = np.median(smoothed_data[max(0, first_edge_pos-15):first_edge_pos])
            first_valley_search_end = min(first_edge_pos + 50, len(smoothed_data))
            first_valley_val = np.min(smoothed_data[first_edge_pos:first_valley_search_end])
            first_amplitude = first_baseline - first_valley_val
        
        # 设置最小幅度阈值
        min_amplitude = first_amplitude * min_amplitude_ratio
        
        # 确定搜索范围（在第一个边沿之后）
        search_start = first_edge_pos + search_start_offset
        search_end = min(int(len(smoothed_data) * search_range_ratio), len(smoothed_data) - 20)
        
        if search_start >= search_end:
            return None
        
        # 在搜索范围内找到所有候选边沿
        candidates = self._find_edge_candidates(
            smoothed_data[search_start:search_end], 
            is_rising, 
            min_amplitude_ratio
        )
        
        # 将候选点位置转换回全局坐标
        global_candidates = [(pos + search_start, amp) for pos, amp in candidates]
        
        if not global_candidates:
            return None
        
        # 筛选：幅度达标并且离第一个边沿最近的点
        valid_candidates = []
        for candidate_pos, candidate_amp in global_candidates:
            if candidate_amp >= min_amplitude:
                valid_candidates.append((candidate_pos, candidate_amp))
        
        if not valid_candidates:
            return None
        
        # 选择离第一个边沿最近的候选点
        valid_candidates.sort(key=lambda x: abs(x[0] - first_edge_pos))
        return valid_candidates[0][0]
    
    def find_second_rise_position(self, sorted_data: np.ndarray, first_rise_pos: int, 
                                min_second_rise_ratio: float = 0.1) -> Optional[int]:
        """查找第二个上升沿位置"""
        return self.find_second_edge_position(
            sorted_data, first_rise_pos, True, min_second_rise_ratio, 30, 0.5
        )
    
    def find_second_fall_position(self, sorted_data: np.ndarray, first_rise_pos: int, 
                                min_second_fall_ratio: float = 0.1) -> Optional[int]:
        """查找下降沿位置"""
        return self.find_second_edge_position(
            sorted_data, first_rise_pos, False, min_second_fall_ratio, 30, 0.7
        )
    
    def analyze_edges(self, sorted_data: np.ndarray) -> Dict[str, Any]:
        """完整的边沿分析流程"""
        # 确保数据长度足够
        if len(sorted_data) < 100:
            return {'first_rise_pos': None, 'second_rise_pos': None, 'fall_pos': None}
        
        first_rise_pos = self.find_rise_position(
            sorted_data, 
            self.config.search_method, 
            np.mean(sorted_data),
            self.config.min_edge_amplitude_ratio
        )
        
        result = {'first_rise_pos': first_rise_pos}
        
        if first_rise_pos is not None:
            # 计算第一个上升沿的幅度
            first_baseline = np.median(sorted_data[max(0, first_rise_pos-15):first_rise_pos])
            first_peak_search_end = min(first_rise_pos + 50, len(sorted_data))
            first_peak_val = np.max(sorted_data[first_rise_pos:first_peak_search_end])
            first_amplitude = first_peak_val - first_baseline
            result['first_rise_amplitude'] = first_amplitude
            
            # 查找第二个上升沿
            second_rise_pos = self.find_second_rise_position(
                sorted_data, first_rise_pos, self.config.min_second_rise_ratio
            )
            result['second_rise_pos'] = second_rise_pos
            
            if second_rise_pos is not None:
                second_peak_search_end = min(second_rise_pos + 50, len(sorted_data))
                second_peak_val = np.max(sorted_data[second_rise_pos:second_peak_search_end])
                second_amplitude = second_peak_val - first_peak_val
                result['second_rise_amplitude'] = second_amplitude
                result['rise_ratio'] = second_amplitude / first_amplitude if first_amplitude != 0 else 0
                
                # 计算中点位置
                rise_midpoint = (first_rise_pos + second_rise_pos) // 2
                result['rise_midpoint'] = rise_midpoint
                result['rise_midpoint_time'] = rise_midpoint * self.config.ts_eff * 1e6
            
            # 查找下降沿
            fall_pos = self.find_second_fall_position(
                sorted_data, first_rise_pos, self.config.min_second_fall_ratio
            )
            result['fall_pos'] = fall_pos
            
            if fall_pos is not None:
                fall_valley_search_end = min(fall_pos + 50, len(sorted_data))
                fall_valley = np.min(sorted_data[fall_pos:fall_valley_search_end])
                fall_amplitude = first_peak_val - fall_valley
                result['fall_amplitude'] = fall_amplitude
                result['fall_ratio'] = fall_amplitude / first_amplitude if first_amplitude != 0 else 0
                
                # 计算中点位置
                fall_midpoint = (first_rise_pos + fall_pos) // 2
                result['fall_midpoint'] = fall_midpoint
                result['fall_midpoint_time'] = fall_midpoint * self.config.ts_eff * 1e6
                
                if second_rise_pos is not None:
                    second_fall_midpoint = (second_rise_pos + fall_pos) // 2
                    result['second_fall_midpoint'] = second_fall_midpoint
                    result['second_fall_midpoint_time'] = second_fall_midpoint * self.config.ts_eff * 1e6
        
        return result




