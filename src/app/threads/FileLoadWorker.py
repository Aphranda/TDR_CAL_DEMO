# src/app/threads/FileLoadWorker.py
import os
import numpy as np
from PyQt5.QtCore import QObject, pyqtSignal, QThread

class FileLoadWorker(QObject):
    """文件加载工作线程"""
    progress = pyqtSignal(int, int, str)  # 当前进度，总文件数，当前文件名
    finished = pyqtSignal(dict, dict)  # 文件信息，段数信息
    error = pyqtSignal(str)
    log_message = pyqtSignal(str, str)  # 消息，级别

    def __init__(self, file_paths, max_read_size_bytes, extract_data_func):
        super().__init__()
        self.file_paths = file_paths
        self.max_read_size_bytes = max_read_size_bytes
        self.extract_adc_data_from_binary = extract_data_func
        self.is_cancelled = False

    def cancel(self):
        """取消加载"""
        self.is_cancelled = True

    def run(self):
        """执行文件加载"""
        try:
            data_files = {'adc1': [], 'adc2': []}
            file_segments = {}
            total_segments = 0
            
            # 存储第一个文件的详细信息
            first_file_segments = None
            first_file_size = None
            first_file_segment_info = None
            
            # 发送开始加载消息
            self.log_message.emit(f"开始加载 {len(self.file_paths)} 个文件", "INFO")
            
            for i, file_path in enumerate(self.file_paths):
                if self.is_cancelled:
                    self.log_message.emit("文件加载已取消", "INFO")
                    return
                
                filename = os.path.basename(file_path)
                filename_lower = filename.lower()
                
                # 发送当前文件处理开始消息
                self.log_message.emit(f"正在处理文件 {i+1}/{len(self.file_paths)}: {filename}", "INFO")
                self.progress.emit(i + 1, len(self.file_paths), f"正在检测: {filename}")
                
                # 获取文件大小
                file_size = os.path.getsize(file_path)
                file_size_mb = file_size / 1024 / 1024
                
                # 发送文件大小信息
                self.log_message.emit(f"文件大小: {file_size_mb:.2f} MB", "DEBUG")
                
                # 检测文件中的段数和详细信息
                if i == 0:  # 第一个文件，进行详细检测
                    self.log_message.emit("正在检测文件段结构...", "DEBUG")
                    segments, segment_info = self.extract_adc_data_from_binary(file_path)
                    first_file_segments = segments
                    first_file_size = file_size
                    first_file_segment_info = segment_info
                    
                    # 发送第一个文件的详细检测结果
                    self.log_message.emit(f"详细检测完成: 检测到 {segments} 个数据段", "INFO")
                    
                    # 发送段详细信息
                    if 'segment_details' in segment_info:
                        seg_details = segment_info['segment_details']
                        if seg_details:
                            self.log_message.emit(f"段长度统计:", "DEBUG")
                            lengths = [seg['length'] for seg in seg_details]
                            self.log_message.emit(f"  最小: {min(lengths)}, 最大: {max(lengths)}, 平均: {np.mean(lengths):.1f}", "DEBUG")
                            
                else:  # 后续文件，只比较文件大小
                    if file_size == first_file_size:
                        segments = first_file_segments
                        segment_info = first_file_segment_info
                        self.log_message.emit(f"文件大小匹配，沿用第一文件段数: {segments}", "DEBUG")
                    else:
                        warning_msg = f"文件大小不匹配，跳过该文件 (期望: {first_file_size}, 实际: {file_size})"
                        self.log_message.emit(warning_msg, "WARNING")
                        continue
                
                total_segments += segments
                file_segments[filename] = segments
                
                # 发送段数信息
                self.log_message.emit(f"当前文件段数: {segments}", "INFO")
                
                # 为每个段创建索引列表
                segment_indices = list(range(segments))
                
                # 创建文件信息字典
                file_info = {
                    'path': file_path, 
                    'segments': segments,
                    'segment_indices': segment_indices,
                    'segment_info': segment_info
                }
                
                # 根据文件名分类到ADC1或ADC2
                channel = None
                if 'adc1' in filename_lower or 'ch1' in filename_lower or 'channel1' in filename_lower:
                    channel = 'ADC1'
                    data_files['adc1'].append(file_info)
                elif 'adc2' in filename_lower or 'ch2' in filename_lower or 'channel2' in filename_lower:
                    channel = 'ADC2'
                    data_files['adc2'].append(file_info)
                else:
                    channel = 'ADC1 (默认)'
                    data_files['adc1'].append(file_info)
                    self.log_message.emit(f"无法确定文件通道，已默认添加到ADC1", "WARNING")
                
                # 发送文件分类信息
                self.log_message.emit(f"文件分类: {channel}", "INFO")
                self.log_message.emit(f"文件 {filename} 处理完成", "INFO")
                
                # 添加分隔线，使日志更清晰
                if i < len(self.file_paths) - 1:
                    self.log_message.emit("-" * 50, "DEBUG")
            
            # 发送加载完成总结信息
            self.log_message.emit("=" * 60, "INFO")
            self.log_message.emit("文件加载完成总结:", "INFO")
            self.log_message.emit(f"成功加载文件数: {len(self.file_paths)}", "INFO")
            self.log_message.emit(f"ADC1 文件数: {len(data_files['adc1'])}", "INFO")
            self.log_message.emit(f"ADC2 文件数: {len(data_files['adc2'])}", "INFO")
            self.log_message.emit(f"总数据段数: {total_segments}", "INFO")
            
            # 检查文件匹配情况
            if len(data_files['adc1']) != len(data_files['adc2']):
                self.log_message.emit(f"警告: ADC1和ADC2的文件数量不匹配 (ADC1: {len(data_files['adc1'])}, ADC2: {len(data_files['adc2'])})", "WARNING")
            
            self.log_message.emit("=" * 60, "INFO")
            
            # 发送完成信号
            self.finished.emit(data_files, file_segments)
            
        except Exception as e:
            error_msg = f"文件加载失败: {str(e)}"
            self.log_message.emit(error_msg, "ERROR")
            self.error.emit(error_msg)

    