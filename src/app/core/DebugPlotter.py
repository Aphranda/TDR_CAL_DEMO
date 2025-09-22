# src/app/core/DebugPlotter.py
import matplotlib
matplotlib.use('Agg')  # 使用非交互式后端
import matplotlib.pyplot as plt
import numpy as np
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
                   y_range: Optional[Union[Tuple[float, float]]] = None) -> str:
        """
        简单的数据绘图，返回图片文件路径
        
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
            filename: 保存文件名
            data_range: 数据范围选择 (start, end) - 可以是索引或百分比
            x_range: X轴显示范围 (xmin, xmax)
            y_range: Y轴显示范围 (ymin, ymax)
        """
        try:
            # 处理数据范围选择
            processed_data = self._process_data_range(data, data_range)
            
            # 创建图形
            fig, ax = plt.subplots(figsize=figsize)
            
            # 生成X轴数据
            x_data = self._generate_x_data(processed_data, data_range, data)
            
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
                filename = f"debug_plot_{timestamp}.png"
            
            filepath = os.path.join(self.save_dir, filename)
            
            # 保存图片
            plt.savefig(filepath, dpi=100, bbox_inches='tight')
            plt.close(fig)
            
            # 自动打开图片
            if self.auto_open:
                self._open_image(filepath)
            
            logger.debug(f"调试图片已保存: {filepath}")
            return filepath
            
        except Exception as e:
            logger.error(f"调试绘图失败: {e}")
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
                       data_range: Optional[Union[Tuple[int, int], Tuple[float, float]]] = None) -> str:
        """
        绘制带边沿标记的图，支持数据范围选择
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
        filepath = os.path.join(self.save_dir, f"edges_plot_{timestamp}.png")
        plt.savefig(filepath, dpi=100, bbox_inches='tight')
        plt.close(fig)
        
        if self.auto_open:
            self._open_image(filepath)
        
        return filepath

    # 新增方法：快速绘制数据范围的便捷方法
    def plot_range(self, data: np.ndarray, 
                  start: Union[int, float], 
                  end: Union[int, float],
                  title: str = "Data Range Plot",
                  **kwargs) -> str:
        """
        快速绘制指定范围的数据
        
        Args:
            data: 数据数组
            start: 起始位置（索引或百分比）
            end: 结束位置（索引或百分比）
            title: 图表标题
            **kwargs: 其他参数传递给simple_plot
            
        Returns:
            图片文件路径
        """
        return self.simple_plot(data, title=title, data_range=(start, end), **kwargs)

    # 新增方法：绘制多个数据范围
    def plot_multiple_ranges(self, data: np.ndarray, 
                            ranges: List[Tuple[Union[int, float], Union[int, float]]],
                            titles: Optional[List[str]] = None,
                            colors: Optional[List[str]] = None,
                            figsize: Tuple[int, int] = (12, 8)) -> str:
        """
        在同一图表中绘制多个数据范围
        
        Args:
            data: 数据数组
            ranges: 范围列表，每个范围是(start, end)
            titles: 每个范围的标题
            colors: 每个范围的颜色
            figsize: 图表尺寸
            
        Returns:
            图片文件路径
        """
        try:
            fig, ax = plt.subplots(figsize=figsize)
            
            colors = colors or ['blue', 'red', 'green', 'orange', 'purple', 'brown']
            titles = titles or [f'Range {i+1}' for i in range(len(ranges))]
            
            for i, (start, end) in enumerate(ranges):
                # 处理数据范围
                processed_data = self._process_data_range(data, (start, end))
                x_data = self._generate_x_data(processed_data, (start, end), data)
                
                color = colors[i % len(colors)]
                label = titles[i]
                
                # 添加范围信息到标签
                if isinstance(start, float) and isinstance(end, float):
                    label += f" ({start*100:.1f}%-{end*100:.1f}%)"
                else:
                    label += f" ({start}-{end})"
                
                ax.plot(x_data, processed_data, color=color, linewidth=1.5, 
                       alpha=0.7, label=label)
            
            ax.set_title('Multiple Data Ranges', fontsize=14)
            ax.set_xlabel('Sample Points', fontsize=12)
            ax.set_ylabel('Amplitude', fontsize=12)
            ax.legend()
            ax.grid(True, alpha=0.3)
            
            plt.tight_layout()
            
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filepath = os.path.join(self.save_dir, f"multi_range_plot_{timestamp}.png")
            plt.savefig(filepath, dpi=100, bbox_inches='tight')
            plt.close(fig)
            
            if self.auto_open:
                self._open_image(filepath)
            
            return filepath
            
        except Exception as e:
            logger.error(f"多范围绘图失败: {e}")
            return ""
