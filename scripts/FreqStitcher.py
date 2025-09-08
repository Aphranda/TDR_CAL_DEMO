import numpy as np
import struct
import logging
from pathlib import Path
from typing import List, Tuple, Optional

logger = logging.getLogger(__name__)

class BinDataProcessor:
    def __init__(self, sample_rate: float = 100e9):
        """
        初始化数据处理器
        
        Args:
            sample_rate: 采样率 (Hz)，默认为100GHz
        """
        self.sample_rate = sample_rate
        self.frequency_resolution = sample_rate  # 频率分辨率
    
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
    
    def get_frequency_axis(self, data_length: int) -> np.ndarray:
        """
        生成频率轴
        
        Args:
            data_length: 数据长度
            
        Returns:
            频率轴数组 (GHz)
        """
        freq_axis = np.fft.fftfreq(data_length, 1/self.sample_rate)
        return freq_axis / 1e9  # 转换为GHz
    
    def stitch_data(self, data1: np.ndarray, data2: np.ndarray, 
                   crossover_freq: float = 15.0) -> np.ndarray:
        """
        拼接两种数据，在指定频率点进行切换
        
        Args:
            data1: 第一种数据 (用于低频部分)
            data2: 第二种数据 (用于高频部分)
            crossover_freq: 切换频率点 (GHz)
            
        Returns:
            拼接后的数据
        """
        if len(data1) != len(data2):
            raise ValueError("两种数据的长度必须相同")
        
        # 生成频率轴
        freq_axis = self.get_frequency_axis(len(data1))
        
        # 找到切换点的索引
        crossover_idx = np.argmin(np.abs(freq_axis - crossover_freq))
        
        # 创建拼接后的数据
        stitched_data = np.zeros_like(data1, dtype=data1.dtype)
        
        # 低频部分使用data1
        stitched_data[:crossover_idx] = data1[:crossover_idx]
        
        # 高频部分使用data2
        stitched_data[crossover_idx:] = data2[crossover_idx:]
        
        return stitched_data
    
    def process_folder_pair(self, folder1: str, folder2: str, 
                          output_folder: str, data_type: str = 'uint32',
                          byte_order: str = '<', crossover_freq: float = 15.0) -> List[str]:
        """
        处理两个文件夹中的所有bin文件对
        
        Args:
            folder1: 第一种数据文件夹路径
            folder2: 第二种数据文件夹路径
            output_folder: 输出文件夹路径
            data_type: 数据类型
            byte_order: 字节序
            crossover_freq: 切换频率点 (GHz)
            
        Returns:
            输出文件路径列表
        """
        folder1_path = Path(folder1)
        folder2_path = Path(folder2)
        output_path = Path(output_folder)
        
        # 确保输出文件夹存在
        output_path.mkdir(parents=True, exist_ok=True)
        
        # 获取两个文件夹中的所有bin文件
        files1 = sorted(folder1_path.glob('*.bin'))
        files2 = sorted(folder2_path.glob('*.bin'))
        
        if len(files1) != len(files2):
            logger.warning(f"文件夹中文件数量不匹配: {folder1}有{len(files1)}个文件, {folder2}有{len(files2)}个文件")
        
        output_files = []
        
        # 处理每对文件
        for i, (file1, file2) in enumerate(zip(files1, files2)):
            try:
                logger.info(f"处理文件对 {i+1}: {file1.name} 和 {file2.name}")
                
                # 加载数据
                data1 = self.load_binary_data(str(file1), data_type, byte_order)
                data2 = self.load_binary_data(str(file2), data_type, byte_order)
                
                # 拼接数据
                stitched_data = self.stitch_data(data1, data2, crossover_freq)
                
                # 保存结果
                output_file = output_path / f"stitched_{file1.stem}_{file2.stem}.bin"
                stitched_data.tofile(str(output_file))
                
                output_files.append(str(output_file))
                logger.info(f"已保存拼接结果: {output_file}")
                
            except Exception as e:
                logger.error(f"处理文件对 {file1.name} 和 {file2.name} 时出错: {str(e)}")
                continue
        
        return output_files
    
    def visualize_stitching(self, data1: np.ndarray, data2: np.ndarray, 
                          stitched_data: np.ndarray, crossover_freq: float = 15.0):
        """
        可视化拼接结果（需要matplotlib）
        
        Args:
            data1: 第一种数据
            data2: 第二种数据
            stitched_data: 拼接后的数据
            crossover_freq: 切换频率点
        """
        try:
            import matplotlib.pyplot as plt
            
            freq_axis = self.get_frequency_axis(len(data1))
            crossover_idx = np.argmin(np.abs(freq_axis - crossover_freq))
            
            plt.figure(figsize=(12, 8))
            
            # 绘制原始数据和拼接结果
            plt.subplot(2, 1, 1)
            plt.plot(freq_axis, np.abs(data1), 'b-', label='Data 1 (0-50GHz)', alpha=0.7)
            plt.plot(freq_axis, np.abs(data2), 'r-', label='Data 2 (0-50GHz)', alpha=0.7)
            plt.plot(freq_axis, np.abs(stitched_data), 'g-', label='Stitched Data', linewidth=2)
            plt.axvline(x=crossover_freq, color='k', linestyle='--', label=f'Crossover at {crossover_freq}GHz')
            plt.xlabel('Frequency (GHz)')
            plt.ylabel('Amplitude')
            plt.title('Data Stitching Comparison')
            plt.legend()
            plt.grid(True)
            
            # 绘制相位信息
            plt.subplot(2, 1, 2)
            plt.plot(freq_axis, np.angle(data1), 'b-', alpha=0.7)
            plt.plot(freq_axis, np.angle(data2), 'r-', alpha=0.7)
            plt.plot(freq_axis, np.angle(stitched_data), 'g-', linewidth=2)
            plt.axvline(x=crossover_freq, color='k', linestyle='--')
            plt.xlabel('Frequency (GHz)')
            plt.ylabel('Phase (radians)')
            plt.title('Phase Comparison')
            plt.grid(True)
            
            plt.tight_layout()
            plt.show()
            
        except ImportError:
            logger.warning("matplotlib未安装，无法可视化")

# 使用示例
if __name__ == "__main__":
    # 设置日志
    logging.basicConfig(level=logging.INFO)
    
    # 创建处理器实例
    processor = BinDataProcessor(sample_rate=100e9)  # 100GHz采样率
    
    # 处理文件夹中的所有文件
    output_files = processor.process_folder_pair(
        folder1=r"data\results\test\Thru",      # 第一种数据文件夹
        folder2=r"data\results\test\AMP",      # 第二种数据文件夹
        output_folder=r"data\results\test\Output", # 输出文件夹
        data_type='uint32',             # 数据类型
        crossover_freq=15.3            # 15GHz切换点
    )
    
    print(f"处理完成，生成 {len(output_files)} 个文件")
