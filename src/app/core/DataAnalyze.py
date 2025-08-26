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
    output_csv: str = 'data\\raw\\calibration\\S_data.csv'
    min_edge_amplitude_ratio:float = 0.3
    cal_mode: str = CalibrationMode.SHORT  # 新增CAL_Mode参数
    
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
    
    def detect_rising_edge(self,bit31: np.ndarray, edge_search_start: int = 1) -> Optional[int]:
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
        print(bit31)
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
    
    def find_rise_position(self,sorted_data: np.ndarray, search_method: int, adc_full_mean: Optional[float] = None) -> int:
        """
        在排序后的数据中搜索上升沿位置
        
        Args:
            sorted_data: 排序后的数据
            search_method: 搜索方法 (RISING或MAX)
            adc_full_mean: 完整数据的平均值(可选)
            
        Returns:
            上升沿位置索引
        """
        if search_method == SearchMethod.RISING:
            # 使用平均值方法检测上升沿
            if adc_full_mean is None:
                adc_full_mean = np.mean(sorted_data)
            
            rise_candidates = np.flatnonzero(
                (sorted_data[10:] > adc_full_mean) & (sorted_data[:-10] <= adc_full_mean)
            )
            
            if rise_candidates.size == 0:
                # 使用差分最大值方法
                dy = np.diff(sorted_data.astype(np.float64))
                rise_pos = int(np.argmax(dy)) + 1
            else:
                rise_pos = int(rise_candidates[0])
        else:
            # 使用最大值方法
            rise_pos = int(np.argmax(sorted_data))
        
        return rise_pos

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
    
    def process_single_file(self, u32_arr: np.ndarray) -> Optional[Tuple]:
        """
        重构后的处理单个文件的方法
        
        Args:
            u32_arr: uint32数据数组
            
        Returns:
            处理结果元组或None
        """
        try:
            # 1. 提取ADC数据
            bit31, adc_full = self.extract_adc_data(u32_arr, self.config.use_signed18)
            
            # 2. 检测上升沿
            rise_idx = self.detect_rising_edge(bit31, self.config.edge_search_start)
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
                y_sorted, self.config.search_method, np.mean(adc_full)
            )
            
            # 6. 数据对齐
            target_idx = self.config.n_points // 4
            y_full = self.align_data(y_sorted, rise_pos, target_idx)
            
            # 7. 提取ROI
            y_roi = self.extract_roi(y_full, self.config.roi_start, self.config.roi_end)
            
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
        """绘制结果图表"""
        # 时间轴
        t_roi_us = (np.arange(self.config.l_roi) * self.config.ts_eff) * 1e6
        t_diff_us = t_roi_us[self.config.diff_points:]
        
        # 频率掩码
        mask = results['freq_ref'] <= (self.config.show_up_to_GHz * 1e9)
        maskd = results['freq_d_ref'] <= (self.config.show_up_to_GHz * 1e9)
        
        # 边缘位置
        edge_in_roi = (self.config.n_points // 4 - self.config.roi_start)
        
        # 原始ROI图 - 添加校准模式到标题
        fig, (ax_t, ax_f) = plt.subplots(2, 1, figsize=(12, 8))
        if 0 <= edge_in_roi < self.config.l_roi:
            ax_t.axvline(t_roi_us[edge_in_roi], linestyle="--", linewidth=0.8, 
                        color='red', alpha=0.7, label='Edge Position')
        ax_t.plot(t_roi_us, averages['y_avg'], label='Average Signal')
        ax_t.set_title(f"{self.config.cal_mode} - Average Time-Domain ROI "
                      f"(across {results['success_count']} files)")
        ax_t.set_xlabel('Time (μs)')
        ax_t.set_ylabel('Amplitude')
        ax_t.legend()
        ax_t.grid(True, alpha=0.3)
        
        ax_f.plot(results['freq_ref'][mask]/1e9, averages['mag_avg_db'][mask])
        ax_f.set_title(f"{self.config.cal_mode} - Average Spectrum ROI")
        ax_f.set_xlabel('Frequency (GHz)')
        ax_f.set_ylabel('Magnitude (dB)')
        ax_f.grid(True, alpha=0.3)
        
        plt.tight_layout()
        plt.show()
        
        # 差分ROI图 - 添加校准模式到标题
        fig2, (ax_t2, ax_f2) = plt.subplots(2, 1, figsize=(12, 8))
        if (0 <= edge_in_roi < self.config.l_roi and 
            0 <= edge_in_roi - self.config.diff_points < averages['y_d_avg'].size):
            ax_t2.axvline(t_roi_us[max(edge_in_roi - self.config.diff_points, 0)], 
                         linestyle="--", linewidth=0.8, color='red', alpha=0.7, 
                         label='Edge Position')
        ax_t2.plot(t_diff_us, averages['y_d_avg'], label='Differenced Signal')
        ax_t2.set_title(f"{self.config.cal_mode} - Differenced Time-Domain Average")
        ax_t2.set_xlabel('Time (μs)')
        ax_t2.set_ylabel('Amplitude')
        ax_t2.legend()
        ax_t2.grid(True, alpha=0.3)
        
        ax_f2.plot(results['freq_d_ref'][maskd]/1e9, averages['mag_d_avg_db'][maskd])
        ax_f2.set_title(f"{self.config.cal_mode} - Differenced Spectrum Average")
        ax_f2.set_xlabel('Frequency (GHz)')
        ax_f2.set_ylabel('Magnitude (dB)')
        ax_f2.grid(True, alpha=0.3)
        
        plt.tight_layout()
        plt.show()


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
        
        # 绘制图表
        self.plot_results(results, averages)
        
        # 保存结果
        self.save_results(results, averages)
        
        logger.info(f"分析完成! 共处理 {results['success_count']}/{results['total_files']} 个文件")

def main():
    """主函数"""
    # 创建配置
    # config_open = AnalysisConfig(cal_mode=CalibrationMode.OPEN)
    # config_short = AnalysisConfig(cal_mode=CalibrationMode.SHORT)
    config = AnalysisConfig(cal_mode=CalibrationMode.LOAD,input_dir="data\\results\\test\\OPEN")
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
