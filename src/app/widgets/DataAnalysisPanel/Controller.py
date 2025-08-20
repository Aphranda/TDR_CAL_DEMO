# src/app/widgets/DataAnalysisPanel/Controller.py
import os
import numpy as np
from PyQt5.QtWidgets import QFileDialog, QMessageBox
from PyQt5.QtCore import QObject, pyqtSignal, QThread, pyqtSlot
from ...core.ADCSample import ADCSample
from ...core.DataAnalyze import DataAnalyzer, AnalysisConfig
from ...core.FileManager import FileManager
from ...widgets.PlotWidget import create_plot_widget
import time

class ADCWorker(QObject):
    """ADC采样工作线程"""
    progress = pyqtSignal(int, int, str)
    finished = pyqtSignal(bool, str)
    sampleData = pyqtSignal(list)
    dataSaved = pyqtSignal(str, str)  # 新增：数据保存信号 (文件路径, 消息)
    
    def __init__(self, adc_sample, count, interval, save_raw_data=True, output_dir=None, filename_prefix=None):
        super().__init__()
        self.adc_sample = adc_sample
        self.count = count
        self.interval = interval
        self.save_raw_data = save_raw_data
        self.output_dir = output_dir or 'data\\results\\test'
        self.filename_prefix = filename_prefix or 'adc_raw_data'  # 新增：文件名前缀
        self.running = False
    
    @pyqtSlot()
    def run(self):
        """执行ADC采样"""
        self.running = True
        successful_samples = 0
        all_samples = []
        
        try:
            # 确保输出目录存在
            if self.save_raw_data:
                self.adc_sample.file_manager.ensure_dir_exists(self.output_dir)
            
            for i in range(self.count):
                if not self.running:
                    break
                
                self.progress.emit(i + 1, self.count, f"采样 {i + 1}/{self.count}")
                
                # 执行单次采样
                u32_values, error = self.adc_sample.perform_single_test(i)
                if error:
                    self.progress.emit(i + 1, self.count, f"采样失败: {error}")
                    continue
                
                successful_samples += 1
                all_samples.append(u32_values)
                
                # 保存原始数据 - 使用文件名前缀作为第一个字段
                if self.save_raw_data:
                    filename = f'{self.filename_prefix}_{i + 1:04d}.csv'  # 修改：使用文件名前缀
                    success, message = self.adc_sample.save_test_result(i, u32_values, filename, self.output_dir)
                    if success:
                        self.dataSaved.emit(os.path.join(self.output_dir, filename), f"数据已保存: {filename}")
                    else:
                        self.progress.emit(i + 1, self.count, f"数据保存失败: {message}")
                
                # 等待间隔
                time.sleep(self.interval)
            
            success = successful_samples > 0
            message = f"完成 {successful_samples}/{self.count} 次采样"
            self.sampleData.emit(all_samples)
            self.finished.emit(success, message)
            
        except Exception as e:
            self.finished.emit(False, f"采样过程中发生错误: {str(e)}")
    
    def stop(self):
        """停止采样"""
        self.running = False

class DataAnalysisController(QObject):
    # 定义信号
    dataLoaded = pyqtSignal(str)  # 数据加载完成信号
    analysisStarted = pyqtSignal(str)  # 分析开始信号
    analysisCompleted = pyqtSignal(dict)  # 分析完成信号，传递结果
    errorOccurred = pyqtSignal(str)  # 错误信号
    adcStatusChanged = pyqtSignal(bool, str)  # ADC连接状态变化信号
    samplingProgress = pyqtSignal(int, int, str)  # 采样进度信号
    dataSaved = pyqtSignal(str, str)  # 新增：数据保存信号
    plotDataReady = pyqtSignal(str, np.ndarray, np.ndarray)  # 新增：绘图数据准备信号 (类型, x_data, y_data)
    
    def __init__(self, view, model):
        super().__init__()
        self.view = view
        self.model = model
        self.adc_sample = ADCSample()
        self.adc_worker = None
        self.adc_thread = None
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
        
        # ADC连接按钮
        self.view.connect_button.clicked.connect(self.on_connect_adc)
        self.view.disconnect_button.clicked.connect(self.on_disconnect_adc)
        self.view.sample_button.clicked.connect(self.on_sample_adc)
        
        # 连接状态信号
        self.adcStatusChanged.connect(self.view.update_adc_connection_status)
        self.samplingProgress.connect(self.view.update_sampling_progress)
        self.dataLoaded.connect(self.view.append_result_text)
        self.analysisCompleted.connect(self.view.display_analysis_results)
        self.errorOccurred.connect(self.view.append_result_text)
        self.dataSaved.connect(self.view.append_result_text)


    
    def on_connect_adc(self):
        """连接ADC"""
        try:
            ip = self.view.adc_ip_edit.text()
            port_text = self.view.adc_port_edit.text()
            try:
                port = int(port_text)
            except ValueError:
                self.errorOccurred.emit("端口号必须是有效的数字")
                return
            
            # 更新模型
            self.model.adc_ip = ip
            self.model.adc_port = port
            
            self.adc_sample.set_server_config(ip, port)
            success, message = self.adc_sample.connect()
            self.model.set_adc_connection_status(success)
            self.adcStatusChanged.emit(success, message)
        except Exception as e:
            self.errorOccurred.emit(f"连接ADC失败: {str(e)}")
            self.adcStatusChanged.emit(False, str(e))
    
    def on_disconnect_adc(self):
        """断开ADC连接"""
        try:
            self.adc_sample.disconnect()
            self.model.set_adc_connection_status(False)
            self.adcStatusChanged.emit(False, "手动断开连接")
        except Exception as e:
            self.errorOccurred.emit(f"断开连接失败: {str(e)}")
    
    def on_sample_adc(self):
        """开始ADC采样"""
        if not self.model.adc_connected:
            self.errorOccurred.emit("请先连接ADC")
            return
        
        # 获取采样参数
        count = self.view.sample_count_spin.value()
        interval = self.view.sample_interval_spin.value()
        save_raw_data = True
        output_dir = self.view.output_dir_edit.text() or 'data\\results\\test'
        filename_prefix = self.view.filename_edit.text() or 'adc_raw_data'  # 新增：获取文件名前缀
        
        # 更新模型
        self.model.sample_count = count
        self.model.sample_interval = interval
        self.model.save_raw_data = save_raw_data
        self.model.output_dir = output_dir
        self.model.filename_prefix = filename_prefix  # 新增：文件名前缀
        
        # 创建工作线程 - 传入文件名前缀
        self.adc_thread = QThread()
        self.adc_worker = ADCWorker(self.adc_sample, count, interval, save_raw_data, output_dir, filename_prefix)
        self.adc_worker.moveToThread(self.adc_thread)
        
        # 连接信号
        self.adc_thread.started.connect(self.adc_worker.run)
        self.adc_worker.progress.connect(self.samplingProgress)
        self.adc_worker.finished.connect(self.on_sampling_finished)
        self.adc_worker.finished.connect(self.adc_thread.quit)
        self.adc_worker.finished.connect(self.adc_worker.deleteLater)
        self.adc_thread.finished.connect(self.adc_thread.deleteLater)
        self.adc_worker.sampleData.connect(self.on_sample_data_received)
        self.adc_worker.dataSaved.connect(self.dataSaved)
        
        # 启动线程
        self.adc_thread.start()
    
    def on_sampling_finished(self, success, message):
        """采样完成"""
        if success:
            self.dataLoaded.emit(message)
        else:
            self.errorOccurred.emit(message)
    
    def on_sample_data_received(self, sample_data):
        """接收到采样数据"""
        for data in sample_data:
            self.model.add_adc_sample(data)
        self.dataLoaded.emit(f"接收到 {len(sample_data)} 组采样数据")
    
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
                
                self.dataLoaded.emit(f"成功加载 {len(file_paths)} 个文件")
        except Exception as e:
            self.errorOccurred.emit(f"加载文件失败: {str(e)}")
    
    def on_clear_files(self):
        """清除文件列表"""
        self.model.data_files.clear()
        self.model.current_data = None
        self.view.file_list.clear()
        self.dataLoaded.emit("已清除文件列表")
    
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
    
    def on_file_selected(self, row):
        """文件选择变化"""
        if 0 <= row < len(self.model.data_files):
            file_path = self.model.data_files[row]
            try:
                self.model.current_data = self.load_data_file(file_path)
                self.dataLoaded.emit(f"已加载文件: {os.path.basename(file_path)}")
            except Exception as e:
                self.errorOccurred.emit(f"加载数据失败: {str(e)}")
                self.model.current_data = None
    
    def on_analyze(self):
        """执行分析"""
        if self.model.analysis_type == "ADC数据分析":
            self.analyze_adc_data()
            return
        
        if not self.model.current_data:
            self.errorOccurred.emit("请先选择数据文件")
            return
        
        try:
            self.analysisStarted.emit(self.model.analysis_type)
            
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
            self.errorOccurred.emit(f"分析失败: {str(e)}")
    
    def analyze_adc_data(self):
        """执行ADC数据分析"""
        try:
            # 更新配置
            config = self.model.adc_config
            config.clock_freq = self.view.adc_clock_freq.value()
            config.trigger_freq = self.view.adc_trigger_freq.value()
            config.roi_start_tenths = self.view.adc_roi_start.value()
            config.roi_end_tenths = self.view.adc_roi_end.value()
            config.recursive = self.view.adc_recursive_check.isChecked()
            config.use_signed18 = self.view.adc_signed_check.isChecked()
            
            self.analysisStarted.emit("ADC数据分析")
            
            # 创建分析器并运行
            analyzer = DataAnalyzer(config)
            results = analyzer.batch_process_files(self.model.data_files)
            averages = analyzer.calculate_averages(results)
        
            # 格式化结果
            analysis_results = {
                "processed_files": f"{results['success_count']}/{results['total_files']}",
                "clock_frequency": f"{config.clock_freq/1e6:.2f} MHz",
                "trigger_frequency": f"{config.trigger_freq/1e6:.2f} MHz",
                "roi_range": f"{config.roi_start_tenths}%-{config.roi_end_tenths}%",
                "sampling_rate": f"{analyzer.config.fs_eff/1e6:.2f} MS/s"
            }
            
            # 生成绘图数据
            self.generate_plot_data(results, averages, analyzer.config)
            self.model.results = analysis_results
            self.analysisCompleted.emit(analysis_results)
            
        except Exception as e:
            self.errorOccurred.emit(f"ADC数据分析失败: {str(e)}")

    def set_main_window_controller(self, main_window_controller):
        """设置主窗口控制器引用"""
        self.main_window_controller = main_window_controller

    def get_plot_controller(self, plot_name):
        """获取绘图控制器"""
        if hasattr(self, 'main_window_controller') and self.main_window_controller:
            return self.main_window_controller.sub_controllers.get(plot_name)
        return None


    def generate_plot_data(self, results, averages, config):
        """生成绘图数据，完全参考plot_results函数的实现"""
        try:
            # 清除所有现有的标记线
            self.clear_all_markers()
            
            # 时域数据 - 转换为电压值
            t_roi_us = (np.arange(config.l_roi) * config.ts_eff) * 1e6
            
            # 将ADC数据转换为电压值 (±3V范围，带符号19位)
            # 19位带符号数据的范围是 -2^18 到 2^18-1 (-262144 到 262143)
            # 电压转换公式: voltage = (adc_value / 2^18) * 3.0
            adc_max_value = 2**19  # 262144
            y_avg_voltage = (averages['y_avg'] / adc_max_value) * 3.0
            
            # 边缘位置计算
            edge_in_roi = (config.n_points // 4 - config.roi_start)
            
            # 获取时域绘图控制器
            time_controller = self.get_plot_controller('plot_time')
            if time_controller:
                # 清除现有绘图
                time_controller.view.clear_plot()
                
                # 绘制时域信号 (使用电压值)
                time_controller.plot_time_domain(t_roi_us, y_avg_voltage, "时间", "电压", "μs", "V")
                
                # 添加边缘位置标记
                if 0 <= edge_in_roi < config.l_roi:
                    self.add_vertical_line(time_controller, t_roi_us[edge_in_roi], 'red', 'Edge Position')
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
            y_d_avg_voltage = (averages['y_d_avg'] / adc_max_value) * 3.0
            
            # 获取或创建差分时域绘图控制器
            diff_time_controller = self.get_plot_controller('plot_diff_time')
            if not diff_time_controller:
                self.create_additional_plot_tabs()
                diff_time_controller = self.get_plot_controller('plot_diff_time')
            
            if diff_time_controller:
                # 清除现有绘图
                diff_time_controller.view.clear_plot()
                
                diff_time_controller.plot_diff_time_domain(t_diff_us, y_d_avg_voltage, "时间", "差分电压", "μs", "V")
                
                # 添加边缘位置标记
                if (0 <= edge_in_roi < config.l_roi and 
                    0 <= edge_in_roi - config.diff_points < len(y_d_avg_voltage)):
                    edge_pos = t_roi_us[max(edge_in_roi - config.diff_points, 0)]
                    self.add_vertical_line(diff_time_controller, edge_pos, 'red', 'Edge Position')
            
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



    def add_vertical_line(self, plot_controller, x_position, color='red', label=''):
        """添加垂直标记线"""
        try:
            if hasattr(plot_controller, 'add_vertical_line'):
                plot_controller.add_vertical_line(x_position, color, 'dashed', label)
            else:
                # 备用方案：直接操作plot_widget
                plot_widget = plot_controller.view.plot_widget
                line = pg.InfiniteLine(pos=x_position, angle=90, 
                                    pen=pg.mkPen(color, width=1, style=pg.QtCore.Qt.DashLine))
                plot_widget.addItem(line)
                
                if label:
                    text = pg.TextItem(text=label, color=color, anchor=(0.5, 1))
                    y_range = plot_widget.getViewBox().viewRange()[1]
                    text.setPos(x_position, y_range[1] * 0.9)
                    plot_widget.addItem(text)
                    
        except Exception as e:
            self.errorOccurred.emit(f"添加标记线失败: {str(e)}")



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

    
    
    def on_export(self):
        """导出分析结果"""
        if not self.model.results:
            self.errorOccurred.emit("没有可导出的分析结果")
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
                # 获取文件扩展名
                file_ext = os.path.splitext(file_path)[1].lower()
                
                if file_ext == '.csv':
                    # 使用DataAnalyze的save_results函数保存CSV数据
                    self.export_csv_results(file_path)
                elif file_ext == '.json':
                    # 保存JSON格式的结果
                    self.export_json_results(file_path)
                else:
                    # 默认保存文本格式
                    self.export_text_results(file_path)
                
                self.dataLoaded.emit(f"结果已导出到: {file_path}")
                
        except Exception as e:
            self.errorOccurred.emit(f"导出失败: {str(e)}")

    def export_csv_results(self, file_path):
        """使用DataAnalyze的save_results函数导出CSV结果"""
        try:
            # 创建临时的分析配置
            config = AnalysisConfig(output_csv=file_path)
            
            # 创建DataAnalyzer实例
            analyzer = DataAnalyzer(config)
            
            # 获取当前的分析结果数据（这里需要根据实际情况调整）
            # 假设我们有存储的results和averages数据
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
                    else:
                        self.errorOccurred.emit("复数FFT结果导出失败")
                
                # 同时保存时域数据
                self.export_additional_csv_data(file_path, results, averages)
                
            else:
                # 如果没有分析数据，保存基本的文本结果
                self.export_text_results(file_path)
                
        except Exception as e:
            self.errorOccurred.emit(f"CSV导出失败: {str(e)}")

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
            
            # 保存频域数据
            freq_domain_file = f"{base_path}_frequency_domain.csv"
            if 'freq_ref' in results and 'mag_avg_db' in averages:
                mask = results['freq_ref'] <= (self.model.adc_config.show_up_to_GHz * 1e9)
                freq_data = np.column_stack((results['freq_ref'][mask] / 1e9, 
                                        averages['mag_avg_db'][mask]))
                np.savetxt(freq_domain_file, freq_data, delimiter=',', 
                        header='Frequency(GHz),Magnitude(dB)', comments='')
                self.dataLoaded.emit(f"频域数据已保存到: {os.path.basename(freq_domain_file)}")
            
            # 保存差分时域数据
            diff_time_file = f"{base_path}_diff_time_domain.csv"
            if 'y_d_avg' in averages:
                t_diff_us = (np.arange(len(averages['y_d_avg'])) * self.model.adc_config.ts_eff * 1e6)
                diff_time_data = np.column_stack((t_diff_us, averages['y_d_avg']))
                np.savetxt(diff_time_file, diff_time_data, delimiter=',', 
                        header='Time(us),Differential_Amplitude', comments='')
                self.dataLoaded.emit(f"差分时域数据已保存到: {os.path.basename(diff_time_file)}")
            
            # 保存差分频域数据
            diff_freq_file = f"{base_path}_diff_frequency_domain.csv"
            if 'freq_d_ref' in results and 'mag_d_avg_db' in averages:
                maskd = results['freq_d_ref'] <= (self.model.adc_config.show_up_to_GHz * 1e9)
                diff_freq_data = np.column_stack((results['freq_d_ref'][maskd] / 1e9, 
                                                averages['mag_d_avg_db'][maskd]))
                np.savetxt(diff_freq_file, diff_freq_data, delimiter=',', 
                        header='Frequency(GHz),Differential_Magnitude(dB)', comments='')
                self.dataLoaded.emit(f"差分频域数据已保存到: {os.path.basename(diff_freq_file)}")
                
        except Exception as e:
            self.errorOccurred.emit(f"附加数据导出失败: {str(e)}")

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
            else:
                self.errorOccurred.emit("JSON导出失败")
                
        except Exception as e:
            self.errorOccurred.emit(f"JSON导出失败: {str(e)}")

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
            
        except Exception as e:
            self.errorOccurred.emit(f"文本导出失败: {str(e)}")

    # 在analyze_adc_data方法中保存分析结果供导出使用
    def analyze_adc_data(self):
        """执行ADC数据分析"""
        try:
            # 更新配置
            config = self.model.adc_config
            config.clock_freq = self.view.adc_clock_freq.value()
            config.trigger_freq = self.view.adc_trigger_freq.value()
            config.roi_start_tenths = self.view.adc_roi_start.value()
            config.roi_end_tenths = self.view.adc_roi_end.value()
            config.recursive = self.view.adc_recursive_check.isChecked()
            config.use_signed18 = self.view.adc_signed_check.isChecked()
            
            self.analysisStarted.emit("ADC数据分析")
            
            # 创建分析器并运行
            analyzer = DataAnalyzer(config)
            results = analyzer.batch_process_files(self.model.data_files)
            averages = analyzer.calculate_averages(results)
        
            # 保存分析结果供导出使用
            self.last_analysis_results = results
            self.last_averages = averages
        
            # 格式化结果
            analysis_results = {
                "processed_files": f"{results['success_count']}/{results['total_files']}",
                "clock_frequency": f"{config.clock_freq/1e6:.2f} MHz",
                "trigger_frequency": f"{config.trigger_freq/1e6:.2f} MHz",
                "roi_range": f"{config.roi_start_tenths}%-{config.roi_end_tenths}%",
                "sampling_rate": f"{analyzer.config.fs_eff/1e6:.2f} MS/s"
            }
            
            # 生成绘图数据
            self.generate_plot_data(results, averages, analyzer.config)
            self.model.results = analysis_results
            self.analysisCompleted.emit(analysis_results)
            
        except Exception as e:
            self.errorOccurred.emit(f"ADC数据分析失败: {str(e)}")

    
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
