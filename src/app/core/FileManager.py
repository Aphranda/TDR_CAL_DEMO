import os
import csv
import re
from pathlib import Path
import pandas as pd
import hashlib
import shutil
import json
import struct
import threading
from typing import Dict, List, Optional, Tuple, Union
from datetime import datetime, timezone

class FileManager:
    """
    校准文件全生命周期管理类
    功能涵盖：创建、写入、验证、版本控制、自动归档、数据完整性检查
    """
    
    def __init__(self, base_dir: str = "calibrations", log_callback: Optional[callable] = None):
        """
        初始化校准文件管理器
        
        :param base_dir: 校准文件存储根目录
        :param log_callback: 日志回调函数，格式为 func(msg: str, level: str)
        """
        self.base_dir = os.path.abspath(base_dir)
        self.active_file: Optional[str] = None
        self.current_meta: Dict = {}
        self.data_points: List = []
        self._file_lock = threading.Lock()
        self.points = 0
        
        os.makedirs(self.base_dir, exist_ok=True)
        
        # 初始化日志系统
        self.log = log_callback if callable(log_callback) else self._default_logger
        
        # 创建必要的子目录
        for subdir in ["archive", "backup"]:
            os.makedirs(os.path.join(self.base_dir, subdir), exist_ok=True)

    def _default_logger(self, msg: str, level: str = "INFO"):
        """默认日志记录器"""
        print(f"[CAL {level}] {msg}")

    def _generate_bin_filename(self, csv_path: str) -> str:
        """根据CSV路径生成对应的BIN文件名"""
        base, ext = os.path.splitext(csv_path)
        return base + ".bin"
    
    def _write_bin_file(self, csv_path: str):
        """将CSV数据写入BIN文件"""
        bin_path = self._generate_bin_filename(csv_path)
        
        # 二进制文件结构：
        # 头部: 4字节幻数(0x524E5843 'RNXC') + 1字节版本(1)
        # 元数据: JSON格式的字符串(UTF-8编码)
        # 数据: 每个数据点7个float32(频率 + 6个参数)
        
        try:
            with open(bin_path, 'wb') as f:
                # 写入头部
                f.write(b'RNXC')  # 幻数
                f.write(bytes([1]))  # 版本号
                
                # 写入元数据
                meta_json = json.dumps(self.current_meta).encode('utf-8')
                f.write(len(meta_json).to_bytes(4, 'little'))  # 元数据长度
                f.write(meta_json)  # 元数据内容
                
                # 写入数据点
                for point in self._data_points:
                    freq = round(point['freq'], 6)  # 确保频率保留6位小数
                    data = [
                        point['theta'], point['phi'],
                        point['horn_gain'],
                        point['theta_corrected'], point['phi_corrected'],
                        point['theta_corrected_vm'], point['phi_corrected_vm']
                    ]
                    # 写入频率(1个float32)和7个参数(7个float32)
                    f.write(struct.pack('f', freq))
                    f.write(struct.pack('7f', *data))
                
            self.log(f"已生成二进制校准文件: {os.path.basename(bin_path)}", "INFO")
            return bin_path
        except Exception as e:
            self.log(f"生成二进制文件失败: {str(e)}", "ERROR")
            return None
        
    def generate_default_calibration(self, freq_range: Tuple[float, float] = (8.0, 40.0), 
                                step: float = 0.01, freq_list: Optional[List[float]] = None) -> str:
        """
        生成默认校准文件（所有参数为0），支持频点列表或频率范围
        
        :param freq_range: 频率范围(GHz) (start, stop) - 当freq_list为None时使用
        :param step: 频率步进(GHz) - 当freq_list为None时使用
        :param freq_list: 自定义频点列表(GHz)，优先级高于freq_range和step
        :return: 生成的校准文件路径
        """
        # 默认设备元数据
        default_meta = {
            'operator': 'SYSTEM',
            'signal_gen': ('PLASG-T8G40G', 'SN00000'),
            'power_meter': ('NRP50S', 'SN00000'),
            'antenna': ('RNX_ANT', 'SN00000'),
            'environment': (25.0, 50.0),  # 25°C, 50%RH
            'ref_power': {'X': -20.0, 'KU': -15.0, 'K': -30.0, 'KA': -20.0}
        }
        
        # 根据输入参数确定频率参数
        if freq_list is not None:
            # 使用自定义频点列表
            if not isinstance(freq_list, list) or len(freq_list) == 0:
                raise ValueError("freq_list必须是非空列表")
            
            # 确保所有频点都是数字且在合理范围内
            valid_freqs = []
            for freq in freq_list:
                try:
                    freq_float = float(freq)
                    if 0.1 <= freq_float <= 100.0:  # 假设合理频率范围是0.1-100GHz
                        valid_freqs.append(round(freq_float, 6))
                    else:
                        self.log(f"忽略超出范围的频率: {freq}GHz", "WARNING")
                except ValueError:
                    self.log(f"忽略无效的频率值: {freq}", "WARNING")
            
            if not valid_freqs:
                raise ValueError("没有有效的频率点")
            
            # 对频点进行排序并去重
            valid_freqs = sorted(list(set(valid_freqs)))
            freq_params = {
                'start_ghz': min(valid_freqs),
                'stop_ghz': max(valid_freqs),
                'step_ghz': 'FreqList',  # 标记为频点列表模式
                'custom_freqs': valid_freqs  # 存储自定义频点
            }
            points = len(valid_freqs)
        else:
            # 使用频率范围和步进
            start_ghz = min(freq_range)
            stop_ghz = max(freq_range)
            step = abs(step)  # 确保步进为正
            
            # 计算精确的点数，避免浮点误差
            points = int(round((stop_ghz - start_ghz) / step)) + 1
            freq_params = {
                'start_ghz': start_ghz,
                'stop_ghz': stop_ghz,
                'step_ghz': step,
                'custom_freqs': None
            }
        
        # 创建新校准文件
        # 构造基础参数
        base_param = {
            'ref_power': default_meta['ref_power']['X'] if isinstance(default_meta['ref_power'], dict) else -20.0,
            'polarization': 'PHI',
            'distance': 1.0
        }
        self.create_new_calibration(
            equipment_meta=default_meta,
            freq_params=freq_params,
            base_param=base_param,
            version_notes="The default calibration file generated by the system" + 
                        (" [自定义频点]" if freq_list is not None else "")
        )
        
        # 填充0值数据
        if freq_list is not None:
            # 使用自定义频点
            for freq in valid_freqs:
                zero_data = {
                    'theta': 0.0, 'phi': 0.0,
                    'horn_gain': 0.0,
                    'theta_corrected': 0.0, 'phi_corrected': 0.0,
                    'theta_corrected_vm': 0.0, 'phi_corrected_vm': 0.0
                }
                self.add_data_point(freq, zero_data)
        else:
            # 使用频率范围和步进
            for i in range(points):
                freq = start_ghz + i * step
                # 处理浮点精度问题，确保最后一个点是stop_ghz
                if i == points - 1:
                    freq = stop_ghz
                    
                default_gain = 18
                zero_data = {
                    'theta': default_gain, 'phi': default_gain,
                    'horn_gain': 8,
                    'theta_corrected': default_gain, 'phi_corrected': default_gain,
                    'theta_corrected_vm': default_gain, 'phi_corrected_vm': default_gain
                }
                self.add_data_point(round(freq, 6), zero_data)  # 保留6位小数避免浮点误差
        
        # 完成校准
        archived_path = self.finalize_calibration("系统自动生成的默认校准文件")
        
        return archived_path

    def create_new_calibration(self, 
                            equipment_meta: Dict, 
                            freq_params: Dict,
                            base_param: Dict,
                            version_notes: Optional[str] = None) -> str:
        """
        创建新校准文件
        
        :param equipment_meta: 设备元数据
        :param freq_params: 频率参数
        :param base_param: 基础参数 {ref_power: float, polarization: str}
        :param version_notes: 版本说明
        :return: 创建的校准文件路径
        """
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%SZ")
        
        # 从base_param获取参考功率和极化信息
        ref_power = base_param.get('ref_power', 'UNKNOWN')
        polarization = base_param.get('polarization', 'DUAL').upper()
        
        # 计算总点数
        if freq_params.get("custom_freqs"):
            points = len(freq_params["custom_freqs"])
        else:
            points = int((freq_params['stop_ghz'] - freq_params['start_ghz']) / freq_params['step_ghz']) + 1

        # 生成文件名
        step_str = "FreqList" if freq_params.get("step_ghz") == "FreqList" else f"{freq_params['step_ghz']}"
        filename = (
            f"RNX_Cal_{polarization}_"
            f"RefPwr{ref_power}dBm_"
            f"{freq_params['start_ghz']}to{freq_params['stop_ghz']}GHz_"
            f"step{step_str}_{timestamp}.csv"
        )
        
        self.active_file = os.path.join(self.base_dir, filename)
        self.active_bin_file = self._generate_bin_filename(self.active_file)
        self.current_meta = {
            **equipment_meta,
            'freq_params': freq_params,
            'base_param': base_param,  # 保存基础参数
            'created': timestamp,
            'points': points,
            'version_notes': version_notes,
            'file_format': 'csv+bin'
        }
        self._data_points = []  # 重置数据点
        
        # 生成文件头内容
        header_content = self._generate_header()
        
        # 分割文件头内容为行
        header_lines = header_content.split('\n')
        
        # 找到数据列标题行的位置（最后一行）
        data_header_index = None
        for i, line in enumerate(header_lines):
            if line.startswith("Frequency,"):
                data_header_index = i
                break
        
        if data_header_index is not None:
            # 在数据列标题行之前插入额外信息
            insert_lines = []
            if version_notes:
                insert_lines.append(f"!VersionNotes: {version_notes}")
            insert_lines.append(f"!BaseParams: {json.dumps(base_param)}")
            
            # 重新构建文件头内容
            header_content = '\n'.join(
                header_lines[:data_header_index] + 
                insert_lines + 
                [header_lines[data_header_index]] +
                ['']
            )
        
        # 写入文件
        with self._file_lock, open(self.active_file, 'w', encoding='utf-8') as f:
            f.write(header_content)
        
        self.log(f"创建新校准文件: {filename}", "INFO")
        return self.active_file

    def merge_calibration_files(self, file_paths: List[str], output_filename: Optional[str] = None) -> str:
        """
        合并多个校准文件为一个综合校准文件，支持数据去重和极化合并
        
        :param file_paths: 要合并的校准文件路径列表
        :param output_filename: 输出文件名(可选)，如果为None则自动生成
        :return: 合并后的文件路径
        
        合并规则:
        1. 相同频率和参考功率的数据点:
        - 如果极化相同且所有数据相同，则去重
        - 如果极化不同，则合并为双极化数据
        2. 不同频率或参考功率的数据点全部保留
        3. 自动剔除已经被合并过的文件(通过检查!VersionNotes: Merged calibration file)
        """
        if not file_paths:
            raise ValueError("至少需要一个校准文件")
        
        # 检查并剔除已合并的文件
        filtered_file_paths = []
        for filepath in file_paths:
            try:
                # 检查文件是否已经是合并文件
                with open(filepath, 'r', encoding='utf-8') as f:
                    for line in f:
                        if line.startswith('!VersionNotes:'):
                            if 'Merged calibration file' in line:
                                self.log(f"检测到已合并文件: {os.path.basename(filepath)}", "WARNING")
                                self.log(f"跳过已合并的文件: {os.path.basename(filepath)}", "INFO")
                                break
                            else:
                                filtered_file_paths.append(filepath)
                                break
                        elif not line.startswith('!'):  # 遇到数据行说明没有VersionNotes
                            filtered_file_paths.append(filepath)
                            break
            except Exception as e:
                self.log(f"检查文件{filepath}失败: {str(e)}", "WARNING")
                continue
        
        if not filtered_file_paths:
            raise ValueError("没有有效的校准文件可以合并")
        
        # 加载所有文件数据
        all_data = []
        all_meta = []
        for filepath in filtered_file_paths:
            file_data = self.load_calibration_file(filepath)
            if file_data is None:
                self.log(f"无法加载文件: {filepath}", "WARNING")
                continue
            
            all_meta.append(file_data['meta'])
            for point in file_data['data']:
                # 确保每个数据点包含参考功率和极化信息
                if 'reference_power' not in point:
                    ref_power = file_data['meta']['base_param'].get('ref_power', 0.0)
                    if isinstance(ref_power, list):
                        if len(ref_power) > 0:
                            point['reference_power'] = ref_power[0]  # 取第一个值
                        else:
                            point['reference_power'] = 0.0  # 默认值
                    else:
                        point['reference_power'] = float(ref_power)  # 确保是float
                
                if 'polarization' not in point:
                    point['polarization'] = file_data['meta']['base_param'].get('polarization', 'DUAL')
                
                all_data.append(point)
        
        if not all_data:
            raise ValueError("没有有效数据可以合并")
        
        # 数据合并处理
        merged_data = {}
        for point in all_data:
            freq = round(point['freq'], 6)  # 频率作为键的一部分，保留6位小数
            ref_power = round(point['reference_power'], 2)  # 参考功率作为键的一部分
            key = (freq, ref_power)
            
            if key not in merged_data:
                # 新数据点
                merged_data[key] = {
                    'theta': None,
                    'phi': None,
                    'horn_gain': point.get('horn_gain', 0.0),
                    'theta_corrected': None,
                    'phi_corrected': None,
                    'theta_corrected_vm': None,
                    'phi_corrected_vm': None,
                    'polarizations': set(),
                    'source_points': []
                }
            
            # 记录极化信息
            merged_data[key]['polarizations'].add(point['polarization'].upper())
            merged_data[key]['source_points'].append(point)
            
            # 根据极化类型填充数据
            pol = point['polarization'].upper()
            if pol == 'THETA':
                merged_data[key]['theta'] = point.get('theta', 0.0)
                merged_data[key]['theta_corrected'] = point.get('theta_corrected', 0.0)
                merged_data[key]['theta_corrected_vm'] = point.get('theta_corrected_vm', 0.0)
            elif pol == 'PHI':
                merged_data[key]['phi'] = point.get('phi', 0.0)
                merged_data[key]['phi_corrected'] = point.get('phi_corrected', 0.0)
                merged_data[key]['phi_corrected_vm'] = point.get('phi_corrected_vm', 0.0)
            elif pol == 'DUAL':
                # 如果是双极化数据，直接覆盖
                merged_data[key]['theta'] = point.get('theta', 0.0)
                merged_data[key]['phi'] = point.get('phi', 0.0)
                merged_data[key]['theta_corrected'] = point.get('theta_corrected', 0.0)
                merged_data[key]['phi_corrected'] = point.get('phi_corrected', 0.0)
                merged_data[key]['theta_corrected_vm'] = point.get('theta_corrected_vm', 0.0)
                merged_data[key]['phi_corrected_vm'] = point.get('phi_corrected_vm', 0.0)
        
        # 准备最终合并后的数据点
        final_data = []
        for key, data in merged_data.items():
            freq, ref_power = key
            
            # 检查是否有完整的双极化数据
            if data['theta'] is not None and data['phi'] is not None:
                # 已有完整双极化数据
                polarization = 'DUAL'
            elif len(data['polarizations']) == 2:
                # 合并两个单极化数据为双极化
                polarization = 'DUAL'
                
                # 如果某个极化数据缺失，保持原值或设为0
                if data['theta'] is None:
                    data['theta'] = 0.0
                    data['theta_corrected'] = 0.0
                    data['theta_corrected_vm'] = 0.0
                
                if data['phi'] is None:
                    data['phi'] = 0.0
                    data['phi_corrected'] = 0.0
                    data['phi_corrected_vm'] = 0.0
            else:
                # 保持单极化
                polarization = data['polarizations'].pop() if data['polarizations'] else 'DUAL'
            
            final_data.append({
                'freq': freq,
                'theta': data['theta'] if data['theta'] is not None else 0.0,
                'phi': data['phi'] if data['phi'] is not None else 0.0,
                'horn_gain': data['horn_gain'],
                'theta_corrected': data['theta_corrected'] if data['theta_corrected'] is not None else 0.0,
                'phi_corrected': data['phi_corrected'] if data['phi_corrected'] is not None else 0.0,
                'theta_corrected_vm': data['theta_corrected_vm'] if data['theta_corrected_vm'] is not None else 0.0,
                'phi_corrected_vm': data['phi_corrected_vm'] if data['phi_corrected_vm'] is not None else 0.0,
                'reference_power': ref_power,
                'polarization': polarization
            })
        
        # 按频率排序
        final_data.sort(key=lambda x: x['freq'])
        
        # 使用第一个文件的元数据作为基础
        base_meta = all_meta[0].copy()
        
        # 更新元数据中的关键字段
        freqs = [p['freq'] for p in final_data]
        ref_powers = list({p['reference_power'] for p in final_data})
        polarizations = list({p['polarization'] for p in final_data})
        
        # 构建新的元数据
        base_meta['freq_params'] = {
            'start_ghz': min(freqs),
            'stop_ghz': max(freqs),
            'step_ghz': 'FreqList',
            'custom_freqs': sorted(freqs)
        }
        base_meta['points'] = len(final_data)
        
        # 处理参考功率显示
        if len(ref_powers) == 1:
            ref_power_str = f"{ref_powers[0]:.1f}"
        else:
            ref_power_str = '_'.join([f"{p:.1f}" for p in sorted(ref_powers)])
        
        # 处理极化模式显示
        if len(polarizations) == 1:
            polarization_str = polarizations[0]
        else:
            polarization_str = 'DUAL'
        
        # 更新基础参数
        base_meta['base_param'] = {
            'ref_power': ref_power_str,
            'polarization': polarization_str,
            'distance': 1.0,
            'operator': 'SYSTEM'
        }
        
        # 生成输出文件名
        if output_filename is None:
            timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%SZ")
            output_filename = (
                f"RNX_Cal_{polarization_str}_"
                f"RefPwr{ref_power_str}dBm_"
                f"{min(freqs)}to{max(freqs)}GHz_"
                f"stepFreqList_{timestamp}.csv"
            )
        
        # 创建新校准文件
        self.create_new_calibration(
            equipment_meta=base_meta,
            freq_params=base_meta['freq_params'],
            base_param=base_meta['base_param'],
            version_notes="Merged calibration file from multiple sources"
        )
        
        # 添加所有数据点
        for point in final_data:
            self.add_data_point(point['freq'], {
                'theta': point['theta'],
                'phi': point['phi'],
                'horn_gain': point['horn_gain'],
                'theta_corrected': point['theta_corrected'],
                'phi_corrected': point['phi_corrected'],
                'theta_corrected_vm': point['theta_corrected_vm'],
                'phi_corrected_vm': point['phi_corrected_vm'],
                'reference_power': point['reference_power'],
                'polarization': point['polarization']
            })
        
        # 完成校准
        archived_path = self.finalize_calibration("Merged calibration file from multiple sources")
        
        return archived_path



    def _generate_header(self) -> str:
        """生成标准文件头"""
        meta = self.current_meta
        freq = meta['freq_params']
        base = meta.get('base_param', {})
        
        header_lines = [
            "!RNX Dual-Polarized Feed Calibration Data",
            f"!Created: {meta['created'].replace('_', 'T')}Z",
            f"!Operator: {meta['operator']}",
            "!Base Parameters:",
            f"!  Reference_Power: {base.get('ref_power', 'UNKNOWN')} dBm",
            f"!  Polarization: {base.get('polarization', 'DUAL')}",
            f"!  Distance: {base.get('distance', 1.0)} m",
            "!Equipment:",
            f"!  Signal_Generator: {meta['signal_gen'][0]}_SN:{meta['signal_gen'][1]}",
            f"!  Spectrum_Analyzer: {meta['power_meter'][0]}_SN:{meta['power_meter'][1]}",
            f"!  Antenna: {meta['antenna'][0]}_SN:{meta['antenna'][1]}",
            f"!Environment: {meta['environment'][0]}C, {meta['environment'][1]}%RH",
            "!Frequency:",
            f"!  Start: {freq['start_ghz']} GHz",
            f"!  Stop: {freq['stop_ghz']} GHz",
            f"!  Step: {freq.get('step_ghz', 'FreqList')} GHz",
            f"!  Points: {meta['points']}",
            "!Data Columns:",
            "!  1: Frequency(GHz)",
            "!  2: Theta(dB)",
            "!  3: Phi(dB)",
            "!  4: Horn_Gain(GHz)",
            "!  5: Theta_corrected(dB)",
            "!  6: Phi_corrected(dB)",
            "!  7: Theta_corrected_V/M(V/M)",
            "!  8: Phi_corrected_V/M(V/M)",
            "!  9: Reference_Power(dBm)",
            "! 10: Polarization",
            "Frequency,Theta,Phi,Horn_Gain,Theta_corrected,Phi_corrected,Theta_corrected_V/M,Phi_corrected_V/M,Reference_Power,Polarization",
        ]
        return '\n'.join(header_lines) + '\n'


    def add_data_point(self, freq_ghz: float, data: Dict) -> bool:
        """
        添加单频点数据
        
        :param freq_ghz: 当前频率(GHz)
        :param data: 测量数据
        :return: 是否成功添加
        """
        if not self.active_file:
            raise RuntimeError("没有活动的校准文件")
        
        # 验证数据范围
        for key, value in data.items():
            # 特殊处理polarization字段
            if key == 'polarization':
                if not isinstance(value, str):
                    self.log(f"极化模式必须是字符串: {value}", "ERROR")
                    return False
                if value.upper() not in ['THETA', 'PHI', 'DUAL']:
                    self.log(f"无效的极化模式: {value}", "ERROR")
                    return False
                continue
                
            # 验证其他数值字段
            if not isinstance(value, (int, float)):
                self.log(f"无效数据格式: {key}={value}", "ERROR")
                return False
            if not (-100 <= value <= 100):  # 假设合理范围是-100到100 dB
                self.log(f"数据超出范围: {key}={value}", "WARNING")
        
        # 存储数据点用于BIN文件
        self._data_points.append({
            'freq': round(freq_ghz, 6),  # 确保频率保留6位小数
            **data
        })
        
        # 判断是否为合并文件
        is_merged_file = "merged" in self.current_meta.get('version_notes', '').lower()
        
        # 格式化数据行
        if is_merged_file:
            # 合并文件包含reference_power和polarization
            data_row = (
                f"{freq_ghz:.6f},"
                f"{data.get('theta', 0.0):.2f},"
                f"{data.get('phi', 0.0):.2f},"
                f"{data.get('horn_gain', 0.0):.5f},"
                f"{data.get('theta_corrected', 0.0):.2f},"
                f"{data.get('phi_corrected', 0.0):.2f},"
                f"{data.get('theta_corrected_vm', 0.0):.2f},"
                f"{data.get('phi_corrected_vm', 0.0):.2f},"
                f"{data.get('reference_power', 0.0):.2f},"
                f"{data.get('polarization', 'DUAL')}\n"
            )
        else:
            # 普通校准文件不包含这两个字段
            data_row = (
                f"{freq_ghz:.6f},"
                f"{data.get('theta', 0.0):.2f},"
                f"{data.get('phi', 0.0):.2f},"
                f"{data.get('horn_gain', 0.0):.5f},"
                f"{data.get('theta_corrected', 0.0):.2f},"
                f"{data.get('phi_corrected', 0.0):.2f},"
                f"{data.get('theta_corrected_vm', 0.0):.2f},"
                f"{data.get('phi_corrected_vm', 0.0):.2f}\n"
            )
        
        # 写入数据（线程安全）
        with self._file_lock, open(self.active_file, 'a', encoding='utf-8') as f:
            f.write(data_row)
        
        return True




    def add_calibration_point(self, point: 'CalibrationPoint') -> bool:
        """
        添加校准点数据（完整实现，包含所有计算）
        
        计算公式说明：
        1. theta_corrected = measured_theta - horn_gain
        2. phi_corrected = measured_phi - horn_gain
        3. V/M值使用SignalUnitConverter的dbm_to_dbuV_m方法计算
        
        :param point: 包含所有测量数据的CalibrationPoint对象
        :return: 是否成功添加数据点
        """
        try:
            converter = SignalUnitConverter()
            freq_ghz = point.freq_hz / 1e9
            
            # 计算基础校正值
            point.theta_corrected = point.measured_theta - point.horn_gain
            point.phi_corrected = point.measured_phi - point.horn_gain
            
            # 计算V/M校正值（考虑天线增益和距离）
            theta_vm = converter.dbm_to_v_m(
                dbm=point.theta_corrected,
                frequency=point.freq_hz,
                distance=point.distance
            )
            
            phi_vm = converter.dbm_to_v_m(
                dbm=point.phi_corrected,
                frequency=point.freq_hz,
                distance=point.distance
            )
            
            # 构建数据点
            data = {
                'theta': round(point.measured_theta, 2),
                'phi': round(point.measured_phi, 2),
                'horn_gain': round(point.horn_gain, 5),
                'theta_corrected': round(point.theta_corrected, 2),
                'phi_corrected': round(point.phi_corrected, 2),
                'theta_corrected_vm': round(theta_vm, 2),
                'phi_corrected_vm': round(phi_vm, 2)
            }
            
            return self.add_data_point(freq_ghz, data)
        
        except Exception as e:
            self.log(f"计算校正值时出错: {str(e)}", "ERROR")
            return False

    
    def finalize_calibration(self, notes: str = "") -> Tuple[str, str]:
        """
        完成校准并添加校验信息
        
        :param notes: 附加说明
        :return: (归档后的CSV文件路径, BIN文件路径)
        """
        if not self.active_file:
            raise RuntimeError("没有活动的校准文件")
        
        # 添加结束标记
        with self._file_lock, open(self.active_file, 'a', encoding='utf-8') as f:
            f.write(f"!EndOfData: {datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')}\n")
            if notes:
                f.write(f"!Notes: {notes}\n")
        
        # 生成MD5校验
        file_hash = self._calculate_file_hash()
        with open(self.active_file, 'a', encoding='utf-8') as f:
            f.write(f"!MD5: {file_hash}\n")
        
        # 生成BIN文件
        bin_path = self._write_bin_file(self.active_file)
        
        self.log(f"校准完成: {os.path.basename(self.active_file)}", "SUCCESS")
        
        # 归档文件
        archived_csv = self._archive_file()  # 归档CSV
        archived_bin = self._archive_file(bin_path) if bin_path else None  # 归档BIN
        
        self.active_file = None
        self.active_bin_file = None
        self.current_meta = {}
        self._data_points = []
        
        return archived_csv, archived_bin

    def load_calibration_file(self, filepath: str) -> Optional[Dict]:
        """
        加载校准文件(支持CSV和BIN格式)
        
        :param filepath: 文件路径
        :return: 包含元数据和数据的字典，None表示失败
        """
        if not os.path.exists(filepath):
            self.log(f"文件不存在: {filepath}", "ERROR")
            return None
        
        # 根据扩展名选择加载方式
        if filepath.lower().endswith('.bin'):
            return self._load_bin_file(filepath)
        else:
            return self._load_csv_file(filepath)
        
    def _load_bin_file(self, bin_path: str) -> Optional[Dict]:
        """
        加载BIN格式校准文件
        1. 先验证文件有效性
        2. 再读取文件内容
        """
        # 先验证文件
        if not self._validate_bin_file(bin_path):
            self.log(f"BIN文件验证失败: {bin_path}", "ERROR")
            return None
        
        # 验证通过后读取内容
        return self._read_bin_content(bin_path)

    def _load_csv_file(self, csv_path: str) -> Optional[Dict]:
        """
        加载CSV格式校准文件
        1. 先验证文件有效性
        2. 再读取文件内容
        """
        # 先验证文件
        if not self._validate_csv_file(csv_path):
            self.log(f"CSV文件验证失败: {csv_path}", "ERROR")
            return None
        
        # 验证通过后读取内容
        return self._read_csv_content(csv_path)

    def _validate_bin_file(self, filepath: str) -> bool:
        """
        验证BIN格式校准文件结构是否有效
        不解析具体内容，只检查文件格式和完整性
        
        更新内容：
        1. 支持验证ref_power为单个值或列表格式
        2. 更新基础参数验证逻辑
        """
        try:
            with open(filepath, 'rb') as f:
                # 验证头部
                magic = f.read(4)
                if magic != b'RNXC':
                    self.log("无效的二进制文件格式", "WARNING")
                    return False
                
                version = ord(f.read(1))
                if version != 1:
                    self.log(f"不支持的版本号: {version}", "WARNING")
                    return False
                
                # 读取元数据长度
                meta_len = int.from_bytes(f.read(4), 'little')
                meta_json = f.read(meta_len).decode('utf-8')
                
                # 验证元数据中的基础参数
                try:
                    meta = json.loads(meta_json)
                    if 'base_param' not in meta:
                        self.log("缺少基础参数", "WARNING")
                        return False
                        
                    required_params = ['ref_power', 'polarization']
                    for param in required_params:
                        if param not in meta['base_param']:
                            self.log(f"缺少必需的基础参数: {param}", "WARNING")
                            return False
                    
                    # 验证ref_power格式
                    ref_power = meta['base_param']['ref_power']
                    if isinstance(ref_power, str) and '_' in ref_power:
                        # 检查列表格式是否有效
                        try:
                            [float(p) for p in ref_power.split('_')]
                        except ValueError:
                            self.log("无效的ref_power列表格式", "WARNING")
                            return False
                    elif not isinstance(ref_power, (int, float, str)):
                        self.log("ref_power必须是数字或字符串", "WARNING")
                        return False
                    
                    # 验证极化模式
                    if meta['base_param']['polarization'] not in ['THETA', 'PHI', 'DUAL']:
                        self.log(f"无效的极化模式: {meta['base_param']['polarization']}", "WARNING")
                        return False
                        
                except json.JSONDecodeError:
                    self.log("元数据JSON格式错误", "WARNING")
                    return False
                    
                # 检查数据点数量
                file_size = os.path.getsize(filepath)
                header_size = 4 + 1 + 4 + meta_len
                data_size = file_size - header_size
                
                if data_size % 32 != 0:
                    self.log("数据大小不匹配", "WARNING")
                    return False
                    
                return True
                
        except Exception as e:
            self.log(f"验证二进制文件失败: {str(e)}", "ERROR")
            return False


    def _read_bin_content(self, bin_path: str) -> Optional[Dict]:
        """
        读取已验证的BIN文件内容
        假设文件已经通过验证，直接解析内容
        
        更新内容：
        1. 支持读取多个参考功率和极化模式的数据
        2. 保持与CSV文件相同的数据结构
        """
        try:
            with open(bin_path, 'rb') as f:
                # 跳过已验证的头部
                f.read(4)  # 幻数
                f.read(1)  # 版本
                meta_len = int.from_bytes(f.read(4), 'little')
                meta_json = f.read(meta_len).decode('utf-8')
                meta = json.loads(meta_json)


                # 处理ref_power可能是列表的情况
                if 'base_param' in meta and 'ref_power' in meta['base_param']:
                    if isinstance(meta['base_param']['ref_power'], str) and '_' in meta['base_param']['ref_power']:
                        # 处理类似"-30_-20"的格式
                        meta['base_param']['ref_power'] = [
                            float(p) for p in meta['base_param']['ref_power'].split('_')
                        ]
                    elif isinstance(meta['base_param']['ref_power'], (int, float)):
                        # 单个值转换为列表
                        meta['base_param']['ref_power'] = [float(meta['base_param']['ref_power'])]
                
                # 验证基础参数完整性
                if 'base_param' not in meta:
                    self.log("BIN文件缺少基础参数", "ERROR")
                    return None
                    
                required_params = ['ref_power', 'polarization']
                for param in required_params:
                    if param not in meta['base_param']:
                        self.log(f"BIN文件缺少必需的基础参数: {param}", "ERROR")
                        return None
                
                # 验证极化模式
                if meta['base_param']['polarization'] not in ['THETA', 'PHI', 'DUAL']:
                    self.log(f"BIN文件无效的极化模式: {meta['base_param']['polarization']}", "ERROR")
                    return None
                    
                # 读取数据点
                data_points = []
                while True:
                    freq_bytes = f.read(4)
                    if not freq_bytes:
                        break
                    
                    freq = struct.unpack('f', freq_bytes)[0]
                    data = struct.unpack('7f', f.read(28))  # 7个float32=28字节
                    
                    # 检查是否有额外的参考功率和极化数据
                    extra_data = {}
                    if meta['base_param'].get('ref_power') == 'REFList':
                        # 读取额外的参考功率和极化数据
                        ref_power = struct.unpack('f', f.read(4))[0]
                        polarization = f.read(6).decode('utf-8').strip('\x00')
                        extra_data = {
                            'reference_power': ref_power,
                            'polarization': polarization
                        }
                    
                    data_points.append({
                        'freq': freq,
                        'theta': data[0],
                        'phi': data[1],
                        'horn_gain': data[2],
                        'theta_corrected': data[3],
                        'phi_corrected': data[4],
                        'theta_corrected_vm': data[5],
                        'phi_corrected_vm': data[6],
                        **extra_data
                    })
                
                # 确保元数据包含所有必需字段
                if 'operator' not in meta:
                    meta['operator'] = '未知'
                if 'environment' not in meta:
                    meta['environment'] = (0.0, 0.0)
                if 'freq_params' not in meta:
                    # 从数据点推断频率参数
                    freqs = [p['freq'] for p in data_points]
                    meta['freq_params'] = {
                        'start_ghz': min(freqs),
                        'stop_ghz': max(freqs),
                        'step_ghz': 'FreqList' if len(freqs) > 1 else 0.0,
                        'custom_freqs': sorted(freqs)
                    }
                
                self.current_meta = meta
                self.data_points = data_points
                return {
                    'meta': meta,
                    'data': data_points
                }
                
        except Exception as e:
            self.log(f"读取二进制文件内容失败: {str(e)}", "ERROR")
            return None


    def _validate_csv_file(self, filepath: str) -> bool:
        """
        验证CSV格式校准文件结构是否有效
        不解析具体数据值，只检查文件结构和元数据
        
        更新内容：
        1. 支持验证ref_power为单个值或列表格式
        2. 更新基础参数验证逻辑
        """
        def clean_line(line: str) -> str:
            """清理数据行，移除多余逗号和空格"""
            line = line.strip().strip('"\'')
            line = re.sub(r',+', ',', line)
            line = re.sub(r',$', '', line)
            return line
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                lines = f.readlines()
            
            # 检查文件头
            if not lines or not lines[0].startswith("!RNX Dual-Polarized Feed Calibration Data"):
                self.log("无效的文件头", "WARNING")
                return False
                
            # 定义必需的头字段（更新后）
            REQUIRED_HEADERS = {
                "!Created:", "!Operator:", 
                "!Base Parameters:", "!  Reference_Power:", "!  Polarization:", "!  Distance:",
                "!Equipment:", "!  Signal_Generator:", "!  Spectrum_Analyzer:", "!  Antenna:", 
                "!Environment:", "!Frequency:", "!  Start:", "!  Stop:", 
                "!  Step:", "!  Points:", "!Data Columns:"
            }
            
            # 检查所有必需字段是否存在
            header_lines = [line.strip() for line in lines if line.startswith("!")]
            missing_headers = [h for h in REQUIRED_HEADERS if not any(l.startswith(h) for l in header_lines)]
            
            if missing_headers:
                self.log(f"文件头缺少必需字段: {', '.join(missing_headers)}", "WARNING")
                return False
            
            # 检查数据部分标题行
            data_lines = [clean_line(line) for line in lines if not line.startswith("!") and line.strip()]
            if not data_lines:
                self.log("缺少数据行", "WARNING")
                return False
                
            # 检查结束标记
            if not any(line.startswith("!EndOfData:") for line in lines[-3:]):
                self.log("缺少结束标记", "WARNING")
                return False
                
            if not any(line.startswith("!MD5:") for line in lines[-3:]):
                self.log("缺少MD5校验", "WARNING")
                return False
                
            # 检查基础参数JSON格式
            base_params_lines = [line for line in header_lines if line.startswith("!BaseParams:")]
            if base_params_lines:
                try:
                    # 尝试解析JSON，处理可能的格式问题
                    base_params_str = base_params_lines[0].split(':', 1)[1].strip()

                    # 处理可能的引号问题
                    if base_params_str.startswith('"') and base_params_str.endswith('"'):
                        base_params_str = base_params_str[1:-1]
                    # 尝试解析JSON
                    try:
                        base_params = json.loads(base_params_str)
                    except json.JSONDecodeError:
                        self.log("检查校准参数是否被改动", "ERROR")
                        base_params_str = base_params_str.replace(' "', '"').replace('",', ',').replace('""', '"').replace('}"', '}')
                        base_params = json.loads(base_params_str)
                        self.log("宽松解析成功", "DEBUG")
                    # 验证ref_power格式
                    if 'ref_power' in base_params:
                        ref_power = base_params['ref_power']
                        if isinstance(ref_power, str) and '_' in ref_power:
                            try:
                                ref_power = [float(p) for p in ref_power.split('_')]
                                self.log(f"解析的ref_power列表: {ref_power}", "DEBUG")
                            except ValueError:
                                self.log("无效的ref_power列表格式", "WARNING")
                                return False
                        elif not isinstance(ref_power, (int, float, str)):
                            self.log("ref_power必须是数字或字符串", "WARNING")
                            return False
                    # 验证极化模式
                    if 'polarization' in base_params and base_params['polarization'] not in ['THETA', 'PHI', 'DUAL']:
                        self.log("无效的极化模式", "WARNING")
                        return False
                except json.JSONDecodeError:
                    self.log("基础参数JSON格式错误", "WARNING")
                    return False
                    
            return True
            
        except Exception as e:
            self.log(f"验证CSV文件失败: {str(e)}", "ERROR")
            return False


    def _read_csv_content(self, csv_path: str) -> Optional[Dict]:
        """
        读取已验证的CSV文件内容
        假设文件已经通过验证，直接解析内容
        
        更新内容：
        1. 支持读取多个参考功率和极化模式的数据
        2. 修复字段提取逻辑
        """
        def clean_line(line: str) -> str:
            """清理数据行，移除多余逗号和空格"""
            line = line.strip().strip('"\'')
            line = re.sub(r',+', ',', line)
            line = re.sub(r',$', '', line)
            return line
    
        try:
            with open(csv_path, 'r', encoding='utf-8') as f:
                lines = f.readlines()
            
            # 初始化元数据字典
            meta = {
                'file_format': 'csv',
                'header': [],
                'signal_gen': ('未知', '未知'),
                'power_meter': ('未知', '未知'),
                'antenna': ('未知', '未知'),
                'environment': (0.0, 0.0),
                'freq_params': {
                    'start_ghz': 0.0,
                    'stop_ghz': 0.0,
                    'step_ghz': 0.0
                },
                'base_param': {
                    'ref_power': 0.0,
                    'polarization': 'DUAL',
                    'distance': 1.0
                }
            }
            
            # 解析头部信息
            for line in lines:
                line = clean_line(line).strip()
                if not line:
                    continue
                    
                if line.startswith('!'):
                    meta['header'].append(line)
                    
                    # 解析创建时间
                    if line.startswith('!Created:'):
                        created_str = line.split(':', 1)[1].strip()
                        try:
                            # 尝试解析ISO格式时间
                            meta['created'] = datetime.strptime(
                                created_str.replace('Z', ''), 
                                "%Y%m%dT%H%M%S"
                            ).isoformat()
                        except ValueError:
                            meta['created'] = created_str
                    
                    # 解析操作员
                    elif line.startswith('!Operator:'):
                        meta['operator'] = line.split(':', 1)[1].strip()
                    
                    # 解析信号源信息
                    elif line.startswith('!  Signal_Generator:'):
                        parts = re.split(r'_SN:', line.split(':', 1)[1].strip())
                        model = parts[0].strip()
                        sn = parts[1].strip() if len(parts) > 1 else '未知'
                        meta['signal_gen'] = (model, sn)
                    
                    # 解析功率计信息
                    elif line.startswith('!  Spectrum_Analyzer:'):
                        parts = re.split(r'_SN:', line.split(':', 1)[1].strip())
                        model = parts[0].strip()
                        sn = parts[1].strip() if len(parts) > 1 else '未知'
                        meta['power_meter'] = (model, sn)
                    
                    # 解析天线信息
                    elif line.startswith('!  Antenna:'):
                        parts = re.split(r'_SN:', line.split(':', 1)[1].strip())
                        model = parts[0].strip()
                        sn = parts[1].strip() if len(parts) > 1 else '未知'
                        meta['antenna'] = (model, sn)
                    
                    # 解析环境信息
                    elif line.startswith('!Environment:'):
                        env_parts = line.split(':', 1)[1].strip().split(',')
                        try:
                            temp = float(env_parts[0].replace('C', '').strip())
                            humidity = float(env_parts[1].replace('%RH', '').strip())
                            meta['environment'] = (temp, humidity)
                        except (ValueError, IndexError):
                            meta['environment'] = (0.0, 0.0)
                    
                    # 解析频率参数
                    elif line.startswith('!  Start:'):
                        try:
                            meta['freq_params']['start_ghz'] = float(
                                line.split(':', 1)[1].replace('GHz', '').strip()
                            )
                        except ValueError:
                            meta['freq_params']['start_ghz'] = 0.0
                    
                    elif line.startswith('!  Stop:'):
                        try:
                            meta['freq_params']['stop_ghz'] = float(
                                line.split(':', 1)[1].replace('GHz', '').strip()
                            )
                        except ValueError:
                            meta['freq_params']['stop_ghz'] = 0.0
                    
                    elif line.startswith('!  Step:'):
                        step_str = line.split(':', 1)[1].replace('GHz', '').strip()
                        if step_str == 'FreqList':
                            meta['freq_params']['step_ghz'] = 'FreqList'
                        else:
                            try:
                                meta['freq_params']['step_ghz'] = float(step_str)
                            except ValueError:
                                meta['freq_params']['step_ghz'] = 0.0
                    
                    elif line.startswith('!  Points:'):
                        try:
                            meta['points'] = int(line.split(':', 1)[1].strip())
                        except ValueError:
                            meta['points'] = 0
                    
                    # 解析基础参数
                    elif line.startswith('!BaseParams:'):
                        try:
                            
                            base_params_str = line.split(':', 1)[1].strip()
                            
                            # 处理可能的引号问题
                            if base_params_str.startswith('"') and base_params_str.endswith('"'):
                                base_params_str = base_params_str[1:-1]
                            # 处理可能的双引号转义
                            base_params_str = base_params_str.replace('\\"', '"').replace('""', '"')
                            # 解析JSON
                            
                            try:
                                base_params = json.loads(base_params_str)
                            except json.JSONDecodeError:
                                self.log("检查校准参数是否被改动", "ERROR")
                                base_params_str = base_params_str.replace(' "', '"').replace('",', ',').replace('""', '"').replace('}"', '}')
                                base_params = json.loads(base_params_str)
                                self.log("宽松解析成功", "DEBUG")
                            if isinstance(base_params, dict):
                                # 处理ref_power可能是列表的情况
                                if 'ref_power' in base_params:
                                    if isinstance(base_params['ref_power'], str) and '_' in base_params['ref_power']:
                                        # 处理类似"-30_-20"的格式
                                        base_params['ref_power'] = [
                                            float(p) for p in base_params['ref_power'].split('_')
                                        ]
                                    elif isinstance(base_params['ref_power'], (int, float)):
                                        # 单个值转换为列表
                                        base_params['ref_power'] = [float(base_params['ref_power'])]
                                
                                # 更新基础参数
                                meta['base_param'].update(base_params)
                        except json.JSONDecodeError as e:
                            self.log(f"基础参数JSON解析失败: {str(e)}", "WARNING")
                            self.log("无法解析基础参数，使用默认值", "WARNING")
                    
                    # 解析版本说明
                    elif line.startswith('!VersionNotes:'):
                        meta['version_notes'] = line.split(':', 1)[1].strip()
                    
                    # 解析结束标记
                    elif line.startswith('!EndOfData:'):
                        meta['end_of_data'] = line.split(':', 1)[1].strip()
                    
                    # 解析MD5校验
                    elif line.startswith('!MD5:'):
                        meta['md5'] = line.split(':', 1)[1].strip()
                
                else:
                    break  # 遇到数据行时停止解析头部
            
            # 验证基础参数
            required_base_params = ['ref_power', 'polarization']
            for param in required_base_params:
                if param not in meta['base_param']:
                    self.log(f"缺少必需的基础参数: {param}", "WARNING")
                    return None
                    
            # 使用csv.reader读取数据部分
            data_points = []
            with open(csv_path, 'r', encoding='utf-8') as f:
                reader = csv.reader(f)
                
                # 跳过头部和标题行
                for row in reader:
                    if not row or not row[0]:
                        continue
                    if row[0] == "Frequency" and len(row) >= 8:
                        # 检查是否有额外的列
                        has_ref_power = len(row) > 8 and row[8] == "Reference_Power"
                        has_polarization = len(row) > 9 and row[9] == "Polarization"
                        break  # 找到标题行
                
                # 读取数据行
                for row in reader:
                    if not row or not row[0] or row[0].startswith('!'):
                        continue
                    
                    # 清理行数据
                    cleaned_row = [cell.strip() for cell in row if cell.strip()]
                    
                    if len(cleaned_row) < 8:
                        continue
                    
                    try:
                        freq = float(cleaned_row[0])
                        data_point = {
                            'freq': freq,
                            'theta': float(cleaned_row[1]),
                            'phi': float(cleaned_row[2]),
                            'horn_gain': float(cleaned_row[3]),
                            'theta_corrected': float(cleaned_row[4]),
                            'phi_corrected': float(cleaned_row[5]),
                            'theta_corrected_vm': float(cleaned_row[6]),
                            'phi_corrected_vm': float(cleaned_row[7])
                        }
                        
                        # 如果有额外的参考功率和极化数据
                        if has_ref_power and len(cleaned_row) > 8:
                            data_point['reference_power'] = float(cleaned_row[8])
                        if has_polarization and len(cleaned_row) > 9:
                            data_point['polarization'] = cleaned_row[9]
                        
                        data_points.append(data_point)
                    except ValueError as e:
                        self.log(f"数据行解析失败: {row} - {str(e)}", "WARNING")
                        continue
            
            # 更新实例变量
            self.current_meta = meta
            self.data_points = data_points
            return {
                'meta': meta,
                'data': data_points
            }
            
        except Exception as e:
            self.log(f"读取CSV文件内容失败: {str(e)}", "ERROR")
            return None


    def _calculate_file_hash(self) -> str:
        """计算文件MD5校验值"""
        hash_md5 = hashlib.md5()
        with open(self.active_file, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hash_md5.update(chunk)
        return hash_md5.hexdigest()

    def _archive_file(self, filepath: Optional[str] = None) -> str:
        """将文件移动到归档目录
        :param filepath: 要归档的文件路径，如果为None则使用self.active_file
        :return: 归档后的文件路径
        """
        archive_dir = os.path.join(self.base_dir, "archive")
        os.makedirs(archive_dir, exist_ok=True)
        
        src = filepath if filepath is not None else self.active_file
        if src is None:
            raise ValueError("没有指定要归档的文件")
        
        filename = os.path.basename(src)
        dst = os.path.join(archive_dir, filename)
        
        shutil.move(src, dst)
        return dst

    def _backup_file(self) -> bool:
        """创建备份文件"""
        if not self.active_file:
            return False
            
        backup_dir = os.path.join(self.base_dir, "backup")
        os.makedirs(backup_dir, exist_ok=True)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_file = os.path.join(
            backup_dir, 
            f"backup_{os.path.basename(self.active_file)}_{timestamp}"
        )
        
        try:
            with self._file_lock:
                shutil.copy2(self.active_file, backup_file)
            self.log(f"创建备份: {backup_file}", "INFO")
            return True
        except Exception as e:
            self.log(f"备份失败: {str(e)}", "ERROR")
            return False

    def get_recent_calibrations(self, days: int = 7) -> List[Dict]:
        """
        获取最近校准记录
        
        :param days: 查询最近多少天的记录
        :return: 校准文件信息列表 [{
                'filename': str,
                'path': str,
                'modified': datetime,
                'size': int
            }]
        """
        recent_files = []
        cutoff_time = datetime.now() - datetime.timedelta(days=days)
        
        # 搜索主目录和归档目录
        search_dirs = [self.base_dir, os.path.join(self.base_dir, "archive")]
        
        for search_dir in search_dirs:
            if not os.path.exists(search_dir):
                continue
                
            for root, _, files in os.walk(search_dir):
                for file in files:
                    if file.startswith("RNX_Cal_DualPol_") and file.endswith(".csv"):
                        filepath = os.path.join(root, file)
                        try:
                            mtime = datetime.fromtimestamp(os.path.getmtime(filepath))
                            if mtime > cutoff_time:
                                recent_files.append({
                                    'filename': file,
                                    'path': filepath,
                                    'modified': mtime,
                                    'size': os.path.getsize(filepath),
                                    'is_archived': "archive" in root
                                })
                        except Exception as e:
                            self.log(f"处理文件{file}失败: {str(e)}", "WARNING")
        
        # 按修改时间排序
        recent_files.sort(key=lambda x: x['modified'], reverse=True)
        return recent_files

    def get_version_history(self, filepath: str) -> List[str]:
        """
        获取文件的版本历史
        
        :param filepath: 校准文件路径
        :return: 版本说明列表
        """
        versions = []
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                for line in f:
                    if line.startswith("!VersionNotes:"):
                        versions.append(line.split(":", 1)[1].strip())
        except Exception as e:
            self.log(f"获取版本历史失败: {str(e)}", "ERROR")
        return versions

    def export_to_csv(self, file_path: str, data: Union[List[CalibrationPoint], CalibrationData]):
        """导出校准数据到CSV文件"""
        if isinstance(data, CalibrationData):
            # 处理CalibrationData类型
            df = pd.DataFrame({
                'Frequency(GHz)': data.frequencies,
                'Measured_Theta(dBm)': data.measured_theta,
                'Measured_Phi(dBm)': data.measured_phi,
                'Reference_Power(dBm)': [data.reference_power] * len(data.frequencies),
                'Horn_Gain(dBi)': data.horn_gains,
                'Corrected_Theta(dB)': data.theta_corrected,
                'Corrected_Phi(dB)': data.phi_corrected,
                'Field_Strength_Theta(dBμV/m)': data.theta_corrected_vm,
                'Field_Strength_Phi(dBμV/m)': data.phi_corrected_vm,
                'Distance(m)': [1.0] * len(data.frequencies),  # 假设固定距离
                'Timestamp': [datetime.now().isoformat()] * len(data.frequencies)
            })
        else:
            # 处理原来的List[CalibrationPoint]类型
            df = pd.DataFrame([{
                'Frequency(GHz)': point.freq_hz / 1e9,
                'Measured_Theta(dBm)': point.measured_theta,
                'Measured_Phi(dBm)': point.measured_phi,
                'Reference_Power(dBm)': point.ref_power,
                'Horn_Gain(dBi)': point.horn_gain,
                'Corrected_Theta(dB)': point.measured_theta - point.ref_power + point.horn_gain,
                'Corrected_Phi(dB)': point.measured_phi - point.ref_power + point.horn_gain,
                'Field_Strength_Theta(dBμV/m)': point.theta_corrected_vm,
                'Field_Strength_Phi(dBμV/m)': point.phi_corrected_vm,
                'Distance(m)': point.distance,
                'Timestamp': point.timestamp
            } for point in data])
        
        # 确保目录存在
        Path(file_path).parent.mkdir(parents=True, exist_ok=True)
        df.to_csv(file_path, index=False)

