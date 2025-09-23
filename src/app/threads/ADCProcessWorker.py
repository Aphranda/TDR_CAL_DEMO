# src/app/threads/ADCProcessWorker.py

import os
import gc
import numpy as np
from PyQt5.QtCore import QObject, pyqtSignal, pyqtSlot

from typing import Optional, Tuple, Dict, Any, Generator, List

from app.core.DataAnalyze import DataAnalyzer, AnalysisConfig
from app.core.FileManager import FileManager


class ADCProcessWorker(QObject):
    """ADC数据处理工作线程 - 支持双通道(adc1和adc2)处理和多段数据处理"""
    progress = pyqtSignal(int, int, str)
    finished = pyqtSignal(dict, dict)  # 传递结果和平均值
    error = pyqtSignal(str)
    log_message = pyqtSignal(str, str)
  
    def __init__(self, file_dict: Dict[str, List[Dict]], config: AnalysisConfig):
        super().__init__()
        self.file_dict = file_dict  # 字典格式 {'adc1': [file_info1, file_info2], 'adc2': [...]}
        self.config = config
        self.analyzer = DataAnalyzer(config)
        self.running = False
        self._should_stop = False
        
        # 设置可追溯的线程名称
        adc1_count = len(file_dict.get('adc1', []))
        adc2_count = len(file_dict.get('adc2', []))
        self.setObjectName(f"双通道数据分析线程_ADC1:{adc1_count}_ADC2:{adc2_count}")

    @pyqtSlot()
    def run(self):
        """执行ADC数据处理 - 主运行函数"""
        self.running = True
        self._should_stop = False
      
        try:
            self._log_start_message()
            
            # 处理所有文件并获取结果
            final_results = self._process_all_files_and_segments()
            
            if final_results is None or final_results['success_count'] == 0:
                raise RuntimeError("没有文件或数据段成功处理")
          
            # 计算平均值
            averages = self._calculate_averages(final_results)
            
            # 进行边沿分析
            self._perform_edge_analysis(final_results, averages)
          
            # 发送完成信号
            self.finished.emit(final_results, averages)
          
        except Exception as e:
            self._handle_error(e)
        finally:
            self._cleanup()

    def _log_start_message(self):
        """记录开始处理的消息"""
        adc1_count = len(self.file_dict.get('adc1', []))
        adc2_count = len(self.file_dict.get('adc2', []))
        
        # 计算总段数
        total_segments = self._get_total_segment_count()
        
        self.log_message.emit(
            f"开始处理 {adc1_count + adc2_count} 个文件，共 {total_segments} 段数据 "
            f"(ADC1: {adc1_count}文件, ADC2: {adc2_count}文件)", 
            "INFO"
        )

    def _get_total_segment_count(self) -> int:
        """获取总段数"""
        total_segments = 0
        for channel in ['adc1', 'adc2']:
            for file_info in self.file_dict.get(channel, []):
                total_segments += file_info.get('segments', 1)
        return int(total_segments/2)

    def _process_all_files_and_segments(self) -> Optional[Dict[str, Any]]:
        """处理所有文件和段并返回结果"""
        results = self._initialize_results()
        
        # 使用生成器处理文件和段
        segment_gen = self._file_segment_generator()
        results_gen = self._process_results_generator(segment_gen, results)
        
        # 处理所有文件和段
        final_results = None
        for results in results_gen:
            final_results = results
            if self._should_stop:
                break
                
        return final_results

    def _initialize_results(self) -> Dict[str, Any]:
        """初始化结果字典 - 支持双通道结构"""
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

    def _file_segment_generator(self) -> Generator[Tuple[int, int, Dict[str, Any]], None, None]:
        """文件和段处理生成器"""
        adc1_files = self.file_dict.get('adc1', [])
        adc2_files = self.file_dict.get('adc2', [])
        
        # 确定要处理的文件数量（取两个通道的最大值）
        file_count = max(len(adc1_files), len(adc2_files))
        
        # 如果两个通道文件数量不同，记录警告
        if len(adc1_files) != len(adc2_files):
            self.log_message.emit(
                f"注意: ADC1和ADC2文件数量不匹配 (ADC1: {len(adc1_files)}, ADC2: {len(adc2_files)})", 
                "WARNING"
            )
        
        segment_counter = 0
        
        for file_idx in range(file_count):
            if self._should_stop:
                break
                
            # 获取当前索引的文件（如果存在）
            adc1_file_info = adc1_files[file_idx] if file_idx < len(adc1_files) else None
            adc2_file_info = adc2_files[file_idx] if file_idx < len(adc2_files) else None
            
            # 确定要处理的段数（取两个文件的最大值）
            adc1_segments = adc1_file_info.get('segments', 1) if adc1_file_info else 0
            adc2_segments = adc2_file_info.get('segments', 1) if adc2_file_info else 0
            segment_count = max(adc1_segments, adc2_segments)
            
            # 如果两个文件的段数不同，记录警告
            if adc1_segments != adc2_segments and adc1_file_info and adc2_file_info:
                self.log_message.emit(
                    f"文件 {file_idx}: ADC1和ADC2段数不匹配 "
                    f"(ADC1: {adc1_segments}, ADC2: {adc2_segments})", 
                    "WARNING"
                )
            
            for segment_idx in range(segment_count):
                if self._should_stop:
                    break
                    
                segment_counter += 1
                
                self._emit_progress(segment_counter, file_idx, segment_idx, adc1_file_info, adc2_file_info)
                
                try:
                    result = self._process_file_segment(adc1_file_info, adc2_file_info, file_idx, segment_idx)
                    if result is not None:
                        yield file_idx, segment_idx, result
                    else:
                        self._log_segment_skip_warning(file_idx, segment_idx, adc1_file_info, adc2_file_info)
                        
                except Exception as e:
                    self._log_segment_error(file_idx, segment_idx, adc1_file_info, adc2_file_info, e)
                    continue

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

    def _process_file_segment(self, adc1_file_info: Optional[Dict], adc2_file_info: Optional[Dict], 
                            file_idx: int, segment_idx: int) -> Optional[Dict[str, Any]]:
        """处理文件段 (adc1和adc2的对应段)，确保数据长度一致"""
        # 加载ADC数据段，允许其中一个为空
        adc1_data = self.load_segment_data(adc1_file_info, segment_idx) if adc1_file_info else None
        adc2_data = self.load_segment_data(adc2_file_info, segment_idx) if adc2_file_info else None
        
        # 检查是否两个通道都为空
        if adc1_data is None and adc2_data is None:
            return None
        
        # 确保两个通道的数据长度一致（如果都存在）
        if adc1_data is not None and adc2_data is not None:
            min_length = min(len(adc1_data), len(adc2_data))
            
            # 如果长度不一致，截取到相同长度
            if len(adc1_data) != len(adc2_data):
                self.log_message.emit(
                    f"文件{file_idx}段{segment_idx}: ADC1和ADC2数据长度不一致 "
                    f"(ADC1: {len(adc1_data)}, ADC2: {len(adc2_data)}), 将截取到最小长度{min_length}", 
                    "WARNING"
                )
                adc1_data = adc1_data[:min_length]
                adc2_data = adc2_data[:min_length]
        
        # 将ADC的数据作为字典传递给处理函数
        adc_data = {}
        if adc1_data is not None:
            adc_data['adc1'] = adc1_data
        if adc2_data is not None:
            adc_data['adc2'] = adc2_data
        
        return self.analyzer.process_single_file(adc_data, file_idx * 1000 + segment_idx)  # 使用唯一ID

    def load_segment_data(self, file_info: Dict, segment_idx: int) -> Optional[np.ndarray]:
        """加载特定段的数据，使用固定段长81920 + 100个点"""
        try:
            file_path = file_info['path']
            segments = file_info.get('segments', 1)
            
            # 检查段索引是否有效
            if segment_idx >= segments:
                self.log_message.emit(
                    f"文件 {os.path.basename(file_path)}: 段索引 {segment_idx} 超出范围 (0-{segments-1})", 
                    "WARNING"
                )
                return None
            
            # 加载整个文件数据
            full_data = self.load_u32_data(file_path)
            if full_data is None:
                return None
            
            # 根据段信息提取特定段的数据
            segment_info = file_info.get('segment_info', {})
            rise_edge_positions = segment_info.get('rise_edge_positions', [])
            segment_details = segment_info.get('segment_details', [])
            
            if rise_edge_positions and segment_details:
                # 使用段详细信息
                if segment_idx < len(segment_details):
                    seg_detail = segment_details[segment_idx]
                    start_idx = seg_detail['start_position']
                    end_idx = seg_detail['end_position']
                    expected_length = seg_detail['expected_length']
                    actual_length = seg_detail['length']
                    
                    # 记录段信息
                    self.log_message.emit(
                        f"文件 {os.path.basename(file_path)} 段 {segment_idx}: "
                        f"起始位置={start_idx}, 结束位置={end_idx}, "
                        f"期望长度={expected_length}, 实际长度={actual_length}", 
                        "DEBUG"
                    )
                else:
                    # 如果没有详细的段信息，使用上升沿位置分段
                    start_idx = rise_edge_positions[segment_idx] if segment_idx < len(rise_edge_positions) else 0
                    # 计算结束位置：起点 + 81920 + 100
                    end_idx = start_idx + 81920 + 100
                    if end_idx > len(full_data):
                        end_idx = len(full_data)
            else:
                # 如果没有上升沿信息，平均分段（使用固定长度）
                segment_length = 81920 + 100  # 固定段长 + 100
                start_idx = segment_idx * segment_length
                end_idx = start_idx + segment_length if segment_idx < segments - 1 else len(full_data)
                
                # 如果超出数组长度，调整到数组末尾
                if end_idx > len(full_data):
                    end_idx = len(full_data)
            
            # 提取段数据
            segment_data = full_data[start_idx:end_idx]
            
            # 记录实际加载的数据长度
            actual_length = len(segment_data)
            self.log_message.emit(
                f"文件 {os.path.basename(file_path)} 段 {segment_idx}: "
                f"加载数据点 {start_idx}-{end_idx} (长度: {actual_length})", 
                "DEBUG"
            )
            
            # 检查数据长度是否符合预期
            expected_min_length = 81920  # 最小需要81920个点
            if actual_length < expected_min_length:
                self.log_message.emit(
                    f"警告: 文件 {os.path.basename(file_path)} 段 {segment_idx} "
                    f"数据长度不足 (期望至少{expected_min_length}, 实际{actual_length})", 
                    "WARNING"
                )
            
            return segment_data
            
        except Exception as e:
            self.log_message.emit(
                f"加载文件段失败 {os.path.basename(file_info['path'])} 段 {segment_idx}: {str(e)}", 
                "ERROR"
            )
            return None


    def _log_segment_skip_warning(self, file_idx: int, segment_idx: int, 
                                adc1_file_info: Optional[Dict], adc2_file_info: Optional[Dict]):
        """记录段跳过警告"""
        adc1_name = os.path.basename(adc1_file_info['path']) if adc1_file_info else "无文件"
        adc2_name = os.path.basename(adc2_file_info['path']) if adc2_file_info else "无文件"
        
        self.log_message.emit(
            f"文件{file_idx}段{segment_idx} ADC1={adc1_name}, ADC2={adc2_name} 处理失败，跳过", 
            "WARNING"
        )

    def _log_segment_error(self, file_idx: int, segment_idx: int, 
                          adc1_file_info: Optional[Dict], adc2_file_info: Optional[Dict], error: Exception):
        """记录段处理错误"""
        adc1_name = os.path.basename(adc1_file_info['path']) if adc1_file_info else "无文件"
        adc2_name = os.path.basename(adc2_file_info['path']) if adc2_file_info else "无文件"
        
        self.log_message.emit(
            f"处理文件{file_idx}段{segment_idx} ADC1={adc1_name}, ADC2={adc2_name} 失败: {str(error)}", 
            "WARNING"
        )

    def _process_results_generator(self, segment_gen: Generator, results: Dict[str, Any]) -> Generator[Dict[str, Any], None, None]:
        """处理结果生成器，累积计算结果"""
        for file_idx, segment_idx, res in segment_gen:
            self._update_results_with_segment_data(results, res)
            
            # 定期清理内存
            if results['success_count'] % 10 == 0:
                self._cleanup_memory()
                
            yield results

    def _update_results_with_segment_data(self, results: Dict[str, Any], segment_result: Dict[str, Any]):
        """使用段结果更新总结果"""
        # 假设 segment_result 是一个嵌套字典，包含 'adc1' 和 'adc2' 键
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
                
                # 存储结果 - 使用内存友好的方式
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

    def _cleanup_memory(self):
        """定期清理内存"""
        gc.collect()

    def _calculate_averages(self, results: Dict[str, Any]) -> Dict[str, Any]:
        """计算平均值 - 使用内存友好的方式，支持双通道和单通道处理"""
        self._emit_calculating_averages()
        
        averages = {}
        
        # 为每个通道计算平均值（只处理有数据的通道）
        for adc_channel in ['adc1', 'adc2']:
            # 检查通道是否有数据
            if not results[adc_channel]['ys_full']:
                self.log_message.emit(
                    f"通道 {adc_channel.upper()} 没有数据，跳过平均值计算", 
                    "INFO"
                )
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

    def _emit_calculating_averages(self):
        """发射计算平均值的进度信号"""
        self.progress.emit(
            self._get_total_segment_count(), 
            self._get_total_segment_count(), 
            "计算平均值..."
        )
        self.log_message.emit("计算平均值...", "INFO")

    def _calculate_mean(self, arrays: List[np.ndarray]) -> np.ndarray:
        """计算数组列表的平均值"""
        if not arrays:
            # 返回一个空的numpy数组，而不是None
            return np.array([], dtype=np.float64)
        
        total = arrays[0].astype(np.float64)
        count = 1
        
        for arr in arrays[1:]:
            total += arr.astype(np.float64)
            count += 1
        
        return total / count

    def _perform_edge_analysis(self, final_results: Dict[str, Any], averages: Dict[str, Any]):
        """执行边沿分析 - 对每个有数据的通道分别进行"""
        self._emit_edge_analysis_progress()
        
        for adc_channel in ['adc1', 'adc2']:
            # 检查通道是否有平均值数据
            if adc_channel not in averages or 'y_full_avg' not in averages[adc_channel]:
                self.log_message.emit(
                    f"通道 {adc_channel.upper()} 没有平均值数据，跳过边沿分析", 
                    "INFO"
                )
                continue
                
            try:
                # 检查平均值数据是否为空
                if len(averages[adc_channel]['y_full_avg']) == 0:
                    self.log_message.emit(
                        f"通道 {adc_channel.upper()} 的平均值数据为空，跳过边沿分析", 
                        "WARNING"
                    )
                    continue
                    
                edge_results = self.analyzer.analyze_edges(averages[adc_channel]['y_full_avg'])
                self._add_time_metrics_to_edge_results(edge_results)
                final_results[adc_channel].update(edge_results)
                    
            except Exception as e:
                self._handle_edge_analysis_error(e, final_results[adc_channel])

    def _emit_edge_analysis_progress(self):
        """发射边沿分析进度信号"""
        self.progress.emit(
            self._get_total_segment_count(), 
            self._get_total_segment_count(), 
            "进行边沿分析..."
        )
        self.log_message.emit("进行边沿分析...", "INFO")

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

    def _handle_error(self, error: Exception):
        """处理运行错误"""
        error_msg = f"ADC数据处理失败: {str(error)}"
        self.log_message.emit(error_msg, "ERROR")
        self.error.emit(error_msg)

    def _cleanup(self):
        """清理资源"""
        self.running = False
        self._should_stop = False
        gc.collect()

    def stop(self):
        """停止处理"""
        self._should_stop = True
        self.running = False

    def load_u32_data(self, path: str) -> np.ndarray:
        """从文件加载uint32数据，支持文本和二进制格式"""
        file_manager = FileManager()
        
        # 检测文件格式
        file_format = file_manager.detect_file_format(path)
        
        if file_format == 'binary':
            return self._load_binary_data(path, file_manager)
        else:
            return file_manager.load_u32_text_first_col(path, skip_first=self.config.skip_first_value)

    def _load_binary_data(self, path: str, file_manager: FileManager) -> np.ndarray:
        """加载二进制数据，尝试不同格式"""
        for data_type in ['uint32', 'int32', 'float32']:
            try:
                data = file_manager.load_binary_data(path, data_type=data_type)
                message = f"成功以{data_type}格式加载二进制文件: {os.path.basename(path)}"
                self.log_message.emit(message, "INFO")
                return data.astype(np.uint32)
            except Exception:
                continue
        
        raise ValueError(f"无法解析二进制文件: {os.path.basename(path)}")
