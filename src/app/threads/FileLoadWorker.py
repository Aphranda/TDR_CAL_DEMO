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

    def _classify_files(self):
        """分类文件到ADC1和ADC2"""
        adc1_files = []
        adc2_files = []
        
        for file_path in self.file_paths:
            filename = os.path.basename(file_path).lower()
            if 'adc1' in filename or 'ch1' in filename or 'channel1' in filename:
                adc1_files.append(file_path)
            elif 'adc2' in filename or 'ch2' in filename or 'channel2' in filename:
                adc2_files.append(file_path)
            else:
                # 默认分配到ADC1并记录警告
                adc1_files.append(file_path)
                self.log_message.emit(f"无法确定文件通道，已默认添加到ADC1: {filename}", "WARNING")
        
        return adc1_files, adc2_files

    def _detect_analysis_mode(self, adc1_files, adc2_files):
        """检测分析模式"""
        has_adc1 = len(adc1_files) > 0
        has_adc2 = len(adc2_files) > 0
        
        if has_adc1 and has_adc2:
            return "simultaneous"  # 同时分析
        elif has_adc1:
            return "adc1_only"     # 仅ADC1分析
        elif has_adc2:
            return "adc2_only"     # 仅ADC2分析
        else:
            return "unknown"       # 未知模式

    def _get_file_size_mb(self, file_path):
        """获取文件大小(MB)"""
        file_size = os.path.getsize(file_path)
        return file_size / 1024 / 1024

    def _perform_detailed_detection(self, file_path, file_index, total_files):
        """执行详细文件检测"""
        filename = os.path.basename(file_path)
        self.log_message.emit(f"正在详细检测文件 {file_index+1}/{total_files}: {filename}", "INFO")
        
        file_size_mb = self._get_file_size_mb(file_path)
        self.log_message.emit(f"文件大小: {file_size_mb:.2f} MB", "DEBUG")
        
        self.log_message.emit("正在检测文件段结构...", "DEBUG")
        segments, segment_info = self.extract_adc_data_from_binary(file_path)
        
        self.log_message.emit(f"详细检测完成: 检测到 {segments} 个数据段", "INFO")
        
        # 发送段详细信息
        if 'segment_details' in segment_info and segment_info['segment_details']:
            seg_details = segment_info['segment_details']
            lengths = [seg['length'] for seg in seg_details]
            self.log_message.emit(f"段长度统计 - 最小: {min(lengths)}, 最大: {max(lengths)}, 平均: {np.mean(lengths):.1f}", "DEBUG")
        
        return segments, segment_info

    def _perform_quick_detection(self, file_path, file_index, total_files, reference_size, reference_segments, reference_info):
        """执行快速文件检测（基于文件大小比较）"""
        filename = os.path.basename(file_path)
        self.log_message.emit(f"正在快速检测文件 {file_index+1}/{total_files}: {filename}", "INFO")
        
        file_size = os.path.getsize(file_path)
        file_size_mb = file_size / 1024 / 1024
        self.log_message.emit(f"文件大小: {file_size_mb:.2f} MB", "DEBUG")
        
        if file_size == reference_size:
            segments = reference_segments
            segment_info = reference_info
            self.log_message.emit(f"文件大小匹配，沿用参考文件段数: {segments}", "DEBUG")
        else:
            warning_msg = f"文件大小不匹配，跳过该文件 (期望: {reference_size}, 实际: {file_size})"
            self.log_message.emit(warning_msg, "WARNING")
            return None, None
        
        return segments, segment_info

    def run(self):
        """执行文件加载"""
        try:
            data_files = {'adc1': [], 'adc2': []}
            file_segments = {}
            total_segments = 0
            
            # 发送开始加载消息
            self.log_message.emit(f"开始加载 {len(self.file_paths)} 个文件", "INFO")
            
            # 分类文件并检测分析模式
            adc1_files, adc2_files = self._classify_files()
            analysis_mode = self._detect_analysis_mode(adc1_files, adc2_files)
            
            self.log_message.emit(f"检测到分析模式: {analysis_mode}", "INFO")
            self.log_message.emit(f"ADC1 文件数: {len(adc1_files)}, ADC2 文件数: {len(adc2_files)}", "INFO")
            
            # 存储参考文件信息
            reference_info = {
                'adc1': {'size': None, 'segments': None, 'info': None},
                'adc2': {'size': None, 'segments': None, 'info': None}
            }
            
            # 处理所有文件
            all_files = []
            file_channels = {}
            
            # 构建统一文件列表和通道映射
            for file_path in adc1_files:
                all_files.append(file_path)
                file_channels[file_path] = 'adc1'
            for file_path in adc2_files:
                all_files.append(file_path)
                file_channels[file_path] = 'adc2'
            
            for i, file_path in enumerate(all_files):
                if self.is_cancelled:
                    self.log_message.emit("文件加载已取消", "INFO")
                    return
                
                filename = os.path.basename(file_path)
                channel = file_channels[file_path]
                
                # 发送进度信号
                self.progress.emit(i + 1, len(all_files), f"正在检测: {filename}")
                
                # 根据分析模式决定检测策略
                if analysis_mode == "simultaneous":
                    # 同时分析模式：所有文件都需要详细检测
                    segments, segment_info = self._perform_detailed_detection(file_path, i, len(all_files))
                    
                    # 如果是该通道的第一个文件，保存为参考
                    if reference_info[channel]['size'] is None:
                        reference_info[channel]['size'] = os.path.getsize(file_path)
                        reference_info[channel]['segments'] = segments
                        reference_info[channel]['info'] = segment_info
                        
                else:
                    # 独立分析模式：只对第一个文件详细检测，后续文件快速检测
                    if reference_info[channel]['size'] is None:
                        # 第一个文件，详细检测
                        segments, segment_info = self._perform_detailed_detection(file_path, i, len(all_files))
                        reference_info[channel]['size'] = os.path.getsize(file_path)
                        reference_info[channel]['segments'] = segments
                        reference_info[channel]['info'] = segment_info
                    else:
                        # 后续文件，快速检测
                        segments, segment_info = self._perform_quick_detection(
                            file_path, i, len(all_files),
                            reference_info[channel]['size'],
                            reference_info[channel]['segments'],
                            reference_info[channel]['info']
                        )
                        if segments is None:  # 文件大小不匹配，跳过
                            continue
                
                # 更新统计信息
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
                
                # 添加到对应的数据文件列表
                data_files[channel].append(file_info)
                
                # 发送文件分类信息
                self.log_message.emit(f"文件分类: {channel.upper()}", "INFO")
                self.log_message.emit(f"文件 {filename} 处理完成", "INFO")
                
                # 添加分隔线，使日志更清晰
                if i < len(all_files) - 1:
                    self.log_message.emit("-" * 50, "DEBUG")
            
            # 发送加载完成总结信息
            self.log_message.emit("=" * 60, "INFO")
            self.log_message.emit("文件加载完成总结:", "INFO")
            self.log_message.emit(f"成功加载文件数: {len(all_files)}", "INFO")
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
