# src/app/core/FileManager.py
import os
import json
import csv
import numpy as np
import pandas as pd
import struct
from datetime import datetime
from pathlib import Path
import h5py
import logging

logger = logging.getLogger(__name__)

class FileManager:
    def __init__(self, base_data_path="data"):
        self.base_data_path = Path(base_data_path)
        self.create_directory_structure()
    
    def create_directory_structure(self):
        """创建数据目录结构"""
        directories = [
            "raw/adc_samples",
            "raw/calibration",
            "processed/s_parameters",
            "processed/tdr",
            "processed/adc_analysis",
            "calibration/s2p_files",
            "calibration/coefficients",
            "results/reports",
            "results/plots",
            "results/exports"
        ]
        
        for directory in directories:
            path = self.base_data_path / directory
            path.mkdir(parents=True, exist_ok=True)
    
    def ensure_dir_exists(self, directory):
        """确保目录存在，如果不存在则创建"""
        if not os.path.exists(directory):
            os.makedirs(directory)
        return directory
    
    def get_today_raw_data_path(self, channel: int = None) -> Path:
        """获取今天的原始数据目录路径"""
        today = datetime.now().strftime("%Y-%m-%d")
        path = self.base_data_path / "raw" / "adc_samples" / today
        if channel is not None:
            path = path / f"channel{channel}"
        path.mkdir(parents=True, exist_ok=True)
        return path
    
    def save_adc_csv_data(self, data, filename, output_dir):
        """保存ADC数据到CSV文件"""
        self.ensure_dir_exists(output_dir)
        filepath = os.path.join(output_dir, filename)
        
        try:
            with open(filepath, 'w', newline='', encoding='utf-8') as csvfile:
                writer = csv.writer(csvfile)
                writer.writerow(['32位原始数据(十进制)'])
                
                for val in data:
                    writer.writerow([str(val)])
            
            logger.info(f"数据已保存到 {filepath}，共{len(data)}个数据点")
            return True, f"数据保存成功: {filepath}"
            
        except Exception as e:
            logger.error(f"数据保存失败: {str(e)}")
            return False, f"数据保存失败: {str(e)}"
    
    def save_analysis_results_csv(self, data, filename, headers=None):
        """保存分析结果到CSV文件"""
        try:
            with open(filename, 'w', newline='', encoding='utf-8') as csvfile:
                writer = csv.writer(csvfile)
                if headers:
                    writer.writerow(headers)
                
                if isinstance(data, np.ndarray):
                    if data.ndim == 1:
                        for val in data:
                            writer.writerow([val])
                    else:
                        for row in data:
                            writer.writerow(row)
                else:
                    for row in data:
                        writer.writerow(row)
            
            logger.info(f"分析结果保存到: {filename}")
            return True
            
        except Exception as e:
            logger.error(f"分析结果保存失败: {str(e)}")
            return False
    
    def save_complex_fft_results(self, freq_data, real_data, imag_data, filename, header="freq_Hz,Re,Im"):
        """保存复数FFT结果到CSV文件"""
        try:
            out_mat = np.column_stack([freq_data, real_data, imag_data])
            np.savetxt(filename, out_mat, delimiter=",", 
                      header=header, comments="", fmt="%.10e")
            logger.info(f"复数FFT结果保存到: {os.path.abspath(filename)}")
            return True
        except Exception as e:
            logger.error(f"复数FFT结果保存失败: {str(e)}")
            return False
    
    def save_json_data(self, data, filename):
        """保存数据到JSON文件"""
        try:
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            logger.info(f"JSON数据保存到: {filename}")
            return True
        except Exception as e:
            logger.error(f"JSON数据保存失败: {str(e)}")
            return False
    
    def load_u32_text_first_col(self, path: str, skip_first: bool = True) -> np.ndarray:
        """
        从文本文件加载uint32数据
        
        Args:
            path: 文件路径
            skip_first: 是否跳过第一行
            
        Returns:
            uint32数组
        """
        import re
        
        encodings = ["utf-8", "utf-8-sig", "gbk", "latin1", "utf-16", "utf-16le", "utf-16be"]
        last_err = None
        
        for enc in encodings:
            try:
                vals = []
                with open(path, "r", encoding=enc, errors="strict") as f:
                    for line in f:
                        s = line.strip()
                        if not s:
                            continue
                        # 使用正则表达式匹配十六进制或十进制数字
                        m = re.search(r'(0x[0-9a-fA-F]+|\d+)', s)
                        if not m:
                            continue
                        vals.append(np.uint32(int(m.group(1), 0)))
                
                arr = np.asarray(vals, dtype=np.uint32)
                if skip_first and arr.size >= 1:
                    arr = arr[1:]
                return arr
                
            except Exception as e:
                last_err = e
                continue
        
        raise last_err or Exception("无法读取文件")
    
    def find_csv_files(self, input_dir, recursive=True):
        """查找CSV文件"""
        import glob
        
        pattern = os.path.join(input_dir, "**", "*.csv") if recursive else os.path.join(input_dir, "*.csv")
        files = sorted(glob.glob(pattern, recursive=recursive))
        
        if not files:
            raise FileNotFoundError(f"未找到csv文件: {pattern}")
        
        logger.info(f"找到 {len(files)} 个CSV文件")
        return files
    
    def save_adc_raw_data_h5(self, data: np.ndarray, metadata: dict, 
                           channel: int = 1, prefix: str = "adc_sample") -> str:
        """保存ADC原始数据到HDF5文件"""
        timestamp = datetime.now().strftime("%H%M%S")
        filename = f"{prefix}_{timestamp}_ch{channel}.h5"
        filepath = self.get_today_raw_data_path(channel) / filename
        
        with h5py.File(filepath, 'w') as f:
            # 保存数据
            f.create_dataset('adc_data', data=data)
            
            # 保存元数据
            metadata_group = f.create_group('metadata')
            for key, value in metadata.items():
                if isinstance(value, (str, int, float, bool)):
                    metadata_group.attrs[key] = value
                elif isinstance(value, dict):
                    # 嵌套字典保存为JSON字符串
                    metadata_group.attrs[key] = json.dumps(value)
        
        return str(filepath)
    
    def load_adc_data_h5(self, filepath: str) -> tuple:
        """从HDF5文件加载ADC数据"""
        with h5py.File(filepath, 'r') as f:
            # 加载数据
            data = f['adc_data'][:]
            
            # 加载元数据
            metadata = {}
            for key, value in f['metadata'].attrs.items():
                try:
                    # 尝试解析JSON字符串
                    metadata[key] = json.loads(value)
                except (json.JSONDecodeError, TypeError):
                    metadata[key] = value
        
        return data, metadata
