import os
import re
import glob
import numpy as np
import matplotlib.pyplot as plt
from tqdm import tqdm
import matplotlib
import logging
from dataclasses import dataclass
from typing import List, Tuple, Optional, Dict, Any
import json

# 设置matplotlib后端
matplotlib.use("TkAgg")

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# 搜索方法枚举
class SearchMethod:
    RISING = 1
    MAX = 2

@dataclass
class AnalysisConfig:
    """数据分析配置类"""
    input_dir: str = 'D:\\Work\\TDR_CAL_DEMO\\CSV_Data_test_results'
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
    roi_start_tenths: int = 20
    roi_end_tenths: int = 30
    output_csv: str = 'Cable_S23.csv'
    
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
    
    def __init__(self, config: AnalysisConfig):
        self.config = config
        self.validate_config()
        
    def validate_config(self):
        """验证配置参数"""
        if self.config.l_roi <= self.config.diff_points:
            raise ValueError(f"截取长度 L_roi={self.config.l_roi} 必须大于 diff_points={self.config.diff_points}")
        
        if not os.path.exists(self.config.input_dir):
            raise FileNotFoundError(f"输入目录不存在: {self.config.input_dir}")
    
    @staticmethod
    def load_u32_text_first_col(path: str, skip_first: bool = True) -> np.ndarray:
        """
        从文本文件加载uint32数据
        
        Args:
            path: 文件路径
            skip_first: 是否跳过第一行
            
        Returns:
            uint32数组
        """
        encodings = ["utf-8", "utf-8-sig", "gbk", "latin1", "utf-16", "utf-16le", "utf-16be"]
        last_err = None
        
        for enc in encodings:
            try:
                vals = []
                with open(path, "r", encoding=enc, errors="strict") as f:
                    for line in f:
                        s = line.strip()
                        if not s:
                            continue
                        # 使用正则表达式匹配十六进制或十进制数字
                        m = re.search(r'(0x[0-9a-fA-F]+|\d+)', s)
                        if not m:
                            continue
                        vals.append(np.uint32(int(m.group(1), 0)))
                
                arr = np.asarray(vals, dtype=np.uint32)
                if skip_first and arr.size >= 1:
                    arr = arr[1:]
                return arr
                
            except Exception as e:
                last_err = e
                continue
        
        raise last_err or Exception("无法读取文件")
    
    def process_single_file(self, u32_arr: np.ndarray) -> Optional[Tuple]:
        """
        处理单个文件的数据
        
        Args:
            u32_arr: uint32数据数组
            
        Returns:
            处理结果元组或None
        """
        try:
            # 提取bit31和ADC数据
            bit31 = ((u32_arr >> 31) & 0x1).astype(np.uint8)
            adc_18u = (u32_arr & ((1 << 20) - 1)).astype(np.uint32)
            
            # 转换为有符号或无符号
            if self.config.use_signed18:
                adc_18s = ((adc_18u + (1 << 19)) & ((1 << 20) - 1)) - (1 << 19)
                adc_full = adc_18s.astype(np.int32)
            else:
                adc_full = adc_18u.astype(np.int32)
            
            # 检测上升沿
            edge_idx = np.flatnonzero((bit31[1:] == 1) & (bit31[:-1] == 0))
            edge_idx = edge_idx[edge_idx >= self.config.edge_search_start]
            if edge_idx.size == 0:
                logger.warning("未找到上升沿")
                return None
            
            rise_idx = edge_idx[0] + 1
            start_capture = rise_idx + self.config.start_index
            
            # 检查数据长度
            if start_capture + self.config.n_points > u32_arr.size:
                logger.warning("数据长度不足")
                return None
            
            # 截取数据段
            segment_adc = adc_full[start_capture : start_capture + self.config.n_points]
            
            # 按周期时间排序
            t_within_period = (np.arange(self.config.n_points, dtype=np.float64) * self.config.t_sample) % self.config.t_trig
            sort_idx = np.argsort(t_within_period)
            y_sorted = segment_adc[sort_idx]
            
            # 搜索上升沿位置
            if self.config.search_method == SearchMethod.RISING:
                adc_full_mean = np.mean(adc_full)
                rise_candidates = np.flatnonzero((y_sorted[10:] > adc_full_mean) & (y_sorted[:-10] <= adc_full_mean))
                if rise_candidates.size == 0:
                    dy = np.diff(y_sorted.astype(np.float64))
                    rise_pos = int(np.argmax(dy)) + 1
                else:
                    rise_pos = int(rise_candidates[0])
            else:
                rise_pos = int(np.argmax(y_sorted))
            
            # 对齐数据
            target_idx = self.config.n_points // 4
            shift = (target_idx - rise_pos) % self.config.n_points
            y_full = np.roll(y_sorted, shift)
            
            # 提取ROI
            y_roi = y_full[self.config.roi_start:self.config.roi_end]
            
            # ROI频谱分析
            y0 = y_roi.astype(np.float64)
            y0 -= np.mean(y0)
            win0 = np.hanning(self.config.l_roi)
            X0 = np.fft.rfft(y0 * win0)
            freq = np.fft.rfftfreq(self.config.l_roi, d=self.config.ts_eff)
            scale0 = (np.sum(win0) / self.config.l_roi) * self.config.l_roi
            mag_linear = np.abs(X0) / (scale0 + 1e-12)
            
            # 差分处理
            if self.config.l_roi <= self.config.diff_points:
                return None
                
            y_diff = y_roi[self.config.diff_points:] - y_roi[:-self.config.diff_points]
            nd = y_diff.size
            y_d = y_diff.astype(np.float64)
            y_d -= np.mean(y_d)
            win_d = np.hanning(nd)
            Xd = np.fft.rfft(y_d * win_d)
            freq_d = np.fft.rfftfreq(nd, d=self.config.ts_eff)
            scale_d = (np.sum(win_d) / nd) * nd
            Xd_norm = Xd / (scale_d + 1e-12)
            mag_linear_d = np.abs(Xd_norm)
            
            return y_roi, freq, mag_linear, y_diff, freq_d, mag_linear_d, Xd_norm
            
        except Exception as e:
            logger.error(f"处理文件时出错: {e}")
            return None
    
    def batch_process_files(self) -> Dict[str, Any]:
        """
        批量处理文件
        
        Returns:
            处理结果字典
        """
        # 查找文件
        pattern = os.path.join(self.config.input_dir, "**", "*.csv") if self.config.recursive else os.path.join(self.config.input_dir, "*.csv")
        files = sorted(glob.glob(pattern, recursive=self.config.recursive))
        
        if not files:
            raise FileNotFoundError(f"未找到csv文件: {pattern}")
        
        logger.info(f"找到 {len(files)} 个文件")
        
        # 初始化结果存储
        results = {
            'ys': [], 'mags': [], 'ys_d': [], 'mags_d': [],
            'freq_ref': None, 'freq_d_ref': None, 'sum_Xd': None,
            'success_count': 0, 'total_files': len(files)
        }
        
        # 处理每个文件
        for f in tqdm(files, desc="处理文件", unit="file"):
            try:
                raw = self.load_u32_text_first_col(f, skip_first=self.config.skip_first_value)
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
        
        logger.info(f"成功处理 {results['success_count']}/{len(files)} 个文件")
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
        
        # 原始ROI图
        fig, (ax_t, ax_f) = plt.subplots(2, 1, figsize=(12, 8))
        if 0 <= edge_in_roi < self.config.l_roi:
            ax_t.axvline(t_roi_us[edge_in_roi], linestyle="--", linewidth=0.8, color='red', alpha=0.7, label='Edge Position')
        ax_t.plot(t_roi_us, averages['y_avg'], label='Average Signal')
        ax_t.set_title(f"Average Time-Domain ROI (across {results['success_count']} files)")
        ax_t.set_xlabel('Time (μs)')
        ax_t.set_ylabel('Amplitude')
        ax_t.legend()
        ax_t.grid(True, alpha=0.3)
        
        ax_f.plot(results['freq_ref'][mask]/1e9, averages['mag_avg_db'][mask])
        ax_f.set_title("Average Spectrum ROI")
        ax_f.set_xlabel('Frequency (GHz)')
        ax_f.set_ylabel('Magnitude (dB)')
        ax_f.grid(True, alpha=0.3)
        
        plt.tight_layout()
        plt.show()
        
        # 差分ROI图
        fig2, (ax_t2, ax_f2) = plt.subplots(2, 1, figsize=(12, 8))
        if (0 <= edge_in_roi < self.config.l_roi and 
            0 <= edge_in_roi - self.config.diff_points < averages['y_d_avg'].size):
            ax_t2.axvline(t_roi_us[max(edge_in_roi - self.config.diff_points, 0)], 
                         linestyle="--", linewidth=0.8, color='red', alpha=0.7, label='Edge Position')
        ax_t2.plot(t_diff_us, averages['y_d_avg'], label='Differenced Signal')
        ax_t2.set_title("Differenced Time-Domain Average")
        ax_t2.set_xlabel('Time (μs)')
        ax_t2.set_ylabel('Amplitude')
        ax_t2.legend()
        ax_t2.grid(True, alpha=0.3)
        
        ax_f2.plot(results['freq_d_ref'][maskd]/1e9, averages['mag_d_avg_db'][maskd])
        ax_f2.set_title("Differenced Spectrum Average")
        ax_f2.set_xlabel('Frequency (GHz)')
        ax_f2.set_ylabel('Magnitude (dB)')
        ax_f2.grid(True, alpha=0.3)
        
        plt.tight_layout()
        plt.show()
    
    def save_results(self, results: Dict[str, Any], averages: Dict[str, Any]):
        """保存结果到文件"""
        # 保存复数FFT结果
        out_mat = np.column_stack([results['freq_d_ref'], np.real(averages['avg_Xd']), np.imag(averages['avg_Xd'])])
        np.savetxt(self.config.output_csv, out_mat, delimiter=",", 
                  header="freq_Hz,Re,Im", comments="", fmt="%.10e")
        
        logger.info(f"结果保存到: {os.path.abspath(self.config.output_csv)}")
        
        # 保存处理统计信息
        stats = {
            'total_files': results['total_files'],
            'successful_files': results['success_count'],
            'success_rate': results['success_count'] / results['total_files'],
            'config': {
                'input_dir': self.config.input_dir,
                'clock_freq': self.config.clock_freq,
                'trigger_freq': self.config.trigger_freq,
                'n_points': self.config.n_points,
                'roi_range': f"{self.config.roi_start_tenths}%-{self.config.roi_end_tenths}%"
            }
        }
        
        stats_file = os.path.splitext(self.config.output_csv)[0] + '_stats.json'
        with open(stats_file, 'w') as f:
            json.dump(stats, f, indent=2)
        
        logger.info(f"统计信息保存到: {stats_file}")
    
    def run_analysis(self):
        """运行完整分析流程"""
        logger.info("开始数据分析...")
        
        # 批量处理文件
        results = self.batch_process_files()
        
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
    config = AnalysisConfig()
    
    try:
        # 创建分析器并运行
        analyzer = DataAnalyzer(config)
        analyzer.run_analysis()
        
    except Exception as e:
        logger.error(f"分析失败: {e}")
        raise

if __name__ == "__main__":
    main()
