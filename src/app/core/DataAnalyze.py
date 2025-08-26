# src/app/core/DataAnalyzer.py
import numpy as np
from typing import Dict, Any, List, Optional, Tuple
import logging
from tqdm import tqdm
try:
    from .ConfigManager import AnalysisConfig, ConfigValidator, CalibrationMode
    from .DataProcessor import DataProcessor
    from .EdgeDetector import EdgeDetector
    from .ResultProcessor import ResultProcessor
    from .FileManager import FileManager
    from .DataPlotter import DataPlotter
except ImportError:
    from ConfigManager import AnalysisConfig, ConfigValidator, CalibrationMode
    from DataProcessor import DataProcessor
    from EdgeDetector import EdgeDetector
    from ResultProcessor import ResultProcessor
    from FileManager import FileManager
    from DataPlotter import DataPlotter
logger = logging.getLogger(__name__)

class DataAnalyzer:
    """重构后的数据分析器类"""
  
    def __init__(self, config: AnalysisConfig, file_manager=None, plotter=None, 
                 data_processor=None, edge_detector=None, result_processor=None):
        self.config = config
        self.file_manager = file_manager or FileManager()
        self.plotter = plotter or DataPlotter(config)
        
        # 初始化各个处理器
        self.data_processor = data_processor or DataProcessor(config)
        self.edge_detector = edge_detector or EdgeDetector(config)
        self.result_processor = result_processor or ResultProcessor(config)
        
        # 验证配置
        ConfigValidator.validate_config(config)
  
    def extract_basic_segment(self, u32_arr: np.ndarray) -> Optional[Tuple[np.ndarray, np.ndarray, np.ndarray]]:
        """提取基本数据段"""
        try:
            # 1. 提取ADC数据
            bit31, adc_full = self.data_processor.extract_adc_data(u32_arr, self.config.use_signed18)
          
            # 2. 检测有效数据
            rise_idx = self.data_processor.detect_valid_data(bit31, self.config.edge_search_start)
            if rise_idx is None:
                return None
          
            # 3. 截取数据段
            segment_adc = self.data_processor.extract_data_segment(
                adc_full, rise_idx, self.config.start_index, self.config.n_points
            )
            if segment_adc is None:
                return None
          
            # 4. 按周期排序
            y_sorted, _ = self.data_processor.sort_data_by_period(
                segment_adc, self.config.t_sample, self.config.t_trig
            )
          
            # 5. 搜索上升沿位置
            rise_pos = self.edge_detector.find_rise_position(
                y_sorted, self.config.search_method, np.mean(adc_full), self.config.min_edge_amplitude_ratio
            )
          
            # 6. 数据对齐
            target_idx = self.config.n_points // 4
            y_full = self.data_processor.align_data(y_sorted, rise_pos, target_idx)
          
            # 7. 提取ROI
            y_roi = self.data_processor.extract_roi(y_full, self.config.roi_start, self.config.roi_end)
          
            return adc_full, y_roi, np.mean(adc_full)
          
        except Exception as e:
            logger.error(f"提取基本数据段时出错: {e}")
            return None

    def process_thru_load_mode(self, y_roi: np.ndarray) -> Optional[Tuple]:
        """
        处理THRU和LOAD模式的数据
      
        Args:
            y_roi: ROI数据
          
        Returns:
            处理结果元组或None
        """
        try:
            # 8. ROI频谱分析
            freq, mag_linear, _ = self.data_processor.compute_spectrum(y_roi, self.config.ts_eff)
          
            # 9. 差分处理
            if self.config.l_roi <= self.config.diff_points:
                return None
              
            y_diff = self.data_processor.compute_difference(y_roi, self.config.diff_points)
          
            # 10. 差分频谱分析
            freq_d, mag_linear_d, Xd_norm = self.data_processor.compute_spectrum(y_diff, self.config.ts_eff)
          
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
            y_diff = self.data_processor.compute_difference(y_roi, self.config.diff_points)
          
            # 对差分数据进行频谱分析
            freq_d, mag_linear_d, Xd_norm = self.data_processor.compute_spectrum(y_diff, self.config.ts_eff)
          
            # 对原始ROI数据也进行频谱分析（可选）
            freq, mag_linear, _ = self.data_processor.compute_spectrum(y_roi, self.config.ts_eff)
          
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
              
            y_diff = self.data_processor.compute_difference(y_roi, self.config.diff_points)
          
            # 差分频谱分析
            freq_d, mag_linear_d, Xd_norm = self.data_processor.compute_spectrum(y_diff, self.config.ts_eff)
          
            return y_roi, freq, magnitude_linear, y_diff, freq_d, mag_linear_d, Xd_norm
          
        except Exception as e:
            logger.error(f"处理OPEN模式时出错: {e}")
            return None

    def process_single_file(self, u32_arr: np.ndarray) -> Optional[Tuple]:
        """
        处理单个文件的方法
      
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
                raw = self.file_manager.load_u32_text_first_col(f, skip_first=self.config.skip_first_value)
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

    def analyze_edges(self, sorted_data: np.ndarray) -> Dict[str, Any]:
        """
        完整的边沿分析流程，返回边沿位置和中点位置
        """
        return self.edge_detector.analyze_edges(sorted_data)

    def save_results(self, results: Dict[str, Any], averages: Dict[str, Any]):
        """保存结果到文件"""
        # 根据校准模式生成输出文件名
        output_filename = self.result_processor.get_output_filename(self.config.output_csv)
      
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
        stats = self.result_processor.prepare_statistics(results)
        stats_file = output_filename.replace('.csv', '_stats.json')
        self.file_manager.save_json_data(stats, stats_file)
      
        logger.info(f"结果已保存到: {output_filename}")

    def run_analysis(self):
        """运行完整分析流程"""
        logger.info("开始数据分析...")
      
        files = self.file_manager.find_csv_files(self.config.input_dir, self.config.recursive)
        if not files:
            raise RuntimeError(f"在目录 {self.config.input_dir} 中未找到CSV文件")
        
        # 批量处理文件
        results = self.batch_process_files(files)
      
        # 计算平均值
        averages = self.result_processor.calculate_averages(results)
      
        # 对平均数据进行边沿分析
        edge_analysis = self.analyze_edges(averages['y_avg'])
      
        # 使用绘图器绘制图表（如果提供了绘图器）
        if self.plotter:
            self.plotter.plot_results(results, averages, edge_analysis)
            t_roi_us = (np.arange(self.config.l_roi) * self.config.ts_eff) * 1e6
            self.plotter.print_edge_analysis_results(edge_analysis, t_roi_us)
        else:
            logger.warning("未提供绘图器，跳过绘图步骤")
      
        # 保存结果
        self.save_results(results, averages)
      
        logger.info(f"分析完成! 共处理 {results['success_count']}/{results['total_files']} 个文件")
        return results, averages, edge_analysis

def main():
    """主函数"""
    import logging
    logging.basicConfig(level=logging.INFO)
    
    # 创建配置
    config = AnalysisConfig(cal_mode=CalibrationMode.LOAD, input_dir="data\\results\\test\\SHORT")
  
    try:
        # 创建分析器并运行
        analyzer = DataAnalyzer(config)
        analyzer.run_analysis()
        
    except Exception as e:
        logger.error(f"分析失败: {e}")
        raise

if __name__ == "__main__":
    main()
