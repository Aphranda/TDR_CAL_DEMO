# src/app/core/EdgeDetector.py
import numpy as np
from typing import Optional, Dict, Any
import logging

logger = logging.getLogger(__name__)

class EdgeDetector:
    """边沿检测器类"""
    
    def __init__(self, config):
        self.config = config
    
    def find_rise_position(self, sorted_data: np.ndarray, search_method: int, 
                        adc_full_mean: Optional[float] = None,
                        min_edge_amplitude_ratio: float = 0.5) -> int:
        """在排序后的数据中搜索上升沿位置"""
        # 计算信号的整体峰峰值
        signal_p2p = np.max(sorted_data) - np.min(sorted_data)
        
        # 预处理：使用移动平均滤波减少毛刺影响
        window_size = 5  # 可根据实际情况调整
        smoothed_data = np.convolve(sorted_data, np.ones(window_size)/window_size, mode='same')
        
        if search_method == 1:  # RISING
            if adc_full_mean is None:
                adc_full_mean = np.mean(sorted_data)
            
            # 方法1：使用滤波后的数据进行初步检测
            basic_candidates = np.flatnonzero(
                (smoothed_data[50:] > adc_full_mean) & 
                (smoothed_data[:-50] <= adc_full_mean)
            ) + 50  # 补偿偏移
            
            # 方法2：使用差分方法找到所有可能的边沿
            dy = np.diff(smoothed_data)
            dy_threshold = np.max(dy) * 0.3  # 设置差分阈值
            diff_candidates = np.flatnonzero(dy > dy_threshold) + 1
            
            # 合并候选点
            all_candidates = np.unique(np.concatenate([basic_candidates, diff_candidates]))
            
            # 筛选幅度比例满足条件的候选点
            valid_candidates = []
            for candidate in all_candidates:
                if 10 <= candidate < len(sorted_data) - 10:  # 确保有足够的点计算
                    # 计算基线（使用滤波前数据）
                    baseline_window = max(0, candidate-20)
                    baseline = np.median(sorted_data[baseline_window:candidate])  # 使用中值滤波减少毛刺影响
                    
                    # 计算峰值（使用滤波前数据）
                    peak_window = min(candidate + 20, len(sorted_data))
                    peak_val = np.max(sorted_data[candidate:peak_window])
                    
                    edge_amplitude = peak_val - baseline
                    
                    # 更严格的筛选条件
                    if (edge_amplitude >= min_edge_amplitude_ratio * signal_p2p and
                        edge_amplitude >= signal_p2p * 0.3):  # 确保是主要边沿
                        valid_candidates.append((candidate, edge_amplitude, peak_val))
            
            if valid_candidates:
                # 选择幅度最大的候选点
                valid_candidates.sort(key=lambda x: x[1], reverse=True)
                
                # 进一步验证：确保不是毛刺
                best_candidate = valid_candidates[0][0]
                best_amplitude = valid_candidates[0][1]
                
                # 检查候选点周围是否有更大的边沿（防止漏检）
                for candidate, amplitude, _ in valid_candidates[1:]:
                    if amplitude > best_amplitude * 0.8:  # 如果存在幅度相近的候选点
                        # 选择更靠前的点（通常是主边沿）
                        if candidate < best_candidate:
                            best_candidate = candidate
                            best_amplitude = amplitude
                
                return best_candidate
            else:
                # 回退到差分方法
                max_dy_idx = np.argmax(np.diff(sorted_data))
                return max_dy_idx + 1
        else:
            # 最大值方法
            max_pos = np.argmax(sorted_data)
            return max_pos

    
    def find_second_rise_position(self, sorted_data: np.ndarray, first_rise_pos: int, 
                                min_second_rise_ratio: float = 0.1) -> Optional[int]:
        """查找第二个上升沿位置"""
        if first_rise_pos >= len(sorted_data) - 10:
            return None
      
        # 计算第一个上升沿的峰值和高电平
        first_peak_search_end = min(first_rise_pos + 100, len(sorted_data))
        first_peak_val = np.max(sorted_data[first_rise_pos:first_peak_search_end])
        first_peak_pos = first_rise_pos + np.argmax(sorted_data[first_rise_pos:first_peak_search_end])
      
        # 计算第一个上升沿的幅度
        first_baseline = np.mean(sorted_data[max(0, first_rise_pos-10):first_rise_pos])
        first_rise_amplitude = first_peak_val - first_baseline
      
        # 计算第二个上升沿的最小幅度阈值
        min_second_amplitude = first_rise_amplitude * min_second_rise_ratio
      
        # 使用第一个上升沿的高电平作为第二个上升沿的起始电平
        start_level = first_peak_val
      
        # 在第一个峰值之后搜索第二个上升沿
        search_start = first_peak_pos + 50
        search_end = int(len(sorted_data) * 0.5)
      
        second_rise_candidates = []
      
        for i in range(search_start, search_end):
            if (abs(sorted_data[i] - start_level) < first_rise_amplitude * 0.2 and
                sorted_data[i + 1] > sorted_data[i] + min_second_amplitude * 0.3):
              
                # 寻找上升沿的峰值
                for j in range(i + 1, min(i + 100, len(sorted_data))):
                    if sorted_data[j] < sorted_data[j - 1]:
                        peak_pos = j - 1
                        peak_val = sorted_data[peak_pos]
                      
                        # 计算上升沿幅度
                        rise_amplitude = peak_val - start_level
                      
                        if rise_amplitude >= min_second_amplitude:
                            second_rise_candidates.append(peak_pos)
                        break
      
        if second_rise_candidates:
            # 选择距离第一个上升沿最近的候选点
            distances = [abs(candidate - first_rise_pos) for candidate in second_rise_candidates]
            closest_idx = np.argmin(distances)
            return second_rise_candidates[closest_idx]
      
        return None
    
    def find_second_fall_position(self, sorted_data: np.ndarray, rise_pos: int, 
                                min_second_fall_ratio: float = 0.1) -> Optional[int]:
        """查找下降沿位置"""
        if rise_pos >= len(sorted_data) - 10:
            return None
      
        # 计算第一个上升沿的峰值
        peak_search_end = min(rise_pos + 100, len(sorted_data))
        peak_val = np.max(sorted_data[rise_pos:peak_search_end])
        peak_pos = rise_pos + np.argmax(sorted_data[rise_pos:peak_search_end])
      
        # 计算第一个上升沿的幅度
        baseline = np.mean(sorted_data[max(0, rise_pos-10):rise_pos])
        rise_amplitude = peak_val - baseline
      
        # 计算下降沿的最小幅度阈值
        min_fall_amplitude = rise_amplitude * min_second_fall_ratio
      
        # 找到稳定后的高电平
        stable_search_start = peak_pos + 20
        stable_search_end = min(stable_search_start + 50, len(sorted_data))
        stable_high_level = np.mean(sorted_data[stable_search_start:stable_search_end])
      
        # 在稳定区域之后搜索下降沿
        search_start = stable_search_end + 10
        search_end = int(len(sorted_data) * 0.5)
      
        fall_candidates = []
      
        for i in range(search_start, search_end):
            current_val = sorted_data[i]
            next_val = sorted_data[i + 1] if i + 1 < len(sorted_data) else current_val
          
            if (abs(current_val - stable_high_level) < rise_amplitude * 0.15 and
                next_val < current_val - min_fall_amplitude * 0.4):
              
                # 寻找下降沿的谷值
                for j in range(i + 2, min(i + 150, len(sorted_data))):
                    if j + 1 >= len(sorted_data):
                        break
                      
                    if (sorted_data[j] < sorted_data[j - 1] and 
                        sorted_data[j] < sorted_data[j + 1]):
                        valley_pos = j
                        valley_val = sorted_data[valley_pos]
                      
                        # 计算下降沿幅度
                        fall_amplitude = stable_high_level - valley_val
                      
                        if fall_amplitude >= min_fall_amplitude:
                            fall_candidates.append(valley_pos)
                        break
      
        if fall_candidates:
            # 选择距离上升沿最近的候选点
            distances = [abs(candidate - rise_pos) for candidate in fall_candidates]
            closest_idx = np.argmin(distances)
            return fall_candidates[closest_idx]
      
        return None
    
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
            first_baseline = np.mean(sorted_data[max(0, first_rise_pos-10):first_rise_pos])
            first_peak_search_end = min(first_rise_pos + 100, len(sorted_data))
            first_peak_val = np.max(sorted_data[first_rise_pos:first_peak_search_end])
            first_amplitude = first_peak_val - first_baseline
            result['first_rise_amplitude'] = first_amplitude
          
            # 找到稳定后的高电平
            first_peak_pos = first_rise_pos + np.argmax(sorted_data[first_rise_pos:first_peak_search_end])
            stable_search_start = first_peak_pos + 20
            stable_search_end = min(stable_search_start + 50, len(sorted_data))
            stable_high_level = np.mean(sorted_data[stable_search_start:stable_search_end])
            result['stable_high_level'] = stable_high_level
          
            # 查找第二个上升沿
            second_rise_pos = self.find_second_rise_position(
                sorted_data, first_rise_pos, self.config.min_second_rise_ratio
            )
            result['second_rise_pos'] = second_rise_pos
          
            if second_rise_pos is not None:
                second_peak_search_end = min(second_rise_pos + 100, len(sorted_data))
                second_peak_val = np.max(sorted_data[second_rise_pos:second_peak_search_end])
                second_amplitude = second_peak_val - stable_high_level
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
                fall_amplitude = stable_high_level - fall_valley
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
