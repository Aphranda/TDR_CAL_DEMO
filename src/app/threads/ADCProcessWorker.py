# src/app/threads/ADCProcessWorker.py

import os
import gc
import numpy as np
from PyQt5.QtCore import QObject, pyqtSignal, pyqtSlot

from typing import Optional, Tuple, Dict, Any, Generator, List

from app.core.DataAnalyze import DataAnalyzer, AnalysisConfig
from app.core.FileManager import FileManager
from app.core.PerformanceMonitor import timeit, performance_monitor


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

        # 文件数据缓存 - 关键优化
        self._file_data_cache = {}  # {file_path: (data, timestamp)}
        self._file_format_cache = {}  # {file_path: format}
        self._cache_hits = 0
        self._cache_misses = 0

    @pyqtSlot()
    def run(self):
        """执行ADC数据处理 - 优化版本"""
        self.running = True
        self._should_stop = False
      
        try:
            self._log_start_message()
            
            # 关键优化：预加载文件缓存
            self._preload_file_cache()
            
            # 处理所有文件并获取结果
            final_results = self._process_all_files_and_segments_optimized()
            
            if final_results is None or final_results['success_count'] == 0:
                raise RuntimeError("没有文件或数据段成功处理")
          
            # 计算平均值
            averages = self._calculate_averages(final_results)
            
            # 进行边沿分析
            self._perform_edge_analysis(final_results, averages)
            
            # 记录缓存统计
            self._log_cache_statistics()
          
            # 发送完成信号
            self.finished.emit(final_results, averages)
          
        except Exception as e:
            self._handle_error(e)
        finally:
            self._cleanup()
    
    def _process_all_files_and_segments_optimized(self) -> Optional[Dict[str, Any]]:
        """处理所有文件和段 - 优化版本"""
        results = self._initialize_results()
        
        # 使用优化的生成器
        segment_gen = self._optimized_file_segment_generator()
        results_gen = self._process_results_generator(segment_gen, results)
        
        # 处理所有文件和段
        final_results = None
        for results in results_gen:
            final_results = results
            if self._should_stop:
                break
                
        return final_results
    
    def _optimized_file_segment_generator(self) -> Generator[Tuple[int, int, Dict[str, Any]], None, None]:
        """优化的文件和段处理生成器"""
        adc1_files = self.file_dict.get('adc1', [])
        adc2_files = self.file_dict.get('adc2', [])
        
        file_count = max(len(adc1_files), len(adc2_files))
        segment_counter = 0
        
        # 预计算总段数
        total_segments = self._get_total_segment_count()
        
        for file_idx in range(file_count):
            if self._should_stop:
                break
                
            adc1_file_info = adc1_files[file_idx] if file_idx < len(adc1_files) else None
            adc2_file_info = adc2_files[file_idx] if file_idx < len(adc2_files) else None
            
            segment_count = self._get_file_segment_count(adc1_file_info, adc2_file_info)
            
            for segment_idx in range(segment_count):
                if self._should_stop:
                    break
                    
                segment_counter += 1
                
                # 优化进度更新频率
                if segment_counter % 10 == 0 or segment_counter == total_segments:
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

    def _get_file_segment_count(self, adc1_file_info: Optional[Dict], adc2_file_info: Optional[Dict]) -> int:
        """
        获取文件对的段数
        
        Args:
            adc1_file_info: ADC1文件信息字典
            adc2_file_info: ADC2文件信息字典
            
        Returns:
            需要处理的段数
        """
        # 如果两个文件都存在，取最大段数
        if adc1_file_info and adc2_file_info:
            adc1_segments = adc1_file_info.get('segments', 1)
            adc2_segments = adc2_file_info.get('segments', 1)
            
            # 如果段数不同，记录警告
            if adc1_segments != adc2_segments:
                adc1_name = os.path.basename(adc1_file_info['path'])
                adc2_name = os.path.basename(adc2_file_info['path'])
                self.log_message.emit(
                    f"文件段数不匹配: {adc1_name}({adc1_segments}段) vs {adc2_name}({adc2_segments}段), "
                    f"将处理最大段数 {max(adc1_segments, adc2_segments)}", 
                    "WARNING"
                )
            
            return max(adc1_segments, adc2_segments)
        
        # 如果只有一个文件存在，使用该文件的段数
        elif adc1_file_info:
            return adc1_file_info.get('segments', 1)
        
        elif adc2_file_info:
            return adc2_file_info.get('segments', 1)
        
        # 两个文件都不存在，返回0
        else:
            return 0
    
    def _log_cache_statistics(self):
        """记录缓存统计信息"""
        cache_hit_rate = self._cache_hits / (self._cache_hits + self._cache_misses) if (self._cache_hits + self._cache_misses) > 0 else 0
        self.log_message.emit(
            f"文件缓存统计: 命中{self._cache_hits}次, 未命中{self._cache_misses}次, 命中率{cache_hit_rate:.1%}", 
            "INFO"
        )

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

    def _preload_file_cache(self):
        """预加载文件数据到缓存 - 大幅减少重复I/O"""
        self.log_message.emit("预加载文件数据到缓存...", "INFO")
        
        all_files = set()
        for channel in ['adc1', 'adc2']:
            for file_info in self.file_dict.get(channel, []):
                all_files.add(file_info['path'])
        
        total_files = len(all_files)
        loaded_count = 0
        
        for file_path in all_files:
            if self._should_stop:
                break
                
            try:
                # 预加载文件数据到缓存
                if file_path not in self._file_data_cache:
                    data = self._load_file_data_with_cache(file_path)
                    if data is not None:
                        loaded_count += 1
                        
                # 更新进度
                if loaded_count % 5 == 0:
                    self.progress.emit(
                        loaded_count, total_files, 
                        f"预加载文件 {loaded_count}/{total_files}: {os.path.basename(file_path)}"
                    )
                    
            except Exception as e:
                self.log_message.emit(f"预加载文件失败 {os.path.basename(file_path)}: {e}", "WARNING")
                continue
        
        self.log_message.emit(f"文件缓存预加载完成: {loaded_count}/{total_files} 个文件", "INFO")

    def _load_file_data_with_cache(self, file_path: str) -> Optional[np.ndarray]:
        """带缓存的文件数据加载"""
        # 检查缓存
        if file_path in self._file_data_cache:
            self._cache_hits += 1
            return self._file_data_cache[file_path]
        
        self._cache_misses += 1
        
        try:
            # 加载文件数据
            file_manager = FileManager()
            
            # 检测文件格式（带缓存）
            if file_path in self._file_format_cache:
                file_format = self._file_format_cache[file_path]
            else:
                file_format = file_manager.detect_file_format(file_path)
                self._file_format_cache[file_path] = file_format
            
            # 根据格式加载数据
            if file_format == 'binary':
                data = self._load_binary_data_cached(file_path, file_manager)
            else:
                data = file_manager.load_u32_text_first_col(
                    file_path, skip_first=self.config.skip_first_value
                )
            
            # 存入缓存
            if data is not None:
                self._file_data_cache[file_path] = data
            
            return data
            
        except Exception as e:
            self.log_message.emit(f"加载文件数据失败 {os.path.basename(file_path)}: {e}", "ERROR")
            return None
    
    def _load_binary_data_cached(self, path: str, file_manager: FileManager) -> np.ndarray:
        """带缓存的二进制数据加载"""
        for data_type in ['uint32', 'int32', 'float32']:
            try:
                data = file_manager.load_binary_data(path, data_type=data_type)
                self.log_message.emit(
                    f"成功以{data_type}格式加载二进制文件: {os.path.basename(path)}", 
                    "DEBUG"
                )
                return data.astype(np.uint32)
            except Exception:
                continue
        
        raise ValueError(f"无法解析二进制文件: {os.path.basename(path)}")


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

    @timeit
    def _process_file_segment(self, adc1_file_info: Optional[Dict], adc2_file_info: Optional[Dict], 
                            file_idx: int, segment_idx: int) -> Optional[Dict[str, Any]]:
        """处理文件段 - 优化版本"""
        # 并行加载两个通道的数据
        adc1_data, adc2_data = self._load_dual_channel_data(
            adc1_file_info, adc2_file_info, segment_idx
        )
        
        # 检查是否两个通道都为空
        if adc1_data is None and adc2_data is None:
            return None
        
        # 同步数据长度
        adc1_data, adc2_data = self._synchronize_channel_lengths(adc1_data, adc2_data, file_idx, segment_idx)
        
        # 准备数据字典
        adc_data = {}
        if adc1_data is not None:
            adc_data['adc1'] = adc1_data
        if adc2_data is not None:
            adc_data['adc2'] = adc2_data
        
        # 处理数据
        return self.analyzer.process_single_file(adc_data, file_idx * 1000 + segment_idx)
    
    def _load_dual_channel_data(self, adc1_file_info: Optional[Dict], adc2_file_info: Optional[Dict], 
                               segment_idx: int) -> Tuple[Optional[np.ndarray], Optional[np.ndarray]]:
        """并行加载双通道数据"""
        adc1_data = None
        adc2_data = None
        
        # 可以在这里添加并行加载逻辑
        # 但由于Python GIL限制，简单的顺序加载可能更快
        if adc1_file_info:
            adc1_data = self.load_segment_data(adc1_file_info, segment_idx)
        
        if adc2_file_info:
            adc2_data = self.load_segment_data(adc2_file_info, segment_idx)
        
        return adc1_data, adc2_data
    
    def _synchronize_channel_lengths(self, adc1_data: Optional[np.ndarray], adc2_data: Optional[np.ndarray],
                                   file_idx: int, segment_idx: int) -> Tuple[Optional[np.ndarray], Optional[np.ndarray]]:
        """同步双通道数据长度"""
        if adc1_data is not None and adc2_data is not None:
            min_length = min(len(adc1_data), len(adc2_data))
            
            if len(adc1_data) != len(adc2_data):
                self.log_message.emit(
                    f"文件{file_idx}段{segment_idx}: 通道长度不一致 "
                    f"(ADC1: {len(adc1_data)}, ADC2: {len(adc2_data)}), 截取到{min_length}", 
                    "WARNING"
                )
                adc1_data = adc1_data[:min_length]
                adc2_data = adc2_data[:min_length]
        
        return adc1_data, adc2_data

    @timeit
    def load_segment_data(self, file_info: Dict, segment_idx: int) -> Optional[np.ndarray]:
        """加载特定段的数据 - 优化版本，使用缓存"""
        if file_info is None:
            return None
            
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
            
            # 从缓存获取文件数据
            full_data = self._load_file_data_with_cache(file_path)
            if full_data is None:
                return None
            
            # 计算段边界
            start_idx, end_idx, expected_length = self._calculate_segment_boundaries(
                file_info, segment_idx, len(full_data)
            )
            
            # 提取段数据
            segment_data = full_data[start_idx:end_idx]
            actual_length = len(segment_data)
            

            # 检查数据长度
            if actual_length < expected_length:
                self.log_message.emit(
                    f"警告: 文件 {os.path.basename(file_path)} 段 {segment_idx} "
                    f"数据长度不足 (期望:{expected_length}, 实际:{actual_length})", 
                    "WARNING"
                )
            
            return segment_data
            
        except Exception as e:
            self.log_message.emit(
                f"加载文件段失败 {os.path.basename(file_info['path'])} 段 {segment_idx}: {str(e)}", 
                "ERROR"
            )
            return None
    
    def _calculate_segment_boundaries(self, file_info: Dict, segment_idx: int, total_length: int) -> Tuple[int, int, int]:
        """计算段边界 - 优化版本"""
        file_path = file_info['path']
        segments = file_info.get('segments', 1)
        
        # 使用段详细信息（如果可用）
        segment_info = file_info.get('segment_info', {})
        rise_edge_positions = segment_info.get('rise_edge_positions', [])
        segment_details = segment_info.get('segment_details', [])
        
        if segment_details and segment_idx < len(segment_details):
            # 使用预计算的段信息
            seg_detail = segment_details[segment_idx]
            start_idx = seg_detail['start_position']
            end_idx = seg_detail['end_position']
            expected_length = seg_detail['expected_length']
        elif rise_edge_positions and segment_idx < len(rise_edge_positions):
            # 使用上升沿位置
            start_idx = rise_edge_positions[segment_idx]
            expected_length = 81920 + 100  # 固定段长 + 100
            end_idx = min(start_idx + expected_length, total_length)
        else:
            # 平均分段
            segment_length = 81920 + 100
            start_idx = segment_idx * segment_length
            end_idx = start_idx + segment_length if segment_idx < segments - 1 else total_length
            expected_length = min(segment_length, total_length - start_idx)
        
        # 确保不超出数组边界
        end_idx = min(end_idx, total_length)
        expected_length = min(expected_length, end_idx - start_idx)
        
        return start_idx, end_idx, expected_length


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
