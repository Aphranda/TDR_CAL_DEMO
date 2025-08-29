# src/app/widgets/DataAnalysisPanel/Controller.py
import os
import numpy as np
import pyqtgraph as pg
from PyQt5.QtWidgets import QFileDialog, QMessageBox
from PyQt5.QtCore import QObject, pyqtSignal, QThread, pyqtSlot
from ...core.DataAnalyze import DataAnalyzer, AnalysisConfig
from ...core.FileManager import FileManager
from ...widgets.PlotWidget import create_plot_widget
import time
from typing import Optional, Tuple, Dict, Any


# 搜索方法枚举
class SearchMethod:
    RISING = 1
    MAX = 2

class ADCProcessWorker(QObject):
    """ADC数据处理工作线程 - 使用DataAnalyzer进行分析"""
    progress = pyqtSignal(int, int, str)
    finished = pyqtSignal(dict, dict)  # 传递结果和平均值
    error = pyqtSignal(str)
    log_message = pyqtSignal(str, str)  # 日志消息信号
  
    def __init__(self, file_list, config):
        super().__init__()
        self.file_list = file_list
        self.config = config
        self.analyzer = DataAnalyzer(config)  # 创建分析器实例
        self.running = False
  
    @pyqtSlot()
    def run(self):
        """执行ADC数据处理 - 使用分析器进行单次数据分析"""
        self.running = True
      
        try:
            # 初始化结果存储
            results = {
                'ys_full':[],'ys': [], 'mags': [], 'ys_d_full':[],'ys_d': [], 'mags_d': [],
                'freq_ref': None, 'freq_d_ref': None, 'sum_Xd': None,
                'success_count': 0, 'total_files': len(self.file_list),
            }
          
            self.log_message.emit(f"开始处理 {len(self.file_list)} 个文件", "INFO")
          
            # 处理每个文件
            for i, file_path in enumerate(self.file_list):
                if not self.running:
                    break
              
                self.progress.emit(i + 1, len(self.file_list), f"处理文件: {os.path.basename(file_path)}")
              
                try:
                    # 先加载数据，然后使用分析器处理
                    raw_data = self.load_u32_data(file_path)
                  
                    # 使用分析器处理单个文件的数据
                    res = self.analyzer.process_single_file(raw_data)
                  
                    if res is None:
                        self.log_message.emit(f"文件 {os.path.basename(file_path)} 处理失败，跳过", "WARNING")
                        continue
                      
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
                    if results['freq_ref'] is None:
                        results['freq_ref'] = freq
                    if results['freq_d_ref'] is None:
                        results['freq_d_ref'] = freq_d
                        results['sum_Xd'] = np.zeros_like(Xd_norm, dtype=np.complex128)
                  
                    # 存储结果
                    results['ys_full'].append(y_full.astype(np.float64))
                    results['ys'].append(y_roi.astype(np.float64))
                    results['mags'].append(mag_linear.astype(np.float64))
                    results['ys_d_full'].append(y_full_diff.astype(np.float64))
                    results['ys_d'].append(y_diff.astype(np.float64))
                    results['mags_d'].append(mag_linear_d.astype(np.float64))
                    results['sum_Xd'] += Xd_norm
                    results['success_count'] += 1
                      
                except Exception as e:
                    self.log_message.emit(f"处理文件 {os.path.basename(file_path)} 失败: {str(e)}", "WARNING")
                    continue
          
            if results['success_count'] == 0:
                raise RuntimeError("没有文件成功处理")
          
            # 计算平均值
            self.progress.emit(len(self.file_list), len(self.file_list), "计算平均值...")
            self.log_message.emit("计算平均值...", "INFO")
            averages = self.calculate_averages(results)
            
            # 直接对平均值进行边沿分析
            self.progress.emit(len(self.file_list), len(self.file_list), "进行边沿分析...")
            self.log_message.emit("进行边沿分析...", "INFO")


            # 对平均后的数据进行边沿分析
            edge_results = self.analyzer.analyze_edges(averages['y_full_avg'])
            

            if 'first_rise_pos' in edge_results and edge_results['first_rise_pos'] is not None:
                edge_results['first_rise_pos_time'] = edge_results['first_rise_pos'] * self.config.ts_eff * 1e6
            if 'second_rise_pos' in edge_results and edge_results['second_rise_pos'] is not None:
                edge_results['second_rise_pos_time'] = edge_results['second_rise_pos'] * self.config.ts_eff * 1e6
            if 'fall_pos' in edge_results and edge_results['fall_pos'] is not None:
                edge_results['fall_pos_time'] = edge_results['fall_pos'] * self.config.ts_eff * 1e6

            # 将边沿分析结果添加到results中
            results.update(edge_results)
          
            self.finished.emit(results, averages)
          
        except Exception as e:
            error_msg = f"ADC数据处理失败: {str(e)}"
            self.log_message.emit(error_msg, "ERROR")
            self.error.emit(error_msg)
  
    def stop(self):
        """停止处理"""
        self.running = False
  
    def load_u32_data(self, path: str) -> np.ndarray:
        """从文件加载uint32数据"""
        file_manager = FileManager()
        return file_manager.load_u32_text_first_col(path, skip_first=self.config.skip_first_value)
  
    def calculate_averages(self, results: Dict[str, Any]) -> Dict[str, Any]:
        """计算平均值"""
        averages = {}
      
        # ROI平均值
        averages['y_full_avg'] = np.mean(np.vstack(results['ys_full']), axis=0)
        averages['y_avg'] = np.mean(np.vstack(results['ys']), axis=0)
        averages['mag_avg_linear'] = np.mean(np.vstack(results['mags']), axis=0)
        averages['mag_avg_db'] = 20 * np.log10(averages['mag_avg_linear'])
    
        # 差分平均值
        averages['y_d_full_avg'] = np.mean(np.vstack(results['ys_d_full']), axis=0)
        averages['y_d_avg'] = np.mean(np.vstack(results['ys_d']), axis=0)
        averages['mag_d_avg_linear'] = np.mean(np.vstack(results['mags_d']), axis=0)
        averages['mag_d_avg_db'] = 20 * np.log10(averages['mag_d_avg_linear'])
    
        # 复数FFT平均值
        averages['avg_Xd'] = results['sum_Xd'] / results['success_count']
    
        return averages


class DataAnalysisController(QObject):
    # 定义信号
    dataLoaded = pyqtSignal(str)  # 数据加载完成信号
    analysisStarted = pyqtSignal(str)  # 分析开始信号
    analysisCompleted = pyqtSignal(dict)  # 分析完成信号，传递结果
    errorOccurred = pyqtSignal(str)  # 错误信号
    plotDataReady = pyqtSignal(str, np.ndarray, np.ndarray)  # 绘图数据准备信号 (类型, x_data, y_data)
  
    def __init__(self, view, model):
        super().__init__()
        self.view = view
        self.model = model
        self.data_analyzer = None
        self.setup_connections()

    def setup_connections(self):
        """设置信号槽连接"""
        # 文件操作按钮
        self.view.load_button.clicked.connect(self.on_load_file)
        self.view.clear_button.clicked.connect(self.on_clear_files)
      
        # 分析类型变化
        self.view.analysis_combo.currentTextChanged.connect(self.on_analysis_type_changed)
      
        # 分析按钮
        self.view.analyze_button.clicked.connect(self.on_analyze)
        self.view.export_button.clicked.connect(self.on_export)
      
        # 文件列表选择变化
        self.view.file_list.currentRowChanged.connect(self.on_file_selected)
      
        # 错误信号连接到日志记录
        self.errorOccurred.connect(lambda msg: self.log_message(msg, "ERROR"))
        self.dataLoaded.connect(lambda msg: self.log_message(msg, "INFO"))
        self.analysisCompleted.connect(self.log_analysis_results)

    def log_message(self, message, level="INFO"):
        """记录消息到日志区域"""
        if hasattr(self, 'main_window_controller') and self.main_window_controller:
            self.main_window_controller.log_controller.log(message, level)
  
    def log_analysis_results(self, results):
        """记录分析结果到日志区域"""
        if hasattr(self, 'main_window_controller') and self.main_window_controller:
            self.main_window_controller.log_controller.log("分析结果:", "INFO")
            self.main_window_controller.log_controller.log("=" * 50, "INFO")
            for key, value in results.items():
                self.main_window_controller.log_controller.log(f"{key}: {value}", "INFO")
  
    def on_load_file(self):
        """加载数据文件"""
        try:
            file_paths, _ = QFileDialog.getOpenFileNames(
                self.view,
                "选择数据文件",
                "",
                "数据文件 (*.s2p *.csv *.txt *.dat);;所有文件 (*)"
            )
          
            if file_paths:
                for file_path in file_paths:
                    if file_path not in self.model.data_files:
                        self.model.data_files.append(file_path)
                        self.view.file_list.addItem(os.path.basename(file_path))
              
                msg = f"成功加载 {len(file_paths)} 个文件"
                self.dataLoaded.emit(msg)
                self.log_message(msg, "INFO")
        except Exception as e:
            error_msg = f"加载文件失败: {str(e)}"
            self.errorOccurred.emit(error_msg)
            self.log_message(error_msg, "ERROR")
  
    def on_clear_files(self):
        """清除文件列表"""
        self.model.data_files.clear()
        self.model.current_data = None
        self.view.file_list.clear()
        msg = "已清除文件列表"
        self.dataLoaded.emit(msg)
        self.log_message(msg, "INFO")
  
    def on_analysis_type_changed(self, analysis_type):
        """分析类型变化"""
        self.model.analysis_type = analysis_type
      
        # 根据分析类型更新界面
        if analysis_type == "ADC数据分析":
            self.view.show_adc_analysis_options()
        elif analysis_type == "S参数":
            self.view.show_s_parameter_options()
        elif analysis_type == "TDR":
            self.view.show_tdr_options()
      
        self.log_message(f"分析类型已更改为: {analysis_type}", "INFO")
  
    def on_file_selected(self, row):
        """文件选择变化"""
        if 0 <= row < len(self.model.data_files):
            file_path = self.model.data_files[row]
            try:
                self.model.current_data = self.load_data_file(file_path)
                msg = f"已加载文件: {os.path.basename(file_path)}"
                self.dataLoaded.emit(msg)
                self.log_message(msg, "INFO")
            except Exception as e:
                error_msg = f"加载数据失败: {str(e)}"
                self.errorOccurred.emit(error_msg)
                self.model.current_data = None
                self.log_message(error_msg, "ERROR")
  
    def on_analyze(self):
        """执行分析"""
        if self.model.analysis_type == "ADC数据分析":
            self.analyze_adc_data()
            return
      
        if not self.model.current_data:
            error_msg = "请先选择数据文件"
            self.errorOccurred.emit(error_msg)
            self.log_message(error_msg, "WARNING")
            return
      
        try:
            self.analysisStarted.emit(self.model.analysis_type)
            self.log_message(f"开始{self.model.analysis_type}分析", "INFO")
          
            # 根据分析类型执行不同的分析
            if self.model.analysis_type == "S参数":
                results = self.analyze_s_parameters()
            elif self.model.analysis_type == "TDR":
                results = self.analyze_tdr()
            else:
                results = {}
          
            self.model.results = results
            self.analysisCompleted.emit(results)
          
        except Exception as e:
            error_msg = f"分析失败: {str(e)}"
            self.errorOccurred.emit(error_msg)
            self.log_message(error_msg, "ERROR")
  
    def analyze_adc_data(self):
        """执行ADC数据分析"""
        if not self.model.data_files:
            error_msg = "请先加载数据文件"
            self.errorOccurred.emit(error_msg)
            self.log_message(error_msg, "WARNING")
            return
        
        try:
            # 更新配置
            config = self.model.adc_config
            config.clock_freq = self.view.adc_clock_freq.value()
            config.trigger_freq = self.view.adc_trigger_freq.value()
            config.roi_start_tenths = self.view.adc_roi_start.value()
            config.roi_end_tenths = self.view.adc_roi_end.value()
            config.diff_points = self.view.adc_diff_points.value()  # 新增：获取差分点数
            config.average_points = self.view.adc_average_points.value()
            config.recursive = True
            config.use_signed18 = True
            config.cal_mode = self.view.cal_type_combo.currentText()
            self.log_message(f"校准模式:{config.cal_mode}", "DEBUG")
            # 获取SearchMethod的值
            config.search_method = self.view.search_method_combo.currentData()
        
            self.analysisStarted.emit("ADC数据分析")
            self.log_message("开始ADC数据分析", "INFO")
        
            # 显示进度条
            self.view.progress_bar.setVisible(True)
            self.view.progress_bar.setMaximum(len(self.model.data_files))
            self.view.progress_bar.setValue(0)
        
            # 创建工作线程
            self.adc_process_thread = QThread()
            self.adc_process_worker = ADCProcessWorker(self.model.data_files, config)
            self.adc_process_worker.moveToThread(self.adc_process_thread)
        
            # 连接信号
            self.adc_process_thread.started.connect(self.adc_process_worker.run)
            self.adc_process_worker.progress.connect(self.on_adc_process_progress)
            self.adc_process_worker.finished.connect(self.on_adc_process_finished)
            self.adc_process_worker.finished.connect(self.adc_process_thread.quit)
            self.adc_process_worker.finished.connect(self.adc_process_worker.deleteLater)
            self.adc_process_thread.finished.connect(self.adc_process_thread.deleteLater)
            self.adc_process_worker.error.connect(self.on_adc_process_error)
            self.adc_process_worker.log_message.connect(self.log_message)
        
            # 启动线程
            self.adc_process_thread.start()
        
        except Exception as e:
            error_msg = f"ADC数据分析失败: {str(e)}"
            self.errorOccurred.emit(error_msg)
            self.log_message(error_msg, "ERROR")

    def on_adc_process_progress(self, current, total, message):
        """ADC处理进度更新"""
        self.view.progress_bar.setValue(current)
        self.log_message(f"处理进度: {current}/{total} - {message}", "INFO")

    def on_adc_process_finished(self, results, averages):
        """ADC处理完成"""
        # 隐藏进度条
        self.view.progress_bar.setVisible(False)
      
        # 保存分析结果供导出使用
        self.last_analysis_results = results
        self.last_averages = averages
      
        # 格式化结果
        config = self.model.adc_config
        analysis_results = {
            "processed_files": f"{results['success_count']}/{results['total_files']}",
            "clock_frequency": f"{config.clock_freq/1e6:.2f} MHz",
            "trigger_frequency": f"{config.trigger_freq/1e6:.2f} MHz",
            "roi_range": f"{config.roi_start_tenths}%-{config.roi_end_tenths}%",
            "sampling_rate": f"{config.fs_eff/1e6:.2f} MS/s"
        }
      
        # 生成绘图数据
        self.generate_plot_data(results, averages, config)
        self.model.results = analysis_results
        self.analysisCompleted.emit(analysis_results)
      
        self.log_message(f"分析完成! 成功处理 {results['success_count']}/{results['total_files']} 个文件", "INFO")

    def on_adc_process_error(self, error_message):
        """ADC处理错误"""
        self.view.progress_bar.setVisible(False)
        self.errorOccurred.emit(error_message)
        self.log_message(error_message, "ERROR")
  
    def set_main_window_controller(self, main_window_controller):
        """设置主窗口控制器引用"""
        self.main_window_controller = main_window_controller

    def get_plot_controller(self, plot_name):
        """获取绘图控制器"""
        if hasattr(self, 'main_window_controller') and self.main_window_controller:
            return self.main_window_controller.sub_controllers.get(plot_name)
        return None

    def generate_plot_data(self, results, averages, config):
        """生成绘图数据"""
        try:
            # 清除所有现有的标记线
            self.clear_all_markers()
          
            # 时域数据 - 转换为电压值
            t_roi_us = (np.arange(config.l_roi) * config.ts_eff) * 1e6
            t_full_us = ((np.arange(config.roi_n(100)) * config.ts_eff) * 1e6)
            # 将ADC数据转换为电压值 (±3V范围，带符号19位)
            adc_max_value = 2**19  # 262144
            y_avg_voltage = (averages['y_full_avg'] / adc_max_value) * 3.0
          
            # 边缘位置计算
            edge_in_roi = (config.n_points // 4 - config.roi_start)
          
            # 获取时域绘图控制器
            time_controller = self.get_plot_controller('plot_time')
            if time_controller:
                # 清除现有绘图
                time_controller.view.clear_plot()
              
                # 绘制时域信号 (使用电压值)
                time_controller.plot_time_domain(t_full_us, y_avg_voltage, "时间", "电压", "ns", "V")
              
                # 添加边缘位置标记线
                self.add_edge_markers(time_controller, results, config, t_full_us, y_avg_voltage)
              
            else:
                self.errorOccurred.emit("时域绘图控制器未找到")
          
            # 频域数据
            mask = results['freq_ref'] <= (config.show_up_to_GHz * 1e9)
            freq_ghz = results['freq_ref'][mask] / 1e9
            mag_db = averages['mag_avg_db'][mask]
          
            # 获取频域绘图控制器
            freq_controller = self.get_plot_controller('plot_freq')
            if freq_controller:
                # 清除现有绘图
                freq_controller.view.clear_plot()
              
                freq_controller.plot_frequency_domain(freq_ghz, mag_db, "频率", "幅度", "GHz", "dB")
            else:
                self.errorOccurred.emit("频域绘图控制器未找到")
          
            # 差分时域数据 - 同样转换为电压值
            t_diff_us = t_roi_us[config.diff_points:]
            t_full_diff_us = t_full_us[config.diff_points:]
            y_d_avg_voltage = (averages['y_d_full_avg'] / adc_max_value) * 3.0
          
            # 获取或创建差分时域绘图控制器
            diff_time_controller = self.get_plot_controller('plot_diff_time')
            if not diff_time_controller:
                self.create_additional_plot_tabs()
            # 获取或创建差分时域绘图控制器
            diff_time_controller = self.get_plot_controller('plot_diff_time')
            if not diff_time_controller:
                self.create_additional_plot_tabs()
                diff_time_controller = self.get_plot_controller('plot_diff_time')
          
            if diff_time_controller:
                # 清除现有绘图
                diff_time_controller.view.clear_plot()
              
                diff_time_controller.plot_diff_time_domain(t_full_diff_us, y_d_avg_voltage, "时间", "差分电压", "ns", "V")
              
          
            # 差分频域数据
            maskd = results['freq_d_ref'] <= (config.show_up_to_GHz * 1e9)
            freq_d_ghz = results['freq_d_ref'][maskd] / 1e9
            mag_d_db = averages['mag_d_avg_db'][maskd]
          
            # 获取或创建差分频域绘图控制器
            diff_freq_controller = self.get_plot_controller('plot_diff_freq')
            if not diff_freq_controller:
                self.create_additional_plot_tabs()
                diff_freq_controller = self.get_plot_controller('plot_diff_freq')
          
            if diff_freq_controller:
                # 清除现有绘图
                diff_freq_controller.view.clear_plot()
              
                diff_freq_controller.plot_diff_frequency_domain(freq_d_ghz, mag_d_db, "频率", "差分幅度", "GHz", "dB")
              
        except Exception as e:
            self.errorOccurred.emit(f"生成绘图数据失败: {str(e)}")
            self.log_message(f"生成绘图数据失败: {str(e)}", "ERROR")

    def add_edge_markers(self, plot_controller, results, config, t_full_us, y_avg_voltage):
        """添加边缘位置标记线 - 使用交替位置方案避免标签重叠"""
        try:
            # 获取边缘位置时间（直接从edge_results中获取时间值，单位：微秒）
            first_rise_time = results.get('first_rise_pos_time')
            second_rise_time = results.get('second_rise_pos_time') 
            fall_time = results.get('fall_pos_time')
            rise_midpoint_time = results.get('rise_midpoint_time')
            fall_midpoint_time = results.get('fall_midpoint_time')
            second_fall_midpoint_time = results.get('second_fall_midpoint_time')
            
            adc_max_value = 2**19  # 262144
            # 获取幅度信息并正确换算为电压值
            first_amplitude = (results.get('first_rise_amplitude', 0)/adc_max_value) * 3
            second_amplitude = (results.get('second_rise_amplitude', 0)/adc_max_value) * 3
            fall_amplitude = (results.get('fall_amplitude', 0)/adc_max_value) * 3
            first_rise_ratio = results.get('first_rise_ratio', 0)
            rise_ratio = results.get('rise_ratio', 0)
            fall_ratio = results.get('fall_ratio', 0)
            
            # 收集所有要添加的标记线
            all_markers = []
            
            # 边缘标记线
            if first_rise_time is not None:
                # 找到对应时间点的Y坐标值
                time_idx = np.argmin(np.abs(t_full_us - first_rise_time))
                x_idx = config.n_roi(time_idx)
                y_position = y_avg_voltage[time_idx+10] if time_idx < len(y_avg_voltage) else np.mean(y_avg_voltage)
                all_markers.append((first_rise_time, y_position, '#FF0000', 'solid', f'Rise\n({y_position:.3f}V {x_idx}%)', 3))
            
            if second_rise_time is not None:
                time_idx = np.argmin(np.abs(t_full_us - second_rise_time))
                x_idx = config.n_roi(time_idx)
                y_position = y_avg_voltage[time_idx+10] if time_idx < len(y_avg_voltage) else np.mean(y_avg_voltage)
                all_markers.append((second_rise_time, y_position, '#0000FF', 'solid', f'2nd Rise\n({y_position:.3f}V,{x_idx}%)', 3))
            
            if fall_time is not None:
                time_idx = np.argmin(np.abs(t_full_us - fall_time))
                x_idx = config.n_roi(time_idx)
                y_position = y_avg_voltage[time_idx+10] if time_idx < len(y_avg_voltage) else np.mean(y_avg_voltage)
                all_markers.append((fall_time, y_position, '#00AA00', 'solid', f'Fall\n({y_position:.3f}V,{x_idx}%)', 3))
            
            # 中点标记线
            if rise_midpoint_time is not None:
                time_idx = np.argmin(np.abs(t_full_us - rise_midpoint_time))
                y_position = y_avg_voltage[time_idx] if time_idx < len(y_avg_voltage) else np.mean(y_avg_voltage)
                all_markers.append((rise_midpoint_time, y_position, '#FFA500', 'dashed', 'Rise-2nd\nRise Mid', 2))
            
            if fall_midpoint_time is not None:
                time_idx = np.argmin(np.abs(t_full_us - fall_midpoint_time))
                y_position = y_avg_voltage[time_idx] if time_idx < len(y_avg_voltage) else np.mean(y_avg_voltage)
                all_markers.append((fall_midpoint_time, y_position, '#800080', 'dashed', 'Rise-Fall Mid', 2))
            
            if second_fall_midpoint_time is not None:
                time_idx = np.argmin(np.abs(t_full_us - second_fall_midpoint_time))
                y_position = y_avg_voltage[time_idx] if time_idx < len(y_avg_voltage) else np.mean(y_avg_voltage)
                all_markers.append((second_fall_midpoint_time, y_position, '#00FFFF', 'dashed', '2ndRise-Fall Mid', 2))
            
            # ROI标记线
            roi_start_time = config.roi_start * config.ts_eff * 1e6
            roi_mid_time = config.roi_mid * config.ts_eff * 1e6
            roi_end_time = config.roi_end * config.ts_eff * 1e6
            
            # 添加ROI标记线，使用平均Y值作为位置
            avg_y = np.mean(y_avg_voltage)
            all_markers.append((roi_start_time, avg_y, '#FF00FF', 'dashdot', f'ROI Start\n({config.roi_start_tenths}%)', 2))
            all_markers.append((roi_mid_time, avg_y, "#94B814", 'dashdot', f'ROI Mid\n({config.roi_mid_tenths}%)', 2))
            all_markers.append((roi_end_time, avg_y, '#00FFFF', 'dashdot', f'ROI End\n({config.roi_end_tenths}%)', 2))
            
            # 按时间排序标记线
            all_markers.sort(key=lambda x: x[0])
            
            # 使用交替位置方案添加标记线
            for i, (x_position, y_position, color, style, label, width) in enumerate(all_markers):
                # 在Y坐标基础上添加小偏移以避免标签重叠
                y_offset = 0.1 * (i % 3 - 1) * (np.max(y_avg_voltage) - np.min(y_avg_voltage))
                final_y_position = y_position + y_offset
                
                self.add_vertical_line_at_position(plot_controller, x_position, color, style, label, width, final_y_position)
            
            # 记录边沿分析结果到日志
            edge_info = []
            if first_rise_time is not None:
                edge_info.append(f"First Rise: {first_rise_time:.3f}ns, Amp: {first_amplitude:.3f}V")
            if second_rise_time is not None:
                edge_info.append(f"Second Rise: {second_rise_time:.3f}ns, Amp: {second_amplitude:.3f}V, Ratio: {rise_ratio:.2%}")
            if fall_time is not None:
                edge_info.append(f"Fall: {fall_time:.3f}ns, Amp: {fall_amplitude:.3f}V, Ratio: {fall_ratio:.2%}")
            
            # 添加ROI信息到日志
            edge_info.append(f"ROI Range: {config.roi_start_tenths}%-{config.roi_end_tenths}%")
            edge_info.append(f"ROI Mid: {config.roi_mid_tenths}%")
            
            if edge_info:
                self.log_message("边沿分析结果:", "INFO")
                for info in edge_info:
                    self.log_message(info, "INFO")
            
            self.log_message("已添加边缘位置标记线", "INFO")
        
        except Exception as e:
            self.errorOccurred.emit(f"添加边缘标记线失败: {str(e)}")
            self.log_message(f"添加边缘标记线失败: {str(e)}", "ERROR")


    def add_vertical_line_at_position(self, plot_controller, x_position, color, style, label, width, y_position):
        """在指定位置添加垂直标记线"""
        try:
            plot_widget = plot_controller.view.plot_widget
            pen_style = pg.QtCore.Qt.DashLine if style == 'dashed' else \
                    pg.QtCore.Qt.DotLine if style == 'dotted' else \
                    pg.QtCore.Qt.DashDotLine if style == 'dashdot' else \
                    pg.QtCore.Qt.SolidLine
            
            # 创建无限线
            line = pg.InfiniteLine(pos=x_position, angle=90, 
                                pen=pg.mkPen(color, width=width, style=pen_style))
            plot_widget.addItem(line)
            
            if label:
                # 添加文本标签
                text = pg.TextItem(text=label, color=color, anchor=(0.5, 1))
                text.setPos(x_position, y_position)
                
                # 设置字体样式
                font = text.textItem.font()
                font.setPointSize(8)  # 使用稍小的字体
                font.setBold(True)
                text.textItem.setFont(font)
                
                plot_widget.addItem(text)
            
            return line
            
        except Exception as e:
            print(f"添加标记线失败: {e}")
            return None



    def clear_all_markers(self):
        """清除所有绘图标记"""
        try:
            # 清除所有绘图控制器的标记
            for plot_name in ['plot_time', 'plot_freq', 'plot_diff_time', 'plot_diff_freq']:
                controller = self.get_plot_controller(plot_name)
                if controller and hasattr(controller, 'clear_markers'):
                    controller.clear_markers()
                  
        except Exception as e:
            self.errorOccurred.emit(f"清除标记失败: {str(e)}")
            self.log_message(f"清除标记失败: {str(e)}", "ERROR")

    def add_vertical_line(self, plot_controller, x_position, color='red', style='dashed', label='', width=2):
        """添加垂直标记线 - 支持宽度参数"""
        try:
            # 创建无限线
            plot_widget = plot_controller.view.plot_widget
            pen_style = pg.QtCore.Qt.DashLine if style == 'dashed' else pg.QtCore.Qt.DotLine if style == 'dotted' else pg.QtCore.Qt.SolidLine
        
            # 使用指定的宽度
            line = pg.InfiniteLine(pos=x_position, angle=90, 
                                pen=pg.mkPen(color, width=width, style=pen_style))
            plot_widget.addItem(line)
        
            if label:
                # 获取当前Y轴数据范围
                y_range = plot_widget.getViewBox().viewRange()[1]
            
                # 计算最大数据值并添加余量
                if hasattr(self.model, 'y_data') and self.model.y_data:
                    # 如果有数据，使用最大值的1.2倍作为高度
                    max_y = max(self.model.y_data)
                    y_position = max_y * 1.0
                else:
                    # 如果没有数据，使用Y轴范围的90%位置
                    y_position = y_range[1] * 0.9
            
                # 确保位置在可见范围内
                y_position = min(y_position, y_range[1] * 0.95)
            
                # 添加文本标签 - 使用更醒目的字体
                text = pg.TextItem(text=label, color=color, anchor=(0.5, 1))
                text.setPos(x_position, y_position)
                # 设置字体大小和样式
                font = text.textItem.font()
                font.setPointSize(10)
                font.setBold(True)
                text.textItem.setFont(font)
                plot_widget.addItem(text)
            return line
        
        except Exception as e:
            print(f"添加标记线失败: {e}")
            return None


    def create_additional_plot_tabs(self):
        """创建额外的绘图标签页"""
        if not hasattr(self, 'main_window_controller') or not self.main_window_controller:
            return
      
        main_window_view = self.main_window_controller.view
      
        # 创建差分时域绘图
        diff_time_view, diff_time_controller = create_plot_widget("差分时域信号")
        main_window_view.add_plot_tab(diff_time_view, "差分时域")
        self.main_window_controller.sub_controllers['plot_diff_time'] = diff_time_controller
      
        # 创建差分频域绘图
        diff_freq_view, diff_freq_controller = create_plot_widget("差分频域信号")
        main_window_view.add_plot_tab(diff_freq_view, "差分频域")
        self.main_window_controller.sub_controllers['plot_diff_freq'] = diff_freq_controller

    def export_plots(self, base_path):
        """导出所有绘图到以base_path为基础的文件名"""
        plot_types = ['plot_time', 'plot_freq', 'plot_diff_time', 'plot_diff_freq']
        suffixes = {
            'plot_time': '_time_domain',
            'plot_freq': '_frequency_domain', 
            'plot_diff_time': '_diff_time_domain',
            'plot_diff_freq': '_diff_frequency_domain'
        }
      
        # 确保目录存在
        output_dir = os.path.dirname(base_path)
        if output_dir and not os.path.exists(output_dir):
            os.makedirs(output_dir)
      
        for plot_type in plot_types:
            controller = self.get_plot_controller(plot_type)
            if controller:
                file_path = f"{base_path}{suffixes[plot_type]}.png"
                success = self.export_single_plot(controller, file_path)
                if success:
                    self.log_message(f"导出{plot_type}图片成功: {file_path}", "INFO")
                else:
                    self.log_message(f"导出{plot_type}图片失败", "WARNING")

    def export_single_plot(self, plot_controller, file_path):
        """导出单个绘图到文件"""
        try:
            # 获取绘图部件
            plot_widget = plot_controller.view.plot_widget
          
            # 使用QPixmap捕获绘图区域
            pixmap = plot_widget.grab()
          
            # 保存图片
            success = pixmap.save(file_path)
            return success
        except Exception as e:
            self.log_message(f"导出图片失败: {e}", "ERROR")
            return False

    def on_export(self):
        """导出分析结果"""
        if not self.model.results:
            self.errorOccurred.emit("没有可导出的分析结果")
            self.log_message("没有可导出的分析结果", "WARNING")
            return
      
        try:
            # 获取保存文件路径
            file_path, _ = QFileDialog.getSaveFileName(
                self.view,
                "导出分析结果",
                "",
                "CSV文件 (*.csv);;JSON文件 (*.json);;文本文件 (*.txt);;所有文件 (*)"
            )
          
            if file_path:
                # 获取文件扩展名和基础路径
                file_ext = os.path.splitext(file_path)[1].lower()
                base_path = os.path.splitext(file_path)[0]
              
                if file_ext == '.csv':
                    # 使用DataAnalyze的save_results函数保存CSV数据
                    self.export_csv_results(file_path)
                elif file_ext == '.json':
                    # 保存JSON格式的结果
                    self.export_json_results(file_path)
                else:
                    # 默认保存文本格式
                    self.export_text_results(file_path)
              
                # 导出图片
                self.export_plots(base_path)
              
                self.dataLoaded.emit(f"结果和图片已导出到: {base_path}*")
                self.log_message(f"结果和图片已导出到: {base_path}*", "INFO")
              
        except Exception as e:
            self.errorOccurred.emit(f"导出失败: {str(e)}")
            self.log_message(f"导出失败: {str(e)}", "ERROR")

    def export_csv_results(self, file_path):
        """使用DataAnalyze的save_results函数导出CSV结果"""
        try:
            # 创建临时的分析配置
            config = AnalysisConfig(output_csv=file_path)
          
            # 创建DataAnalyzer实例
            analyzer = DataAnalyzer(config)
          
            # 获取当前的分析结果数据
            if hasattr(self, 'last_analysis_results') and hasattr(self, 'last_averages'):
                results = self.last_analysis_results
                averages = self.last_averages
              
                # 保存复数FFT结果
                if 'freq_d_ref' in results and 'avg_Xd' in averages:
                    success = analyzer.file_manager.save_complex_fft_results(
                        results['freq_d_ref'], 
                        np.real(averages['avg_Xd']), 
                        np.imag(averages['avg_Xd']), 
                        file_path
                    )
                  
                    if success:
                        self.dataLoaded.emit("复数FFT结果已成功导出为CSV")
                        self.log_message("复数FFT结果已成功导出为CSV", "INFO")
                    else:
                        self.errorOccurred.emit("复数FFT结果导出失败")
                        self.log_message("复数FFT结果导出失败", "ERROR")
              
                # 同时保存时域数据
                self.export_additional_csv_data(file_path, results, averages)
              
            else:
                # 如果没有分析数据，保存基本的文本结果
                self.export_text_results(file_path)
              
        except Exception as e:
            self.errorOccurred.emit(f"CSV导出失败: {str(e)}")
            self.log_message(f"CSV导出失败: {str(e)}", "ERROR")

    def export_additional_csv_data(self, file_path, results, averages):
        """导出额外的CSV数据"""
        try:
            # 创建基础文件名（不带扩展名）
            base_path = os.path.splitext(file_path)[0]
          
            # 保存时域数据
            time_domain_file = f"{base_path}_time_domain.csv"
            if 'y_avg' in averages:
                t_roi_us = (np.arange(len(averages['y_avg'])) * self.model.adc_config.ts_eff * 1e6)
                time_data = np.column_stack((t_roi_us, averages['y_avg']))
                np.savetxt(time_domain_file, time_data, delimiter=',', 
                        header='Time(us),Amplitude', comments='')
                self.dataLoaded.emit(f"时域数据已保存到: {os.path.basename(time_domain_file)}")
                self.log_message(f"时域数据已保存到: {os.path.basename(time_domain_file)}", "INFO")
          
            # 保存频域数据
            freq_domain_file = f"{base_path}_frequency_domain.csv"
            if 'freq_ref' in results and 'mag_avg_db' in averages:
                mask = results['freq_ref'] <= (self.model.adc_config.show_up_to_GHz * 1e9)
                freq_data = np.column_stack((results['freq_ref'][mask] / 1e9, 
                                        averages['mag_avg_db'][mask]))
                np.savetxt(freq_domain_file, freq_data, delimiter=',', 
                        header='Frequency(GHz),Magnitude(dB)', comments='')
                self.dataLoaded.emit(f"频域数据已保存到: {os.path.basename(freq_domain_file)}")
                self.log_message(f"频域数据已保存到: {os.path.basename(freq_domain_file)}", "INFO")
          
            # 保存差分时域数据
            diff_time_file = f"{base_path}_diff_time_domain.csv"
            if 'y_d_avg' in averages:
                t_diff_us = (np.arange(len(averages['y_d_avg'])) * self.model.adc_config.ts_eff * 1e6)
                diff_time_data = np.column_stack((t_diff_us, averages['y_d_avg']))
                np.savetxt(diff_time_file, diff_time_data, delimiter=',', 
                        header='Time(us),Differential_Amplitude', comments='')
                self.dataLoaded.emit(f"差分时域数据已保存到: {os.path.basename(diff_time_file)}")
                self.log_message(f"差分时域数据已保存到: {os.path.basename(diff_time_file)}", "INFO")
          
            # 保存差分频域数据
            diff_freq_file = f"{base_path}_diff_frequency_domain.csv"
            if 'freq_d_ref' in results and 'mag_d_avg_db' in averages:
                maskd = results['freq_d_ref'] <= (self.model.adc_config.show_up_to_GHz * 1e9)
                diff_freq_data = np.column_stack((results['freq_d_ref'][maskd] / 1e9, 
                                                averages['mag_d_avg_db'][maskd]))
                np.savetxt(diff_freq_file, diff_freq_data, delimiter=',', 
                        header='Frequency(GHz),Differential_Magnitude(dB)', comments='')
                self.dataLoaded.emit(f"差分频域数据已保存到: {os.path.basename(diff_freq_file)}")
                self.log_message(f"差分频域数据已保存到: {os.path.basename(diff_freq_file)}", "INFO")
              
        except Exception as e:
            self.errorOccurred.emit(f"附加数据导出失败: {str(e)}")
            self.log_message(f"附加数据导出失败: {str(e)}", "ERROR")

    def export_json_results(self, file_path):
        """导出JSON格式的结果"""
        try:
            # 创建完整的结果字典
            export_data = {
                "analysis_results": self.model.results,
                "config": self.model.get_adc_config_dict(),
                "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
                "files_processed": len(self.model.data_files)
            }
            
            # 如果有分析数据，添加更多详细信息
            if hasattr(self, 'last_analysis_results') and hasattr(self, 'last_averages'):
                export_data.update({
                    "successful_files": self.last_analysis_results.get('success_count', 0),
                    "total_files": self.last_analysis_results.get('total_files', 0)
                })
            
            # 使用FileManager保存JSON
            file_manager = FileManager()
            success = file_manager.save_json_data(export_data, file_path)
            
            if success:
                self.dataLoaded.emit("结果已成功导出为JSON格式")
                self.log_message("结果已成功导出为JSON格式", "INFO")
            else:
                self.errorOccurred.emit("JSON导出失败")
                self.log_message("JSON导出失败", "ERROR")
                
        except Exception as e:
            self.errorOccurred.emit(f"JSON导出失败: {str(e)}")
            self.log_message(f"JSON导出失败: {str(e)}", "ERROR")

    def export_text_results(self, file_path):
        """导出文本格式的结果"""
        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write("数据分析结果\n")
                f.write("=" * 50 + "\n\n")
                
                f.write("分析配置:\n")
                f.write("-" * 30 + "\n")
                config_dict = self.model.get_adc_config_dict()
                for key, value in config_dict.items():
                    f.write(f"{key}: {value}\n")
                
                f.write("\n分析结果:\n")
                f.write("-" * 30 + "\n")
                for key, value in self.model.results.items():
                    f.write(f"{key}: {value}\n")
                
                f.write(f"\n处理文件数: {len(self.model.data_files)}\n")
                f.write(f"导出时间: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
            
            self.dataLoaded.emit("结果已成功导出为文本格式")
            self.log_message("结果已成功导出为文本格式", "INFO")
            
        except Exception as e:
            self.errorOccurred.emit(f"文本导出失败: {str(e)}")
            self.log_message(f"文本导出失败: {str(e)}", "ERROR")

    def load_data_file(self, file_path):
        """加载数据文件的具体实现"""
        # 这里应该根据文件格式实现具体的数据加载逻辑
        # 返回加载的数据
        return {"file_path": file_path, "data": None}
    
    def analyze_s_parameters(self):
        """S参数分析"""
        # 实现S参数分析逻辑
        return {
            "s11_magnitude": 0.1,
            "s11_phase": -45.0,
            "s21_magnitude": 0.8,
            "s21_phase": -10.0,
            "bandwidth": 2.5e9,
            "insertion_loss": 1.2
        }
    
    def analyze_tdr(self):
        """TDR分析"""
        # 实现TDR分析逻辑
        return {
            "impedance": 50.0,
            "rise_time": 35e-12,
            "reflection_coefficient": 0.05,
            "delay": 1.2e-9
        }
    
    def export_results(self, file_path, results):
        """导出结果到文件"""
        # 实现导出逻辑
        with open(file_path, 'w', encoding='utf-8') as f:
            for key, value in results.items():
                f.write(f"{key}: {value}\n")
