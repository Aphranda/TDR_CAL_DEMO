# src/app/core/DataCacheManager.py

import os
import numpy as np
from typing import Dict, Optional, List
from PyQt5.QtCore import QObject, pyqtSignal

from app.core.PerformanceMonitor import timeit, performance_monitor
from app.core.FileManager import FileManager


class DataCacheManager(QObject):
    """数据缓存管理器 - 一次性加载所有文件数据到内存"""
    
    cache_loaded = pyqtSignal(dict)  # 缓存加载完成信号
    cache_error = pyqtSignal(str)    # 缓存错误信号
    
    def __init__(self):
        super().__init__()
        self._file_cache: Dict[str, np.ndarray] = {}  # 文件路径 -> 数据数组
        self._segment_cache: Dict[str, List[np.ndarray]] = {}  # 文件路径 -> 段数据列表
        self.file_manager = FileManager()
        
    @timeit
    def preload_files(self, file_dict: Dict[str, List[Dict]]) -> Dict[str, Dict]:
        """预加载所有文件数据到缓存"""
        try:
            self._log_start_message(file_dict)
            
            # 清空现有缓存
            self._file_cache.clear()
            self._segment_cache.clear()
            
            # 收集所有需要加载的文件路径
            all_files = self._collect_all_files(file_dict)
            
            # 批量加载所有文件
            loaded_files = self._batch_load_files(all_files)
            
            # 预分割所有文件的段数据
            segmented_files = self._pre_segment_all_files(file_dict, loaded_files)
            
            self._log_success_message(segmented_files)
            self.cache_loaded.emit(segmented_files)
            
            return segmented_files
            
        except Exception as e:
            error_msg = f"预加载文件失败: {str(e)}"
            self.cache_error.emit(error_msg)
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
                        'segment_info': file_info.get('segment_info', {})
                    })
        return all_files
    
    @timeit
    def _batch_load_files(self, file_list: List[Dict]) -> Dict[str, np.ndarray]:
        """批量加载所有文件数据"""
        loaded_files = {}
        
        for file_info in file_list:
            file_path = file_info['path']
            try:
                # 加载文件数据
                data = self._load_single_file(file_path)
                if data is not None:
                    loaded_files[file_path] = data
                    self._file_cache[file_path] = data
                    
                    self._log_file_loaded(file_path, len(data))
                    
            except Exception as e:
                self._log_file_error(file_path, e)
                continue
                
        return loaded_files
    
    @timeit
    def _load_single_file(self, file_path: str) -> Optional[np.ndarray]:
        """加载单个文件数据"""
        # 检测文件格式
        file_format = 'binary'  # 根据实际情况调整
        
        if file_format == 'binary':
            data = self.file_manager.load_binary_data(file_path, data_type='uint32')
            return data.astype(np.uint32)
        else:
            return self.file_manager.load_u32_text_first_col(
                file_path, skip_first=False  # 根据实际情况调整
            )
    
    @timeit
    def _pre_segment_all_files(self, file_dict: Dict, loaded_files: Dict) -> Dict[str, Dict]:
        """预分割所有文件的段数据"""
        segmented_result = {}
        
        for channel in ['adc1', 'adc2']:
            segmented_result[channel] = []
            
            for file_info in file_dict.get(channel, []):
                file_path = file_info['path']
                
                if file_path not in loaded_files:
                    continue
                    
                # 预分割该文件的所有段
                segments = self._pre_segment_single_file(file_info, loaded_files[file_path])
                
                segmented_file_info = file_info.copy()
                segmented_file_info['pre_segmented_data'] = segments
                segmented_result[channel].append(segmented_file_info)
                
        return segmented_result
    
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
                # 使用段详细信息
                if segment_idx < len(segment_details):
                    seg_detail = segment_details[segment_idx]
                    start_idx = seg_detail['start_position']
                    end_idx = seg_detail['end_position']
                else:
                    # 使用上升沿位置
                    start_idx = rise_edge_positions[segment_idx] if segment_idx < len(rise_edge_positions) else 0
                    end_idx = start_idx + 81920 + 100
            else:
                # 平均分段
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
    
    def get_segment_data(self, file_path: str, segment_idx: int) -> Optional[np.ndarray]:
        """从缓存获取段数据"""
        if file_path in self._segment_cache:
            segments = self._segment_cache[file_path]
            if segment_idx < len(segments):
                return segments[segment_idx]
        return None
    
    def clear_cache(self):
        """清空缓存"""
        self._file_cache.clear()
        self._segment_cache.clear()
    
    def _log_start_message(self, file_dict: Dict):
        """记录开始消息"""
        adc1_count = len(file_dict.get('adc1', []))
        adc2_count = len(file_dict.get('adc2', []))
        print(f"开始预加载 {adc1_count + adc2_count} 个文件 (ADC1: {adc1_count}, ADC2: {adc2_count})")
    
    def _log_file_loaded(self, file_path: str, data_length: int):
        """记录文件加载成功"""
        print(f"成功加载文件: {os.path.basename(file_path)} (数据点: {data_length})")
    
    def _log_file_error(self, file_path: str, error: Exception):
        """记录文件加载错误"""
        print(f"加载文件失败 {file_path}: {str(error)}")
    
    def _log_success_message(self, segmented_files: Dict):
        """记录成功消息"""
        adc1_count = len(segmented_files.get('adc1', []))
        adc2_count = len(segmented_files.get('adc2', []))
        total_segments = sum(
            len(file_info.get('pre_segmented_data', [])) 
            for channel in ['adc1', 'adc2'] 
            for file_info in segmented_files.get(channel, [])
        )
        print(f"预加载完成: {adc1_count + adc2_count} 个文件, {total_segments} 个数据段")
