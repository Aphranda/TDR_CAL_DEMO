# src/app/widgets/DataAnalysisPanel/Controller.py
import os
import numpy as np
from PyQt5.QtWidgets import QFileDialog
from PyQt5.QtCore import QObject, pyqtSignal, QThread

from ...core.DataAnalyze import DataAnalyzer, AnalysisConfig
from ...core.FileManager import FileManager
from app.core.ConfigManager import ADCMode
from ...widgets.PlotWidget import create_plot_widget
from app.threads import ADCProcessWorker
from app.threads import FileLoadWorker
from app.threads import DataExportWorker
import time
from ...core.PerformanceMonitor import timeit, performance_monitor


# 搜索方法枚举
class SearchMethod:
    RISING = 1
    MAX = 2

class DataAnalysisController(QObject):
    # 定义信号
    dataLoaded = pyqtSignal(str)  # 数据加载完成信号
    analysisStarted = pyqtSignal(str)  # 分析开始信号
    analysisCompleted = pyqtSignal(dict)  # 分析完成信号，传递结果
    errorOccurred = pyqtSignal(str)  # 错误信号
    plotDataReady = pyqtSignal(str, np.ndarray, np.ndarray)  # 绘图数据准备信号 (类型, x_data, y_data)
    analysisProgress = pyqtSignal(int, int, str)  # 新增：分析进度信号
    fileLoadProgress = pyqtSignal(int, int, str)  # 新增：文件加载进度信号
  
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
        self.view.clear_plot.clicked.connect(self.on_clear_plots)  # 新增：连接清除绘图按钮
      
      
        # 分析按钮
        self.view.analyze_button.clicked.connect(self.on_analyze)
        self.view.export_button.clicked.connect(self.on_export)
      
        # 文件列表选择变化
        self.view.file_list.currentRowChanged.connect(self.on_file_selected)
      
        # 错误信号连接到日志记录
        self.errorOccurred.connect(lambda msg: self.log_message(msg, "ERROR"))
        self.dataLoaded.connect(lambda msg: self.log_message(msg, "INFO"))
        self.analysisCompleted.connect(self.log_analysis_results)

        # 连接分析进度信号
        self.analysisProgress.connect(self.on_analysis_progress)

    def on_clear_plots(self):
        """清除所有绘图"""
        self.clear_all_plot_tabs()
        self.log_message("已清除所有绘图", "INFO")

    def on_analysis_progress(self, current, total, message):
        """处理分析进度更新"""
        # 这里不再更新本地进度条，而是通过信号传递给主窗口
        pass

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
        """加载数据文件 - 使用工作线程避免界面卡顿"""
        try:
            file_paths, _ = QFileDialog.getOpenFileNames(
                self.view,
                "选择数据文件",
                "",
                "数据文件 (*.s2p *.csv *.txt *.dat *.bin);;"
                "文本文件 (*.csv *.txt *.dat);;"
                "二进制文件 (*.bin *.raw);;"
                "所有文件 (*)"
            )
        
            if not file_paths:
                return

            # 更新配置
            self.model.adc_config.max_read_size_bytes = self.view.adc_max_read_size.value()*0.32+0.32
            
            # 禁用加载按钮，避免重复点击
            self.view.load_button.setEnabled(False)
            self.view.load_button.setText("加载中...")

            # 创建工作线程
            self.file_load_thread = QThread()
            self.file_load_worker = FileLoadWorker(
                file_paths, 
                self.model.adc_config.max_read_size_bytes,
                self.extract_adc_data_from_binary  # 传递段数检测函数
            )
            self.file_load_worker.moveToThread(self.file_load_thread)

            # 连接信号
            self.file_load_thread.started.connect(self.file_load_worker.run)
            self.file_load_worker.progress.connect(self.on_file_load_progress)
            self.file_load_worker.finished.connect(self.on_file_load_finished)
            self.file_load_worker.finished.connect(self.file_load_thread.quit)
            self.file_load_worker.finished.connect(self.file_load_worker.deleteLater)
            self.file_load_thread.finished.connect(self.file_load_thread.deleteLater)
            self.file_load_worker.error.connect(self.on_file_load_error)
            self.file_load_worker.log_message.connect(self.log_message)

            # 启动线程
            self.file_load_thread.start()

        except Exception as e:
            error_msg = f"启动文件加载失败: {str(e)}"
            self.errorOccurred.emit(error_msg)
            self.log_message(error_msg, "ERROR")

    def on_file_load_progress(self, current, total, filename):
        """文件加载进度更新"""
        # 通过信号传递给主窗口控制器
        if hasattr(self, 'fileLoadProgress'):
            self.fileLoadProgress.emit(current, total, f"检测文件: {filename}")
        

    def on_file_load_finished(self, data_files, file_segments):
        """文件加载完成"""
        try:
            # 恢复按钮状态
            self.view.load_button.setEnabled(True)
            self.view.load_button.setText("加载文件")
            
            # 更新模型数据
            self.model.data_files = data_files
            self.view.file_list.clear()
            
            # 更新文件列表显示
            total_segments = 0
            for channel in ['adc1', 'adc2']:
                for file_info in data_files[channel]:
                    filename = os.path.basename(file_info['path'])
                    segments = file_info['segments']
                    total_segments += segments
                    
                    # file_format = FileManager().detect_file_format(file_info['path'])
                    file_format = 'bin'
                    display_name = f"[{channel.upper()}] {filename} [{file_format}] - {segments}段"
                    self.view.file_list.addItem(display_name)
            
            # 检查文件匹配情况
            adc1_count = len(data_files['adc1'])
            adc2_count = len(data_files['adc2'])
            
            
            if adc1_count != adc2_count:
                self.log_message(f"警告: ADC1和ADC2的文件数量不匹配 (ADC1: {adc1_count}, ADC2: {adc2_count})", "WARNING")
            
            # 检查段数匹配
            self.check_segment_matching(file_segments)
            
            # 记录详细信息
            # self.log_loaded_file_details()
            
            # 修复这里：使用正确的数据源计算总文件数
            total_files = adc1_count + adc2_count
            msg = f"成功加载 {total_files} 个文件 (ADC1: {adc1_count}, ADC2: {adc2_count}), 共 {total_segments} 段数据"
            self.dataLoaded.emit(msg)
            self.log_message(msg, "INFO")
            
            # 清除进度显示
            if hasattr(self, 'main_window_controller') and self.main_window_controller:
                self.main_window_controller.clear_progress()
                
        except Exception as e:
            error_msg = f"处理加载结果失败: {str(e)}"
            self.errorOccurred.emit(error_msg)
            self.log_message(error_msg, "ERROR")
            
            # 确保按钮状态恢复
            self.view.load_button.setEnabled(True)
            self.view.load_button.setText("加载文件")

    def on_file_load_error(self, error_message):
        """文件加载错误"""
        # 恢复按钮状态
        self.view.load_button.setEnabled(True)
        self.view.load_button.setText("加载文件")
        
        self.errorOccurred.emit(error_message)
        self.log_message(error_message, "ERROR")
        
        # 清除进度显示
        if hasattr(self, 'main_window_controller') and self.main_window_controller:
            self.main_window_controller.clear_progress()


    def log_loaded_file_details(self):
        """记录加载文件的详细信息，用于调试"""
        self.log_message("加载的文件详细信息:", "DEBUG")
        self.log_message("=" * 50, "DEBUG")
        
        for channel in ['adc1', 'adc2']:
            if self.model.data_files[channel]:
                self.log_message(f"{channel.upper()} 文件:", "DEBUG")
                for i, file_info in enumerate(self.model.data_files[channel]):
                    self.log_message(f"  文件 {i+1}: {os.path.basename(file_info['path'])}", "DEBUG")
                    self.log_message(f"    段数: {file_info['segments']}", "DEBUG")
                    self.log_message(f"    段索引: {file_info['segment_indices']}", "DEBUG")
                    
                    # 如果有段信息，记录上升沿位置
                    if 'segment_info' in file_info and 'rise_edge_positions' in file_info['segment_info']:
                        rise_edges = file_info['segment_info']['rise_edge_positions']
                        if len(rise_edges) > 0:
                            self.log_message(f"    上升沿位置(前5个): {rise_edges[:5]}", "DEBUG")
                    
                    if 'segment_info' in file_info and 'segment_lengths' in file_info['segment_info']:
                        seg_lengths = file_info['segment_info']['segment_lengths']
                        if len(seg_lengths) > 0:
                            self.log_message(f"    段长度统计: 最小={min(seg_lengths)}, 最大={max(seg_lengths)}, 平均={np.mean(seg_lengths):.1f}", "DEBUG")

    def check_segment_matching(self, file_segments):
        """检查ADC1和ADC2文件的段数是否匹配"""
        adc1_files = [f for f in file_segments.keys() if 'adc1' in f or 'ch1' in f or 'channel1' in f]
        adc2_files = [f for f in file_segments.keys() if 'adc2' in f or 'ch2' in f or 'channel2' in f]
        
        # 如果两个ADC的文件数量不同，无法进行一一匹配
        if len(adc1_files) != len(adc2_files):
            self.log_message("ADC1和ADC2文件数量不同，无法进行段数匹配检查", "WARNING")
            return
        
        # 对文件进行排序，确保匹配正确的文件对
        adc1_files.sort()
        adc2_files.sort()
        
        # 检查每对文件的段数是否匹配
        for i, (adc1_file, adc2_file) in enumerate(zip(adc1_files, adc2_files)):
            adc1_segments = file_segments[adc1_file]
            adc2_segments = file_segments[adc2_file]
            
            if adc1_segments != adc2_segments:
                self.log_message(f"警告: 文件对 {adc1_file} 和 {adc2_file} 的段数不匹配 (ADC1: {adc1_segments}, ADC2: {adc2_segments})", "WARNING")
            else:
                self.log_message(f"文件对 {adc1_file} 和 {adc2_file} 的段数匹配: {adc1_segments} 段", "INFO")

 

    def extract_adc_data_from_binary(self, file_path, max_read_size=None):
        """
        从二进制文件中提取ADC数据并检测段数 - numpy优化版本
        
        Args:
            file_path: 二进制文件路径
            max_read_size: 最大读取大小（字节），如果为None则使用配置中的值
            
        Returns:
            段数和数据信息字典
        """
        try:
            # 使用配置中的最大读取大小，如果未指定则使用默认值
            if max_read_size is None:
                max_read_size = int(self.model.adc_config.max_read_size_bytes * 1024 * 1024)
            
            file_size = os.path.getsize(file_path)
            read_size = min(file_size, max_read_size)
            
            # 记录读取信息
            self.log_message(f"读取文件 {os.path.basename(file_path)}: 文件大小 {file_size/1024/1024:.2f}MB, 读取大小 {read_size/1024/1024:.2f}MB", "DEBUG")
            
            # 优化1: 使用numpy直接读取文件，避免中间转换
            uint32_arr = np.fromfile(file_path, dtype=np.uint32, count=read_size//4)
            
            if len(uint32_arr) == 0:
                self.log_message(f"文件 {file_path} 太小或格式不正确", "WARNING")
                return 1, {"error": "文件太小或格式不正确"}
            
            # 优化2: 使用向量化操作提取bit31
            bit31 = (uint32_arr >> 31) & 1
            
            # 打印bit31的基本统计信息
            self.log_message(f"文件 {os.path.basename(file_path)}: bit31统计 - 总点数: {len(bit31)}, 1的数量: {np.sum(bit31)}, 0的数量: {len(bit31) - np.sum(bit31)}", "DEBUG")
            
            # 检测上升沿：使用新的固定段长方法
            rise_edges = self.detect_valid_data_segments(bit31)
            
            # 计算段数
            segments = len(rise_edges)
            
            # 优化3: 向量化提取ADC数据
            adc_data = uint32_arr & 0x3FFFF  # 0x3FFFF = 2^18-1
            
            # 计算每段的长度（应该是固定的81920 + 100）
            segment_lengths = []
            segment_details = []
            
            for i in range(segments):
                start_idx = rise_edges[i]
                # 计算结束位置：起点 + 固定段长 + 100
                end_idx = start_idx + 81920 + 100
                
                # 如果超出数组长度，调整到数组末尾
                if end_idx > len(uint32_arr):
                    end_idx = len(uint32_arr)
                
                segment_length = end_idx - start_idx
                segment_lengths.append(segment_length)
                
                segment_details.append({
                    'segment_index': i,
                    'start_position': start_idx,
                    'end_position': end_idx,
                    'length': segment_length,
                    'expected_length': 81920 + 100,  # 固定段长 + 100
                    'length_diff': segment_length - (81920 + 100),
                    'data_points_available': segment_length
                })
            
            # 打印段长度信息
            if segment_lengths:
                self.log_message(f"文件 {os.path.basename(file_path)}: 段长度统计 - 最小: {min(segment_lengths)}, 最大: {max(segment_lengths)}, 平均: {np.mean(segment_lengths):.1f}", "DEBUG")
                
                # 检查段长度是否接近期望值
                expected_length = 81920 + 100
                for i, length in enumerate(segment_lengths):
                    if abs(length - expected_length) > 200:  # 允许200个点的误差
                        self.log_message(f"警告: 段 {i} 长度 {length} 与期望值 {expected_length} 相差较大", "WARNING")
            
            result = {
                "total_samples": len(uint32_arr),
                "rise_edge_positions": rise_edges,
                "segment_lengths": segment_lengths,
                "segment_details": segment_details,
                "avg_segment_length": np.mean(segment_lengths) if segment_lengths else len(uint32_arr),
                "adc_data_sample": adc_data[:100].tolist(),  # 前100个采样点作为示例
                "segmentation_method": "fixed_length_81920_plus_100"  # 标记使用的分段方法
            }
            
            self.log_message(f"文件 {os.path.basename(file_path)}: 检测到 {segments} 段数据（使用固定段长81920+100）", "INFO")
            
            return max(1, segments), result
            
        except Exception as e:
            self.log_message(f"提取ADC数据失败: {str(e)}", "ERROR")
            return 1, {"error": str(e)}
       
    # @timeit
    def detect_valid_data_segments(self, bit31_data, start_index=0):
        """
        检测有效数据段（基于bit31的上升沿）
        修改：第一个上升沿固定为10，后续都加上81920固定长度
        
        Args:
            bit31_data: bit31数据数组
            start_index: 开始检测的索引
            
        Returns:
            上升沿位置列表
        """
        try:
            diff = np.diff(bit31_data)
            first_rise_edge = None
            
            # 从start_index开始寻找第一个上升沿
            for i in range(start_index, len(diff)):
                if diff[i] == 1:
                    first_rise_edge = i + 1  # +1 因为diff使索引偏移
                    break
            
            if first_rise_edge is None:
                self.log_message("未找到有效的上升沿,使用默认有效上升沿10", "WARNING")
                first_rise_edge = 10
            
            
            # 计算总长度
            total_length = len(bit31_data)
            segment_length = 81920  # 固定段长度
            
            # 生成所有上升沿位置
            rise_edges = []
            current_edge = first_rise_edge
            
            while current_edge < total_length:
                rise_edges.append(current_edge)
                current_edge += segment_length
            
            self.log_message(f"使用固定第一个上升沿位置: {first_rise_edge}", "DEBUG")
            self.log_message(f"基于固定段长度 {segment_length} 生成了 {len(rise_edges)} 个段", "DEBUG")
            if rise_edges:
                self.log_message(f"前5个上升沿位置: {rise_edges[:5]}{'...' if len(rise_edges) > 5 else ''}", "DEBUG")
            
            return rise_edges
            
        except Exception as e:
            self.log_message(f"检测有效数据段失败: {str(e)}", "ERROR")
            return []
    
    def detect_valid_data_segments1(self, bit31_data, start_index=0):
        """
        检测有效数据段（基于bit31的上升沿）
        修改：找到第一个valid index后，后续的valid index都是在前一个基础上加上81920固定长度
        
        Args:
            bit31_data: bit31数据数组
            start_index: 开始检测的索引
            
        Returns:
            上升沿位置列表
        """
        try:
            # 检测第一个上升沿：从0变为1的位置
            diff = np.diff(bit31_data)
            first_rise_edge = 10
            
            # 从start_index开始寻找第一个上升沿
            for i in range(start_index, len(diff)):
                if diff[i] == 1:
                    first_rise_edge = i + 1  # +1 因为diff使索引偏移
                    break
            
            if first_rise_edge is None:
                self.log_message("未找到有效的上升沿", "WARNING")
                return []
            
            # 计算总长度
            total_length = len(bit31_data)
            segment_length = 81920  # 固定段长度（不包括尾部的100个点）
            
            # 生成所有上升沿位置
            rise_edges = []
            current_edge = first_rise_edge
            
            while current_edge < total_length:
                rise_edges.append(current_edge)
                current_edge += segment_length
            
            self.log_message(f"检测到第一个上升沿位置: {first_rise_edge}", "DEBUG")
            self.log_message(f"基于固定段长度 {segment_length} 生成了 {len(rise_edges)} 个段", "DEBUG")
            self.log_message(f"上升沿位置: {rise_edges[:5]}{'...' if len(rise_edges) > 5 else ''}", "DEBUG")
            
            return rise_edges
            
        except Exception as e:
            self.log_message(f"检测有效数据段失败: {str(e)}", "ERROR")
            return []

     
    # 在on_clear_files方法中清除段数信息
    def on_clear_files(self):
        """清除文件列表"""
        self.model.data_files = {'adc1': [], 'adc2': []}
        self.model.current_data = None
        self.view.file_list.clear()
        

        # 清理分析数据
        self.cleanup_analysis()
        
        msg = "已清除文件列表和分析数据"
        self.dataLoaded.emit(msg)
        self.log_message(msg, "INFO")

  
  
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
      

    def analyze_adc_data(self):
        """执行ADC数据分析"""
        if not self.model.data_files['adc1'] and not self.model.data_files['adc2']:
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
            config.roi_mid_tenths = self.view.adc_roi_mid.value()
            config.roi_end_tenths = self.view.adc_roi_end.value()
            config.diff_points = self.view.adc_diff_points.value()
            config.average_points = self.view.adc_average_points.value()
            config.max_read_size_mb = self.view.adc_max_read_size.value()*0.32+0.32  # 新增：获取最大读取大小
            config.recursive = True
            config.use_signed18 = True
            
            config.adc_bit = self.view.get_selected_bit_width()
            self.log_message(f"校准模式:{config.cal_mode}", "DEBUG")
            # 校准模式和搜索模式固定
            config.cal_mode = 'THRU'
            config.search_method = 1
           
            adc1_count = len(self.model.data_files['adc1'])
            adc2_count = len(self.model.data_files['adc2'])

            # 更新分析模式
            if adc1_count > 0 and adc2_count > 0:
                config.adc_mode = ADCMode.BOTH_ADCS
                self.log_message("检测到ADC1和ADC2数据文件，启用双通道模式", "INFO")
            elif adc1_count > 0 and adc2_count == 0:
                config.adc_mode = ADCMode.ADC1_ONLY
                self.log_message("仅检测到ADC1数据文件，启用单通道模式", "INFO")
            elif adc1_count == 0 and adc2_count > 0:
                config.adc_mode = ADCMode.ADC2_ONLY
                self.log_message("仅检测到ADC2数据文件，启用单通道模式", "INFO")
            else:
                config.adc_mode = ADCMode.ADC1_ONLY  # 默认模式
                self.log_message("未检测到有效数据文件，使用默认模式", "WARNING")

            
            # 获取对齐方式
            alignment_reference = self.view.get_alignment_reference()

            # 新增：获取AlignPos值
            config.align_pos = int(100/self.view.align_pos_spin.value())

            self.log_message(f"使用对齐参考: {alignment_reference.upper()}", "INFO")
        
            self.analysisStarted.emit("ADC数据分析")
            self.log_message("开始ADC数据分析", "INFO")
        
            # 创建工作线程，传递两个ADC的文件路径
            self.adc_process_thread = QThread()
            self.adc_process_worker = ADCProcessWorker(self.model.data_files, config, batch_size=10,alignment_reference=alignment_reference)
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
        # 通过信号传递给主窗口的进度面板
        self.analysisProgress.emit(current, total, message)
        
        # 记录日志
        self.log_message(f"处理进度: {current}/{total} - {message}", "INFO")

    def on_adc_process_finished(self, results, averages):
        """ADC处理完成 - 处理双通道数据"""
        try:
            # 保存分析结果供导出使用
            self.last_analysis_results = results
            self.last_averages = averages
        
            # 格式化结果
            config = self.model.adc_config
            analysis_results = {
                "clock_frequency": f"{config.clock_freq/1e6:.2f} MHz",
                "trigger_frequency": f"{config.trigger_freq/1e6:.2f} MHz",
                "roi_range": f"{config.roi_start_tenths}%-{config.roi_end_tenths}%",
                "sampling_rate": f"{config.fs_eff/1e6:.2f} MS/s"
            }
        
            # 生成绘图数据 - 分别处理ADC1和ADC2
            self.generate_plot_data(results, averages, config)
            self.model.results = analysis_results
            self.analysisCompleted.emit(analysis_results)
        
            self.log_message("分析完成! 成功处理")
            
        finally:
            # 清理工作线程引用
            import gc
            gc.collect()

    def cleanup_analysis(self):
        """清理分析过程中使用的内存"""
        if hasattr(self, 'last_analysis_results'):
            del self.last_analysis_results
        if hasattr(self, 'last_averages'):
            del self.last_averages
        
        # 清理绘图数据
        for plot_name in ['plot_time', 'plot_freq', 'plot_diff_time', 'plot_diff_freq']:
            controller = self.get_plot_controller(plot_name)
            if controller and hasattr(controller, 'clear_plot_data'):
                controller.clear_plot_data()
        
        # 强制垃圾回收
        import gc
        gc.collect()
    

    def on_adc_process_error(self, error_message):
        """ADC处理错误"""
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
        """生成绘图数据 - 支持双通道"""
        try:
            # 移除主界面默认的绘图页
            self.clear_all_plot_tabs()
            
            # 清除所有现有的标记线
            self.clear_all_markers()
            
            # 为每个通道生成绘图数据
            for channel in ['adc1', 'adc2']:
                if channel in results and channel in averages:
                    self._generate_channel_plot_data(channel, results[channel], averages[channel], config)
                
        except Exception as e:
            self.errorOccurred.emit(f"生成绘图数据失败: {str(e)}")
            self.log_message(f"生成绘图数据失败: {str(e)}", "ERROR")

    def create_plot_tab(self, plot_name, plot_title):
        """创建绘图标签页，并根据类型设置不同颜色"""
        if not hasattr(self, 'main_window_controller') or not self.main_window_controller:
            return None
        
        main_window_view = self.main_window_controller.view
        
        # 检查是否已存在同名的控制器，如果存在则先移除
        if plot_name in self.main_window_controller.sub_controllers:
            # 查找对应的标签页并移除
            tab_name = plot_title.replace(" ", "")
            for i in range(main_window_view.plot_area.count()):
                if main_window_view.plot_area.tabText(i) == tab_name:
                    main_window_view.plot_area.removeTab(i)
                    break
            
            # 移除控制器引用
            del self.main_window_controller.sub_controllers[plot_name]
        
        # 创建绘图控件
        plot_view, plot_controller = create_plot_widget(plot_title)
        
        # 添加到主窗口
        tab_name = plot_title.replace(" ", "")
        index = main_window_view.add_plot_tab(plot_view, tab_name)
        
        # 根据绘图类型设置标签颜色
        if "时域" in plot_title and "差分" not in plot_title:
            color = "#3498DB"  # 蓝色 - 时域信号
        elif "频域" in plot_title and "差分" not in plot_title:
            color = "#27AE60"  # 绿色 - 频域信号
        elif "差分时域" in plot_title:
            color = "#E67E22"  # 橙色 - 差分时域
        elif "差分频域" in plot_title:
            color = "#9B59B6"  # 紫色 - 差分频域
        else:
            color = "#7F8C8D"  # 灰色 - 默认
        
        # 设置标签颜色
        try:
            main_window_view.set_plot_tab_color(index, color)
        except Exception as e:
            self.log_message(f"设置标签颜色失败: {str(e)}", "WARNING")
        
        # 保存控制器引用
        self.main_window_controller.sub_controllers[plot_name] = plot_controller
        
        return plot_controller


    def clear_all_plot_tabs(self):
        """移除所有绘图标签页，并清除对应的控制器引用"""
        if not hasattr(self, 'main_window_controller') or not self.main_window_controller:
            return
        
        main_window_view = self.main_window_controller.view
        
        # 获取左侧绘图区域的所有标签页名称
        plot_tab_names = []
        for i in range(main_window_view.plot_area.count()):
            tab_name = main_window_view.plot_area.tabText(i)
            plot_tab_names.append(tab_name)
        
        # 移除所有绘图标签页
        for tab_name in plot_tab_names:
            main_window_view.remove_plot_tab(tab_name)
        
        # 清除所有绘图控制器的引用
        keys_to_remove = [key for key in self.main_window_controller.sub_controllers.keys() 
                        if key.startswith('plot_')]
        for key in keys_to_remove:
            del self.main_window_controller.sub_controllers[key]
        
        # 强制垃圾回收
        import gc
        gc.collect()
        
        self.log_message("已移除所有绘图页和控制器引用", "INFO")



    def _generate_channel_plot_data(self, channel, results, averages, config):
        """生成单个通道的绘图数据"""
        try:
            # 生成时域数据并绘制
            self._generate_time_domain_data(channel, results, averages, config)
            
            # 生成频域数据并绘制
            self._generate_frequency_domain_data(channel, results, averages, config)
            
            # 生成差分时域数据并绘制
            self._generate_diff_time_domain_data(channel, results, averages, config)
            
            # 生成差分频域数据并绘制
            self._generate_diff_frequency_domain_data(channel, results, averages, config)
            
        except Exception as e:
            self.errorOccurred.emit(f"生成{channel}绘图数据失败: {str(e)}")
            self.log_message(f"生成{channel}绘图数据失败: {str(e)}", "ERROR")

    def _generate_time_domain_data(self, channel, results, averages, config):
        """生成时域数据并绘制"""
        # 时域数据 - 转换为电压值
        t_full_us = ((np.arange(config.roi_n(100)) * config.ts_eff) * 1e6)
        adc_max_value = 2**19  # 262144
        y_avg_voltage = (averages['y_full_avg'] / adc_max_value) * 3.0
        # 计算ROI时间范围
        roi_start_time = config.roi_start * config.ts_eff * 1e6
        roi_end_time = config.roi_end * config.ts_eff * 1e6
        
        # 获取时域绘图控制器
        plot_name = f'plot_time_{channel}'
        time_controller = self.get_plot_controller(plot_name)
        if not time_controller:
            time_controller = self.create_plot_tab(plot_name, f"{channel.upper()}时域信号")
        
        if time_controller:
            # 清除现有绘图
            time_controller.view.clear_plot()
            
            # 绘制时域信号 (使用电压值)
            time_controller.plot_time_domain(t_full_us, y_avg_voltage, "时间", "电压", "ns", "V", roi_start_time, roi_end_time)
            
            # 只有在边沿分析成功时才添加标记线
            if results.get('first_rise_pos') is not None:
                # 添加边缘位置标记线
                self.add_edge_markers(time_controller, results, config, t_full_us, y_avg_voltage)
        else:
            self.errorOccurred.emit(f"{channel}时域绘图控制器未找到")

    def _generate_frequency_domain_data(self, channel, results, averages, config):
        """生成频域数据并绘制"""
        # 频域数据
        mask = results['freq_ref'] <= (config.show_up_to_GHz * 1e9)
        freq_ghz = results['freq_ref'][mask] / 1e9
        mag_db = averages['mag_avg_db'][mask]
        
        # 获取频域绘图控制器
        plot_name = f'plot_freq_{channel}'
        freq_controller = self.get_plot_controller(plot_name)
        if not freq_controller:
            freq_controller = self.create_plot_tab(plot_name, f"{channel.upper()}频域信号")
        
        if freq_controller:
            # 清除现有绘图
            freq_controller.view.clear_plot()
            
            freq_controller.plot_frequency_domain(freq_ghz, mag_db, "频率", "幅度", "GHz", "dB")
        else:
            self.errorOccurred.emit(f"{channel}频域绘图控制器未找到")

    def _generate_diff_time_domain_data(self, channel, results, averages, config):
        """生成差分时域数据并绘制"""
        # 差分时域数据 - 同样转换为电压值
        t_full_us = ((np.arange(config.roi_n(100)) * config.ts_eff) * 1e6)
        t_full_diff_us = t_full_us[config.diff_points:]
        adc_max_value = 2**19  # 262144
        y_d_avg_voltage = (averages['y_d_full_avg'] / adc_max_value) * 3.0
        
        # 获取或创建差分时域绘图控制器
        plot_name = f'plot_diff_time_{channel}'
        diff_time_controller = self.get_plot_controller(plot_name)
        if not diff_time_controller:
            diff_time_controller = self.create_plot_tab(plot_name, f"{channel.upper()}差分时域信号")
        
        if diff_time_controller:
            # 清除现有绘图
            diff_time_controller.view.clear_plot()
            
            diff_time_controller.plot_diff_time_domain(t_full_diff_us, y_d_avg_voltage, "时间", "差分电压", "ns", "V")
            # 添加边缘位置标记线到差分时域图
            # 只有在边沿分析成功时才添加标记线
            if results.get('first_rise_pos') is not None:
                self.add_edge_markers(diff_time_controller, results, config, t_full_diff_us, y_d_avg_voltage)

    def _generate_diff_frequency_domain_data(self, channel, results, averages, config):
        """生成差分频域数据并绘制"""
        # 差分频域数据
        maskd = results['freq_d_ref'] <= (config.show_up_to_GHz * 1e9)
        freq_d_ghz = results['freq_d_ref'][maskd] / 1e9
        mag_d_db = averages['mag_d_avg_db'][maskd]
        
        # 获取或创建差分频域绘图控制器
        plot_name = f'plot_diff_freq_{channel}'
        diff_freq_controller = self.get_plot_controller(plot_name)
        if not diff_freq_controller:
            diff_freq_controller = self.create_plot_tab(plot_name, f"{channel.upper()}差分频域信号")
        
        if diff_freq_controller:
            # 清除现有绘图
            diff_freq_controller.view.clear_plot()
            
            diff_freq_controller.plot_diff_frequency_domain(freq_d_ghz, mag_d_db, "频率", "差分幅度", "GHz", "dB")




    def add_edge_markers(self, plot_controller, results, config, t_full_us, y_avg_voltage):
        """添加边缘位置标记线 - 使用交替位置方案避免标签重叠"""
        try:
            # 获取边缘位置信息
            edge_times = self._get_edge_times(results)
            edge_amplitudes = self._get_edge_amplitudes(results)
            edge_ratios = self._get_edge_ratios(results)
            
            # 创建所有标记线
            all_markers = self._create_edge_markers(edge_times, edge_amplitudes, edge_ratios, 
                                                config, t_full_us, y_avg_voltage)
            
            # 添加ROI标记线
            roi_markers = self._create_roi_markers(config, y_avg_voltage)
            all_markers.extend(roi_markers)
            
            # 按时间排序并添加标记线
            self._add_sorted_markers(plot_controller, all_markers, y_avg_voltage)
            
            # 记录边沿分析结果到日志
            self._log_edge_analysis_results(edge_times, edge_amplitudes, edge_ratios, config)
            
            self.log_message("已添加边缘位置标记线", "INFO")
        
        except Exception as e:
            self.errorOccurred.emit(f"添加边缘标记线失败: {str(e)}")
            self.log_message(f"添加边缘标记线失败: {str(e)}", "ERROR")

    def _get_edge_times(self, results):
        """获取边缘时间信息"""
        return {
            'first_rise_time': results.get('first_rise_pos_time'),
            'second_rise_time': results.get('second_rise_pos_time'),
            'fall_time': results.get('fall_pos_time'),
            'rise_midpoint_time': results.get('rise_midpoint_time'),
            'fall_midpoint_time': results.get('fall_midpoint_time'),
            'second_fall_midpoint_time': results.get('second_fall_midpoint_time')
        }
    
    def _get_edge_amplitudes(self, results):
        """获取边缘幅度信息并转换为电压值"""
        adc_max_value = 2**19  # 262144
        return {
            'first_amplitude': (results.get('first_rise_amplitude', 0)/adc_max_value) * 3,
            'second_amplitude': (results.get('second_rise_amplitude', 0)/adc_max_value) * 3,
            'fall_amplitude': (results.get('fall_amplitude', 0)/adc_max_value) * 3
        }
    
    def _get_edge_ratios(self, results):
        """获取边缘比率信息"""
        return {
            'first_rise_ratio': results.get('first_rise_ratio', 0),
            'rise_ratio': results.get('rise_ratio', 0),
            'fall_ratio': results.get('fall_ratio', 0)
        }
    
    def _create_edge_markers(self, edge_times, edge_amplitudes, edge_ratios, config, t_full_us, y_avg_voltage):
        """创建边缘标记线"""
        markers = []
        
        # 边缘标记线
        if edge_times['first_rise_time'] is not None:
            time_idx = np.argmin(np.abs(t_full_us - edge_times['first_rise_time']))
            x_idx = config.n_roi(time_idx)
            y_position = y_avg_voltage[time_idx+15] if time_idx < len(y_avg_voltage) else np.mean(y_avg_voltage)
            markers.append((edge_times['first_rise_time'], y_position, "#D2A5A5", 'dashed', 
                        f'Rise\n({y_position:.3f}V {round(x_idx,2)}%)', 3))
        
        if edge_times['second_rise_time'] is not None:
            time_idx = np.argmin(np.abs(t_full_us - edge_times['second_rise_time']))
            x_idx = config.n_roi(time_idx)
            y_position = y_avg_voltage[time_idx+25] if time_idx < len(y_avg_voltage) else np.mean(y_avg_voltage)
            markers.append((edge_times['second_rise_time'], y_position, "#49A333", 'dashed', 
                        f'2nd Rise\n({y_position:.3f}V,{round(x_idx,2)}%)', 3))
        
        if edge_times['fall_time'] is not None:
            time_idx = np.argmin(np.abs(t_full_us - edge_times['fall_time']))
            x_idx = config.n_roi(time_idx)
            y_position = y_avg_voltage[time_idx+25] if time_idx < len(y_avg_voltage) else np.mean(y_avg_voltage)
            markers.append((edge_times['fall_time'], y_position, '#00AA00', 'dashed', 
                        f'Fall\n({y_position:.3f}V,{round(x_idx,2)}%)', 3))
        
        # 中点标记线
        if edge_times['rise_midpoint_time'] is not None:
            time_idx = np.argmin(np.abs(t_full_us - edge_times['rise_midpoint_time']))
            x_idx = config.n_roi(time_idx)
            y_position = y_avg_voltage[time_idx] if time_idx < len(y_avg_voltage) else np.mean(y_avg_voltage)
            markers.append((edge_times['rise_midpoint_time'], y_position, '#FFA500', 'dashed', 
                        f'Rise-2nd\n({y_position:.3f}V {round(x_idx,2)}%)', 2))
        
        if edge_times['fall_midpoint_time'] is not None:
            time_idx = np.argmin(np.abs(t_full_us - edge_times['fall_midpoint_time']))
            x_idx = config.n_roi(time_idx)
            y_position = y_avg_voltage[time_idx] if time_idx < len(y_avg_voltage) else np.mean(y_avg_voltage)
            markers.append((edge_times['fall_midpoint_time'], y_position, '#800080', 'dashed', 
                        f'Rise-Fall\n({y_position:.3f}V{round(x_idx,2)}%)', 2))
        
        if edge_times['second_fall_midpoint_time'] is not None:
            time_idx = np.argmin(np.abs(t_full_us - edge_times['second_fall_midpoint_time']))
            x_idx = config.n_roi(time_idx)
            y_position = y_avg_voltage[time_idx] if time_idx < len(y_avg_voltage) else np.mean(y_avg_voltage)
            markers.append((edge_times['second_fall_midpoint_time'], y_position, '#00FFFF', 'dashed', 
                        f'2ndRise\n({y_position:.3f}V {round(x_idx,2)}%)', 2))
        
        return markers
    
    def _create_roi_markers(self, config, y_avg_voltage):
        """创建ROI标记线"""
        markers = []
        
        # ROI标记线
        roi_start_time = config.roi_start * config.ts_eff * 1e6
        roi_mid_time = config.roi_mid * config.ts_eff * 1e6
        roi_end_time = config.roi_end * config.ts_eff * 1e6
        
        # 添加ROI标记线，使用平均Y值作为位置
        avg_y = np.mean(y_avg_voltage)
        markers.append((roi_start_time, avg_y, '#FF00FF', 'dashdot', f'ROI Start\n({config.roi_start_tenths}%)', 2))
        markers.append((roi_mid_time, avg_y, "#94B814", 'dashdot', f'ROI Mid\n({config.roi_mid_tenths}%)', 2))
        markers.append((roi_end_time, avg_y, '#00FFFF', 'dashdot', f'ROI End\n({config.roi_end_tenths}%)', 2))
        
        return markers
    
    def _add_sorted_markers(self, plot_controller, all_markers, y_avg_voltage):
        """按时间排序并添加标记线"""
        # 按时间排序标记线
        all_markers.sort(key=lambda x: x[0])
        
        # 使用交替位置方案添加标记线
        for i, (x_position, y_position, color, style, label, width) in enumerate(all_markers):
            # 在Y坐标基础上添加小偏移以避免标签重叠
            y_offset = 0.1 * (i % 3 - 1) * (np.max(y_avg_voltage) - np.min(y_avg_voltage))
            final_y_position = y_position + y_offset
            
            plot_controller.add_marker_line(x_position, final_y_position, color, style, label, width)

    def _log_edge_analysis_results(self, edge_times, edge_amplitudes, edge_ratios, config):
        """记录边沿分析结果到日志"""
        edge_info = []
        
        if edge_times['first_rise_time'] is not None:
            edge_info.append(f"First Rise: {edge_times['first_rise_time']:.3f}ns, Amp: {edge_amplitudes['first_amplitude']:.3f}V")
        
        if edge_times['second_rise_time'] is not None:
            edge_info.append(f"Second Rise: {edge_times['second_rise_time']:.3f}ns, Amp: {edge_amplitudes['second_amplitude']:.3f}V, Ratio: {edge_ratios['rise_ratio']:.4%}")
        
        if edge_times['fall_time'] is not None:
            edge_info.append(f"Fall: {edge_times['fall_time']:.3f}ns, Amp: {edge_amplitudes['fall_amplitude']:.3f}V, Ratio: {edge_ratios['fall_ratio']:.4%}")
        
        # 添加ROI信息到日志
        edge_info.append(f"ROI Range: {config.roi_start_tenths}%-{config.roi_end_tenths}%")
        edge_info.append(f"ROI Mid: {config.roi_mid_tenths}%")
        
        if edge_info:
            self.log_message("边沿分析结果:", "INFO")
            for info in edge_info:
                self.log_message(info, "INFO")

    def clear_all_markers(self):
        """清除所有绘图标记"""
        try:
            # 清除所有绘图控制器的标记
            for channel in ['adc1', 'adc2']:
                for plot_type in ['plot_time', 'plot_freq', 'plot_diff_time', 'plot_diff_freq']:
                    plot_name = f"{plot_type}_{channel}"
                    controller = self.get_plot_controller(plot_name)
                    if controller and hasattr(controller, 'clear_markers'):
                        controller.clear_markers()
                    
        except Exception as e:
            self.errorOccurred.emit(f"清除标记失败: {str(e)}")
            self.log_message(f"清除标记失败: {str(e)}", "ERROR")


    def export_plots(self, base_path):
        """导出所有绘图到以base_path为基础的文件名 - 支持ADC1和ADC2双通道"""
        # 定义绘图类型和对应的后缀
        plot_types = ['plot_time', 'plot_freq', 'plot_diff_time', 'plot_diff_freq']
        suffixes = {
            'plot_time': '_time_domain',
            'plot_freq': '_frequency_domain', 
            'plot_diff_time': '_diff_time_domain',
            'plot_diff_freq': '_diff_frequency_domain'
        }
        
        # 定义通道映射
        channels = ['adc1', 'adc2']
        channel_names = {
            'adc1': 'ADC1',
            'adc2': 'ADC2'
        }
    
        # 确保目录存在
        output_dir = os.path.dirname(base_path)
        if output_dir and not os.path.exists(output_dir):
            os.makedirs(output_dir)
        
        exported_count = 0
        
        # 遍历所有通道和绘图类型
        for channel in channels:
            for plot_type in plot_types:
                plot_name = f'{plot_type}_{channel}'
                controller = self.get_plot_controller(plot_name)
                
                if controller and hasattr(controller.view, 'plot_widget'):
                    # 构建文件路径：基础路径_通道名_绘图类型.png
                    channel_suffix = channel_names[channel].lower()
                    file_path = f"{base_path}_{channel_suffix}{suffixes[plot_type]}.png"
                    
                    success = self.export_single_plot(controller, file_path)
                    if success:
                        self.log_message(f"导出{channel_names[channel]}{plot_type}图片成功: {file_path}", "INFO")
                        exported_count += 1
                    else:
                        self.log_message(f"导出{channel_names[channel]}{plot_type}图片失败", "WARNING")
        
        # 如果没有找到任何绘图控制器，尝试导出基本的绘图类型（向后兼容）
        if exported_count == 0:
            self.log_message("未找到通道特定的绘图，尝试导出基本绘图类型", "WARNING")
            for plot_type in plot_types:
                controller = self.get_plot_controller(plot_type)
                if controller:
                    file_path = f"{base_path}{suffixes[plot_type]}.png"
                    success = self.export_single_plot(controller, file_path)
                    if success:
                        self.log_message(f"导出{plot_type}图片成功: {file_path}", "INFO")
                    else:
                        self.log_message(f"导出{plot_type}图片失败", "WARNING")
        
        self.log_message(f"共导出 {exported_count} 个绘图文件", "INFO")


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

# 在 DataAnalysisController 类中添加以下方法

    def on_export(self):
        """导出分析结果 - 使用工作线程避免界面卡顿"""
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
                # 准备导出配置
                export_config = self.prepare_export_config(file_path)
                
                # 禁用导出按钮，避免重复点击
                self.view.export_button.setEnabled(False)
                self.view.export_button.setText("导出中...")
                
                # 创建工作线程
                self.export_thread = QThread()
                self.export_worker = DataExportWorker(export_config)
                self.export_worker.moveToThread(self.export_thread)

                # 连接信号
                self.export_thread.started.connect(self.export_worker.run)
                self.export_worker.progress.connect(self.on_export_progress)
                self.export_worker.finished.connect(self.on_export_finished)
                self.export_worker.finished.connect(self.export_thread.quit)
                self.export_worker.finished.connect(self.export_worker.deleteLater)
                self.export_thread.finished.connect(self.export_thread.deleteLater)
                self.export_worker.error.connect(self.on_export_error)
                self.export_worker.log_message.connect(self.log_message)

                # 启动线程
                self.export_thread.start()
                
        except Exception as e:
            self.errorOccurred.emit(f"导出失败: {str(e)}")
            self.log_message(f"导出失败: {str(e)}", "ERROR")

    def prepare_export_config(self, file_path):
        """准备导出配置"""
        # 获取文件扩展名和基础路径
        file_ext = os.path.splitext(file_path)[1].lower()
        base_path = os.path.splitext(file_path)[0]
        
        # 准备导出数据
        export_data_dict = {
            "analysis_results": self.model.results,
            "config": self.model.get_adc_config_dict(),
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        }
        
        # 如果有分析数据，添加更多详细信息
        if hasattr(self, 'last_analysis_results') and hasattr(self, 'last_averages'):
            export_data_dict.update({
                "successful_files": self.last_analysis_results.get('success_count', 0),
                "total_files": self.last_analysis_results.get('total_files', 0)
            })
        
        # 准备图片数据
        plot_images = self.prepare_plot_images(base_path)
        
        return {
            'file_path': file_path,
            'base_path': base_path,
            'file_ext': file_ext,
            'export_data': True,
            'export_images': True,
            'export_additional_data': True,
            'export_data_dict': export_data_dict,
            'results': getattr(self, 'last_analysis_results', None),
            'averages': getattr(self, 'last_averages', None),
            'config': self.model.adc_config,
            'channels': ['adc1', 'adc2'],
            'plot_types': ['plot_time', 'plot_freq', 'plot_diff_time', 'plot_diff_freq'],
            'plot_images': plot_images,
            'roi_params': {
                'start': self.view.adc_roi_start.value(),
                'end': self.view.adc_roi_end.value()
            }
        }

    def prepare_plot_images(self, base_path):
        """准备绘图图片数据"""
        plot_images = {}
        
        # 定义绘图类型和对应的后缀
        plot_types = ['plot_time', 'plot_freq', 'plot_diff_time', 'plot_diff_freq']
        suffixes = {
            'plot_time': '_time_domain',
            'plot_freq': '_frequency_domain', 
            'plot_diff_time': '_diff_time_domain',
            'plot_diff_freq': '_diff_frequency_domain'
        }
        
        # 定义通道映射
        channels = ['adc1', 'adc2']
        channel_names = {'adc1': 'ADC1', 'adc2': 'ADC2'}
        
        # 捕获所有绘图图片
        for channel in channels:
            for plot_type in plot_types:
                plot_name = f'{plot_type}_{channel}'
                controller = self.get_plot_controller(plot_name)
                
                if controller and hasattr(controller.view, 'plot_widget'):
                    # 构建文件路径
                    channel_suffix = channel_names[channel].lower()
                    file_path = f"{base_path}_{channel_suffix}{suffixes[plot_type]}.png"
                    
                    # 捕获图片
                    plot_widget = controller.view.plot_widget
                    pixmap = plot_widget.grab()
                    image = pixmap.toImage()
                    
                    plot_images[plot_name] = {
                        'file_path': file_path,
                        'image': image
                    }
        
        return plot_images

    def on_export_progress(self, current, total, message):
        """导出进度更新"""
        # 通过信号传递给主窗口的进度面板
        if hasattr(self, 'main_window_controller') and self.main_window_controller:
            self.main_window_controller.update_progress(current, total, message)
        
        # 记录日志
        self.log_message(f"导出进度: {current}/{total} - {message}", "INFO")

    def on_export_finished(self, success, message):
        """导出完成"""
        # 恢复按钮状态
        self.view.export_button.setEnabled(True)
        self.view.export_button.setText("导出结果")
        
        if success:
            self.dataLoaded.emit(message)
            self.log_message(message, "INFO")
        else:
            self.errorOccurred.emit(message)
            self.log_message(message, "ERROR")
        
        # 清除进度显示
        if hasattr(self, 'main_window_controller') and self.main_window_controller:
            self.main_window_controller.clear_progress()

    def on_export_error(self, error_message):
        """导出错误"""
        # 恢复按钮状态
        self.view.export_button.setEnabled(True)
        self.view.export_button.setText("导出结果")
        
        self.errorOccurred.emit(error_message)
        self.log_message(error_message, "ERROR")
        
        # 清除进度显示
        if hasattr(self, 'main_window_controller') and self.main_window_controller:
            self.main_window_controller.clear_progress()


    def export_edge_analysis_results(self, results, file_path, channel_name):
        """导出边沿分析结果"""
        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(f"{channel_name}边沿分析结果\n")
                f.write("=" * 50 + "\n")
                
                # 边沿时间信息
                edge_times = self._get_edge_times(results)
                for key, value in edge_times.items():
                    if value is not None:
                        f.write(f"{key}: {value:.3f} ns\n")
                
                # 边沿幅度信息
                edge_amplitudes = self._get_edge_amplitudes(results)
                for key, value in edge_amplitudes.items():
                    f.write(f"{key}: {value:.3f} V\n")
                
                # 边沿比率信息
                edge_ratios = self._get_edge_ratios(results)
                for key, value in edge_ratios.items():
                    f.write(f"{key}: {value:.4%}\n")
            
            self.log_message(f"{channel_name}边沿分析结果已保存到: {os.path.basename(file_path)}", "INFO")
            
        except Exception as e:
            self.log_message(f"导出{channel_name}边沿分析结果失败: {str(e)}", "WARNING")

    def export_channel_difference_data(self, results, averages, file_path):
        """导出ADC1和ADC2的差异数据"""
        try:
            if 'adc1' in results and 'adc2' in results:
                # 计算时域差异
                if 'y_full_avg' in averages['adc1'] and 'y_full_avg' in averages['adc2']:
                    min_len = min(len(averages['adc1']['y_full_avg']), len(averages['adc2']['y_full_avg']))
                    diff_data = averages['adc1']['y_full_avg'][:min_len] - averages['adc2']['y_full_avg'][:min_len]
                    t_full_us = (np.arange(min_len)) * self.model.adc_config.ts_eff * 1e6
                    
                    diff_data_combined = np.column_stack((t_full_us, diff_data))
                    np.savetxt(file_path, diff_data_combined, delimiter=',', 
                            header='Time(us),ADC1-ADC2_Difference', comments='')
                    
                    self.log_message(f"ADC1-ADC2差异数据已保存到: {os.path.basename(file_path)}", "INFO")
                    
        except Exception as e:
            self.log_message(f"导出ADC1-ADC2差异数据失败: {str(e)}", "WARNING")


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
