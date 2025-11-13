# src/app/threads/ADCProcessWorker.py

import os
import gc
import numpy as np
from PyQt5.QtCore import QObject, pyqtSignal, pyqtSlot
from typing import Optional, Tuple, Dict, Any, Generator, List

from app.core.DataAnalyze import DataAnalyzer, AnalysisConfig
from app.core.DataCacheManager import DataCacheManager  # 新增导入
from app.core.PerformanceMonitor import timeit, performance_monitor


class ADCProcessWorker(QObject):
    """ADC数据处理工作线程 - 使用数据缓存优化"""
    
    progress = pyqtSignal(int, int, str)
    finished = pyqtSignal(dict, dict)
    error = pyqtSignal(str)
    log_message = pyqtSignal(str, str)
    
    def __init__(self, file_dict: Dict[str, List[Dict]], config: AnalysisConfig):
        super().__init__()
        self.file_dict = file_dict
        self.config = config
        self.analyzer = DataAnalyzer(config)
        self.cache_manager = DataCacheManager()  # 新增缓存管理器
        self.running = False
        self._should_stop = False
        self._segmented_files = None  # 缓存预分割的文件数据
        
        # 设置线程名称
        adc1_count = len(file_dict.get('adc1', []))
        adc2_count = len(file_dict.get('adc2', []))
        self.setObjectName(f"双通道数据分析线程_ADC1:{adc1_count}_ADC2:{adc2_count}")

    @pyqtSlot()
    def run(self):
        """执行ADC数据处理 - 使用缓存优化版本"""
        self.running = True
        self._should_stop = False
        
        try:
            # 第一步：预加载所有数据到缓存
            self._preload_all_data()
            
            # 第二步：处理所有段数据
            final_results = self._process_all_segments()
            
            if final_results is None or final_results['success_count'] == 0:
                raise RuntimeError("没有文件或数据段成功处理")
            
            # 第三步：计算平均值和边沿分析
            averages = self._calculate_averages(final_results)
            self._perform_edge_analysis(final_results, averages)
            
            # 发送完成信号
            self.finished.emit(final_results, averages)
            
        except Exception as e:
            self._handle_error(e)
        finally:
            self._cleanup()

    def _preload_all_data(self):
        """预加载所有数据到缓存"""
        self.log_message.emit("开始预加载所有文件数据到缓存...", "INFO")
        
        # 预加载所有文件
        self._segmented_files = self.cache_manager.preload_files(self.file_dict)
        
        # 计算总段数
        total_segments = self._get_total_segment_count()
        self.log_message.emit(f"预加载完成，共 {total_segments} 个数据段", "INFO")

    def _get_total_segment_count(self) -> int:
        """获取总段数 - 从缓存数据计算"""
        if self._segmented_files is None:
            return 0
            
        total_segments = 0
        for channel in ['adc1', 'adc2']:
            for file_info in self._segmented_files.get(channel, []):
                total_segments += len(file_info.get('pre_segmented_data', []))
        return total_segments

    def _process_all_segments(self) -> Optional[Dict[str, Any]]:
        """处理所有段数据 - 使用缓存版本"""
        if self._segmented_files is None:
            return None
            
        results = self._initialize_results()
        segment_counter = 0
        
        # 使用缓存数据直接处理
        for file_idx, (adc1_file_info, adc2_file_info) in enumerate(
            self._get_file_pairs()
        ):
            if self._should_stop:
                break
                
            # 处理该文件对的所有段
            segment_results = self._process_file_pair_segments(
                file_idx, adc1_file_info, adc2_file_info, results, segment_counter
            )
            segment_counter = segment_results
            
        return results

    def _get_file_pairs(self) -> Generator[Tuple[Optional[Dict], Optional[Dict]], None, None]:
        """获取文件对生成器"""
        adc1_files = self._segmented_files.get('adc1', [])
        adc2_files = self._segmented_files.get('adc2', [])
        
        file_count = max(len(adc1_files), len(adc2_files))
        
        for i in range(file_count):
            adc1_file = adc1_files[i] if i < len(adc1_files) else None
            adc2_file = adc2_files[i] if i < len(adc2_files) else None
            yield adc1_file, adc2_file

    def _process_file_pair_segments(self, file_idx: int, adc1_file_info: Optional[Dict], 
                                  adc2_file_info: Optional[Dict], results: Dict, 
                                  start_counter: int) -> int:
        """处理文件对的所有段"""
        segment_counter = start_counter
        
        # 确定要处理的段数
        adc1_segments = len(adc1_file_info.get('pre_segmented_data', [])) if adc1_file_info else 0
        adc2_segments = len(adc2_file_info.get('pre_segmented_data', [])) if adc2_file_info else 0
        segment_count = max(adc1_segments, adc2_segments)
        
        for segment_idx in range(segment_count):
            if self._should_stop:
                break
                
            segment_counter += 1
            
            # 直接从缓存获取段数据
            adc1_data = self._get_cached_segment_data(adc1_file_info, segment_idx)
            adc2_data = self._get_cached_segment_data(adc2_file_info, segment_idx)
            
            self._emit_progress(segment_counter, file_idx, segment_idx, adc1_file_info, adc2_file_info)
            
            try:
                # 处理段数据
                adc_data = {}
                if adc1_data is not None:
                    adc_data['adc1'] = adc1_data
                if adc2_data is not None:
                    adc_data['adc2'] = adc2_data
                
                if adc_data:  # 确保至少有一个通道有数据
                    segment_result = self.analyzer.process_single_file(
                        adc_data, file_idx * 1000 + segment_idx
                    )
                    self._update_results_with_segment_data(results, segment_result)
                    
            except Exception as e:
                self._log_segment_error(file_idx, segment_idx, adc1_file_info, adc2_file_info, e)
                continue
                
        return segment_counter

    def _get_cached_segment_data(self, file_info: Optional[Dict], segment_idx: int) -> Optional[np.ndarray]:
        """从缓存获取段数据"""
        if file_info is None:
            return None
            
        pre_segmented = file_info.get('pre_segmented_data', [])
        if segment_idx < len(pre_segmented):
            return pre_segmented[segment_idx]
        return None

    def _emit_progress(self, segment_counter: int, file_idx: int, segment_idx: int, 
                      adc1_file_info: Optional[Dict], adc2_file_info: Optional[Dict]):
        """发射进度信号"""
        adc1_name = os.path.basename(adc1_file_info['path']) if adc1_file_info else "无文件"
        adc2_name = os.path.basename(adc2_file_info['path']) if adc2_file_info else "无文件"
        
        self.progress.emit(
            segment_counter, 
            self._get_total_segment_count(), 
            f"处理文件{file_idx}段{segment_idx}: ADC1={adc1_name}, ADC2={adc2_name}"
        )

    # 以下方法保持不变（_initialize_results, _update_results_with_segment_data, 
    # _calculate_averages, _perform_edge_analysis, _handle_error, _cleanup, stop 等）
    
    def _initialize_results(self) -> Dict[str, Any]:
        """初始化结果字典"""
        return {
            'adc1': {
                'ys_full': [], 'ys': [], 'mags': [],
                'ys_d_full': [], 'ys_d': [], 'mags_d': [],
                'freq_ref': None, 'freq_d_ref': None, 'sum_Xd': None,
            },
            'adc2': {
                'ys_full': [], 'ys': [], 'mags': [],
                'ys_d_full': [], 'ys_d': [], 'mags_d': [],
                'freq_ref': None, 'freq_d_ref': None, 'sum_Xd': None,
            },
            'success_count': 0, 
            'total_segments': self._get_total_segment_count(),
        }

    def _update_results_with_segment_data(self, results: Dict[str, Any], segment_result: Dict[str, Any]):
        """使用段结果更新总结果"""
        for adc_channel in ['adc1', 'adc2']:
            if adc_channel in segment_result:
                channel_result = segment_result[adc_channel]
                
                # 从字典中提取数据
                y_full = channel_result['y_full']
                y_roi = channel_result['y_roi']
                freq = channel_result['freq']
                mag_linear = channel_result['mag_linear']
                y_full_diff = channel_result['y_full_diff']
                y_diff = channel_result['y_diff']
                freq_d = channel_result['freq_d']
                mag_linear_d = channel_result['mag_linear_d']
                Xd_norm = channel_result['Xd_norm']
                
                # 初始化参考频率
                if results[adc_channel]['freq_ref'] is None:
                    results[adc_channel]['freq_ref'] = freq
                if results[adc_channel]['freq_d_ref'] is None:
                    results[adc_channel]['freq_d_ref'] = freq_d
                    results[adc_channel]['sum_Xd'] = np.zeros_like(Xd_norm, dtype=np.complex128)
                
                # 存储结果
                results[adc_channel]['ys_full'].append(self._optimize_array(y_full))
                results[adc_channel]['ys'].append(self._optimize_array(y_roi))
                results[adc_channel]['mags'].append(self._optimize_array(mag_linear))
                results[adc_channel]['ys_d_full'].append(self._optimize_array(y_full_diff))
                results[adc_channel]['ys_d'].append(self._optimize_array(y_diff))
                results[adc_channel]['mags_d'].append(self._optimize_array(mag_linear_d))
                results[adc_channel]['sum_Xd'] += Xd_norm
        
        results['success_count'] += 1

    def _optimize_array(self, array: np.ndarray) -> np.ndarray:
        """优化数组内存使用"""
        if array.dtype == np.float64:
            return array.astype(np.float32)
        elif array.dtype == np.uint32 and np.max(array) < 65536:
            return array.astype(np.uint16)
        return array

    def _calculate_averages(self, results: Dict[str, Any]) -> Dict[str, Any]:
        """计算平均值"""
        self.progress.emit(
            self._get_total_segment_count(), 
            self._get_total_segment_count(), 
            "计算平均值..."
        )
        self.log_message.emit("计算平均值...", "INFO")
        
        averages = {}
        
        for adc_channel in ['adc1', 'adc2']:
            if not results[adc_channel]['ys_full']:
                self.log_message.emit(f"通道 {adc_channel.upper()} 没有数据，跳过平均值计算", "INFO")
                continue
                
            averages[adc_channel] = {}
            
            # ROI平均值
            averages[adc_channel]['y_full_avg'] = self._calculate_mean(results[adc_channel]['ys_full'])
            averages[adc_channel]['y_avg'] = self._calculate_mean(results[adc_channel]['ys'])
            averages[adc_channel]['mag_avg_linear'] = self._calculate_mean(results[adc_channel]['mags'])
            averages[adc_channel]['mag_avg_db'] = 20 * np.log10(averages[adc_channel]['mag_avg_linear'])
        
            # 差分平均值
            averages[adc_channel]['y_d_full_avg'] = self._calculate_mean(results[adc_channel]['ys_d_full'])
            averages[adc_channel]['y_d_avg'] = self._calculate_mean(results[adc_channel]['ys_d'])
            averages[adc_channel]['mag_d_avg_linear'] = self._calculate_mean(results[adc_channel]['mags_d'])
            averages[adc_channel]['mag_d_avg_db'] = 20 * np.log10(averages[adc_channel]['mag_d_avg_linear'])
        
            # 复数FFT平均值
            averages[adc_channel]['avg_Xd'] = results[adc_channel]['sum_Xd'] / results['success_count']
        
        return averages

    def _calculate_mean(self, arrays: List[np.ndarray]) -> np.ndarray:
        """计算数组列表的平均值"""
        if not arrays:
            return np.array([], dtype=np.float64)
        
        total = arrays[0].astype(np.float64)
        count = 1
        
        for arr in arrays[1:]:
            total += arr.astype(np.float64)
            count += 1
        
        return total / count

    def _perform_edge_analysis(self, final_results: Dict[str, Any], averages: Dict[str, Any]):
        """执行边沿分析"""
        self.progress.emit(
            self._get_total_segment_count(), 
            self._get_total_segment_count(), 
            "进行边沿分析..."
        )
        self.log_message.emit("进行边沿分析...", "INFO")
        
        for adc_channel in ['adc1', 'adc2']:
            if adc_channel not in averages or 'y_full_avg' not in averages[adc_channel]:
                self.log_message.emit(f"通道 {adc_channel.upper()} 没有平均值数据，跳过边沿分析", "INFO")
                continue
                
            try:
                if len(averages[adc_channel]['y_full_avg']) == 0:
                    self.log_message.emit(f"通道 {adc_channel.upper()} 的平均值数据为空，跳过边沿分析", "WARNING")
                    continue
                    
                edge_results = self.analyzer.analyze_edges(averages[adc_channel]['y_full_avg'])
                self._add_time_metrics_to_edge_results(edge_results)
                final_results[adc_channel].update(edge_results)
                    
            except Exception as e:
                self._handle_edge_analysis_error(e, final_results[adc_channel])

    def _add_time_metrics_to_edge_results(self, edge_results: Dict[str, Any]):
        """为边沿分析结果添加时间指标"""
        if 'first_rise_pos' in edge_results and edge_results['first_rise_pos'] is not None:
            edge_results['first_rise_pos_time'] = edge_results['first_rise_pos'] * self.config.ts_eff * 1e6
        if 'second_rise_pos' in edge_results and edge_results['second_rise_pos'] is not None:
            edge_results['second_rise_pos_time'] = edge_results['second_rise_pos'] * self.config.ts_eff * 1e6
        if 'fall_pos' in edge_results and edge_results['fall_pos'] is not None:
            edge_results['fall_pos_time'] = edge_results['fall_pos'] * self.config.ts_eff * 1e6

    def _handle_edge_analysis_error(self, error: Exception, final_results: Dict[str, Any]):
        """处理边沿分析错误"""
        error_msg = f"边沿分析失败: {str(error)}，将继续处理其他数据"
        self.log_message.emit(error_msg, "WARNING")
        final_results.update({
            'first_rise_pos': None, 'second_rise_pos': None, 'fall_pos': None,
            'first_rise_pos_time': None, 'second_rise_pos_time': None, 'fall_pos_time': None
        })

    def _log_segment_error(self, file_idx: int, segment_idx: int, 
                          adc1_file_info: Optional[Dict], adc2_file_info: Optional[Dict], error: Exception):
        """记录段处理错误"""
        adc1_name = os.path.basename(adc1_file_info['path']) if adc1_file_info else "无文件"
        adc2_name = os.path.basename(adc2_file_info['path']) if adc2_file_info else "无文件"
        
        self.log_message.emit(
            f"处理文件{file_idx}段{segment_idx} ADC1={adc1_name}, ADC2={adc2_name} 失败: {str(error)}", 
            "WARNING"
        )

    def _handle_error(self, error: Exception):
        """处理运行错误"""
        error_msg = f"ADC数据处理失败: {str(error)}"
        self.log_message.emit(error_msg, "ERROR")
        self.error.emit(error_msg)

    def _cleanup(self):
        """清理资源"""
        self.running = False
        self._should_stop = False
        if hasattr(self, 'cache_manager'):
            self.cache_manager.clear_cache()
        gc.collect()

    def stop(self):
        """停止处理"""
        self._should_stop = True
        self.running = False
