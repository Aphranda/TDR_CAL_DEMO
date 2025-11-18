# src/app/threads/DataExportWorker.py
import os
import time
import numpy as np
from PyQt5.QtCore import QObject, pyqtSignal, QThread
from PyQt5.QtGui import QPixmap

from app.core.FileManager import FileManager
from app.core.DataAnalyze import DataAnalyzer, AnalysisConfig


class DataExportWorker(QObject):
    """数据导出工作线程"""
    
    # 定义信号
    progress = pyqtSignal(int, int, str)  # 当前进度，总进度，消息
    finished = pyqtSignal(bool, str)      # 完成信号 (成功状态, 消息)
    error = pyqtSignal(str)               # 错误信号
    log_message = pyqtSignal(str, str)    # 日志消息 (消息, 级别)

    def __init__(self, export_config):
        super().__init__()
        self.export_config = export_config
        self.is_cancelled = False

    def run(self):
        """执行导出操作"""
        try:
            self.is_cancelled = False
            total_steps = self.calculate_total_steps()
            current_step = 0
            
            # 步骤1: 导出数据文件
            if not self.is_cancelled:
                current_step = self.export_data_files(current_step, total_steps)
            
            # 步骤2: 导出图片
            if not self.is_cancelled:
                current_step = self.export_images(current_step, total_steps)
            
            if self.is_cancelled:
                self.finished.emit(False, "导出操作已取消")
            else:
                self.finished.emit(True, f"导出完成: {self.export_config['base_path']}")
                
        except Exception as e:
            self.error.emit(f"导出失败: {str(e)}")

    def calculate_total_steps(self):
        """准确计算总步骤数"""
        total = 0
        
        # 数据文件步骤
        if self.export_config.get('export_data', True):
            total += 1  # 主数据文件
            
            # 额外数据文件：精确计算每个通道的文件数量
            if self.export_config.get('export_additional_data', True):
                channels = self.export_config.get('channels', ['adc1', 'adc2'])
                for channel in channels:
                    # 每个通道包含的文件类型：
                    # 1. 全部时域数据
                    # 2. ROI时域数据
                    # 3. 频域数据
                    # 4. 全部差分时域数据
                    # 5. ROI差分时域数据
                    # 6. 差分频域数据
                    # 7. 边沿分析结果
                    total += 7
        
        # 图片步骤：根据实际图片数量计算
        if self.export_config.get('export_images', True):
            plot_images = self.export_config.get('plot_images', {})
            total += len(plot_images)
        
        return max(total, 1)

    def export_data_files(self, current_step, total_steps):
        """导出数据文件 - 精确进度控制"""
        if not self.export_config.get('export_data', True):
            return current_step

        file_path = self.export_config['file_path']
        file_ext = os.path.splitext(file_path)[1].lower()
        base_path = os.path.splitext(file_path)[0]
        
        self.progress.emit(current_step, total_steps, "开始导出数据文件...")
        
        try:
            # 根据文件类型导出数据
            if file_ext == '.csv':
                current_step = self.export_csv_data(base_path, file_path, current_step, total_steps)
            elif file_ext == '.json':
                self.export_json_data(file_path)
                current_step += 1
                self.progress.emit(current_step, total_steps, "JSON数据文件导出完成")
            else:
                self.export_text_data(file_path)
                current_step += 1
                self.progress.emit(current_step, total_steps, "文本数据文件导出完成")
                
        except Exception as e:
            self.error.emit(f"数据文件导出失败: {str(e)}")
            raise
        
        return current_step

    def export_csv_data(self, base_path, file_path, current_step, total_steps):
        """导出CSV数据 - 精确进度控制"""
        results = self.export_config.get('results')
        averages = self.export_config.get('averages')
        config = self.export_config.get('config')
        
        if results and averages and config:
            # 创建DataAnalyzer实例
            analyzer = DataAnalyzer(AnalysisConfig(output_csv=file_path))
            
            # 保存复数FFT结果
            if 'freq_d_ref' in results and 'avg_Xd' in averages:
                success = analyzer.file_manager.save_complex_fft_results(
                    results['freq_d_ref'], 
                    np.real(averages['avg_Xd']), 
                    np.imag(averages['avg_Xd']), 
                    file_path
                )
                
                if success:
                    self.log_message.emit("复数FFT结果已成功导出为CSV", "INFO")
                else:
                    self.error.emit("复数FFT结果导出失败")
            
            # 更新主数据文件进度
            current_step += 1
            self.progress.emit(current_step, total_steps, "主数据文件导出完成")
            
            # 导出额外CSV数据
            if self.export_config.get('export_additional_data', True):
                current_step = self.export_additional_csv_data(base_path, results, averages, config, current_step, total_steps)
        else:
            # 如果没有分析数据，保存基本的文本结果
            self.export_text_data(file_path)
            current_step += 1
            self.progress.emit(current_step, total_steps, "文本数据文件导出完成")
        
        return current_step

    def export_additional_csv_data(self, base_path, results, averages, config, current_step, total_steps):
        """导出额外的CSV数据 - 精确进度控制"""
        channels = self.export_config.get('channels', ['adc1', 'adc2'])
        channel_names = {'adc1': 'ADC1', 'adc2': 'ADC2'}
        
        for channel in channels:
            if self.is_cancelled:
                break
                
            if channel in results and channel in averages:
                channel_results = results[channel]
                channel_averages = averages[channel]
                channel_suffix = channel_names[channel].lower()
                
                # 保存时域数据
                current_step = self.save_time_domain_data(base_path, channel, channel_results, channel_averages, config, channel_suffix, current_step, total_steps)
                
                # 保存频域数据
                current_step = self.save_frequency_domain_data(base_path, channel, channel_results, channel_averages, config, channel_suffix, current_step, total_steps)
                
                # 保存差分数据
                current_step = self.save_differential_data(base_path, channel, channel_results, channel_averages, config, channel_suffix, current_step, total_steps)
                
                # 保存边沿分析结果
                current_step = self.save_edge_analysis_data(base_path, channel, channel_results, channel_suffix, current_step, total_steps)
        
        return current_step

    def save_time_domain_data(self, base_path, channel, results, averages, config, channel_suffix, current_step, total_steps):
        """保存时域数据 - 精确进度控制"""
        if 'y_full_avg' in averages:
            # 全部时域数据
            time_domain_file = f"{base_path}_{channel_suffix}_time_domain.csv"
            t_full_us = (np.arange(len(averages['y_full_avg'])) * config.ts_eff * 1e6)
            time_data = np.column_stack((t_full_us, averages['y_full_avg']))
            np.savetxt(time_domain_file, time_data, delimiter=',', 
                      header='Time(us),Amplitude', comments='')
            self.log_message.emit(f"{channel.upper()}时域数据已保存", "INFO")
            current_step += 1
            self.progress.emit(current_step, total_steps, f"保存{channel.upper()}时域数据")
            
            # ROI时域数据
            if 'y_avg' in averages:
                roi_params = self.export_config.get('roi_params', {})
                roi_start = roi_params.get('start', 0)
                roi_end = roi_params.get('end', 100)
                roi_time_domain_file = f"{base_path}_{channel_suffix}_{roi_start}_{roi_end}_time_domain.csv"
                t_roi_us = (np.arange(len(averages['y_avg'])) * config.ts_eff * 1e6)
                time_data = np.column_stack((t_roi_us, averages['y_avg']))
                np.savetxt(roi_time_domain_file, time_data, delimiter=',', 
                          header='Time(us),Amplitude', comments='')
                current_step += 1
                self.progress.emit(current_step, total_steps, f"保存{channel.upper()} ROI时域数据")
        
        return current_step

    def save_frequency_domain_data(self, base_path, channel, results, averages, config, channel_suffix, current_step, total_steps):
        """保存频域数据 - 精确进度控制"""
        if 'freq_ref' in results and 'mag_avg_db' in averages:
            freq_domain_file = f"{base_path}_{channel_suffix}_frequency_domain.csv"
            mask = results['freq_ref'] <= (config.show_up_to_GHz * 1e9)
            freq_data = np.column_stack((results['freq_ref'][mask] / 1e9, 
                                      averages['mag_avg_db'][mask]))
            np.savetxt(freq_domain_file, freq_data, delimiter=',', 
                      header='Frequency(GHz),Magnitude(dB)', comments='')
            self.log_message.emit(f"{channel.upper()}频域数据已保存", "INFO")
            current_step += 1
            self.progress.emit(current_step, total_steps, f"保存{channel.upper()}频域数据")
        
        return current_step

    def save_differential_data(self, base_path, channel, results, averages, config, channel_suffix, current_step, total_steps):
        """保存差分数据 - 精确进度控制"""
        # 差分时域数据
        if 'y_d_full_avg' in averages:
            diff_time_file = f"{base_path}_{channel_suffix}_diff_time_domain.csv"
            t_full_diff_us = (np.arange(len(averages['y_d_full_avg'])) * config.ts_eff * 1e6)
            diff_time_data = np.column_stack((t_full_diff_us, averages['y_d_full_avg']))
            np.savetxt(diff_time_file, diff_time_data, delimiter=',', 
                      header='Time(us),Differential_Amplitude', comments='')
            current_step += 1
            self.progress.emit(current_step, total_steps, f"保存{channel.upper()}差分时域数据")
            
            # ROI差分时域数据
            if 'y_d_avg' in averages:
                roi_params = self.export_config.get('roi_params', {})
                roi_start = roi_params.get('start', 0)
                roi_end = roi_params.get('end', 100)
                roi_diff_time_file = f"{base_path}_{channel_suffix}_{roi_start}_{roi_end}_diff_time_domain.csv"
                t_diff_us = (np.arange(len(averages['y_d_avg'])) * config.ts_eff * 1e6)
                diff_time_data = np.column_stack((t_diff_us, averages['y_d_avg']))
                np.savetxt(roi_diff_time_file, diff_time_data, delimiter=',', 
                          header='Time(us),Differential_Amplitude', comments='')
                current_step += 1
                self.progress.emit(current_step, total_steps, f"保存{channel.upper()} ROI差分时域数据")

        # 差分频域数据
        if 'freq_d_ref' in results and 'mag_d_avg_db' in averages:
            diff_freq_file = f"{base_path}_{channel_suffix}_diff_frequency_domain.csv"
            maskd = results['freq_d_ref'] <= (config.show_up_to_GHz * 1e9)
            diff_freq_data = np.column_stack((results['freq_d_ref'][maskd] / 1e9, 
                                            averages['mag_d_avg_db'][maskd]))
            np.savetxt(diff_freq_file, diff_freq_data, delimiter=',', 
                      header='Frequency(GHz),Differential_Magnitude(dB)', comments='')
            self.log_message.emit(f"{channel.upper()}差分频域数据已保存", "INFO")
            current_step += 1
            self.progress.emit(current_step, total_steps, f"保存{channel.upper()}差分频域数据")
        
        return current_step

    def save_edge_analysis_data(self, base_path, channel, results, channel_suffix, current_step, total_steps):
        """保存边沿分析结果 - 精确进度控制"""
        edge_analysis_file = f"{base_path}_{channel_suffix}_edge_analysis.csv"
        try:
            with open(edge_analysis_file, 'w', encoding='utf-8') as f:
                f.write(f"{channel.upper()}边沿分析结果\n")
                f.write("=" * 50 + "\n")
                
                # 这里可以添加具体的边沿分析数据保存逻辑
                # 例如：f.write(f"First Rise Time: {results.get('first_rise_time', 'N/A')}ns\n")
                
            current_step += 1
            self.progress.emit(current_step, total_steps, f"保存{channel.upper()}边沿分析结果")
                
        except Exception as e:
            self.log_message.emit(f"导出{channel.upper()}边沿分析结果失败: {str(e)}", "WARNING")
        
        return current_step

    def export_json_data(self, file_path):
        """导出JSON数据"""
        file_manager = FileManager()
        export_data = self.export_config.get('export_data_dict', {})
        success = file_manager.save_json_data(export_data, file_path)
        
        if success:
            self.log_message.emit("JSON数据导出成功", "INFO")
        else:
            self.error.emit("JSON数据导出失败")

    def export_text_data(self, file_path):
        """导出文本数据"""
        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write("数据分析结果\n")
                f.write("=" * 50 + "\n\n")
                
                # 这里可以添加具体的文本数据导出逻辑
                
            self.log_message.emit("文本数据导出成功", "INFO")
        except Exception as e:
            self.error.emit(f"文本数据导出失败: {str(e)}")

    def export_images(self, current_step, total_steps):
        """导出图片 - 精确进度控制"""
        if not self.export_config.get('export_images', True):
            return current_step

        base_path = self.export_config['base_path']
        plot_images = self.export_config.get('plot_images', {})
        
        self.progress.emit(current_step, total_steps, "开始导出图片...")
        
        try:
            for plot_name, image_data in plot_images.items():
                if self.is_cancelled:
                    break
                    
                file_path = image_data['file_path']
                image = image_data['image']
                
                success = image.save(file_path)
                if success:
                    self.log_message.emit(f"图片导出成功: {os.path.basename(file_path)}", "INFO")
                else:
                    self.log_message.emit(f"图片导出失败: {os.path.basename(file_path)}", "WARNING")
                
                current_step += 1
                self.progress.emit(current_step, total_steps, f"导出图片: {plot_name}")
                
        except Exception as e:
            self.error.emit(f"图片导出失败: {str(e)}")
            raise
        
        return current_step

    def cancel(self):
        """取消导出操作"""
        self.is_cancelled = True
