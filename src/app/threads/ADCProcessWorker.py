# src/app/widgets/DataAnalysisPanel/Controller.py
import os
import gc
import numpy as np
from PyQt5.QtCore import QObject, pyqtSignal, pyqtSlot

from typing import Optional, Tuple, Dict, Any, Generator, List

from app.core.DataAnalyze import DataAnalyzer, AnalysisConfig
from app.core.FileManager import FileManager


class ADCProcessWorker(QObject):
    """ADC数据处理工作线程 - 使用生成器优化内存"""
    progress = pyqtSignal(int, int, str)
    finished = pyqtSignal(dict, dict)  # 传递结果和平均值
    error = pyqtSignal(str)
    log_message = pyqtSignal(str, str)
  
    def __init__(self, file_list: List[str], config: AnalysisConfig):
        super().__init__()
        self.file_list = file_list
        self.config = config
        self.analyzer = DataAnalyzer(config)
        self.running = False
        self._should_stop = False
        
        # 设置可追溯的线程名称
        file_count = len(file_list)
        first_file = os.path.basename(file_list[0]) if file_list else "no_files"
        self.setObjectName(f"数据分析线程_{first_file}_{file_count}files")

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
        self.log_message.emit(f"开始处理 {len(self.file_list)} 个文件", "INFO")

    def _process_all_files(self) -> Optional[Dict[str, Any]]:
        """处理所有文件并返回结果"""
        results = self._initialize_results()
        
        # 使用生成器处理文件
        file_gen = self._file_processor_generator()
        results_gen = self._process_results_generator(file_gen, results)
        
        # 处理所有文件
        final_results = None
        for results in results_gen:
            final_results = results
            if self._should_stop:
                break
                
        return final_results

    def _initialize_results(self) -> Dict[str, Any]:
        """初始化结果字典"""
        return {
            'ys_full': [], 'ys': [], 'mags': [],
            'ys_d_full': [], 'ys_d': [], 'mags_d': [],
            'freq_ref': None, 'freq_d_ref': None, 'sum_Xd': None,
            'success_count': 0, 'total_files': len(self.file_list),
        }

    def _file_processor_generator(self) -> Generator[Tuple[int, Dict[str, Any]], None, None]:
        """文件处理生成器，逐文件产生处理结果"""
        for i, file_path in enumerate(self.file_list):
            if self._should_stop:
                break
                
            self._emit_progress(i, file_path)
            
            try:
                result = self._process_single_file(file_path, i)
                if result is not None:
                    yield i, result
                else:
                    self._log_file_skip_warning(file_path)
                    
            except Exception as e:
                self._log_file_error(file_path, e)
                continue

    def _emit_progress(self, index: int, file_path: str):
        """发射进度信号"""
        self.progress.emit(
            index + 1, 
            len(self.file_list), 
            f"处理文件: {os.path.basename(file_path)}"
        )

    def _process_single_file(self, file_path: str, index: int) -> Optional[Dict[str, Any]]:
        """处理单个文件"""
        raw_data = self.load_u32_data(file_path)
        return self.analyzer.process_single_file(raw_data, index)

    def _log_file_skip_warning(self, file_path: str):
        """记录文件跳过警告"""
        self.log_message.emit(
            f"文件 {os.path.basename(file_path)} 处理失败，跳过", 
            "WARNING"
        )

    def _log_file_error(self, file_path: str, error: Exception):
        """记录文件处理错误"""
        self.log_message.emit(
            f"处理文件 {os.path.basename(file_path)} 失败: {str(error)}", 
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
        """使用文件结果更新总结果"""
        # 从字典中提取数据
        y_full = file_result['y_full']
        y_roi = file_result['y_roi']
        freq = file_result['freq']
        mag_linear = file_result['mag_linear']
        y_full_diff = file_result['y_full_diff']
        y_diff = file_result['y_diff']
        freq_d = file_result['freq_d']
        mag_linear_d = file_result['mag_linear_d']
        Xd_norm = file_result['Xd_norm']
        
        # 初始化参考频率
        if results['freq_ref'] is None:
            results['freq_ref'] = freq
        if results['freq_d_ref'] is None:
            results['freq_d_ref'] = freq_d
            results['sum_Xd'] = np.zeros_like(Xd_norm, dtype=np.complex128)
        
        # 存储结果 - 使用内存友好的方式
        results['ys_full'].append(self._optimize_array(y_full))
        results['ys'].append(self._optimize_array(y_roi))
        results['mags'].append(self._optimize_array(mag_linear))
        results['ys_d_full'].append(self._optimize_array(y_full_diff))
        results['ys_d'].append(self._optimize_array(y_diff))
        results['mags_d'].append(self._optimize_array(mag_linear_d))
        results['sum_Xd'] += Xd_norm
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
        """计算平均值 - 使用内存友好的方式"""
        self._emit_calculating_averages()
        
        averages = {}
        
        # ROI平均值
        averages['y_full_avg'] = self._calculate_mean(results['ys_full'])
        averages['y_avg'] = self._calculate_mean(results['ys'])
        averages['mag_avg_linear'] = self._calculate_mean(results['mags'])
        averages['mag_avg_db'] = 20 * np.log10(averages['mag_avg_linear'])
    
        # 差分平均值
        averages['y_d_full_avg'] = self._calculate_mean(results['ys_d_full'])
        averages['y_d_avg'] = self._calculate_mean(results['ys_d'])
        averages['mag_d_avg_linear'] = self._calculate_mean(results['mags_d'])
        averages['mag_d_avg_db'] = 20 * np.log10(averages['mag_d_avg_linear'])
    
        # 复数FFT平均值
        averages['avg_Xd'] = results['sum_Xd'] / results['success_count']
    
        return averages

    def _emit_calculating_averages(self):
        """发射计算平均值的进度信号"""
        self.progress.emit(
            len(self.file_list), 
            len(self.file_list), 
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
        """执行边沿分析"""
        self._emit_edge_analysis_progress()
        
        try:
            edge_results = self.analyzer.analyze_edges(averages['y_full_avg'])
            self._add_time_metrics_to_edge_results(edge_results)
            final_results.update(edge_results)
                
        except Exception as e:
            self._handle_edge_analysis_error(e, final_results)

    def _emit_edge_analysis_progress(self):
        """发射边沿分析进度信号"""
        self.progress.emit(
            len(self.file_list), 
            len(self.file_list), 
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
