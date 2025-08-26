# src/app/core/DataAnalyze.py
import os
import numpy as np
import matplotlib.pyplot as plt
from tqdm import tqdm
import matplotlib
import logging
from dataclasses import dataclass
from typing import List, Tuple, Optional, Dict, Any
import json
try:
    from .FileManager import FileManager
except:
    from FileManager import FileManager
# 设置matplotlib后端
matplotlib.use("TkAgg")

# 配置日志
logger = logging.getLogger(__name__)

# 搜索方法枚举
class SearchMethod:
    RISING = 1
    MAX = 2

# 校准模式枚举
class CalibrationMode:
    OPEN = "OPEN"
    SHORT = "SHORT" 
    LOAD = "LOAD"
    THRU = "THRU"

@dataclass
class AnalysisConfig:
    """数据分析配置类"""
    input_dir: str = 'data\\results\\test'
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
    search_method: int = SearchMethod.RISING
    roi_start_tenths: int = 0
    roi_end_tenths: int = 100
    roi_mid_tenths: int = 10
    output_csv: str = 'data\\raw\\calibration\\S_data.csv'
    min_edge_amplitude_ratio:float = 0.2
    min_second_rise_ratio: float = 0.1    # 第二个上升沿最小幅度比例
    min_second_fall_ratio: float = 0.1    # 下降沿最小幅度比例
    cal_mode: str = CalibrationMode.LOAD  # 新增CAL_Mode参数
    
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
    def roi_mid(self) -> int:
        return int(self.n_points * self.roi_mid_tenths / 100)
    
    @property
    def l_roi(self) -> int:
        return self.roi_end - self.roi_start

class DataAnalyzer:
    """数据分析器类"""
    
    def __init__(self, config: AnalysisConfig, file_manager=None):
        self.config = config
        self.file_manager = file_manager or FileManager()
        self.validate_config()
        
    def validate_config(self):
        """验证配置参数"""
        # 修改这里：使用正确的属性名
        # if self.config.roi_start_tenths <= self.config.diff_points:
        #     raise ValueError("ROI起始位置必须大于差分点数")

        valid_modes = [CalibrationMode.OPEN, CalibrationMode.SHORT, CalibrationMode.LOAD, CalibrationMode.THRU]
        if self.config.cal_mode not in valid_modes:
            raise ValueError(f"无效的校准模式: {self.config.cal_mode}。"f"有效模式: {valid_modes}")
        
        if self.config.roi_start_tenths >= self.config.roi_end_tenths:
            raise ValueError("ROI起始位置必须小于结束位置")
        
        if self.config.roi_end_tenths > 100:
            raise ValueError("ROI结束位置不能超过100%")
    
    def load_u32_data(self, path: str) -> np.ndarray:
        """从文件加载uint32数据"""
        return self.file_manager.load_u32_text_first_col(path, skip_first=self.config.skip_first_value)
    
    def extract_adc_data(self, u32_arr: np.ndarray, use_signed18: bool = True) -> Tuple[np.ndarray, np.ndarray]:
        """
        从uint32数组中提取bit31和ADC数据
        
        Args:
            u32_arr: uint32数据数组
            use_signed18: 是否使用18位有符号转换
            
        Returns:
            bit31数组和ADC数据数组
        """
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
    
    def detect_valid_data(self,bit31: np.ndarray, edge_search_start: int = 1) -> Optional[int]:
        """
        检测bit31数组中的上升沿位置
        
        Args:
            bit31: bit31数据数组
            edge_search_start: 搜索起始位置
            
        Returns:
            上升沿位置索引或None
        """
        # 检测上升沿 (0->1转换)
        edge_idx = np.flatnonzero((bit31[1:] == 1) & (bit31[:-1] == 0))
        # 过滤起始位置
        edge_idx = edge_idx[edge_idx >= edge_search_start]
        
        if edge_idx.size == 0:
            logger.warning("未找到上升沿")
            return None
        
        return edge_idx[0] + 1  # 返回上升沿位置
    

    def extract_data_segment(self,adc_data: np.ndarray, rise_idx: int, start_index: int, n_points: int) -> Optional[np.ndarray]:
        """
        从ADC数据中截取指定长度的数据段
        
        Args:
            adc_data: ADC数据数组
            rise_idx: 上升沿位置
            start_index: 起始偏移
            n_points: 数据点数
            
        Returns:
            截取的数据段或None
        """
        start_capture = rise_idx + start_index
        
        # 检查数据长度是否足够
        if start_capture + n_points > adc_data.size:
            logger.warning("数据长度不足")
            return None
        
        # 截取数据段
        return adc_data[start_capture : start_capture + n_points]
    
    def sort_data_by_period(self,segment_data: np.ndarray, t_sample: float, t_trig: float) -> Tuple[np.ndarray, np.ndarray]:
        """
        按周期时间对数据进行排序
        
        Args:
            segment_data: 数据段
            t_sample: 采样时间
            t_trig: 触发周期
            
        Returns:
            排序后的数据和排序索引
        """
        # 计算周期内时间
        t_within_period = (np.arange(len(segment_data), dtype=np.float64) * t_sample) % t_trig
        
        # 按时间排序
        sort_idx = np.argsort(t_within_period)
        sorted_data = segment_data[sort_idx]
        
        return sorted_data, sort_idx
    
    def find_rise_position(self, sorted_data: np.ndarray, search_method: int, 
                        adc_full_mean: Optional[float] = None,
                        min_edge_amplitude_ratio: float = 0.3) -> int:
        """
        在排序后的数据中搜索上升沿位置
        """
        # 计算信号的整体峰峰值
        signal_p2p = np.max(sorted_data) - np.min(sorted_data)
        
        if search_method == SearchMethod.RISING:
            if adc_full_mean is None:
                adc_full_mean = np.mean(sorted_data)
            
            # 寻找满足基本条件的候选点
            basic_candidates = np.flatnonzero(
                (sorted_data[10:] > adc_full_mean) & 
                (sorted_data[:-10] <= adc_full_mean)
            ) + 10  # 补偿偏移
            
            # 筛选幅度比例满足条件的候选点
            valid_candidates = []
            for candidate in basic_candidates:
                if candidate >= 10:  # 确保有足够的点计算基线
                    baseline = np.mean(sorted_data[candidate-10:candidate])
                    edge_amplitude = sorted_data[candidate] - baseline
                    
                    if edge_amplitude >= min_edge_amplitude_ratio * signal_p2p:
                        valid_candidates.append((candidate, edge_amplitude))
            
            if valid_candidates:
                # 选择幅度最大的候选点
                valid_candidates.sort(key=lambda x: x[1], reverse=True)
                return valid_candidates[0][0]
            else:
                # 回退到差分方法
                dy = np.diff(sorted_data)
                max_dy_idx = np.argmax(dy)
                return max_dy_idx + 1
        else:
            # 最大值方法
            max_pos = np.argmax(sorted_data)
            return max_pos

    def find_second_rise_position(self, sorted_data: np.ndarray, first_rise_pos: int, 
                                min_second_rise_ratio: float = 0.1) -> Optional[int]:
        """
        查找第二个上升沿位置，基于第一个上升沿的高电平作为起始电平
        
        Args:
            sorted_data: 排序后的数据
            first_rise_pos: 第一个上升沿位置
            min_second_rise_ratio: 第二个上升沿最小幅度与第一个上升沿幅度的比例
            
        Returns:
            第二个上升沿位置索引，如果未找到则返回None
        """
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
        search_start = first_peak_pos + 50  # 避免检测到同一个上升沿
        search_end = int(len(sorted_data) * 0.5)  # 只搜索前80%的数据
        
        second_rise_candidates = []
        
        for i in range(search_start, search_end):
            # 检查是否从高电平开始新的上升
            # 当前点应该接近起始电平，然后开始上升
            if (abs(sorted_data[i] - start_level) < first_rise_amplitude * 0.2 and  # 接近起始电平
                sorted_data[i + 1] > sorted_data[i] + min_second_amplitude * 0.3):  # 开始显著上升
                
                # 寻找上升沿的峰值
                for j in range(i + 1, min(i + 100, len(sorted_data))):
                    if sorted_data[j] < sorted_data[j - 1]:  # 开始下降，找到峰值
                        peak_pos = j - 1
                        peak_val = sorted_data[peak_pos]
                        
                        # 计算上升沿幅度（从起始电平到峰值）
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
        """
        查找下降沿位置，基于第一个上升沿稳定后的高电平作为起始电平
        """
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
        
        # 找到第一个上升沿稳定后的高电平（去掉过冲）
        stable_search_start = peak_pos + 20  # 跳过过冲区域
        stable_search_end = min(stable_search_start + 50, len(sorted_data))
        
        # 计算稳定后的高电平（取稳定区域的均值）
        stable_high_level = np.mean(sorted_data[stable_search_start:stable_search_end])
        
        # 使用稳定后的高电平作为下降沿的起始电平
        start_level = stable_high_level
        
        # 在稳定区域之后搜索下降沿
        search_start = stable_search_end + 10
        search_end = int(len(sorted_data) * 0.5)
        
        fall_candidates = []
        
        for i in range(search_start, search_end):
            # 检查是否从稳定高电平开始下降
            current_val = sorted_data[i]
            next_val = sorted_data[i + 1] if i + 1 < len(sorted_data) else current_val
            
            if (abs(current_val - start_level) < rise_amplitude * 0.15 and  # 接近稳定电平
                next_val < current_val - min_fall_amplitude * 0.4):  # 开始显著下降
                
                # 寻找下降沿的谷值
                valley_found = False
                for j in range(i + 2, min(i + 150, len(sorted_data))):
                    if j + 1 >= len(sorted_data):
                        break
                        
                    # 检测谷值：当前点比前一点低，但比后一点高
                    if (sorted_data[j] < sorted_data[j - 1] and 
                        sorted_data[j] < sorted_data[j + 1]):
                        valley_pos = j
                        valley_val = sorted_data[valley_pos]
                        
                        # 计算下降沿幅度（从稳定电平到谷值）
                        fall_amplitude = start_level - valley_val
                        
                        if fall_amplitude >= min_fall_amplitude:
                            fall_candidates.append(valley_pos)
                        valley_found = True
                        break
                
                if valley_found:
                    continue
        
        if fall_candidates:
            # 选择距离上升沿最近的候选点
            distances = [abs(candidate - rise_pos) for candidate in fall_candidates]
            closest_idx = np.argmin(distances)
            return fall_candidates[closest_idx]
        
        return None

    def align_data(self,sorted_data: np.ndarray, rise_pos: int, target_position: int) -> np.ndarray:
        """
        对齐数据，使上升沿位于目标位置
        
        Args:
            sorted_data: 排序后的数据
            rise_pos: 上升沿当前位置
            target_position: 目标位置
            
        Returns:
            对齐后的数据
        """
        shift = (target_position - rise_pos) % len(sorted_data)
        return np.roll(sorted_data, shift)
    
    def extract_roi(self,aligned_data: np.ndarray, roi_start: int, roi_end: int) -> np.ndarray:
        """
        从对齐后的数据中提取感兴趣区域(ROI)
        
        Args:
            aligned_data: 对齐后的数据
            roi_start: ROI起始索引
            roi_end: ROI结束索引
            
        Returns:
            ROI数据
        """
        return aligned_data[roi_start:roi_end]
    

    def compute_spectrum(self,data: np.ndarray, ts_eff: float) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        """
        计算数据的频谱
        
        Args:
            data: 输入数据
            ts_eff: 有效采样时间
            
        Returns:
            频率数组、幅度谱(线性)、复数FFT结果
        """
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

    def compute_difference(self,data: np.ndarray, diff_points: int) -> np.ndarray:
        """
        计算数据的差分
        
        Args:
            data: 输入数据
            diff_points: 差分点数
            
        Returns:
            差分数据
        """
        return data[diff_points:] - data[:-diff_points]
    
    def extract_basic_segment(self, u32_arr: np.ndarray) -> Optional[Tuple[np.ndarray, np.ndarray, np.ndarray]]:
        """
        提取基本数据段（步骤1-7）
        
        Args:
            u32_arr: uint32数据数组
            
        Returns:
            (adc_full, y_roi, adc_full_mean) 或 None
        """
        try:
            # 1. 提取ADC数据
            bit31, adc_full = self.extract_adc_data(u32_arr, self.config.use_signed18)
            
            # 2. 检测有效数据
            rise_idx = self.detect_valid_data(bit31, self.config.edge_search_start)
            if rise_idx is None:
                return None
            
            # 3. 截取数据段
            segment_adc = self.extract_data_segment(
                adc_full, rise_idx, self.config.start_index, self.config.n_points
            )
            if segment_adc is None:
                return None
            
            # 4. 按周期排序
            y_sorted, _ = self.sort_data_by_period(
                segment_adc, self.config.t_sample, self.config.t_trig
            )
            
            # 5. 搜索上升沿位置
            rise_pos = self.find_rise_position(
                y_sorted, self.config.search_method, np.mean(adc_full), self.config.min_edge_amplitude_ratio
            )
            
            # 6. 数据对齐
            target_idx = self.config.n_points // 4
            y_full = self.align_data(y_sorted, rise_pos, target_idx)
            
            # 7. 提取ROI
            y_roi = self.extract_roi(y_full, self.config.roi_start, self.config.roi_end)
            
            return adc_full, y_roi, np.mean(adc_full)
            
        except Exception as e:
            logger.error(f"提取基本数据段时出错: {e}")
            return None

    def process_thru_load_mode(self, y_roi: np.ndarray) -> Optional[Tuple]:
        """
        处理THRU和LOAD模式的数据（步骤8-10）
        
        Args:
            y_roi: ROI数据
            
        Returns:
            处理结果元组或None
        """
        try:
            # 8. ROI频谱分析
            freq, mag_linear, _ = self.compute_spectrum(y_roi, self.config.ts_eff)
            
            # 9. 差分处理
            if self.config.l_roi <= self.config.diff_points:
                return None
                
            y_diff = self.compute_difference(y_roi, self.config.diff_points)
            
            # 10. 差分频谱分析
            freq_d, mag_linear_d, Xd_norm = self.compute_spectrum(y_diff, self.config.ts_eff)
            
            return y_roi, freq, mag_linear, y_diff, freq_d, mag_linear_d, Xd_norm
            
        except Exception as e:
            logger.error(f"处理THRU/LOAD模式时出错: {e}")
            return None

    def process_short_mode(self, y_roi: np.ndarray, adc_full_mean: float) -> Optional[Tuple]:
        """
        处理SHORT模式的数据
        
        Args:
            y_roi: ROI数据
            adc_full_mean: 完整数据的平均值
            
        Returns:
            处理结果元组或None
        """
        try:
            # SHORT模式特殊处理：使用差分后的数据进行频谱分析
            if self.config.l_roi <= self.config.diff_points:
                return None
                
            # 先进行差分处理
            y_diff = self.compute_difference(y_roi, self.config.diff_points)
            
            # 对差分数据进行频谱分析
            freq_d, mag_linear_d, Xd_norm = self.compute_spectrum(y_diff, self.config.ts_eff)
            
            # 对原始ROI数据也进行频谱分析（可选）
            freq, mag_linear, _ = self.compute_spectrum(y_roi, self.config.ts_eff)
            
            return y_roi, freq, mag_linear, y_diff, freq_d, mag_linear_d, Xd_norm
            
        except Exception as e:
            logger.error(f"处理SHORT模式时出错: {e}")
            return None

    def process_open_mode(self, y_roi: np.ndarray, adc_full_mean: float) -> Optional[Tuple]:
        """
        处理OPEN模式的数据
        
        Args:
            y_roi: ROI数据
            adc_full_mean: 完整数据的平均值
            
        Returns:
            处理结果元组或None
        """
        try:
            # OPEN模式特殊处理：可能需要不同的窗口函数或预处理
            # 去均值处理
            y_roi_centered = y_roi.astype(np.float64) - np.mean(y_roi)
            
            # 使用不同的窗口函数（Blackman窗）
            window = np.blackman(len(y_roi_centered))
            windowed_data = y_roi_centered * window
            
            # 计算FFT
            fft_result = np.fft.rfft(windowed_data)
            freq = np.fft.rfftfreq(len(y_roi_centered), d=self.config.ts_eff)
            
            # 归一化
            scale = (np.sum(window) / len(y_roi_centered)) * len(y_roi_centered)
            magnitude_linear = np.abs(fft_result) / (scale + 1e-12)
            
            # 差分处理
            if self.config.l_roi <= self.config.diff_points:
                return None
                
            y_diff = self.compute_difference(y_roi, self.config.diff_points)
            
            # 差分频谱分析
            freq_d, mag_linear_d, Xd_norm = self.compute_spectrum(y_diff, self.config.ts_eff)
            
            return y_roi, freq, magnitude_linear, y_diff, freq_d, mag_linear_d, Xd_norm
            
        except Exception as e:
            logger.error(f"处理OPEN模式时出错: {e}")
            return None

    def process_single_file(self, u32_arr: np.ndarray) -> Optional[Tuple]:
        """
        重构后的处理单个文件的方法
        
        Args:
            u32_arr: uint32数据数组
            
        Returns:
            处理结果元组或None
        """
        try:
            # 提取基本数据段（步骤1-7）
            basic_result = self.extract_basic_segment(u32_arr)
            if basic_result is None:
                return None
                
            adc_full, y_roi, adc_full_mean = basic_result
            
            # 根据校准模式选择不同的处理方法
            if self.config.cal_mode in [CalibrationMode.THRU, CalibrationMode.LOAD]:
                # THRU和LOAD模式使用标准处理
                return self.process_thru_load_mode(y_roi)
                
            elif self.config.cal_mode == CalibrationMode.SHORT:
                # SHORT模式特殊处理
                return self.process_short_mode(y_roi, adc_full_mean)
                
            elif self.config.cal_mode == CalibrationMode.OPEN:
                # OPEN模式特殊处理
                return self.process_open_mode(y_roi, adc_full_mean)
                
            else:
                logger.error(f"未知的校准模式: {self.config.cal_mode}")
                return None
                
        except Exception as e:
            logger.error(f"处理文件时出错: {e}")
            return None


    def batch_process_files(self, file_list: List[str]) -> Dict[str, Any]:
        """
        批量处理文件列表
        
        Args:
            file_list: 要处理的文件路径列表
            
        Returns:
            处理结果字典
        """
        logger.info(f"开始处理 {len(file_list)} 个文件")
        
        # 初始化结果存储
        results = {
            'ys': [], 'mags': [], 'ys_d': [], 'mags_d': [],
            'freq_ref': None, 'freq_d_ref': None, 'sum_Xd': None,
            'success_count': 0, 'total_files': len(file_list)
        }
        
        # 处理每个文件
        for f in tqdm(file_list, desc="处理文件", unit="file"):
            try:
                raw = self.load_u32_data(f)
                res = self.process_single_file(raw)
                
                if res is None:
                    continue
                    
                y_roi, freq, mag_linear, y_diff, freq_d, mag_linear_d, Xd_norm = res
                
                # 初始化参考频率
                if results['freq_ref'] is None:
                    results['freq_ref'] = freq
                if results['freq_d_ref'] is None:
                    results['freq_d_ref'] = freq_d
                    results['sum_Xd'] = np.zeros_like(Xd_norm, dtype=np.complex128)
                
                # 存储结果
                results['ys'].append(y_roi.astype(np.float64))
                results['mags'].append(mag_linear.astype(np.float64))
                results['ys_d'].append(y_diff.astype(np.float64))
                results['mags_d'].append(mag_linear_d.astype(np.float64))
                results['sum_Xd'] += Xd_norm
                results['success_count'] += 1
                
            except Exception as e:
                logger.warning(f"处理文件 {f} 失败: {e}")
                continue
        
        if results['success_count'] == 0:
            raise RuntimeError("没有文件成功处理")
        
        logger.info(f"成功处理 {results['success_count']}/{len(file_list)} 个文件")
        return results
    
    def calculate_averages(self, results: Dict[str, Any]) -> Dict[str, Any]:
        """计算平均值"""
        averages = {}
        
        # ROI平均值
        averages['y_avg'] = np.mean(np.vstack(results['ys']), axis=0)
        averages['mag_avg_linear'] = np.mean(np.vstack(results['mags']), axis=0)
        averages['mag_avg_db'] = 20 * np.log10(averages['mag_avg_linear'])
        
        # 差分平均值
        averages['y_d_avg'] = np.mean(np.vstack(results['ys_d']), axis=0)
        averages['mag_d_avg_linear'] = np.mean(np.vstack(results['mags_d']), axis=0)
        averages['mag_d_avg_db'] = 20 * np.log10(averages['mag_d_avg_linear'])
        
        # 复数FFT平均值
        averages['avg_Xd'] = results['sum_Xd'] / results['success_count']
        
        return averages
    
    def plot_results(self, results: Dict[str, Any], averages: Dict[str, Any]):
        """绘制结果图表，包含边沿检测标记和中点标记"""
        # 时间轴
        t_roi_us = (np.arange(self.config.l_roi) * self.config.ts_eff) * 1e6
        t_diff_us = t_roi_us[self.config.diff_points:]
        
        # 频率掩码
        mask = results['freq_ref'] <= (self.config.show_up_to_GHz * 1e9)
        maskd = results['freq_d_ref'] <= (self.config.show_up_to_GHz * 1e9)
        
        # 边缘位置
        edge_in_roi = (self.config.n_points // 4 - self.config.roi_start)
        
        # 对平均数据进行边沿分析
        edge_analysis = self.analyze_edges(averages['y_avg'])
        
        # 原始ROI图 - 添加校准模式到标题
        fig, (ax_t, ax_f) = plt.subplots(2, 1, figsize=(16, 12))
        
        # 绘制时域信号
        ax_t.plot(t_roi_us, averages['y_avg'], label='Average Signal', linewidth=2, color='blue')
        
        # 标记第一个上升沿
        if edge_analysis['first_rise_pos'] is not None:
            first_rise_time = t_roi_us[edge_analysis['first_rise_pos']]
            ax_t.axvline(first_rise_time, linestyle='-', linewidth=2, 
                        color='red', alpha=0.8, label='First Rise Edge')
            
            # 在图上添加文本标注
            ax_t.text(first_rise_time, np.max(averages['y_avg']) * 0.9, 
                    f'1st Rise\n{first_rise_time:.2f}μs', 
                    ha='center', va='top', fontsize=9, color='red',
                    bbox=dict(boxstyle="round,pad=0.3", facecolor="yellow", alpha=0.7))
        
        # 标记第二个上升沿
        if edge_analysis['second_rise_pos'] is not None:
            second_rise_time = t_roi_us[edge_analysis['second_rise_pos']]
            ax_t.axvline(second_rise_time, linestyle='--', linewidth=2, 
                        color='green', alpha=0.8, label='Second Rise Edge')
            
            # 计算并显示幅度比例
            rise_ratio = edge_analysis.get('rise_ratio', 0)
            ax_t.text(second_rise_time, np.max(averages['y_avg']) * 0.8, 
                    f'2nd Rise\n{second_rise_time:.2f}μs\nRatio: {rise_ratio:.2f}', 
                    ha='center', va='top', fontsize=9, color='green',
                    bbox=dict(boxstyle="round,pad=0.3", facecolor="lightgreen", alpha=0.7))
            
            # 标记第一个和第二个上升沿的中点
            if 'rise_midpoint_time' in edge_analysis:
                rise_midpoint_time = edge_analysis['rise_midpoint_time']
                ax_t.axvline(rise_midpoint_time, linestyle='-', linewidth=1.5, 
                            color='cyan', alpha=0.7, label='Rise Midpoint')
                ax_t.text(rise_midpoint_time, np.max(averages['y_avg']) * 0.6, 
                        f'Rise Mid\n{rise_midpoint_time:.2f}μs', 
                        ha='center', va='top', fontsize=8, color='cyan',
                        bbox=dict(boxstyle="round,pad=0.2", facecolor="lightcyan", alpha=0.7))
        
        # 标记下降沿
        if edge_analysis['fall_pos'] is not None:
            fall_time = t_roi_us[edge_analysis['fall_pos']]
            ax_t.axvline(fall_time, linestyle=':', linewidth=2, 
                        color='purple', alpha=0.8, label='Fall Edge')
            
            # 计算并显示下降幅度比例
            fall_ratio = edge_analysis.get('fall_ratio', 0)
            ax_t.text(fall_time, np.max(averages['y_avg']) * 0.7, 
                    f'Fall\n{fall_time:.2f}μs\nRatio: {fall_ratio:.2f}', 
                    ha='center', va='top', fontsize=9, color='purple',
                    bbox=dict(boxstyle="round,pad=0.3", facecolor="lavender", alpha=0.7))
            
            # 标记第一个上升沿和下降沿的中点
            if 'fall_midpoint_time' in edge_analysis:
                fall_midpoint_time = edge_analysis['fall_midpoint_time']
                ax_t.axvline(fall_midpoint_time, linestyle='-', linewidth=1.5, 
                            color='magenta', alpha=0.7, label='Fall Midpoint')
                ax_t.text(fall_midpoint_time, np.max(averages['y_avg']) * 0.5, 
                        f'Fall Mid\n{fall_midpoint_time:.2f}μs', 
                        ha='center', va='top', fontsize=8, color='magenta',
                        bbox=dict(boxstyle="round,pad=0.2", facecolor="lightpink", alpha=0.7))
            
            # 标记第二个上升沿和下降沿的中点（如果存在）
            if 'second_fall_midpoint_time' in edge_analysis:
                second_fall_midpoint_time = edge_analysis['second_fall_midpoint_time']
                ax_t.axvline(second_fall_midpoint_time, linestyle='-', linewidth=1.5, 
                            color='orange', alpha=0.7, label='2nd Rise-Fall Midpoint')
                ax_t.text(second_fall_midpoint_time, np.max(averages['y_avg']) * 0.4, 
                        f'2nd Mid\n{second_fall_midpoint_time:.2f}μs', 
                        ha='center', va='top', fontsize=8, color='orange',
                        bbox=dict(boxstyle="round,pad=0.2", facecolor="wheat", alpha=0.7))
        
        # 标记原始边缘位置
        if 0 <= edge_in_roi < self.config.l_roi:
            ax_t.axvline(t_roi_us[edge_in_roi], linestyle="-.", linewidth=1.5, 
                        color='gray', alpha=0.6, label='Original Edge')
        
        ax_t.set_title(f"{self.config.cal_mode} - Average Time-Domain ROI with Edge Detection\n"
                    f"(across {results['success_count']} files)")
        ax_t.set_xlabel('Time (μs)')
        ax_t.set_ylabel('Amplitude')
        ax_t.legend(loc='upper right')
        ax_t.grid(True, alpha=0.3)
        
        # 频谱图
        ax_f.plot(results['freq_ref'][mask]/1e9, averages['mag_avg_db'][mask], 
                linewidth=2, color='blue')
        ax_f.set_title(f"{self.config.cal_mode} - Average Spectrum ROI")
        ax_f.set_xlabel('Frequency (GHz)')
        ax_f.set_ylabel('Magnitude (dB)')
        ax_f.grid(True, alpha=0.3)
        
        plt.tight_layout()
        plt.show()
        
        # 差分ROI图（也添加中点标记）
        fig2, (ax_t2, ax_f2) = plt.subplots(2, 1, figsize=(16, 12))
        
        # 绘制差分时域信号
        ax_t2.plot(t_diff_us, averages['y_d_avg'], label='Differenced Signal', 
                linewidth=2, color='darkblue')
        
        # 在差分数据上也标记边沿和中点（需要调整位置）
        if edge_analysis['first_rise_pos'] is not None:
            first_rise_diff_time = t_roi_us[max(edge_analysis['first_rise_pos'] - self.config.diff_points, 0)]
            ax_t2.axvline(first_rise_diff_time, linestyle='-', linewidth=2, 
                        color='red', alpha=0.6, label='First Rise (Diff)')
        
        if edge_analysis['second_rise_pos'] is not None:
            second_rise_diff_time = t_roi_us[max(edge_analysis['second_rise_pos'] - self.config.diff_points, 0)]
            ax_t2.axvline(second_rise_diff_time, linestyle='--', linewidth=2, 
                        color='green', alpha=0.6, label='Second Rise (Diff)')
            
            # 标记中点
            if 'rise_midpoint' in edge_analysis:
                rise_midpoint_diff_time = t_roi_us[max(edge_analysis['rise_midpoint'] - self.config.diff_points, 0)]
                ax_t2.axvline(rise_midpoint_diff_time, linestyle='-', linewidth=1.5, 
                            color='cyan', alpha=0.5, label='Rise Midpoint (Diff)')
        
        if edge_analysis['fall_pos'] is not None:
            fall_diff_time = t_roi_us[max(edge_analysis['fall_pos'] - self.config.diff_points, 0)]
            ax_t2.axvline(fall_diff_time, linestyle=':', linewidth=2, 
                        color='purple', alpha=0.6, label='Fall (Diff)')
            
            # 标记中点
            if 'fall_midpoint' in edge_analysis:
                fall_midpoint_diff_time = t_roi_us[max(edge_analysis['fall_midpoint'] - self.config.diff_points, 0)]
                ax_t2.axvline(fall_midpoint_diff_time, linestyle='-', linewidth=1.5, 
                            color='magenta', alpha=0.5, label='Fall Midpoint (Diff)')
        
        # 标记原始边缘位置
        if (0 <= edge_in_roi < self.config.l_roi and 
            0 <= edge_in_roi - self.config.diff_points < averages['y_d_avg'].size):
            ax_t2.axvline(t_roi_us[max(edge_in_roi - self.config.diff_points, 0)], 
                        linestyle="-.", linewidth=1.5, color='gray', alpha=0.6, 
                        label='Original Edge (Diff)')
        
        ax_t2.set_title(f"{self.config.cal_mode} - Differenced Time-Domain Average with Edge Detection")
        ax_t2.set_xlabel('Time (μs)')
        ax_t2.set_ylabel('Amplitude')
        ax_t2.legend(loc='upper right')
        ax_t2.grid(True, alpha=0.3)
        
        # 差分频谱图
        ax_f2.plot(results['freq_d_ref'][maskd]/1e9, averages['mag_d_avg_db'][maskd], 
                linewidth=2, color='darkblue')
        ax_f2.set_title(f"{self.config.cal_mode} - Differenced Spectrum Average")
        ax_f2.set_xlabel('Frequency (GHz)')
        ax_f2.set_ylabel('Magnitude (dB)')
        ax_f2.grid(True, alpha=0.3)
        
        plt.tight_layout()
        plt.show()
        
        # 打印边沿分析结果（包含中点信息）
        self.print_edge_analysis_results(edge_analysis, t_roi_us)


    def print_edge_analysis_results(self, edge_analysis: Dict[str, Any], t_roi_us: np.ndarray):
        """打印边沿分析结果，包含中点信息"""
        print("\n" + "="*80)
        print("EDGE DETECTION ANALYSIS RESULTS")
        print("="*80)
        
        if edge_analysis['first_rise_pos'] is not None:
            first_rise_time = t_roi_us[edge_analysis['first_rise_pos']]
            first_amplitude = edge_analysis.get('first_rise_amplitude', 0)
            print(f"First Rise Edge: Position={edge_analysis['first_rise_pos']}, "
                f"Time={first_rise_time:.2f}μs, Amplitude={first_amplitude:.1f}")
        
        if edge_analysis['second_rise_pos'] is not None:
            second_rise_time = t_roi_us[edge_analysis['second_rise_pos']]
            second_amplitude = edge_analysis.get('second_rise_amplitude', 0)
            rise_ratio = edge_analysis.get('rise_ratio', 0)
            print(f"Second Rise Edge: Position={edge_analysis['second_rise_pos']}, "
                f"Time={second_rise_time:.2f}μs, Amplitude={second_amplitude:.1f}, "
                f"Ratio={rise_ratio:.3f}")
            
            if 'rise_midpoint' in edge_analysis:
                rise_midpoint_time = edge_analysis.get('rise_midpoint_time', 0)
                print(f"Rise Midpoint: Position={edge_analysis['rise_midpoint']}, "
                    f"Time={rise_midpoint_time:.2f}μs, "
                    f"Distance from 1st: {edge_analysis['rise_midpoint'] - edge_analysis['first_rise_pos']} points")
        
        if edge_analysis['fall_pos'] is not None:
            fall_time = t_roi_us[edge_analysis['fall_pos']]
            fall_amplitude = edge_analysis.get('fall_amplitude', 0)
            fall_ratio = edge_analysis.get('fall_ratio', 0)
            print(f"Fall Edge: Position={edge_analysis['fall_pos']}, "
                f"Time={fall_time:.2f}μs, Amplitude={fall_amplitude:.1f}, "
                f"Ratio={fall_ratio:.3f}")
            
            if 'fall_midpoint' in edge_analysis:
                fall_midpoint_time = edge_analysis.get('fall_midpoint_time', 0)
                print(f"Fall Midpoint: Position={edge_analysis['fall_midpoint']}, "
                    f"Time={fall_midpoint_time:.2f}μs, "
                    f"Distance from 1st: {edge_analysis['fall_midpoint'] - edge_analysis['first_rise_pos']} points")
            
            # 如果同时有第二个上升沿和下降沿，打印它们的中点
            if 'second_fall_midpoint' in edge_analysis:
                second_fall_midpoint_time = edge_analysis.get('second_fall_midpoint_time', 0)
                print(f"2nd Rise-Fall Midpoint: Position={edge_analysis['second_fall_midpoint']}, "
                    f"Time={second_fall_midpoint_time:.2f}μs, "
                    f"Distance from 2nd: {edge_analysis['second_fall_midpoint'] - edge_analysis['second_rise_pos']} points")
        
        # 计算并打印时间间隔信息
        if (edge_analysis['first_rise_pos'] is not None and 
            edge_analysis['second_rise_pos'] is not None):
            rise_interval = edge_analysis['second_rise_pos'] - edge_analysis['first_rise_pos']
            rise_interval_time = rise_interval * self.config.ts_eff * 1e6  # 转换为微秒
            print(f"Rise-Rise Interval: {rise_interval} points, {rise_interval_time:.2f}μs")
        
        if (edge_analysis['first_rise_pos'] is not None and 
            edge_analysis['fall_pos'] is not None):
            rise_fall_interval = edge_analysis['fall_pos'] - edge_analysis['first_rise_pos']
            rise_fall_interval_time = rise_fall_interval * self.config.ts_eff * 1e6
            print(f"Rise-Fall Interval: {rise_fall_interval} points, {rise_fall_interval_time:.2f}μs")
        
        if (edge_analysis['second_rise_pos'] is not None and 
            edge_analysis['fall_pos'] is not None):
            second_rise_fall_interval = edge_analysis['fall_pos'] - edge_analysis['second_rise_pos']
            second_rise_fall_interval_time = second_rise_fall_interval * self.config.ts_eff * 1e6
            print(f"2nd Rise-Fall Interval: {second_rise_fall_interval} points, {second_rise_fall_interval_time:.2f}μs")
        
        # 打印稳定高电平信息
        if 'stable_high_level' in edge_analysis:
            print(f"Stable High Level: {edge_analysis['stable_high_level']:.1f}")
        
        print("="*80)

    def analyze_edges(self, sorted_data: np.ndarray) -> Dict[str, Any]:
        """
        完整的边沿分析流程，返回边沿位置和中点位置
        """
        # 查找第一个上升沿
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
                # 计算第二个上升沿的幅度（使用稳定高电平作为基准）
                second_peak_search_end = min(second_rise_pos + 100, len(sorted_data))
                second_peak_val = np.max(sorted_data[second_rise_pos:second_peak_search_end])
                second_amplitude = second_peak_val - stable_high_level
                result['second_rise_amplitude'] = second_amplitude
                result['rise_ratio'] = second_amplitude / first_amplitude
                
                # 计算第一个和第二个上升沿的中点位置
                rise_midpoint = (first_rise_pos + second_rise_pos) // 2
                result['rise_midpoint'] = rise_midpoint
                result['rise_midpoint_time'] = rise_midpoint * self.config.ts_eff * 1e6  # 转换为微秒
            
            # 查找下降沿
            fall_pos = self.find_second_fall_position(
                sorted_data, first_rise_pos, self.config.min_second_fall_ratio
            )
            result['fall_pos'] = fall_pos
            
            if fall_pos is not None:
                # 计算下降幅度（使用稳定高电平作为基准）
                fall_valley_search_end = min(fall_pos + 50, len(sorted_data))
                fall_valley = np.min(sorted_data[fall_pos:fall_valley_search_end])
                fall_amplitude = stable_high_level - fall_valley
                result['fall_amplitude'] = fall_amplitude
                result['fall_ratio'] = fall_amplitude / first_amplitude
                
                # 计算第一个上升沿和下降沿的中点位置
                fall_midpoint = (first_rise_pos + fall_pos) // 2
                result['fall_midpoint'] = fall_midpoint
                result['fall_midpoint_time'] = fall_midpoint * self.config.ts_eff * 1e6  # 转换为微秒
                
                # 如果同时有第二个上升沿和下降沿，计算它们的中点
                if second_rise_pos is not None:
                    second_fall_midpoint = (second_rise_pos + fall_pos) // 2
                    result['second_fall_midpoint'] = second_fall_midpoint
                    result['second_fall_midpoint_time'] = second_fall_midpoint * self.config.ts_eff * 1e6
        
        return result

    def get_output_filename(self) -> str:
        """
        根据校准模式生成输出文件名
        
        Returns:
            格式化的输出文件名
        """
        base_name = os.path.splitext(self.config.output_csv)[0]
        extension = os.path.splitext(self.config.output_csv)[1]
        
        # 根据校准模式添加后缀
        mode_suffix = f"_{self.config.cal_mode.lower()}"
        return f"{base_name}{mode_suffix}{extension}"
    
    def save_results(self, results: Dict[str, Any], averages: Dict[str, Any]):
        """保存结果到文件"""
        # 根据校准模式生成输出文件名
        output_filename = self.get_output_filename()
        
        # 保存复数FFT结果
        success = self.file_manager.save_complex_fft_results(
            results['freq_d_ref'], 
            np.real(averages['avg_Xd']), 
            np.imag(averages['avg_Xd']), 
            output_filename
        )
        
        if not success:
            logger.error("复数FFT结果保存失败")
        
        # 保存处理统计信息
        stats = {
            'total_files': results['total_files'],
            'successful_files': results['success_count'],
            'success_rate': results['success_count'] / results['total_files'],
            'calibration_mode': self.config.cal_mode,  # 添加校准模式信息
            'config': {
                'input_dir': self.config.input_dir,
                'clock_freq': self.config.clock_freq,
                'trigger_freq': self.config.trigger_freq,
                'n_points': self.config.n_points,
                'roi_range': f"{self.config.roi_start_tenths}%-{self.config.roi_end_tenths}%",
                'cal_mode': self.config.cal_mode  # 添加校准模式到配置
            }
        }
        
        stats_file = os.path.splitext(output_filename)[0] + '_stats.json'
        self.file_manager.save_json_data(stats, stats_file)
        
        logger.info(f"结果已保存到: {output_filename}")
    
    def run_analysis(self):
        """运行完整分析流程"""
        logger.info("开始数据分析...")
        
        files = self.file_manager.find_csv_files(self.config.input_dir, self.config.recursive)
        # 批量处理文件
        results = self.batch_process_files(files)
        
        # 计算平均值
        averages = self.calculate_averages(results)
        
        # 绘制图表（包含边沿检测标记）
        self.plot_results(results, averages)
        
        # 保存结果
        self.save_results(results, averages)
        
        logger.info(f"分析完成! 共处理 {results['success_count']}/{results['total_files']} 个文件")

def main():
    """主函数"""
    # 创建配置
    # config_open = AnalysisConfig(cal_mode=CalibrationMode.OPEN)
    # config_short = AnalysisConfig(cal_mode=CalibrationMode.SHORT)
    config = AnalysisConfig(cal_mode=CalibrationMode.LOAD,input_dir="data\\results\\test\\SHORT")
    # config_thru = AnalysisConfig(cal_mode=CalibrationMode.THRU)
    # config = AnalysisConfig()
    
    try:
        # 创建分析器并运行
        analyzer = DataAnalyzer(config)
        analyzer.run_analysis()
        
    except Exception as e:
        logger.error(f"分析失败: {e}")
        raise

if __name__ == "__main__":
    main()
