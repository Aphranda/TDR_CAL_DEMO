# src/app/threads/ADCProcessWorker.py

import os
import gc
import numpy as np
from PyQt5.QtCore import QObject, pyqtSignal, pyqtSlot
from typing import Optional, Tuple, Dict, Any, List

from app.core.DataAnalyze import DataAnalyzer, AnalysisConfig
from app.core.DataCacheManager import DataCacheManager
from app.core.PerformanceMonitor import timeit, performance_monitor


class ADCProcessWorker(QObject):
    """ADC数据处理工作线程 - 使用分批加载和内存管理优化"""
    
    progress = pyqtSignal(int, int, str)
    finished = pyqtSignal(dict, dict)
    error = pyqtSignal(str)
    log_message = pyqtSignal(str, str)
    
    def __init__(self, file_dict: Dict[str, List[Dict]], config: AnalysisConfig, batch_size: int = 10):
        super().__init__()
        self.file_dict = file_dict
        self.config = config
        self.batch_size = batch_size
        self.analyzer = DataAnalyzer(config)
        self.cache_manager = DataCacheManager(batch_size=batch_size)
        self.running = False
        self._should_stop = False
        
        # 结果存储
        self.final_results = self._initialize_results()
        
        # 设置线程名称
        adc1_count = len(file_dict.get('adc1', []))
        adc2_count = len(file_dict.get('adc2', []))
        self.setObjectName(f"双通道数据分析线程_ADC1:{adc1_count}_ADC2:{adc2_count}_批次:{batch_size}")

    @pyqtSlot()
    def run(self):
        """执行ADC数据处理 - 分批加载版本"""
        self.running = True
        self._should_stop = False
        
        try:
            # 第一步：计算总文件对数和总段数
            self.log_message.emit("开始计算文件信息...", "INFO")
            total_file_pairs, total_segments = self._calculate_total_file_pairs_and_segments()
            
            if total_file_pairs == 0:
                raise RuntimeError("没有找到有效的文件对")
                
            self.log_message.emit(f"共发现 {total_file_pairs} 个文件对，{total_segments} 个数据段", "INFO")
            
            # 第二步：分批处理文件对
            segment_counter = 0
            processed_file_pairs = 0
            
            for batch_start in range(0, total_file_pairs, self.batch_size):
                if self._should_stop:
                    break
                    
                batch_end = min(batch_start + self.batch_size, total_file_pairs)
                self.log_message.emit(f"处理批次 {batch_start//self.batch_size + 1}/{(total_file_pairs + self.batch_size - 1)//self.batch_size}", "INFO")
                
                for file_idx in range(batch_start, batch_end):
                    if self._should_stop:
                        break
                        
                    processed_file_pairs += 1
                    
                    # 获取文件对信息
                    adc1_file_info = self._get_file_info('adc1', file_idx)
                    adc2_file_info = self._get_file_info('adc2', file_idx)
                    
                    # 加载文件数据
                    adc1_data = self._load_file_data(adc1_file_info)
                    adc2_data = self._load_file_data(adc2_file_info)
                    
                    # 分割成段
                    adc1_segments = self._segment_file(adc1_file_info, adc1_data)
                    adc2_segments = self._segment_file(adc2_file_info, adc2_data)
                    
                    # 处理段数据
                    segment_count = self._process_file_segments(
                        file_idx, adc1_segments, adc2_segments, 
                        adc1_file_info, adc2_file_info, segment_counter, total_segments
                    )
                    segment_counter += segment_count
                    
                    # 释放文件内存
                    self._release_file_data(adc1_file_info)
                    self._release_file_data(adc2_file_info)
                    
                    # 强制垃圾回收
                    gc.collect()
            
            if self._should_stop:
                self.log_message.emit("处理被用户中断", "WARNING")
                return
            
            # 第三步：计算平均值和边沿分析
            if self.final_results['success_count'] == 0:
                raise RuntimeError("没有数据段成功处理")
            
            averages = self._calculate_averages()
            self._perform_edge_analysis(averages)
            
            # 发送完成信号
            self.finished.emit(self.final_results, averages)
            
        except Exception as e:
            self._handle_error(e)
        finally:
            self._cleanup()

    def _calculate_total_file_pairs_and_segments(self) -> Tuple[int, int]:
        """计算总文件对数和总段数"""
        adc1_files = self.file_dict.get('adc1', [])
        adc2_files = self.file_dict.get('adc2', [])
        total_file_pairs = max(len(adc1_files), len(adc2_files))
        
        total_segments = 0
        for file_idx in range(total_file_pairs):
            adc1_file_info = self._get_file_info('adc1', file_idx)
            adc2_file_info = self._get_file_info('adc2', file_idx)
            
            segments_adc1 = adc1_file_info.get('segments', 1) if adc1_file_info else 0
            segments_adc2 = adc2_file_info.get('segments', 1) if adc2_file_info else 0
            total_segments += max(segments_adc1, segments_adc2)
        
        return total_file_pairs, total_segments

    def _get_file_info(self, channel: str, index: int) -> Optional[Dict]:
        """获取指定通道和索引的文件信息"""
        channel_files = self.file_dict.get(channel, [])
        if index < len(channel_files):
            return channel_files[index]
        return None

    def _load_file_data(self, file_info: Optional[Dict]) -> Optional[np.ndarray]:
        """加载文件数据"""
        if file_info is None:
            return None
            
        try:
            file_path = file_info['path']
            self.log_message.emit(f"加载文件: {os.path.basename(file_path)}", "DEBUG")
            return self.cache_manager.load_single_file(file_path)
        except Exception as e:
            self.log_message.emit(f"加载文件失败 {file_info.get('path', '未知')}: {str(e)}", "WARNING")
            return None

    def _segment_file(self, file_info: Optional[Dict], file_data: Optional[np.ndarray]) -> List[np.ndarray]:
        """分割文件数据成段"""
        if file_info is None or file_data is None:
            return []
            
        try:
            return self.cache_manager.pre_segment_single_file(file_info, file_data)
        except Exception as e:
            self.log_message.emit(f"分割文件失败 {file_info.get('path', '未知')}: {str(e)}", "WARNING")
            return []

    def _process_file_segments(self, file_idx: int, adc1_segments: List[np.ndarray], 
                             adc2_segments: List[np.ndarray], adc1_file_info: Optional[Dict],
                             adc2_file_info: Optional[Dict], start_segment_counter: int, 
                             total_segments: int) -> int:
        """处理文件的所有段"""
        segment_count = max(len(adc1_segments), len(adc2_segments))
        processed_segments = 0
        
        for segment_idx in range(segment_count):
            if self._should_stop:
                break
                
            current_segment = start_segment_counter + processed_segments + 1
            
            # 获取段数据
            adc1_segment_data = adc1_segments[segment_idx] if segment_idx < len(adc1_segments) else None
            adc2_segment_data = adc2_segments[segment_idx] if segment_idx < len(adc2_segments) else None
            
            # 发射进度信号
            self._emit_progress(current_segment, total_segments, file_idx, segment_idx, 
                              adc1_file_info, adc2_file_info)
            
            print("segment_idx:",segment_idx)
            # 处理段数据
            if self._process_segment(adc1_segment_data, adc2_segment_data, file_idx, segment_idx):
                processed_segments += 1
        
        return processed_segments

    def _process_segment(self, adc1_data: Optional[np.ndarray], adc2_data: Optional[np.ndarray], 
                        file_idx: int, segment_idx: int) -> bool:
        """处理单个段数据"""
        # 构建adc_data字典
        adc_data = {}
        if adc1_data is not None:
            adc_data['adc1'] = adc1_data
        if adc2_data is not None:
            adc_data['adc2'] = adc2_data
        
        if not adc_data:
            return False
        
        try:
            segment_result = self.analyzer.process_single_file(adc_data, file_idx * 1000 + segment_idx)
            self._update_results_with_segment_data(segment_result)
            return True
        except Exception as e:
            self._log_segment_error(file_idx, segment_idx, adc1_data is not None, adc2_data is not None, e)
            return False

    def _emit_progress(self, current_segment: int, total_segments: int, file_idx: int, 
                      segment_idx: int, adc1_file_info: Optional[Dict], adc2_file_info: Optional[Dict]):
        """发射进度信号"""
        adc1_name = os.path.basename(adc1_file_info['path']) if adc1_file_info else "无文件"
        adc2_name = os.path.basename(adc2_file_info['path']) if adc2_file_info else "无文件"
        
        progress_text = f"处理文件{file_idx}段{segment_idx}: ADC1={adc1_name}, ADC2={adc2_name}"
        self.progress.emit(current_segment, total_segments, progress_text)

    def _release_file_data(self, file_info: Optional[Dict]):
        """释放文件数据内存"""
        if file_info is None:
            return
            
        try:
            file_path = file_info['path']
            self.cache_manager.release_file(file_path)
        except Exception as e:
            self.log_message.emit(f"释放文件内存失败 {file_info.get('path', '未知')}: {str(e)}", "DEBUG")

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
            'total_segments': 0,
        }

    def _update_results_with_segment_data(self, segment_result: Dict[str, Any]):
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
                if self.final_results[adc_channel]['freq_ref'] is None:
                    self.final_results[adc_channel]['freq_ref'] = freq
                if self.final_results[adc_channel]['freq_d_ref'] is None:
                    self.final_results[adc_channel]['freq_d_ref'] = freq_d
                    self.final_results[adc_channel]['sum_Xd'] = np.zeros_like(Xd_norm, dtype=np.complex128)
                
                # 存储结果
                self.final_results[adc_channel]['ys_full'].append(self._optimize_array(y_full))
                self.final_results[adc_channel]['ys'].append(self._optimize_array(y_roi))
                self.final_results[adc_channel]['mags'].append(self._optimize_array(mag_linear))
                self.final_results[adc_channel]['ys_d_full'].append(self._optimize_array(y_full_diff))
                self.final_results[adc_channel]['ys_d'].append(self._optimize_array(y_diff))
                self.final_results[adc_channel]['mags_d'].append(self._optimize_array(mag_linear_d))
                self.final_results[adc_channel]['sum_Xd'] += Xd_norm
        
        self.final_results['success_count'] += 1

    def _optimize_array(self, array: np.ndarray) -> np.ndarray:
        """优化数组内存使用"""
        if array.dtype == np.float64:
            return array.astype(np.float32)
        elif array.dtype == np.uint32 and np.max(array) < 65536:
            return array.astype(np.uint16)
        return array

    def _calculate_averages(self) -> Dict[str, Any]:
        """计算平均值"""
        self.log_message.emit("计算平均值...", "INFO")

        # 保存所有y_full数据用于抖动分析（使用numpy二进制格式）
        self._save_y_full_for_jitter_analysis()
        
        averages = {}
        
        for adc_channel in ['adc1', 'adc2']:
            if not self.final_results[adc_channel]['ys_full']:
                self.log_message.emit(f"通道 {adc_channel.upper()} 没有数据，跳过平均值计算", "INFO")
                continue
                
            averages[adc_channel] = {}
            
            # ROI平均值
            averages[adc_channel]['y_full_avg'] = self._calculate_mean(self.final_results[adc_channel]['ys_full'])
            averages[adc_channel]['y_avg'] = self._calculate_mean(self.final_results[adc_channel]['ys'])
            averages[adc_channel]['mag_avg_linear'] = self._calculate_mean(self.final_results[adc_channel]['mags'])
            averages[adc_channel]['mag_avg_db'] = 20 * np.log10(averages[adc_channel]['mag_avg_linear'])
        
            # 差分平均值
            averages[adc_channel]['y_d_full_avg'] = self._calculate_mean(self.final_results[adc_channel]['ys_d_full'])
            averages[adc_channel]['y_d_avg'] = self._calculate_mean(self.final_results[adc_channel]['ys_d'])
            averages[adc_channel]['mag_d_avg_linear'] = self._calculate_mean(self.final_results[adc_channel]['mags_d'])
            averages[adc_channel]['mag_d_avg_db'] = 20 * np.log10(averages[adc_channel]['mag_d_avg_linear'])
        
            # 复数FFT平均值
            averages[adc_channel]['avg_Xd'] = self.final_results[adc_channel]['sum_Xd'] / self.final_results['success_count']
        
        return averages
    
    def _save_y_full_for_jitter_analysis(self):
        """保存所有y_full数据用于抖动分析 - 使用numpy二进制格式"""
        try:
            import time
            
            # 创建临时目录
            temp_dir = os.path.join(os.path.dirname(__file__), '../../../temp/y_full_jitter_analysis')
            os.makedirs(temp_dir, exist_ok=True)
            
            # 保存ADC1数据
            if self.final_results['adc1']['ys_full']:
                adc1_data = np.array(self.final_results['adc1']['ys_full'])
                adc1_filepath = os.path.join(temp_dir, "adc1_y_full_data.npy")
                np.save(adc1_filepath, adc1_data)
                
                self.log_message.emit(f"保存了 ADC1 y_full数据到 {adc1_filepath}，形状: {adc1_data.shape}", "INFO")
            
            # 保存ADC2数据
            if self.final_results['adc2']['ys_full']:
                adc2_data = np.array(self.final_results['adc2']['ys_full'])
                adc2_filepath = os.path.join(temp_dir, "adc2_y_full_data.npy")
                np.save(adc2_filepath, adc2_data)
                
                self.log_message.emit(f"保存了 ADC2 y_full数据到 {adc2_filepath}，形状: {adc2_data.shape}", "INFO")
            
            # 保存汇总信息
            summary_file = os.path.join(temp_dir, "summary.npz")
            summary_data = {
                'success_count': self.final_results['success_count'],
                'adc1_segment_count': len(self.final_results['adc1']['ys_full']),
                'adc2_segment_count': len(self.final_results['adc2']['ys_full']),
                'ts_eff': self.config.ts_eff,
                'timestamp': time.time()
            }
            np.savez(summary_file, **summary_data)
            
            self.log_message.emit(f"抖动分析数据已保存到 {temp_dir}", "INFO")
            
        except Exception as e:
            self.log_message.emit(f"保存y_full数据用于抖动分析失败: {str(e)}", "WARNING")

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

    def _perform_edge_analysis(self, averages: Dict[str, Any]):
        """执行边沿分析"""

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
                self.final_results[adc_channel].update(edge_results)
                    
            except Exception as e:
                self._handle_edge_analysis_error(e, self.final_results[adc_channel])

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
                          has_adc1: bool, has_adc2: bool, error: Exception):
        """记录段处理错误"""
        adc1_status = "有文件" if has_adc1 else "无文件"
        adc2_status = "有文件" if has_adc2 else "无文件"
        
        self.log_message.emit(
            f"处理文件{file_idx}段{segment_idx} ADC1={adc1_status}, ADC2={adc2_status} 失败: {str(error)}", 
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
