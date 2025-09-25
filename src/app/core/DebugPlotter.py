# src/app/core/DebugPlotter.py
import matplotlib
matplotlib.use('Agg')  # 使用非交互式后端
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from typing import Optional, Tuple, List, Dict, Any, Union
import logging
import tempfile
import os
import subprocess
from datetime import datetime

logger = logging.getLogger(__name__)

class DebugPlotter:
    """独立的调试绘图工具，完全解耦"""
    
    def __init__(self, auto_open: bool = True, save_dir: Optional[str] = None):
        """
        初始化调试绘图器
        
        Args:
            auto_open: 是否自动打开生成的图片
            save_dir: 图片保存目录，None则使用临时目录
        """
        self.auto_open = auto_open
        self.save_dir = save_dir or tempfile.gettempdir()
        self.save_dir = r"scripts\temp\test_raw"
        os.makedirs(self.save_dir, exist_ok=True)
        
    def simple_plot(self, data: np.ndarray, 
                   title: str = "Debug Plot", 
                   xlabel: str = "Sample Points", 
                   ylabel: str = "Amplitude",
                   show_grid: bool = True,
                   figsize: Tuple[int, int] = (10, 6),
                   line_style: str = 'b-',
                   line_width: float = 1.5,
                   alpha: float = 1.0,
                   filename: Optional[str] = None,
                   data_range: Optional[Union[Tuple[int, int], Tuple[float, float]]] = None,
                   x_range: Optional[Union[Tuple[int, int], Tuple[float, float]]] = None,
                   y_range: Optional[Union[Tuple[float, float]]] = None,
                   save_csv: bool = True) -> Dict[str, str]:
        """
        简单的数据绘图，返回包含图片和CSV文件路径的字典
        
        Args:
            data: 要绘制的数据数组
            title: 图表标题
            xlabel: X轴标签
            ylabel: Y轴标签
            show_grid: 是否显示网格
            figsize: 图表尺寸
            line_style: 线条样式
            line_width: 线条宽度
            alpha: 透明度
            filename: 保存文件名（不包含扩展名）
            data_range: 数据范围选择 (start, end) - 可以是索引或百分比
            x_range: X轴显示范围 (xmin, xmax)
            y_range: Y轴显示范围 (ymin, ymax)
            save_csv: 是否保存CSV文件
            
        Returns:
            包含图片和CSV文件路径的字典
        """
        try:
            # 处理数据范围选择
            processed_data = self._process_data_range(data, data_range)
            
            # 生成X轴数据
            x_data = self._generate_x_data(processed_data, data_range, data)
            
            # 保存CSV文件
            csv_filepath = ""
            if save_csv:
                csv_filepath = self._save_csv_data(x_data, processed_data, filename, title, data_range)
            
            # 创建图形
            fig, ax = plt.subplots(figsize=figsize)
            
            # 绘制数据
            ax.plot(x_data, processed_data, line_style, linewidth=line_width, alpha=alpha)
            
            # 设置标题和标签
            ax.set_title(title, fontsize=14)
            ax.set_xlabel(xlabel, fontsize=12)
            ax.set_ylabel(ylabel, fontsize=12)
            
            # 设置坐标轴范围
            if x_range is not None:
                ax.set_xlim(x_range)
            if y_range is not None:
                ax.set_ylim(y_range)
            
            # 显示网格
            if show_grid:
                ax.grid(True, alpha=0.3)
            
            # 添加数据范围信息到标题（如果指定了范围）
            if data_range is not None:
                if isinstance(data_range[0], float) and isinstance(data_range[1], float):
                    # 百分比范围
                    range_info = f" (数据范围: {data_range[0]*100:.1f}%-{data_range[1]*100:.1f}%)"
                else:
                    # 索引范围
                    range_info = f" (数据范围: {data_range[0]}-{data_range[1]})"
                ax.set_title(title + range_info, fontsize=14)
            
            # 生成文件名
            if filename is None:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                filename = f"debug_plot_{timestamp}"
            
            image_filepath = os.path.join(self.save_dir, f"{filename}.png")
            
            # 保存图片
            plt.savefig(image_filepath, dpi=100, bbox_inches='tight')
            plt.close(fig)
            
            # 自动打开图片
            if self.auto_open:
                self._open_image(image_filepath)
            
            logger.debug(f"调试图片已保存: {image_filepath}")
            if save_csv:
                logger.debug(f"CSV数据已保存: {csv_filepath}")
            
            return {
                "image_path": image_filepath,
                "csv_path": csv_filepath,
                "data_points": len(processed_data)
            }
            
        except Exception as e:
            logger.error(f"调试绘图失败: {e}")
            return {"image_path": "", "csv_path": "", "data_points": 0}
    
    def _save_csv_data(self, x_data: np.ndarray, y_data: np.ndarray, 
                      filename: Optional[str], title: str, 
                      data_range: Optional[Union[Tuple[int, int], Tuple[float, float]]]) -> str:
        """
        保存数据到CSV文件
        
        Args:
            x_data: X轴数据
            y_data: Y轴数据
            filename: 文件名（不包含扩展名）
            title: 图表标题
            data_range: 数据范围信息
            
        Returns:
            CSV文件路径
        """
        try:
            # 生成文件名
            if filename is None:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                filename = f"debug_plot_{timestamp}"
            
            csv_filepath = os.path.join(self.save_dir, f"{filename}.csv")
            
            # 创建DataFrame
            df = pd.DataFrame({
                'Sample_Point': x_data,
                'Amplitude': y_data
            })
            
            # 添加元数据注释
            metadata = {
                'Title': title,
                'Data_Points': len(y_data),
                'Timestamp': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }
            
            if data_range is not None:
                if isinstance(data_range[0], float) and isinstance(data_range[1], float):
                    metadata['Data_Range_Percent'] = f"{data_range[0]*100:.1f}%-{data_range[1]*100:.1f}%"
                else:
                    metadata['Data_Range_Index'] = f"{data_range[0]}-{data_range[1]}"
            
            # 保存CSV文件，包含元数据注释
            with open(csv_filepath, 'w', encoding='utf-8') as f:
                # 写入元数据注释
                f.write("# Debug Plotter Data Export\n")
                for key, value in metadata.items():
                    f.write(f"# {key}: {value}\n")
                f.write("# Columns: Sample_Point, Amplitude\n")
                f.write("# \n")
                
                # 写入数据 - 修复：不使用已弃用的line_terminator参数
                # 先写入列名
                f.write("Sample_Point,Amplitude\n")
                
                # 然后逐行写入数据
                for i in range(len(x_data)):
                    f.write(f"{x_data[i]},{y_data[i]}\n")
            
            logger.debug(f"CSV数据已保存: {csv_filepath}")
            
            # 验证文件是否成功写入
            if os.path.exists(csv_filepath):
                file_size = os.path.getsize(csv_filepath)
                logger.debug(f"CSV文件大小: {file_size} 字节")
                
                # 读取文件内容进行验证
                with open(csv_filepath, 'r', encoding='utf-8') as f:
                    lines = f.readlines()
                    logger.debug(f"CSV文件行数: {len(lines)}")
                    
                    # 检查是否有数据行（跳过注释行）
                    data_lines = [line for line in lines if not line.startswith('#') and line.strip()]
                    logger.debug(f"数据行数: {len(data_lines)}")
            
            return csv_filepath
            
        except Exception as e:
            logger.error(f"保存CSV文件失败: {e}")
            return ""
    
    def _process_data_range(self, data: np.ndarray, data_range: Optional[Union[Tuple[int, int], Tuple[float, float]]]) -> np.ndarray:
        """
        根据数据范围选择处理数据
        
        Args:
            data: 原始数据
            data_range: 数据范围 (start, end)
            
        Returns:
            处理后的数据片段
        """
        if data_range is None:
            return data
        
        start, end = data_range
        
        # 处理百分比范围
        if isinstance(start, float) and isinstance(end, float):
            if 0 <= start <= 1 and 0 <= end <= 1 and start < end:
                start_idx = int(len(data) * start)
                end_idx = int(len(data) * end)
                return data[start_idx:end_idx]
            else:
                logger.warning(f"无效的百分比范围: ({start}, {end})，使用全部数据")
                return data
        
        # 处理索引范围
        elif isinstance(start, int) and isinstance(end, int):
            if 0 <= start < len(data) and 0 <= end <= len(data) and start < end:
                return data[start:end]
            else:
                logger.warning(f"无效的索引范围: ({start}, {end})，数据长度: {len(data)}，使用全部数据")
                return data
        
        # 无效范围类型
        else:
            logger.warning(f"无效的范围类型: {type(start)}, {type(end)}，使用全部数据")
            return data
    
    def _generate_x_data(self, processed_data: np.ndarray, 
                        data_range: Optional[Union[Tuple[int, int], Tuple[float, float]]],
                        original_data: np.ndarray) -> np.ndarray:
        """
        生成X轴数据，考虑数据范围选择
        
        Args:
            processed_data: 处理后的数据
            data_range: 数据范围
            original_data: 原始数据
            
        Returns:
            X轴数据
        """
        if data_range is None:
            return np.arange(len(processed_data))
        
        start, end = data_range
        
        # 百分比范围
        if isinstance(start, float) and isinstance(end, float):
            start_idx = int(len(original_data) * start)
            return np.arange(start_idx, start_idx + len(processed_data))
        
        # 索引范围
        elif isinstance(start, int) and isinstance(end, int):
            return np.arange(start, start + len(processed_data))
        
        # 默认情况
        else:
            return np.arange(len(processed_data))
    
    def _open_image(self, filepath: str):
        """打开图片文件"""
        try:
            if os.name == 'nt':  # Windows
                os.startfile(filepath)
            elif os.name == 'posix':  # macOS or Linux
                if 'darwin' in os.sys.platform:  # macOS
                    subprocess.run(['open', filepath])
                else:  # Linux
                    subprocess.run(['xdg-open', filepath])
        except Exception as e:
            logger.warning(f"无法自动打开图片: {e}")

    def plot_with_edges(self, data: np.ndarray, edge_positions: List[int],
                       titles: Optional[List[str]] = None,
                       colors: Optional[List[str]] = None,
                       data_range: Optional[Union[Tuple[int, int], Tuple[float, float]]] = None,
                       save_csv: bool = True) -> Dict[str, str]:
        """
        绘制带边沿标记的图，支持数据范围选择
        
        Returns:
            包含图片和CSV文件路径的字典
        """
        # 处理数据范围
        processed_data = self._process_data_range(data, data_range)
        x_data = self._generate_x_data(processed_data, data_range, data)
        
        # 调整边沿位置到新的数据范围
        adjusted_edges = []
        if data_range is not None:
            start, end = data_range
            if isinstance(start, float) and isinstance(end, float):
                start_idx = int(len(data) * start)
            elif isinstance(start, int) and isinstance(end, int):
                start_idx = start
            else:
                start_idx = 0
            
            for edge in edge_positions:
                if start_idx <= edge < start_idx + len(processed_data):
                    adjusted_edges.append(edge - start_idx)
        else:
            adjusted_edges = [edge for edge in edge_positions if 0 <= edge < len(processed_data)]
        
        # 保存CSV文件（包含边沿标记信息）
        csv_filepath = ""
        if save_csv:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"edges_plot_{timestamp}"
            csv_filepath = self._save_edges_csv(x_data, processed_data, adjusted_edges, filename, data_range)
        
        fig, ax = plt.subplots(figsize=(12, 6))
        
        # 绘制原始数据
        ax.plot(x_data, processed_data, 'b-', linewidth=1.5, alpha=0.8, label='Data')
        
        # 标记边沿位置
        colors = colors or ['red', 'green', 'orange', 'purple']
        titles = titles or [f'Edge {i+1}' for i in range(len(adjusted_edges))]
        
        for i, pos in enumerate(adjusted_edges):
            if 0 <= pos < len(processed_data):
                color = colors[i % len(colors)]
                ax.axvline(x=x_data[pos], color=color, linestyle='--', 
                          alpha=0.7, label=titles[i])
                ax.plot(x_data[pos], processed_data[pos], 'o', color=color, markersize=8)
        
        # 添加数据范围信息到标题
        title_suffix = ""
        if data_range is not None:
            if isinstance(data_range[0], float) and isinstance(data_range[1], float):
                title_suffix = f" (数据范围: {data_range[0]*100:.1f}%-{data_range[1]*100:.1f}%)"
            else:
                title_suffix = f" (数据范围: {data_range[0]}-{data_range[1]})"
        
        ax.set_title('Data with Edge Markers' + title_suffix, fontsize=14)
        ax.set_xlabel('Sample Points', fontsize=12)
        ax.set_ylabel('Amplitude', fontsize=12)
        ax.legend()
        ax.grid(True, alpha=0.3)
        
        plt.tight_layout()
        
        # 保存图片
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        image_filepath = os.path.join(self.save_dir, f"edges_plot_{timestamp}.png")
        plt.savefig(image_filepath, dpi=100, bbox_inches='tight')
        plt.close(fig)
        
        if self.auto_open:
            self._open_image(image_filepath)
        
        return {
            "image_path": image_filepath,
            "csv_path": csv_filepath,
            "data_points": len(processed_data),
            "edges_count": len(adjusted_edges)
        }
    
    def _save_edges_csv(self, x_data: np.ndarray, y_data: np.ndarray, 
                       edges: List[int], filename: str,
                       data_range: Optional[Union[Tuple[int, int], Tuple[float, float]]]) -> str:
        """
        保存带边沿标记的数据到CSV文件
        """
        try:
            csv_filepath = os.path.join(self.save_dir, f"{filename}.csv")
            
            # 创建DataFrame
            df = pd.DataFrame({
                'Sample_Point': x_data,
                'Amplitude': y_data,
                'Is_Edge': [1 if i in edges else 0 for i in range(len(x_data))]
            })
            
            # 添加边沿详细信息
            edge_details = []
            for i, edge_pos in enumerate(edges):
                if 0 <= edge_pos < len(x_data):
                    edge_details.append({
                        'Edge_Index': i,
                        'Sample_Point': x_data[edge_pos],
                        'Amplitude': y_data[edge_pos],
                        'Position_In_Data': edge_pos
                    })
            
            # 保存CSV文件
            with open(csv_filepath, 'w', encoding='utf-8') as f:
                # 写入元数据
                f.write("# Edge Detection Data Export\n")
                f.write(f"# Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                f.write(f"# Total_Edges: {len(edges)}\n")
                if data_range is not None:
                    if isinstance(data_range[0], float) and isinstance(data_range[1], float):
                        f.write(f"# Data_Range_Percent: {data_range[0]*100:.1f}%-{data_range[1]*100:.1f}%\n")
                    else:
                        f.write(f"# Data_Range_Index: {data_range[0]}-{data_range[1]}\n")
                
                # 写入边沿详细信息
                f.write("# Edge Details:\n")
                for edge in edge_details:
                    f.write(f"# Edge_{edge['Edge_Index']}: Sample={edge['Sample_Point']}, Amplitude={edge['Amplitude']:.6f}\n")
                
                f.write("# Columns: Sample_Point, Amplitude, Is_Edge\n")
                f.write("# \n")
                
                # 写入数据 - 修复：不使用已弃用的line_terminator参数
                # 先写入列名
                f.write("Sample_Point,Amplitude,Is_Edge\n")
                
                # 然后逐行写入数据
                for i in range(len(x_data)):
                    is_edge = 1 if i in edges else 0
                    f.write(f"{x_data[i]},{y_data[i]},{is_edge}\n")
            
            return csv_filepath
            
        except Exception as e:
            logger.error(f"保存边沿CSV文件失败: {e}")
            return ""

    # 其他方法保持不变...

# 使用示例
if __name__ == "__main__":
    # 创建测试数据
    test_data = np.random.randn(1000)
    
    # 创建绘图器
    plotter = DebugPlotter(auto_open=False)
    
    # 绘制并保存CSV
    result = plotter.simple_plot(
        data=test_data,
        title="测试数据",
        data_range=(0.1, 0.5),  # 10%-50%的数据范围
        save_csv=True
    )
    
    print(f"图片保存路径: {result['image_path']}")
    print(f"CSV保存路径: {result['csv_path']}")
    print(f"数据点数: {result['data_points']}")
    
    # 验证CSV文件内容
    if result['csv_path'] and os.path.exists(result['csv_path']):
        with open(result['csv_path'], 'r', encoding='utf-8') as f:
            content = f.read()
            print(f"CSV文件内容预览（前500字符）:")
            print(content[:500])
