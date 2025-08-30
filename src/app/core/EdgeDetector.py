# src/app/core/EdgeDetector.py
import matplotlib.pyplot as plt
import numpy as np
from typing import Optional, Dict, Any, List, Tuple
import logging
logger = logging.getLogger(__name__)
class EdgeDetector:
    """边沿检测器类"""
    
    def __init__(self, config):
        self.config = config
    
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
    
    def _find_edge_candidates(self, smoothed_data: np.ndarray, 
                            is_rising: bool = True, 
                            min_amplitude_ratio: float = 0.3) -> List[Tuple[int, float]]:
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
        # 第一步：窗口移动检测候选区间
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
        
        # 第二步：对候选区间做平均值处理，去掉平均值最小的异常点
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
        
        # 第三步：在有效窗口内使用差分法搜索精确的边沿位置
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
                    if self._is_spike_noise(smoothed_data, 3):
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

    def debug_plot_edges(self, sorted_data: np.ndarray, title: str = "Edge Detection Debug") -> plt.Figure:
        """
        调试绘图函数，显示边沿检测的详细过程
        
        Args:
            sorted_data: 输入数据曲线
            title: 图表标题
            
        Returns:
            matplotlib Figure对象
        """
        # 预处理数据
        smoothed_data = self._preprocess_data(sorted_data)
        
        # 创建图表
        fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 8))
        fig.suptitle(title, fontsize=14)
        
        # 绘制原始数据和平滑数据
        ax1.plot(sorted_data, 'b-', label='原始数据', alpha=0.7, linewidth=1)
        ax1.plot(smoothed_data, 'r-', label='平滑数据', alpha=0.8, linewidth=1.5)
        
        # 检测第一个上升沿
        first_rise_pos = self.find_rise_position(
            sorted_data, self.config.search_method, np.mean(sorted_data)
        )
        
        if first_rise_pos is not None:
            # 标记第一个上升沿
            ax1.axvline(x=first_rise_pos, color='g', linestyle='--', 
                       label=f'第一上升沿: {first_rise_pos}')
            ax1.plot(first_rise_pos, sorted_data[first_rise_pos], 'go', markersize=8)
            
            # 计算第一个上升沿的幅度
            first_baseline = np.median(sorted_data[max(0, first_rise_pos-15):first_rise_pos])
            first_peak_search_end = min(first_rise_pos + 50, len(sorted_data))
            first_peak_val = np.max(sorted_data[first_rise_pos:first_peak_search_end])
            first_amplitude = first_peak_val - first_baseline
            
            # 标记基线和峰值
            ax1.axhline(y=first_baseline, color='orange', linestyle=':', alpha=0.7)
            ax1.axhline(y=first_peak_val, color='orange', linestyle=':', alpha=0.7)
            
            # 检测第二个上升沿
            second_rise_candidates = self._find_edge_candidates(
                smoothed_data[first_rise_pos + 50:], True, 0.1
            )
            second_rise_candidates = [(pos + first_rise_pos + 50, amp) 
                                    for pos, amp in second_rise_candidates]
            
            if second_rise_candidates:
                # 筛选合格的候选点
                valid_second_rise = []
                for candidate_pos, candidate_amp in second_rise_candidates:
                    if candidate_amp >= first_amplitude * 0.1:
                        valid_second_rise.append((candidate_pos, candidate_amp))
                
                # 标记所有候选点
                for pos, amp in second_rise_candidates:
                    ax1.plot(pos, sorted_data[pos], 'yo', markersize=6, alpha=0.5)
                
                # 标记合格的候选点
                for pos, amp in valid_second_rise:
                    ax1.plot(pos, sorted_data[pos], 'mo', markersize=6)
                
                # 选择最近的合格候选点
                if valid_second_rise:
                    valid_second_rise.sort(key=lambda x: abs(x[0] - first_rise_pos))
                    second_rise_pos = valid_second_rise[0][0]
                    ax1.axvline(x=second_rise_pos, color='m', linestyle='--',
                               label=f'第二上升沿: {second_rise_pos}')
                    ax1.plot(second_rise_pos, sorted_data[second_rise_pos], 'mo', markersize=8)
            
            # 检测下降沿
            fall_candidates = self._find_edge_candidates(
                smoothed_data[first_rise_pos + 100:], False, 0.1
            )
            fall_candidates = [(pos + first_rise_pos + 100, amp) 
                             for pos, amp in fall_candidates]
            
            if fall_candidates:
                # 筛选合格的候选点
                valid_fall = []
                for candidate_pos, candidate_amp in fall_candidates:
                    if candidate_amp >= first_amplitude * 0.1:
                        valid_fall.append((candidate_pos, candidate_amp))
                
                # 标记所有候选点
                for pos, amp in fall_candidates:
                    ax1.plot(pos, sorted_data[pos], 'co', markersize=6, alpha=0.5)
                
                # 标记合格的候选点
                for pos, amp in valid_fall:
                    ax1.plot(pos, sorted_data[pos], 'co', markersize=6)
                
                # 选择最近的合格候选点
                if valid_fall:
                    valid_fall.sort(key=lambda x: abs(x[0] - first_rise_pos))
                    fall_pos = valid_fall[0][0]
                    ax1.axvline(x=fall_pos, color='c', linestyle='--',
                               label=f'下降沿: {fall_pos}')
                    ax1.plot(fall_pos, sorted_data[fall_pos], 'co', markersize=8)
        
        ax1.set_xlabel('采样点')
        ax1.set_ylabel('幅值')
        ax1.legend()
        ax1.grid(True, alpha=0.3)
        
        # 绘制差分数据
        dy = np.diff(smoothed_data)
        ax2.plot(dy, 'g-', label='一阶差分', alpha=0.8)
        
        # 标记差分阈值
        rising_threshold = np.max(dy) * 0.3
        falling_threshold = np.min(dy) * 0.3
        ax2.axhline(y=rising_threshold, color='r', linestyle=':', label='上升沿阈值')
        ax2.axhline(y=falling_threshold, color='b', linestyle=':', label='下降沿阈值')
        
        ax2.set_xlabel('采样点')
        ax2.set_ylabel('差分值')
        ax2.legend()
        ax2.grid(True, alpha=0.3)
        
        plt.tight_layout()
        return fig
    
    def quick_debug_plot(self, sorted_data: np.ndarray, save_path: Optional[str] = None):
        """
        快速调试绘图，显示主要边沿检测结果
        
        Args:
            sorted_data: 输入数据曲线
            save_path: 可选，保存图片的路径
        """
        result = self.analyze_edges(sorted_data)
        
        plt.figure(figsize=(10, 6))
        plt.plot(sorted_data, 'b-', label='原始数据', linewidth=1.5)
        
        # 标记检测到的边沿
        if result['first_rise_pos'] is not None:
            plt.axvline(x=result['first_rise_pos'], color='g', linestyle='--', 
                       label=f'第一上升沿: {result["first_rise_pos"]}')
            plt.plot(result['first_rise_pos'], sorted_data[result['first_rise_pos']], 
                    'go', markersize=8)
            
            if 'stable_high_level' in result:
                plt.axhline(y=result['stable_high_level'], color='orange', 
                           linestyle=':', alpha=0.7, label='稳定高电平')
        
        if result.get('second_rise_pos') is not None:
            plt.axvline(x=result['second_rise_pos'], color='m', linestyle='--',
                       label=f'第二上升沿: {result["second_rise_pos"]}')
            plt.plot(result['second_rise_pos'], sorted_data[result['second_rise_pos']],
                    'mo', markersize=8)
        
        if result.get('fall_pos') is not None:
            plt.axvline(x=result['fall_pos'], color='c', linestyle='--',
                       label=f'下降沿: {result["fall_pos"]}')
            plt.plot(result['fall_pos'], sorted_data[result['fall_pos']],
                    'co', markersize=8)
        
        plt.xlabel('采样点')
        plt.ylabel('幅值')
        plt.title('边沿检测结果')
        plt.legend()
        plt.grid(True, alpha=0.3)
        
        if save_path:
            plt.savefig(save_path, dpi=300, bbox_inches='tight')
        
        plt.show()
    
    def plot_comparison(self, data_list: List[np.ndarray], titles: List[str] = None):
        """
        比较多个数据曲线的边沿检测结果
        
        Args:
            data_list: 多个数据曲线的列表
            titles: 每个曲线的标题列表
        """
        if titles is None:
            titles = [f'曲线 {i+1}' for i in range(len(data_list))]
        
        n_plots = len(data_list)
        fig, axes = plt.subplots(n_plots, 1, figsize=(12, 4 * n_plots))
        
        if n_plots == 1:
            axes = [axes]
        
        for i, (data, title) in enumerate(zip(data_list, titles)):
            result = self.analyze_edges(data)
            
            axes[i].plot(data, 'b-', label='数据', linewidth=1.5)
            
            # 标记检测到的边沿
            if result['first_rise_pos'] is not None:
                axes[i].axvline(x=result['first_rise_pos'], color='g', linestyle='--')
                axes[i].plot(result['first_rise_pos'], data[result['first_rise_pos']], 
                           'go', markersize=6)
            
            if result.get('second_rise_pos') is not None:
                axes[i].axvline(x=result['second_rise_pos'], color='m', linestyle='--')
                axes[i].plot(result['second_rise_pos'], data[result['second_rise_pos']],
                           'mo', markersize=6)
            
            if result.get('fall_pos') is not None:
                axes[i].axvline(x=result['fall_pos'], color='c', linestyle='--')
                axes[i].plot(result['fall_pos'], data[result['fall_pos']],
                           'co', markersize=6)
            
            axes[i].set_title(f'{title} - 边沿检测')
            axes[i].set_xlabel('采样点')
            axes[i].set_ylabel('幅值')
            axes[i].grid(True, alpha=0.3)
        
        plt.tight_layout()
        plt.show()

    def simple_plot_data(self, data: np.ndarray, 
                        title: str = "Data Plot", 
                        xlabel: str = "Sample Points", 
                        ylabel: str = "Amplitude",
                        show_grid: bool = True,
                        figsize: Tuple[int, int] = (10, 6),
                        line_style: str = 'b-',
                        line_width: float = 1.5,
                        alpha: float = 1.0,
                        save_path: Optional[str] = None,
                        dpi: int = 100) -> plt.Figure:
        """
        单纯的数据绘图函数，不进行任何检测
        
        Args:
            data: 输入数据数组
            title: 图表标题
            xlabel: x轴标签
            ylabel: y轴标签
            show_grid: 是否显示网格
            figsize: 图表尺寸
            line_style: 线条样式
            line_width: 线条宽度
            alpha: 透明度
            save_path: 保存路径（可选）
            dpi: 图片分辨率
            
        Returns:
            matplotlib Figure对象
        """
        fig, ax = plt.subplots(figsize=figsize)
        
        # 绘制数据
        ax.plot(data, line_style, linewidth=line_width, alpha=alpha)
        
        # 设置标题和标签
        ax.set_title(title, fontsize=14)
        ax.set_xlabel(xlabel, fontsize=12)
        ax.set_ylabel(ylabel, fontsize=12)
        
        # 显示网格
        if show_grid:
            ax.grid(True, alpha=0.3)
        
        # 自动调整布局
        plt.tight_layout()
        plt.show()