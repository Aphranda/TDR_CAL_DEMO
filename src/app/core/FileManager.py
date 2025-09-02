# src/app/core/FileManager.py
import os
import json
import csv
import numpy as np
import pandas as pd
import struct
from datetime import datetime
from pathlib import Path
import logging

logger = logging.getLogger(__name__)

class FileManager:
    def __init__(self, base_data_path="data"):
        self.base_data_path = Path(base_data_path)
        self.create_directory_structure()
    
    def create_directory_structure(self):
        """创建数据目录结构"""
        directories = [
            "calibration",
            "results/plots",
            "results/test"  # 新增默认输出目录
        ]
        
        for directory in directories:
            path = self.base_data_path / directory
            path.mkdir(parents=True, exist_ok=True)
        
        logger.info(f"数据目录结构已创建在: {self.base_data_path.absolute()}")
    
    def ensure_dir_exists(self, directory):
        """确保目录存在，如果不存在则创建 - 优化内存版本"""
        if not directory:
            return directory
        
        # 使用缓存避免重复检查相同的目录
        if not hasattr(self, '_dir_cache'):
            self._dir_cache = set()
        
        # 如果目录已经在缓存中，直接返回
        if directory in self._dir_cache:
            return directory
        
        # 检查目录是否存在
        if not os.path.exists(directory):
            try:
                os.makedirs(directory)
                logger.info(f"创建目录: {directory}")
            except OSError as e:
                # 如果目录已存在（可能由其他进程创建），忽略错误
                if e.errno != 17:  # 17 = 文件已存在
                    logger.error(f"创建目录失败: {str(e)}")
                    raise
        
        # 添加到缓存
        self._dir_cache.add(directory)
        return directory

    
    def save_adc_csv_data(self, data, filename, output_dir, include_timestamp=True):
        """保存ADC数据到CSV文件"""
        self.ensure_dir_exists(output_dir)
        filepath = os.path.join(output_dir, filename)
        
        try:
            with open(filepath, 'w', newline='', encoding='utf-8') as csvfile:
                writer = csv.writer(csvfile)
                writer.writerow(['Index', '32位原始数据(十进制)', '32位原始数据(十六进制)', '时间戳'])
                
                timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f") if include_timestamp else ""
                
                for idx, val in enumerate(data):
                    hex_val = f"0x{val:08X}"
                    writer.writerow([idx, str(val), hex_val, timestamp])
            
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
            skip_first: 是否跳过第一行（标题行）
            
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
                    # 跳过标题行（如果存在）
                    if skip_first:
                        next(f, None)
                    
                    for line in f:
                        s = line.strip()
                        if not s:
                            continue
                        
                        # 分割CSV行的列
                        parts = s.split(',')
                        if len(parts) >= 2:  # 确保至少有2列
                            # 使用第二列的数据（索引1）
                            second_col = parts[1].strip()
                            
                            # 尝试解析第二列的值
                            try:
                                # 尝试直接转换为整数
                                val = int(second_col)
                                vals.append(np.uint32(val))
                            except ValueError:
                                # 如果直接转换失败，尝试十六进制格式
                                try:
                                    if second_col.startswith('0x'):
                                        val = int(second_col, 16)
                                    else:
                                        # 使用正则表达式匹配数字
                                        m = re.search(r'(0x[0-9a-fA-F]+|\d+)', second_col)
                                        if m:
                                            val = int(m.group(1), 0)
                                        else:
                                            continue
                                    vals.append(np.uint32(val))
                                except (ValueError, TypeError):
                                    continue
                
                arr = np.asarray(vals, dtype=np.uint32)
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
    


    def load_binary_data(self, path: str, data_type: str = 'uint32', byte_order: str = '<') -> np.ndarray:
        """
        从二进制文件加载数据
        
        Args:
            path: 文件路径
            data_type: 数据类型 ('uint32', 'int32', 'float32', 'float64')
            byte_order: 字节序 ('<' 小端, '>' 大端)
            
        Returns:
            numpy数组
        """
        try:
            with open(path, 'rb') as f:
                raw_data = f.read()
            
            if not raw_data:
                raise ValueError("文件为空")
            
            # 根据数据类型确定格式字符串
            format_map = {
                'uint32': 'I',
                'int32': 'i', 
                'float32': 'f',
                'float64': 'd'
            }
            
            if data_type not in format_map:
                raise ValueError(f"不支持的数据类型: {data_type}")
            
            fmt_char = format_map[data_type]
            element_size = struct.calcsize(byte_order + fmt_char)
            
            # 检查数据长度是否匹配
            if len(raw_data) % element_size != 0:
                logger.warning(f"文件大小({len(raw_data)}字节)不是{data_type}类型大小的整数倍，将截断数据")
                raw_data = raw_data[:-(len(raw_data) % element_size)]
            
            # 解析二进制数据
            num_elements = len(raw_data) // element_size
            fmt_string = byte_order + fmt_char * num_elements
            
            try:
                data = struct.unpack(fmt_string, raw_data)
            except struct.error as e:
                raise ValueError(f"二进制数据解析失败: {str(e)}")
            
            return np.array(data, dtype=getattr(np, data_type))
            
        except Exception as e:
            logger.error(f"加载二进制文件失败: {str(e)}")
            raise

    def detect_file_format(self, path: str) -> str:
        """
        检测文件格式，特别处理ADC二进制数据
        
        Returns:
            'text' 或 'binary'
        """
        try:
            with open(path, 'rb') as f:
                # 读取前1024字节进行检测
                sample = f.read(1024)
                
            if not sample:
                return 'text'  # 空文件视为文本
            
            # ADC二进制数据的特殊检测逻辑
            # 检查是否包含典型的ADC数据特征
            if len(sample) >= 4:
                # 检查前几个32位值是否在合理的ADC范围内
                try:
                    # 解析前几个uint32值
                    num_values = min(10, len(sample) // 4)
                    for i in range(num_values):
                        offset = i * 4
                        if offset + 4 <= len(sample):
                            value = struct.unpack('<I', sample[offset:offset+4])[0]
                            # ADC数据通常在特定范围内，排除明显的错误值
                            if value == 0xFFFFFFFF or value == 0x00000000:
                                continue  # 可能是填充值
                            if value > 0xFF000000:  # 高字节为FF可能是错误数据
                                return 'binary'  # 但仍然认为是二进制格式
                except:
                    pass
            
            # 标准检测逻辑
            text_chars = bytearray({7,8,9,10,12,13,27} | set(range(0x20, 0x100)) - {0x7f})
            
            if b'\x00' in sample:
                return 'binary'
                
            # 检查非文本字符的比例
            non_text = [byte for byte in sample if byte not in text_chars]
            if len(non_text) / len(sample) > 0.3:
                return 'binary'
                
            return 'text'
            
        except Exception as e:
            logger.warning(f"文件格式检测失败: {str(e)}，默认视为二进制文件")
            return 'binary'  # 对于ADC数据，默认视为二进制


    
    
