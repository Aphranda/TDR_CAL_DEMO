# src/app/threads/ADCProcessWorker.py

import os
import gc
import numpy as np
from PyQt5.QtCore import QObject, pyqtSignal, pyqtSlot

from typing import Optional, Tuple, Dict, Any, Generator, List

from app.core.DataAnalyze import DataAnalyzer, AnalysisConfig
from app.core.FileManager import FileManager


class ADCProcessWorker(QObject):
    """ADC数据处理工作线程 - 支持双通道(adc1和adc2)处理"""
    progress = pyqtSignal(int, int, str)
    finished = pyqtSignal(dict, dict)  # 传递结果和平均值
    error = pyqtSignal(str)
    log_message = pyqtSignal(str, str)
  
    def __init__(self, file_dict: Dict[str, List[str]], config: AnalysisConfig):
        super().__init__()
        self.file_dict = file_dict  # 字典格式 {'adc1': [], 'adc2': []}
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
            final_results = self._process_all_files()
            
            if final_results is None or final_results['success_count'] == 0:
                raise RuntimeError("没有文件成功处理")
          
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
        self.log_message.emit(f"开始处理 {adc1_count + adc2_count} 个文件 (ADC1: {adc1_count}, ADC2: {adc2_count})", "INFO")

    def _process_all_files(self) -> Optional[Dict[str, Any]]:
        """处理所有文件并返回结果"""
        results = self._initialize_results()
        
        # 使用生成器处理文件对
        file_pair_gen = self._file_pair_generator()
        results_gen = self._process_results_generator(file_pair_gen, results)
        
        # 处理所有文件对
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
            'total_files': self._get_total_file_count(),
        }

    def _get_total_file_count(self) -> int:
        """获取总文件数量"""
        adc1_count = len(self.file_dict.get('adc1', []))
        adc2_count = len(self.file_dict.get('adc2', []))
        return adc1_count + adc2_count

    def _file_pair_generator(self) -> Generator[Tuple[int, Dict[str, Any]], None, None]:
        """文件对处理生成器，支持单个ADC通道处理"""
        adc1_files = self.file_dict.get('adc1', [])
        adc2_files = self.file_dict.get('adc2', [])
        
        # 确定要处理的文件数量（取两个通道的最大值）
        file_count = max(len(adc1_files), len(adc2_files))
        
        # 如果两个通道文件数量不同，记录警告
        if len(adc1_files) != len(adc2_files):
            self.log_message.emit(
                f"注意: ADC1和ADC2文件数量不匹配 (ADC1: {len(adc1_files)}, ADC2: {len(adc2_files)})，"
                f"将处理{file_count}个文件", 
                "WARNING"
            )
        
        for i in range(file_count):
            if self._should_stop:
                break
                
            # 获取当前索引的文件（如果存在）
            adc1_file = adc1_files[i] if i < len(adc1_files) else None
            adc2_file = adc2_files[i] if i < len(adc2_files) else None
            
            self._emit_progress(i, adc1_file, adc2_file)
            
            try:
                result = self._process_file_pair(adc1_file, adc2_file, i)
                if result is not None:
                    yield i, result
                else:
                    self._log_file_skip_warning(adc1_file, adc2_file)
                    
            except Exception as e:
                self._log_file_error(adc1_file, adc2_file, e)
                continue


    def _emit_progress(self, index: int, adc1_file: Optional[str], adc2_file: Optional[str]):
        """发射进度信号 - 支持单个ADC通道"""
        adc1_name = os.path.basename(adc1_file) if adc1_file else "无文件"
        adc2_name = os.path.basename(adc2_file) if adc2_file else "无文件"
        
        self.progress.emit(
            index + 1, 
            max(len(self.file_dict.get('adc1', [])), len(self.file_dict.get('adc2', []))), 
            f"处理文件: ADC1={adc1_name}, ADC2={adc2_name}"
        )


    def _process_file_pair(self, adc1_file: str, adc2_file: str, index: int) -> Optional[Dict[str, Any]]:
        """处理文件对 (adc1和adc2) - 支持单个通道处理"""
        # 加载ADC数据，允许其中一个为空
        adc1_data = self.load_u32_data(adc1_file) if adc1_file else None
        adc2_data = self.load_u32_data(adc2_file) if adc2_file else None
        
        # 检查是否两个通道都为空
        if adc1_data is None and adc2_data is None:
            self.log_message.emit(
                f"文件索引 {index}: ADC1和ADC2数据都为空，跳过处理", 
                "WARNING"
            )
            return None
        
        # 将ADC的数据作为字典传递给处理函数
        adc_data = {}
        if adc1_data is not None:
            adc_data['adc1'] = adc1_data
        if adc2_data is not None:
            adc_data['adc2'] = adc2_data
        
        return self.analyzer.process_single_file(adc_data, index)


    def _log_file_skip_warning(self, adc1_file: Optional[str], adc2_file: Optional[str]):
        """记录文件跳过警告 - 支持单个ADC通道"""
        adc1_name = os.path.basename(adc1_file) if adc1_file else "无文件"
        adc2_name = os.path.basename(adc2_file) if adc2_file else "无文件"
        
        self.log_message.emit(
            f"文件 ADC1={adc1_name}, ADC2={adc2_name} 处理失败，跳过", 
            "WARNING"
        )

    def _log_file_error(self, adc1_file: Optional[str], adc2_file: Optional[str], error: Exception):
        """记录文件处理错误 - 支持单个ADC通道"""
        adc1_name = os.path.basename(adc1_file) if adc1_file else "无文件"
        adc2_name = os.path.basename(adc2_file) if adc2_file else "无文件"
        
        self.log_message.emit(
            f"处理文件 ADC1={adc1_name}, ADC2={adc2_name} 失败: {str(error)}", 
            "WARNING"
        )


    def _process_results_generator(self, results_gen: Generator, results: Dict[str, Any]) -> Generator[Dict[str, Any], None, None]:
        """处理结果生成器，累积计算结果"""
        for i, res in results_gen:
            self._update_results_with_file_data(results, res)
            
            # 定期清理内存
            if results['success_count'] % 10 == 0:
                self._cleanup_memory()
                
            yield results

    def _update_results_with_file_data(self, results: Dict[str, Any], file_result: Dict[str, Any]):
        """使用文件结果更新总结果 - 支持嵌套字典结构"""
        # 假设 file_result 是一个嵌套字典，包含 'adc1' 和 'adc2' 键
        for adc_channel in ['adc1', 'adc2']:
            if adc_channel in file_result:
                channel_result = file_result[adc_channel]
                
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
            self._get_total_file_count(), 
            self._get_total_file_count(), 
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
            self._get_total_file_count(), 
            self._get_total_file_count(), 
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
