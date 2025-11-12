# src/app/core/DataAnalyze.py

import numpy as np
from typing import Dict, Any, List, Optional, Tuple
import logging
from pandas import date_range
from tqdm import tqdm

try:
    from .ConfigManager import AnalysisConfig, ConfigValidator, CalibrationMode
    from .DataProcessor import DataProcessor
    from .EdgeDetector import EdgeDetector
    from .ResultProcessor import ResultProcessor
    from .FileManager import FileManager
    from .DataPlotter import DataPlotter
    from .DebugPlotter import DebugPlotter
    from .PerformanceMonitor import timeit, performance_monitor
except ImportError:
    from ConfigManager import AnalysisConfig, ConfigValidator, CalibrationMode
    from DataProcessor import DataProcessor
    from EdgeDetector import EdgeDetector
    from ResultProcessor import ResultProcessor
    from FileManager import FileManager
    from DataPlotter import DataPlotter
    from DebugPlotter import DebugPlotter
    from PerformanceMonitor import timeit, performance_monitor

logger = logging.getLogger(__name__)

class DataAnalyzer:
    """重构后的数据分析器类 - 支持双通道处理"""
  
    def __init__(self, config: AnalysisConfig, file_manager=None, plotter=None, 
                 data_processor=None, edge_detector=None, result_processor=None):
        self.config = config
        self.file_manager = file_manager or FileManager()
        self.plotter = plotter or DataPlotter(config)
        
        # 初始化各个处理器
        self.data_processor = data_processor or DataProcessor(config)
        self.edge_detector = edge_detector or EdgeDetector(config)
        self.result_processor = result_processor or ResultProcessor(config)
        self.debug_plotter = DebugPlotter()
        
        # 验证配置
        ConfigValidator.validate_config(config)

        # 性能优化：缓存常用计算结果
        self._cached_adc_mean = None
        self._cached_sorted_data = None

    def _clear_cache(self):
        """清空缓存，防止内存泄漏"""
        self._cached_adc_mean = None
        self._cached_sorted_data = None
    

    def extract_basic_segment(self, u32_arr: np.ndarray, data_index: int = -1, 
                             target_idx: Optional[int] = None) -> Optional[Dict[str, Any]]:
        """提取基本数据段 - 优化版本"""
        try:
            # 优化1: 预检查数据有效性
            if len(u32_arr) < self.config.n_points + self.config.start_index + 10:
                logger.warning(f"数据索引 {data_index}: 数据长度不足")
                return None
            
            # 优化2: 批量提取ADC数据
            bit31, adc_full = self.data_processor.extract_adc_data(u32_arr, self.config.use_signed18)
            
            # 优化3: 跳过无效数据检测（如果配置允许）
            rise_idx = 0  # 简化处理，直接使用起始位置
            
            # 优化4: 使用预分配内存的数据段提取
            segment_adc = self.data_processor.extract_data_segment(
                adc_full, rise_idx, self.config.start_index, self.config.n_points
            )
            
            if segment_adc is None:
                logger.warning(f"数据索引 {data_index}: 数据段截取失败")
                return None
        
            # 优化5: 使用缓存的排序结果（如果可用）
            if (self._cached_sorted_data is not None and 
                len(self._cached_sorted_data) == len(segment_adc)):
                y_sorted = self._cached_sorted_data
            else:
                y_sorted, _ = self.data_processor.sort_data_by_period(
                    segment_adc, self.config.t_sample, self.config.t_trig
                )
                # 缓存排序结果
                self._cached_sorted_data = y_sorted
            
            # 优化6: 简化边沿搜索逻辑
            if target_idx is None:
                # 使用快速边沿检测
                rise_pos = self.edge_detector.find_rise_position(
                    y_sorted, self.config.search_method, 
                    np.mean(adc_full), self.config.min_edge_amplitude_ratio,
                    use_fast_mode=True  # 启用快速方法
                )
                logger.debug(f"ADC1_idx: {rise_pos}")
            else:
                # 直接使用提供的目标位置
                rise_pos = target_idx
                logger.debug(f"ADC2_idx: {rise_pos}")
            # 优化7: 简化数据对齐
            if target_idx is None:
                target_idx = self.config.n_points // 4
            y_full = self.data_processor.align_data(y_sorted, rise_pos, target_idx)
            # 优化8: 使用高效的ROI提取
            y_roi = self.data_processor.extract_roi(y_full, self.config.roi_start, self.config.roi_end)
            return {
                'adc_full': adc_full,
                'y_roi': y_roi,
                'adc_full_mean': np.mean(adc_full),
                'rise_pos': rise_pos,
                'y_sorted': y_sorted,
                'y_full': y_full
            }
        
        except Exception as e:
            logger.error(f"数据索引 {data_index}: 提取基本数据段时出错: {e}")
            # 清空缓存以防内存泄漏
            self._clear_cache()
            return None
        
    def process_thru_load_mode(self, data_dict: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        处理THRU和LOAD模式的数据
        
        Args:
            data_dict: 包含处理数据的字典，必须包含 'y_roi' 键
            
        Returns:
            处理结果字典或None
        """
        try:
            y_full = data_dict['y_full']
            y_roi = data_dict['y_roi']
            
            
            # 8. ROI频谱分析
            freq, mag_linear, _ = self.data_processor.compute_spectrum(y_roi, self.config.ts_eff)
            
            # 9. 差分处理
            if self.config.l_roi <= self.config.diff_points:
                return None
            
            y_full_diff = self.data_processor.compute_difference(y_full, self.config.diff_points)
            
            y_full_diff = self.data_processor.smooth_data(y_full_diff,self.config.average_points)

            y_diff = self.data_processor.compute_difference(y_roi, self.config.diff_points)

            y_diff = self.data_processor.smooth_data(y_diff,self.config.average_points)
          
            # 10. 差分频谱分析
            freq_d, mag_linear_d, Xd_norm = self.data_processor.compute_spectrum(y_diff, self.config.ts_eff)
            
            # 返回字典格式的结果
            return {
                'y_full' : y_full,
                'y_roi': y_roi,
                'freq': freq,
                'mag_linear': mag_linear,
                'y_diff': y_diff,
                'y_full_diff': y_full_diff,
                'freq_d': freq_d,
                'mag_linear_d': mag_linear_d,
                'Xd_norm': Xd_norm,
                'data_dict':data_dict
            }
          
        except Exception as e:
            logger.error(f"处理THRU/LOAD模式时出错: {e}")
            return None
        
    @timeit
    def process_single_file(self, u32_arr_dict: Dict[str, np.ndarray], file_index: int = -1) -> Optional[Dict[str, Any]]:
        """
        处理单个文件的方法 - 支持双通道数据
        
        Args:
            u32_arr_dict: 包含'adc1'和'adc2'键的字典，值为uint32数据数组
            file_index: 文件索引，用于错误追踪
            
        Returns:
            处理结果字典或None
        """
        try:
            # 检查输入数据
            if not isinstance(u32_arr_dict, dict) or ('adc1' not in u32_arr_dict and 'adc2' not in u32_arr_dict):
                logger.error(f"文件索引 {file_index}: 输入数据格式不正确")
                return None
            
            adc1_data = u32_arr_dict.get('adc1', None)
            adc2_data = u32_arr_dict.get('adc2', None)
            
            # 检查ADC数据是否都为空
            if adc1_data is None and adc2_data is None:
                logger.warning(f"文件索引 {file_index}: ADC1和ADC2数据都为空")
                return None
            
            # 处理ADC1数据（如果存在）
            adc1_basic_result = None
            target_idx = None
            
            if adc1_data is not None:
                adc1_basic_result = self.extract_basic_segment(adc1_data, file_index)
                
                if adc1_basic_result is not None:
                    target_idx = adc1_basic_result.get('rise_pos')



            # 处理ADC2数据（如果存在）
            adc2_basic_result = None
            if adc2_data is not None:
                # 使用ADC1的目标对齐位置来处理ADC2数据（如果存在）
                adc2_basic_result = self.extract_basic_segment(adc2_data, file_index, target_idx)

            
            # 如果两个通道的基本结果都为空，返回None
            if adc1_basic_result is None and adc2_basic_result is None:
                logger.warning(f"文件索引 {file_index}: 两个通道的基本处理结果都为空")
                return None
            
            # 根据校准模式选择不同的处理方法
            if self.config.cal_mode in [CalibrationMode.THRU, CalibrationMode.LOAD]:
                # THRU和LOAD模式使用标准处理
                adc1_result = self.process_thru_load_mode(adc1_basic_result) if adc1_basic_result else None
                adc2_result = self.process_thru_load_mode(adc2_basic_result) if adc2_basic_result else None
            elif self.config.cal_mode == CalibrationMode.SHORT:
                # SHORT模式特殊处理
                adc1_result = self.process_thru_load_mode(adc1_basic_result) if adc1_basic_result else None
                adc2_result = self.process_thru_load_mode(adc2_basic_result) if adc2_basic_result else None
            elif self.config.cal_mode == CalibrationMode.OPEN:
                # OPEN模式特殊处理
                adc1_result = self.process_thru_load_mode(adc1_basic_result) if adc1_basic_result else None
                adc2_result = self.process_thru_load_mode(adc2_basic_result) if adc2_basic_result else None
            else:
                logger.error(f"未知的校准模式: {self.config.cal_mode}")
                return None
            
            # 返回嵌套字典结果
            result = {}
            if adc1_result is not None:
                result['adc1'] = adc1_result
            if adc2_result is not None:
                result['adc2'] = adc2_result
            
            return result if result else None
            
        except Exception as e:
            logger.error(f"处理文件索引 {file_index} 时出错: {e}")
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
            'adc1': {
                'ys_full':[], 'ys': [], 'mags': [], 'ys_d_full':[], 'ys_d': [], 'mags_d': [],
                'freq_ref': None, 'freq_d_ref': None, 'sum_Xd': None
            },
            'adc2': {
                'ys_full':[], 'ys': [], 'mags': [], 'ys_d_full':[], 'ys_d': [], 'mags_d': [],
                'freq_ref': None, 'freq_d_ref': None, 'sum_Xd': None
            },
            'success_count': 0, 
            'total_files': len(file_list)
        }
    
        # 处理每个文件
        for i, f in enumerate(tqdm(file_list, desc="处理文件", unit="file")):
            try:
                raw = self.file_manager.load_u32_text_first_col(f, skip_first=self.config.skip_first_value)
                
                # 创建单通道数据字典
                u32_arr_dict = {'adc1': raw}
                
                res = self.process_single_file(u32_arr_dict, i)  # 传递文件索引
                
                if res is None:
                    continue
                
                # 更新ADC1结果
                self._update_channel_results(results['adc1'], res['adc1'])
                
                # 更新ADC2结果（如果存在）
                if 'adc2' in res and res['adc2'] is not None:
                    self._update_channel_results(results['adc2'], res['adc2'])
                
                results['success_count'] += 1
                
            except Exception as e:
                logger.warning(f"处理文件 {f} (索引 {i}) 失败: {e}")
                continue
    
        if results['success_count'] == 0:
            raise RuntimeError("没有文件成功处理")
    
        logger.info(f"成功处理 {results['success_count']}/{len(file_list)} 个文件")
        return results

    def _update_channel_results(self, channel_results: Dict[str, Any], res: Dict[str, Any]):
        """更新通道结果"""
        # 从字典中提取数据
        y_full = res['y_full']
        y_roi = res['y_roi']
        freq = res['freq']
        mag_linear = res['mag_linear']
        y_full_diff = res['y_full_diff']
        y_diff = res['y_diff']
        freq_d = res['freq_d']
        mag_linear_d = res['mag_linear_d']
        Xd_norm = res['Xd_norm']
    
        # 初始化参考频率
        if channel_results['freq_ref'] is None:
            channel_results['freq_ref'] = freq
        if channel_results['freq_d_ref'] is None:
            channel_results['freq_d_ref'] = freq_d
            channel_results['sum_Xd'] = np.zeros_like(Xd_norm, dtype=np.complex128)
    
        # 存储结果
        channel_results['ys_full'].append(y_full.astype(np.float64))
        channel_results['ys'].append(y_roi.astype(np.float64))
        channel_results['mags'].append(mag_linear.astype(np.float64))
        channel_results['ys_d_full'].append(y_full_diff.ast(np.float64))
        channel_results['ys_d'].append(y_diff.astype(np.float64))
        channel_results['mags_d'].append(mag_linear_d.astype(np.float64))
        channel_results['sum_Xd'] += Xd_norm

    @timeit
    def analyze_edges(self, sorted_data: np.ndarray) -> Dict[str, Any]:
        """
        完整的边沿分析流程，返回边沿位置和中点位置
        """
        try:
            edges_dict = self.edge_detector.analyze_edges(sorted_data)
            return edges_dict
        except Exception as e:
            logger.error(f"边沿分析失败: {e}")
            # 返回空的边沿分析结果，避免中断整个流程
            return {
                'first_rise_pos': None,
                'second_rise_pos': None, 
                'fall_pos': None,
                'first_rise_amplitude': 0,
                'second_rise_amplitude': 0,
                'fall_amplitude': 0,
                'rise_ratio': 0,
                'fall_ratio': 0
            }

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
        edge_analysis = self.analyze_edges(averages['y_full_avg'])
      
        # 使用绘图器绘制图表（如果提供了绘图器）
        if self.plotter:
            self.plotter.plot_results(results, averages, edge_analysis)
            t_full_us = (np.arange(len(averages['y_full_avg'])) * self.config.ts_eff) * 1e6
            self.plotter.print_edge_analysis_results(edge_analysis, t_full_us)
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
    config = AnalysisConfig(cal_mode=CalibrationMode.LOAD, input_dir="data\\results\\test\\TT")
  
    try:
        # 创建分析器并运行
        analyzer = DataAnalyzer(config)
        analyzer.run_analysis()
        
    except Exception as e:
        logger.error(f"分析失败: {e}")
        raise

if __name__ == "__main__":
    main()
