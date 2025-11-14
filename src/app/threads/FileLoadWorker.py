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
            
            for i, file_path in enumerate(self.file_paths):
                if self.is_cancelled:
                    self.log_message.emit("文件加载已取消", "INFO")
                    return
                
                filename = os.path.basename(file_path).lower()
                self.progress.emit(i + 1, len(self.file_paths), f"正在检测: {filename}")
                
                # 获取文件大小
                file_size = os.path.getsize(file_path)
                
                # 检测文件中的段数和详细信息
                if i == 0:  # 第一个文件，进行详细检测
                    segments, segment_info = self.extract_adc_data_from_binary(file_path)
                    first_file_segments = segments
                    first_file_size = file_size
                    first_file_segment_info = segment_info
                    
                    self.log_message.emit(f"第一个文件详细检测: {filename}", "DEBUG")
                    self.log_message.emit(f"  文件大小: {file_size/1024/1024:.2f}MB", "DEBUG")
                    self.log_message.emit(f"  段数: {segments}", "DEBUG")
                else:  # 后续文件，只比较文件大小
                    if file_size == first_file_size:
                        segments = first_file_segments
                        segment_info = first_file_segment_info
                        self.log_message.emit(f"文件 {filename}: 大小匹配，沿用第一文件段数 {segments}", "DEBUG")
                    else:
                        self.log_message.emit(f"警告: 文件 {filename} 大小与第一文件不匹配，跳过该文件", "WARNING")
                        continue
                
                total_segments += segments
                file_segments[filename] = segments
                
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
                if 'adc1' in filename or 'ch1' in filename or 'channel1' in filename:
                    data_files['adc1'].append(file_info)
                elif 'adc2' in filename or 'ch2' in filename or 'channel2' in filename:
                    data_files['adc2'].append(file_info)
                else:
                    data_files['adc1'].append(file_info)
                    self.log_message.emit(f"警告: 无法确定文件 {filename} 属于哪个ADC，已默认添加到ADC1", "WARNING")
            
            # 发送完成信号
            self.finished.emit(data_files, file_segments)
            self.log_message.emit(f"文件加载完成，共处理 {len(self.file_paths)} 个文件", "INFO")
            
        except Exception as e:
            self.error.emit(f"文件加载失败: {str(e)}")
