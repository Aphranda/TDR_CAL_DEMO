# src/app/core/DataPlotter.py
import numpy as np
import matplotlib.pyplot as plt
from typing import Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)

class DataPlotter:
    """数据绘图器类，负责所有绘图功能"""
    
    def __init__(self, config):
        self.config = config
    
    def plot_results(self, results: Dict[str, Any], averages: Dict[str, Any], 
                    edge_analysis: Optional[Dict[str, Any]] = None):
        """绘制结果图表，包含边沿检测标记和中点标记"""
        # 时间轴
        t_roi_us = (np.arange(self.config.l_roi) * self.config.ts_eff) * 1e6
        t_diff_us = t_roi_us[self.config.diff_points:]
        
        # 频率掩码
        mask = results['freq_ref'] <= (self.config.show_up_to_GHz * 1e9)
        maskd = results['freq_d_ref'] <= (self.config.show_up_to_GHz * 1e9)
        
        # 边缘位置
        edge_in_roi = (self.config.n_points // 4 - self.config.roi_start)
        
        # 原始ROI图 - 添加校准模式到标题
        fig, (ax_t, ax_f) = plt.subplots(2, 1, figsize=(16, 12))
        
        # 绘制时域信号
        ax_t.plot(t_roi_us, averages['y_avg'], label='Average Signal', linewidth=2, color='blue')
        
        # 标记边沿（如果提供了边沿分析结果）
        if edge_analysis:
            self._plot_edges(ax_t, t_roi_us, averages['y_avg'], edge_analysis)
        
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
        
        # 在差分数据上也标记边沿和中点
        if edge_analysis:
            self._plot_diff_edges(ax_t2, t_roi_us, edge_analysis)
        
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
    
    def _plot_edges(self, ax, t_roi_us, y_data, edge_analysis):
        """在时域图上绘制边沿标记"""
        # 标记第一个上升沿
        if edge_analysis['first_rise_pos'] is not None:
            first_rise_time = t_roi_us[edge_analysis['first_rise_pos']]
            ax.axvline(first_rise_time, linestyle='-', linewidth=2, 
                      color='red', alpha=0.8, label='First Rise Edge')
            
            # 在图上添加文本标注
            ax.text(first_rise_time, np.max(y_data) * 0.9, 
                   f'1st Rise\n{first_rise_time:.2f}μs', 
                   ha='center', va='top', fontsize=9, color='red',
                   bbox=dict(boxstyle="round,pad=0.3", facecolor="yellow", alpha=0.7))
        
        # 标记第二个上升沿
        if edge_analysis['second_rise_pos'] is not None:
            second_rise_time = t_roi_us[edge_analysis['second_rise_pos']]
            ax.axvline(second_rise_time, linestyle='--', linewidth=2, 
                      color='green', alpha=0.8, label='Second Rise Edge')
            
            # 计算并显示幅度比例
            rise_ratio = edge_analysis.get('rise_ratio', 0)
            ax.text(second_rise_time, np.max(y_data) * 0.8, 
                   f'2nd Rise\n{second_rise_time:.2f}μs\nRatio: {rise_ratio:.2f}', 
                   ha='center', va='top', fontsize=9, color='green',
                   bbox=dict(boxstyle="round,pad=0.3", facecolor="lightgreen", alpha=0.7))
            
            # 标记第一个和第二个上升沿的中点
            if 'rise_midpoint_time' in edge_analysis:
                rise_midpoint_time = edge_analysis['rise_midpoint_time']
                ax.axvline(rise_midpoint_time, linestyle='-', linewidth=1.5, 
                          color='cyan', alpha=0.7, label='Rise Midpoint')
                ax.text(rise_midpoint_time, np.max(y_data) * 0.6, 
                       f'Rise Mid\n{rise_midpoint_time:.2f}μs', 
                       ha='center', va='top', fontsize=8, color='cyan',
                       bbox=dict(boxstyle="round,pad=0.2", facecolor="lightcyan", alpha=0.7))
        
        # 标记下降沿
        if edge_analysis['fall_pos'] is not None:
            fall_time = t_roi_us[edge_analysis['fall_pos']]
            ax.axvline(fall_time, linestyle=':', linewidth=2, 
                      color='purple', alpha=0.8, label='Fall Edge')
            
            # 计算并显示下降幅度比例
            fall_ratio = edge_analysis.get('fall_ratio', 0)
            ax.text(fall_time, np.max(y_data) * 0.7, 
                   f'Fall\n{fall_time:.2f}μs\nRatio: {fall_ratio:.2f}', 
                   ha='center', va='top', fontsize=9, color='purple',
                   bbox=dict(boxstyle="round,pad=0.3", facecolor="lavender", alpha=0.7))
            
            # 标记第一个上升沿和下降沿的中点
            if 'fall_midpoint_time' in edge_analysis:
                fall_midpoint_time = edge_analysis['fall_midpoint_time']
                ax.axvline(fall_midpoint_time, linestyle='-', linewidth=1.5, 
                          color='magenta', alpha=0.7, label='Fall Midpoint')
                ax.text(fall_midpoint_time, np.max(y_data) * 0.5, 
                       f'Fall Mid\n{fall_midpoint_time:.2f}μs', 
                       ha='center', va='top', fontsize=8, color='magenta',
                       bbox=dict(boxstyle="round,pad=0.2", facecolor="lightpink", alpha=0.7))
            
            # 标记第二个上升沿和下降沿的中点（如果存在）
            if 'second_fall_midpoint_time' in edge_analysis:
                second_fall_midpoint_time = edge_analysis['second_fall_midpoint_time']
                ax.axvline(second_fall_midpoint_time, linestyle='-', linewidth=1.5, 
                          color='orange', alpha=0.7, label='2nd Rise-Fall Midpoint')
                ax.text(second_fall_midpoint_time, np.max(y_data) * 0.4, 
                       f'2nd Mid\n{second_fall_midpoint_time:.2f}μs', 
                       ha='center', va='top', fontsize=8, color='orange',
                       bbox=dict(boxstyle="round,pad=0.2", facecolor="wheat", alpha=0.7))
    
    def _plot_diff_edges(self, ax, t_roi_us, edge_analysis):
        """在差分时域图上绘制边沿标记"""
        # 标记第一个上升沿
        if edge_analysis['first_rise_pos'] is not None:
            first_rise_diff_time = t_roi_us[max(edge_analysis['first_rise_pos'] - self.config.diff_points, 0)]
            ax.axvline(first_rise_diff_time, linestyle='-', linewidth=2, 
                      color='red', alpha=0.6, label='First Rise (Diff)')
        
        # 标记第二个上升沿
        if edge_analysis['second_rise_pos'] is not None:
            second_rise_diff_time = t_roi_us[max(edge_analysis['second_rise_pos'] - self.config.diff_points, 0)]
            ax.axvline(second_rise_diff_time, linestyle='--', linewidth=2, 
                      color='green', alpha=0.6, label='Second Rise (Diff)')
            
            # 标记中点
            if 'rise_midpoint' in edge_analysis:
                rise_midpoint_diff_time = t_roi_us[max(edge_analysis['rise_midpoint'] - self.config.diff_points, 0)]
                ax.axvline(rise_midpoint_diff_time, linestyle='-', linewidth=1.5, 
                          color='cyan', alpha=0.5, label='Rise Midpoint (Diff)')
        
        # 标记下降沿
        if edge_analysis['fall_pos'] is not None:
            fall_diff_time = t_roi_us[max(edge_analysis['fall_pos'] - self.config.diff_points, 0)]
            ax.axvline(fall_diff_time, linestyle=':', linewidth=2, 
                      color='purple', alpha=0.6, label='Fall (Diff)')
            
            # 标记中点
            if 'fall_midpoint' in edge_analysis:
                fall_midpoint_diff_time = t_roi_us[max(edge_analysis['fall_midpoint'] - self.config.diff_points, 0)]
                ax.axvline(fall_midpoint_diff_time, linestyle='-', linewidth=1.5, 
                          color='magenta', alpha=0.5, label='Fall Midpoint (Diff)')
    
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
