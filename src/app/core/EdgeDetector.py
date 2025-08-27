# src/app/core/EdgeDetector.py
import numpy as np
from typing import Optional, Dict, Any, List, Tuple
import logging

logger = logging.getLogger(__name__)

class EdgeDetector:
    """边沿检测器类"""
    
    def __init__(self, config):
        self.config = config
    
    def _preprocess_data(self, data: np.ndarray) -> np.ndarray:
        """数据预处理：移动平均滤波"""
        window_size = 5
        return np.convolve(data, np.ones(window_size)/window_size, mode='same')
    
    def _find_edge_candidates(self, smoothed_data: np.ndarray, 
                            is_rising: bool = True, 
                            min_amplitude_ratio: float = 0.3) -> List[Tuple[int, float]]:
        """使用差分方法找到所有可能的边沿候选点"""
        # 计算差分
        dy = np.diff(smoothed_data)
        
        # 设置差分阈值
        if is_rising:
            dy_threshold = np.max(dy) * 0.3
            candidate_indices = np.flatnonzero(dy > dy_threshold) + 1
        else:
            dy_threshold = np.min(dy) * 0.3
            candidate_indices = np.flatnonzero(dy < dy_threshold) + 1
        
        # 计算信号的整体峰峰值用于幅度筛选
        signal_p2p = np.max(smoothed_data) - np.min(smoothed_data)
        min_amplitude = signal_p2p * min_amplitude_ratio
        
        # 筛选候选点
        valid_candidates = []
        for candidate in candidate_indices:
            if 20 <= candidate < len(smoothed_data) - 20:  # 确保有足够的点计算
                # 计算边沿前后的幅度变化
                if is_rising:
                    pre_window = max(0, candidate-15)
                    post_window = min(candidate + 15, len(smoothed_data))
                    baseline = np.median(smoothed_data[pre_window:candidate])
                    peak = np.max(smoothed_data[candidate:post_window])
                    amplitude = peak - baseline
                else:
                    pre_window = max(0, candidate-15)
                    post_window = min(candidate + 15, len(smoothed_data))
                    baseline = np.median(smoothed_data[pre_window:candidate])
                    valley = np.min(smoothed_data[candidate:post_window])
                    amplitude = baseline - valley
                
                if amplitude >= min_amplitude:
                    valid_candidates.append((candidate, amplitude))
        
        return valid_candidates
    
    def find_rise_position(self, sorted_data: np.ndarray, search_method: int, 
                         adc_full_mean: Optional[float] = None,
                         min_edge_amplitude_ratio: float = 0.5) -> int:
        """在排序后的数据中搜索上升沿位置"""
        # 预处理数据
        smoothed_data = self._preprocess_data(sorted_data)
        
        if search_method == 1:  # RISING
            if adc_full_mean is None:
                adc_full_mean = np.mean(sorted_data)
            
            # 找到所有上升沿候选点
            candidates = self._find_edge_candidates(smoothed_data, True, min_edge_amplitude_ratio)
            
            if candidates:
                # 选择幅度最大的候选点
                candidates.sort(key=lambda x: x[1], reverse=True)
                return candidates[0][0]
            else:
                # 回退到差分方法
                max_dy_idx = np.argmax(np.diff(sorted_data))
                return max_dy_idx + 1
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
            sorted_data, first_rise_pos, True, min_second_rise_ratio, 50, 0.5
        )
    
    def find_second_fall_position(self, sorted_data: np.ndarray, first_rise_pos: int, 
                                min_second_fall_ratio: float = 0.1) -> Optional[int]:
        """查找下降沿位置"""
        return self.find_second_edge_position(
            sorted_data, first_rise_pos, False, min_second_fall_ratio, 100, 0.7
        )
    
    def analyze_edges(self, sorted_data: np.ndarray) -> Dict[str, Any]:
        """完整的边沿分析流程"""
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
                result['rise_ratio'] = second_amplitude / first_amplitude
                
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
                result['fall_ratio'] = fall_amplitude / first_amplitude
                
                # 计算中点位置
                fall_midpoint = (first_rise_pos + fall_pos) // 2
                result['fall_midpoint'] = fall_midpoint
                result['fall_midpoint_time'] = fall_midpoint * self.config.ts_eff * 1e6
                
                if second_rise_pos is not None:
                    second_fall_midpoint = (second_rise_pos + fall_pos) // 2
                    result['second_fall_midpoint'] = second_fall_midpoint
                    result['second_fall_midpoint_time'] = second_fall_midpoint * self.config.ts_eff * 1e6
        
        return result
