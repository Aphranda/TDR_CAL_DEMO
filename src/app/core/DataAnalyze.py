# src/app/core/DataAnalyze.py

from ctypes import alignment
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
    from .ConfigManager import ADCMode
except ImportError:
    from ConfigManager import AnalysisConfig, ConfigValidator, CalibrationMode
    from DataProcessor import DataProcessor
    from EdgeDetector import EdgeDetector
    from ResultProcessor import ResultProcessor
    from FileManager import FileManager
    from DataPlotter import DataPlotter
    from DebugPlotter import DebugPlotter
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
  
    def extract_basic_segment(self, u32_arr: np.ndarray, data_index: int = -1, 
                            target_idx: Optional[int] = None,
                            do_alignment: bool = True) -> Optional[Dict[str, Any]]:
        """提取基本数据段，返回字典格式的结果
        
        Args:
            u32_arr: uint32数据数组
            data_index: 数据索引，用于错误追踪
            target_idx: 目标对齐位置，如果提供则跳过边沿搜索直接使用此位置对齐
            do_alignment: 是否进行数据对齐，ADC1为True，ADC2为False
                
        Returns:
            处理结果字典或None
        """
        try:
            # 1. 提取ADC数据
            bit31, adc_full = self.data_processor.extract_adc_data(u32_arr, self.config.use_signed18, self.config.adc_bit)
            # self.debug_plotter.simple_plot(bit31,"Vaild")
            # 2. 检测有效数据
            # rise_idx = self.data_processor.detect_valid_data(bit31, self.config.edge_search_start)
            rise_idx = 0
            if rise_idx is None:
                logger.warning(f"数据索引 {data_index}: 未检测到有效数据")
                return None
            
            # 3. 截取数据段
            segment_adc = self.data_processor.extract_data_segment(
                adc_full, rise_idx, self.config.start_index, self.config.n_points
            )
            

            if segment_adc is None:
                logger.warning(f"数据索引 {data_index}: 数据段截取失败")
                return None
        
            # 4. 按周期排序
            y_sorted, _ = self.data_processor.sort_data_by_period(
                segment_adc, self.config.t_sample, self.config.t_trig
            )
            
            enable_spike_removal = False

            # self.debug_plotter.simple_plot(y_sorted,title="Before removing singular points")
            if not target_idx :
                enable_spike_removal = True

            # 4.5 去除奇异点（新增步骤）- 使用DataProcessor的方法
            if enable_spike_removal:  # 可以在配置中添加这个开关
                y_sorted_cleaned, spikes_detected = self.data_processor.remove_spikes_robust_final(
                    y_sorted, 
                    threshold=3,    # 默认3.0
                    window_size=5 # 默认5
                )
                
                # 记录奇异点信息
                if spikes_detected:
                    logger.info(f"数据索引 {data_index}: 检测到 {len(spikes_detected)} 个奇异点，已使用中位数替换")
                    
                    # 记录前几个奇异点的详细信息
                    if len(spikes_detected) > 0 and logger.isEnabledFor(logging.DEBUG):
                        spike_details = []
                        for spike_pos in spikes_detected[:3]:
                            if 0 <= spike_pos < len(y_sorted):
                                original_val = y_sorted[spike_pos]
                                cleaned_val = y_sorted_cleaned[spike_pos]
                                spike_details.append(f"位置{spike_pos}:{original_val:.1f}→{cleaned_val:.1f}")
                        
                        logger.debug(f"奇异点替换详情: {'; '.join(spike_details)}")
                
                y_sorted = y_sorted_cleaned
            else:
                spikes_detected = []
            # self.debug_plotter.simple_plot(y_sorted,title="After removing singular points")


            # 5. 搜索边沿位置（如果未提供目标对齐位置）
            if target_idx is None:
                # 搜索所有边沿位置,第一上升沿，第二上升沿，下降沿
                rise_pos = self.edge_detector.find_rise_position(
                    y_sorted, self.config.search_method, np.mean(adc_full), self.config.min_edge_amplitude_ratio
                )
                print("ADC1_idx:", rise_pos)
                # self.debug_plotter.simple_plot(y_sorted, title="ADC1", data_range=(0.39,0.41))
            else:
                rise_pos = target_idx
                # self.debug_plotter.simple_plot(y_sorted, title="ADC2",data_range=(0.39,0.41))
            print("final_rise_pos:",rise_pos)

            # 6. 数据对齐 - 根据do_alignment参数决定是否进行对齐
            if do_alignment:
                # ADC1进行数据对齐
                alignment_idx = self.config.n_points // self.config.align_pos
                
                y_full = self.data_processor.align_data(y_sorted, rise_pos, alignment_idx)
            else:
                # ADC2不进行数据对齐，直接使用排序后的数据
                y_full = y_sorted
            
            # 7. 提取ROI
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

    def process_single_file(self, u32_arr_dict: Dict[str, np.ndarray], file_index: int = -1, 
                            target_idx: Optional[int] = None) -> Optional[Dict[str, Any]]:
        """
        处理单个文件的方法 - 支持双通道数据
        
        Args:
            u32_arr_dict: 包含'adc1'和'adc2'键的字典，值为uint32数据数组
            file_index: 文件索引，用于错误追踪
            target_idx: 目标对齐位置，如果提供则跳过边沿搜索直接使用此位置对齐
                
        Returns:
            处理结果字典或None
        """
        try:
            # 输入验证：确保数据格式正确且至少包含一个有效通道
            if not isinstance(u32_arr_dict, dict) or ('adc1' not in u32_arr_dict and 'adc2' not in u32_arr_dict):
                logger.error(f"文件索引 {file_index}: 输入数据格式不正确")
                return None
            
            # 数据提取：从字典中分离双通道数据
            adc1_data = u32_arr_dict.get('adc1', None)
            adc2_data = u32_arr_dict.get('adc2', None)
            
            # 空数据检查：两个通道都为空时提前返回
            if adc1_data is None and adc2_data is None:
                logger.warning(f"文件索引 {file_index}: ADC1和ADC2数据都为空")
                return None
            
            # 通道处理状态初始化
            adc1_basic_result = None
            adc2_basic_result = None
            adc1_target_idx = target_idx
            adc1_result = None
            adc2_result = None
            
            # 根据ADC模式决定数据处理策略
            if self.config.adc_mode == ADCMode.ADC1_ONLY:
                # 仅ADC1模式：只处理ADC1数据并进行对齐
                if adc1_data is not None:
                    adc1_basic_result = self.extract_basic_segment(adc1_data, file_index, adc1_target_idx, do_alignment=True)
                    
            elif self.config.adc_mode == ADCMode.ADC2_ONLY:
                # 仅ADC2模式：只处理ADC2数据并进行对齐
                if adc2_data is not None:
                    adc2_basic_result = self.extract_basic_segment(adc2_data, file_index, adc1_target_idx, do_alignment=True)
                    
            elif self.config.adc_mode == ADCMode.BOTH_ADCS:
                # 双通道模式：ADC1进行对齐，ADC2使用ADC1的边沿位置但不进行对齐
                if adc1_data is not None:
                    adc1_basic_result = self.extract_basic_segment(adc1_data, file_index, adc1_target_idx, do_alignment=False)
                    
                    # 如果未提供目标对齐位置且ADC1处理成功，提取其边沿位置供ADC2使用
                    if target_idx is None and adc1_basic_result is not None:
                        adc1_target_idx = adc1_basic_result.get('rise_pos')
                
                if adc2_data is not None:
                    # 双通道模式下ADC2不进行数据对齐，直接使用ADC1的边沿位置
                    adc2_basic_result = self.extract_basic_segment(adc2_data, file_index, adc1_target_idx, do_alignment=False)
            
            else:
                logger.error(f"未知的ADC模式: {self.config.adc_mode}")
                return None

            # 处理结果有效性检查
            if adc1_basic_result is None and adc2_basic_result is None:
                logger.warning(f"文件索引 {file_index}: 两个通道的基本处理结果都为空")
                return None
            
            # 根据校准模式选择相应的数据处理方法
            if self.config.cal_mode in [CalibrationMode.THRU, CalibrationMode.LOAD, 
                                    CalibrationMode.SHORT, CalibrationMode.OPEN]:
                # 所有校准模式目前都使用相同的频谱分析方法处理
                adc1_result = self.process_thru_load_mode(adc1_basic_result) if adc1_basic_result else None
                adc2_result = self.process_thru_load_mode(adc2_basic_result) if adc2_basic_result else None
            else:
                # 未知校准模式处理
                logger.error(f"未知的校准模式: {self.config.cal_mode}")
                return None
            
            # 构建返回结果：只包含成功处理的通道数据
            result = {}
            if adc1_result is not None:
                result['adc1'] = adc1_result
            if adc2_result is not None:
                result['adc2'] = adc2_result
            
            # 返回非空结果，确保调用方能正确处理
            return result if result else None
            
        except Exception as e:
            # 统一异常处理：记录详细错误信息但不中断整体流程
            logger.error(f"处理文件索引 {file_index} 时出错: {e}")
            return None


    def process_averaged_data(self, y_full_avg: np.ndarray, target_idx: Optional[int] = None, 
                            do_alignment: bool = True) -> Optional[Dict[str, Any]]:
        """
        处理平均后的时域数据，进行边沿搜索、对齐和频谱分析
        
        Args:
            y_full_avg: 平均后的时域数据
            target_idx: 目标对齐位置，如果提供则跳过边沿搜索直接使用此位置对齐
            do_alignment: 是否进行数据对齐
            
        Returns:
            处理结果字典或None
        """
        try:
            # 输入验证
            if y_full_avg is None or len(y_full_avg) == 0:
                logger.error("平均数据为空")
                return None
            
            # 如果未提供target_idx，则搜索边沿
            if target_idx is None:
                # 搜索边沿位置
                rise_pos = self.edge_detector.find_rise_position(
                    y_full_avg, self.config.search_method, np.mean(y_full_avg), self.config.min_edge_amplitude_ratio
                )
                logger.debug(f"平均数据边沿搜索位置: {rise_pos}")
            else:
                rise_pos = target_idx
                logger.debug(f"使用指定边沿位置: {rise_pos}")
            
            # 数据对齐
            if do_alignment and rise_pos is not None:
                alignment_idx = self.config.n_points // self.config.align_pos
                print('AlignPos:',self.config.align_pos)
                y_full_aligned = self.data_processor.align_data(y_full_avg, rise_pos, alignment_idx)
                logger.debug(f"数据对齐完成，从位置 {rise_pos} 对齐到 {alignment_idx}")
            else:
                y_full_aligned = y_full_avg
                logger.debug("跳过数据对齐")
            
            # 提取ROI
            y_roi = self.data_processor.extract_roi(y_full_aligned, self.config.roi_start, self.config.roi_end)
            
            # 计算频谱
            freq, mag_linear, _ = self.data_processor.compute_spectrum(y_roi, self.config.ts_eff)
            
            # 计算差分
            y_full_diff = self.data_processor.compute_difference(y_full_aligned, self.config.diff_points)
            y_full_diff = self.data_processor.smooth_data(y_full_diff, self.config.average_points)
            
            y_diff = self.data_processor.compute_difference(y_roi, self.config.diff_points)
            y_diff = self.data_processor.smooth_data(y_diff, self.config.average_points)
            
            # 计算差分频谱
            freq_d, mag_linear_d, Xd_norm = self.data_processor.compute_spectrum(y_diff, self.config.ts_eff)
            
            return {
                'y_full': y_full_aligned,
                'y_roi': y_roi,
                'freq': freq,
                'mag_linear': mag_linear,
                'y_diff': y_diff,
                'y_full_diff': y_full_diff,
                'freq_d': freq_d,
                'mag_linear_d': mag_linear_d,
                'Xd_norm': Xd_norm,
                'rise_pos': rise_pos
            }
            
        except Exception as e:
            logger.error(f"处理平均数据时出错: {e}")
            return None
        
    def realign_dual_channel_averages(self, adc1_y_full_avg: Optional[np.ndarray], 
                                    adc2_y_full_avg: Optional[np.ndarray],
                                    alignment_reference: str = 'adc1') -> Tuple[Optional[Dict], Optional[Dict]]:
        """
        双通道重新对齐和频谱分析
        
        Args:
            adc1_y_full_avg: ADC1平均时域数据
            adc2_y_full_avg: ADC2平均时域数据
            alignment_reference: 对齐参考通道 ('adc1' 或 'adc2')
            
        Returns:
            (adc1_result, adc2_result) 重新对齐后的结果
        """
        try:
            # 检查输入数据
            if adc1_y_full_avg is None and adc2_y_full_avg is None:
                logger.warning("双通道数据都为空，跳过重新对齐")
                return None, None
            
            # 步骤1：获取各通道的边沿位置
            adc1_edges = None
            adc2_edges = None
            
            if adc1_y_full_avg is not None:
                adc1_result = self.process_averaged_data(adc1_y_full_avg, target_idx=None, do_alignment=False)
                adc1_edges = adc1_result['rise_pos'] if adc1_result else None
            
            if adc2_y_full_avg is not None:
                adc2_result = self.process_averaged_data(adc2_y_full_avg, target_idx=None, do_alignment=False)
                adc2_edges = adc2_result['rise_pos'] if adc2_result else None
            
            # 步骤2：选择目标边沿位置
            target_rise_pos = None
            if alignment_reference == 'adc1' and adc1_edges is not None:
                target_rise_pos = adc1_edges
                logger.info(f"使用ADC1边沿位置作为参考: {target_rise_pos}")
            elif alignment_reference == 'adc2' and adc2_edges is not None:
                target_rise_pos = adc2_edges
                logger.info(f"使用ADC2边沿位置作为参考: {target_rise_pos}")
            else:
                # 如果参考通道没有数据，则使用另一个通道
                if adc1_edges is not None:
                    target_rise_pos = adc1_edges
                    logger.info(f"参考通道无数据，使用ADC1边沿位置: {target_rise_pos}")
                elif adc2_edges is not None:
                    target_rise_pos = adc2_edges
                    logger.info(f"参考通道无数据，使用ADC2边沿位置: {target_rise_pos}")
                else:
                    # 两个通道都没有边沿，则使用默认位置
                    target_rise_pos = self.config.n_points // self.config.align_pos
                    print('AlignPos:',self.config.align_pos)
                    logger.warning(f"两个通道都未找到边沿，使用默认位置: {target_rise_pos}")
            
            # 步骤3：使用目标边沿位置重新处理两个通道
            adc1_final_result = None
            adc2_final_result = None
            
            if adc1_y_full_avg is not None:
                adc1_final_result = self.process_averaged_data(
                    adc1_y_full_avg, target_idx=target_rise_pos, do_alignment=True
                )
                if adc1_final_result:
                    logger.info(f"ADC1重新对齐完成，边沿位置: {target_rise_pos}")
            
            if adc2_y_full_avg is not None:
                adc2_final_result = self.process_averaged_data(
                    adc2_y_full_avg, target_idx=target_rise_pos, do_alignment=True
                )
                if adc2_final_result:
                    logger.info(f"ADC2重新对齐完成，边沿位置: {target_rise_pos}")
            
            return adc1_final_result, adc2_final_result
            
        except Exception as e:
            logger.error(f"双通道重新对齐失败: {e}")
            return None, None

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



