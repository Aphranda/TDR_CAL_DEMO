# src/app/core/DataCacheManager.py

import os
import gc
import numpy as np
from typing import Dict, Optional, List, Tuple
from PyQt5.QtCore import QObject, pyqtSignal, QTimer

from app.core.PerformanceMonitor import timeit, performance_monitor
from app.core.FileManager import FileManager


class DataCacheManager(QObject):
    """数据缓存管理器 - 支持分批加载和内存管理"""
    
    # 信号定义
    batch_loaded = pyqtSignal(int, int, str)  # 当前批次, 总批次, 状态信息
    file_processed = pyqtSignal(str, bool)    # 文件路径, 是否成功
    all_files_loaded = pyqtSignal(dict)       # 所有文件加载完成
    memory_status = pyqtSignal(int, int)      # 当前内存使用, 峰值内存使用
    
    def __init__(self, batch_size: int = 10):
        super().__init__()
        self.batch_size = batch_size
        
        # 缓存管理
        self._file_cache: Dict[str, np.ndarray] = {}  # 文件路径 -> 数据数组
        self._segment_cache: Dict[str, List[np.ndarray]] = {}  # 文件路径 -> 段数据列表
        self._current_batch: List[Dict] = []  # 当前批次文件
        
        # 文件处理状态
        self._pending_files: List[Dict] = []  # 待处理文件
        self._processed_files: Dict[str, Dict] = {}  # 已处理文件
        
        # 内存监控
        self._peak_memory = 0
        self._file_manager = FileManager()
        
        # 设置内存监控定时器
        self._memory_timer = QTimer()
        self._memory_timer.timeout.connect(self._update_memory_status)
        self._memory_timer.start(1000)  # 每秒更新一次内存状态

    def set_batch_size(self, batch_size: int):
        """设置批次大小"""
        self.batch_size = batch_size

    @timeit
    def load_files_in_batches(self, file_dict: Dict[str, List[Dict]]) -> Dict[str, Dict]:
        """分批加载文件数据"""
        try:
            self._log_start_message(file_dict)
            
            # 清空现有缓存
            self.clear_cache()
            
            # 收集所有需要加载的文件
            all_files = self._collect_all_files(file_dict)
            self._pending_files = all_files
            
            # 分批加载文件
            return self._process_file_batches(file_dict)
            
        except Exception as e:
            error_msg = f"分批加载文件失败: {str(e)}"
            self.batch_loaded.emit(0, 0, f"错误: {error_msg}")
            raise

    def _collect_all_files(self, file_dict: Dict[str, List[Dict]]) -> List[Dict]:
        """收集所有需要加载的文件信息"""
        all_files = []
        for channel in ['adc1', 'adc2']:
            for file_info in file_dict.get(channel, []):
                file_path = file_info['path']
                if file_path not in [f['path'] for f in all_files]:
                    all_files.append({
                        'path': file_path,
                        'segments': file_info.get('segments', 1),
                        'segment_info': file_info.get('segment_info', {}),
                        'channel': channel,
                        'original_info': file_info  # 保存原始信息
                    })
        return all_files

    def _process_file_batches(self, file_dict: Dict) -> Dict[str, Dict]:
        """处理文件批次"""
        total_batches = (len(self._pending_files) + self.batch_size - 1) // self.batch_size
        
        segmented_result = {'adc1': [], 'adc2': []}
        
        for batch_idx in range(total_batches):
            if self._should_stop_loading:
                break
                
            # 获取当前批次文件
            start_idx = batch_idx * self.batch_size
            end_idx = min(start_idx + self.batch_size, len(self._pending_files))
            current_batch_files = self._pending_files[start_idx:end_idx]
            
            self._log_batch_start(batch_idx + 1, total_batches, current_batch_files)
            
            # 加载当前批次
            batch_result = self._load_and_process_batch(current_batch_files, file_dict)
            
            # 更新结果
            self._update_segmented_result(segmented_result, batch_result)
            
            # 清理当前批次内存
            self._cleanup_current_batch(current_batch_files)
            
            self._log_batch_complete(batch_idx + 1, total_batches)
        
        self.all_files_loaded.emit(segmented_result)
        return segmented_result

    def _load_and_process_batch(self, batch_files: List[Dict], file_dict: Dict) -> Dict[str, List[Dict]]:
        """加载并处理单个批次"""
        batch_result = {'adc1': [], 'adc2': []}
        
        for file_info in batch_files:
            try:
                # 加载文件数据
                file_data = self._load_single_file(file_info['path'])
                if file_data is None:
                    self.file_processed.emit(file_info['path'], False)
                    continue
                
                # 预分割段数据
                segments = self._pre_segment_single_file(file_info, file_data)
                
                # 构建结果
                segmented_file_info = file_info['original_info'].copy()
                segmented_file_info['pre_segmented_data'] = segments
                
                batch_result[file_info['channel']].append(segmented_file_info)
                
                self.file_processed.emit(file_info['path'], True)
                
            except Exception as e:
                self._log_file_error(file_info['path'], e)
                self.file_processed.emit(file_info['path'], False)
                continue
                
        return batch_result

    @timeit
    def _load_single_file(self, file_path: str) -> Optional[np.ndarray]:
        """加载单个文件数据"""
        try:
            # 检测文件格式
            file_format = 'binary'  # 根据实际情况调整
            
            if file_format == 'binary':
                data = self._file_manager.load_binary_data(file_path, data_type='uint32')
                return data.astype(np.uint32)
            else:
                return self._file_manager.load_u32_text_first_col(
                    file_path, skip_first=False
                )
                
        except Exception as e:
            self._log_file_error(file_path, e)
            return None

    @timeit
    def _pre_segment_single_file(self, file_info: Dict, full_data: np.ndarray) -> List[np.ndarray]:
        """预分割单个文件的所有段"""
        file_path = file_info['path']
        segments = file_info.get('segments', 1)
        segment_info = file_info.get('segment_info', {})
        
        segmented_data = []
        
        for segment_idx in range(segments):
            segment_data = self._extract_segment_data(
                file_path, segment_idx, segments, segment_info, full_data
            )
            if segment_data is not None:
                segmented_data.append(segment_data)
        
        return segmented_data

    def _extract_segment_data(self, file_path: str, segment_idx: int, segments: int, 
                            segment_info: Dict, full_data: np.ndarray) -> Optional[np.ndarray]:
        """提取特定段的数据"""
        try:
            rise_edge_positions = segment_info.get('rise_edge_positions', [])
            segment_details = segment_info.get('segment_details', [])
            
            if rise_edge_positions and segment_details:
                if segment_idx < len(segment_details):
                    seg_detail = segment_details[segment_idx]
                    start_idx = seg_detail['start_position']
                    end_idx = seg_detail['end_position']
                else:
                    start_idx = rise_edge_positions[segment_idx] if segment_idx < len(rise_edge_positions) else 0
                    end_idx = start_idx + 81920 + 100
            else:
                segment_length = 81920 + 100
                start_idx = segment_idx * segment_length
                end_idx = start_idx + segment_length
            
            # 确保不超出数组边界
            if end_idx > len(full_data):
                end_idx = len(full_data)
            if start_idx >= end_idx:
                return None
                
            segment_data = full_data[start_idx:end_idx]
            
            # 检查数据长度
            if len(segment_data) < 81920:
                print(f"警告: {os.path.basename(file_path)} 段 {segment_idx} 数据长度不足")
                
            return segment_data
            
        except Exception as e:
            print(f"提取段数据失败 {file_path} 段 {segment_idx}: {str(e)}")
            return None

    def _update_segmented_result(self, segmented_result: Dict, batch_result: Dict):
        """更新分段结果"""
        for channel in ['adc1', 'adc2']:
            segmented_result[channel].extend(batch_result[channel])

    def _cleanup_current_batch(self, batch_files: List[Dict]):
        """清理当前批次的内存"""
        for file_info in batch_files:
            file_path = file_info['path']
            
            # 从文件缓存中移除
            if file_path in self._file_cache:
                del self._file_cache[file_path]
            
            # 从段缓存中移除
            if file_path in self._segment_cache:
                del self._segment_cache[file_path]
        
        # 强制垃圾回收
        gc.collect()
        
        # 更新内存状态
        self._update_memory_status()

    def _update_memory_status(self):
        """更新内存状态"""
        try:
            import psutil
            process = psutil.Process()
            memory_info = process.memory_info()
            current_memory = memory_info.rss // (1024 * 1024)  # MB
            
            if current_memory > self._peak_memory:
                self._peak_memory = current_memory
                
            self.memory_status.emit(current_memory, self._peak_memory)
            
        except ImportError:
            # 如果没有psutil，跳过内存监控
            pass

    def get_segment_data(self, file_path: str, segment_idx: int) -> Optional[np.ndarray]:
        """从缓存获取段数据 - 如果不在缓存中则动态加载"""
        # 检查是否在段缓存中
        if file_path in self._segment_cache:
            segments = self._segment_cache[file_path]
            if segment_idx < len(segments):
                return segments[segment_idx]
        
        # 如果不在缓存中，尝试动态加载
        try:
            # 查找文件信息
            file_info = None
            for pending_file in self._pending_files:
                if pending_file['path'] == file_path:
                    file_info = pending_file
                    break
            
            if file_info is None:
                return None
            
            # 动态加载文件
            file_data = self._load_single_file(file_path)
            if file_data is None:
                return None
            
            # 提取段数据
            segment_data = self._extract_segment_data(
                file_path, segment_idx, 
                file_info.get('segments', 1),
                file_info.get('segment_info', {}),
                file_data
            )
            
            return segment_data
            
        except Exception as e:
            print(f"动态加载段数据失败 {file_path} 段 {segment_idx}: {str(e)}")
            return None

    def clear_cache(self):
        """清空所有缓存"""
        self._file_cache.clear()
        self._segment_cache.clear()
        self._current_batch.clear()
        self._pending_files.clear()
        self._processed_files.clear()
        gc.collect()

    def _log_start_message(self, file_dict: Dict):
        """记录开始消息"""
        adc1_count = len(file_dict.get('adc1', []))
        adc2_count = len(file_dict.get('adc2', []))
        total_files = adc1_count + adc2_count
        total_batches = (total_files + self.batch_size - 1) // self.batch_size
        
        print(f"开始分批加载 {total_files} 个文件，批次大小: {self.batch_size}, 总批次: {total_batches}")

    def _log_batch_start(self, batch_idx: int, total_batches: int, batch_files: List[Dict]):
        """记录批次开始"""
        batch_info = f"批次 {batch_idx}/{total_batches}: 加载 {len(batch_files)} 个文件"
        self.batch_loaded.emit(batch_idx, total_batches, batch_info)
        print(batch_info)

    def _log_batch_complete(self, batch_idx: int, total_batches: int):
        """记录批次完成"""
        complete_info = f"批次 {batch_idx}/{total_batches} 完成，内存已清理"
        self.batch_loaded.emit(batch_idx, total_batches, complete_info)
        print(complete_info)

    def _log_file_error(self, file_path: str, error: Exception):
        """记录文件加载错误"""
        error_msg = f"加载文件失败 {file_path}: {str(error)}"
        print(error_msg)


    def load_single_file(self, file_path: str) -> Optional[np.ndarray]:
        """加载单个文件到缓存"""
        if file_path in self._file_cache:
            return self._file_cache[file_path]
        
        try:
            data = self._load_single_file(file_path)
            if data is not None:
                self._file_cache[file_path] = data
            return data
        except Exception as e:
            print(f"加载单个文件失败 {file_path}: {str(e)}")
            return None

    def release_file(self, file_path: str):
        """释放单个文件的内存"""
        if file_path in self._file_cache:
            del self._file_cache[file_path]
        
        if file_path in self._segment_cache:
            del self._segment_cache[file_path]
        
        # 强制垃圾回收
        gc.collect()

    def pre_segment_single_file(self, file_info: Dict, full_data: np.ndarray) -> List[np.ndarray]:
        """预分割单个文件的所有段 - 公有方法"""
        return self._pre_segment_single_file(file_info, full_data)


    @property
    def _should_stop_loading(self):
        """检查是否应该停止加载"""
        # 这里可以添加停止条件
        return False
