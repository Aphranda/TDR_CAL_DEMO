# src/app/widgets/DataAnalysisPanel/Controller.py
import os
import numpy as np
from PyQt5.QtWidgets import QFileDialog, QMessageBox
from PyQt5.QtCore import QObject, pyqtSignal, QThread, pyqtSlot
from ...core.ADCSample import ADCSample
from ...core.DataAnalyze import DataAnalyzer, AnalysisConfig
from ...core.FileManager import FileManager
import time

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
    
    def __init__(self, view, model):
        super().__init__()
        self.view = view
        self.model = model
        self.adc_sample = ADCSample()
        self.adc_worker = None
        self.adc_thread = None
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

        # 数据保存信号连接
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
        save_raw_data = self.view.save_raw_check.isChecked()
        output_dir = self.view.output_dir_edit.text() or 'CSV_Data_test_results'
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
        if analysis_type == "S参数":
            self.view.show_s_parameter_options()
        elif analysis_type == "TDR":
            self.view.show_tdr_options()
        elif analysis_type == "ADC数据分析":
            self.view.show_adc_analysis_options()
    
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
            config.clock_freq = self.view.adc_clock_freq.value() * 1e6
            config.trigger_freq = self.view.adc_trigger_freq.value() * 1e6
            config.roi_start_tenths = self.view.adc_roi_start.value()
            config.roi_end_tenths = self.view.adc_roi_end.value()
            config.recursive = self.view.adc_recursive_check.isChecked()
            config.use_signed18 = self.view.adc_signed_check.isChecked()
            
            self.analysisStarted.emit("ADC数据分析")
            
            # 创建分析器并运行
            analyzer = DataAnalyzer(config)
            results = analyzer.batch_process_files()
            averages = analyzer.calculate_averages(results)
            
            # 格式化结果
            analysis_results = {
                "processed_files": f"{results['success_count']}/{results['total_files']}",
                "clock_frequency": f"{config.clock_freq/1e6:.2f} MHz",
                "trigger_frequency": f"{config.trigger_freq/1e6:.2f} MHz",
                "roi_range": f"{config.roi_start_tenths}%-{config.roi_end_tenths}%",
                "sampling_rate": f"{analyzer.config.fs_eff/1e6:.2f} MS/s"
            }
            
            self.model.results = analysis_results
            self.analysisCompleted.emit(analysis_results)
            
        except Exception as e:
            self.errorOccurred.emit(f"ADC数据分析失败: {str(e)}")
    
    def on_export(self):
        """导出分析结果"""
        if not self.model.results:
            self.errorOccurred.emit("没有可导出的分析结果")
            return
        
        try:
            file_path, _ = QFileDialog.getSaveFileName(
                self.view,
                "导出分析结果",
                "",
                "CSV文件 (*.csv);;文本文件 (*.txt);;所有文件 (*)"
            )
            
            if file_path:
                self.export_results(file_path, self.model.results)
                self.dataLoaded.emit(f"结果已导出到: {file_path}")
                
        except Exception as e:
            self.errorOccurred.emit(f"导出失败: {str(e)}")
    
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
