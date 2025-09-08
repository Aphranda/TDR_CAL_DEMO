# src/app/core/DebugPlotter.py
import matplotlib
matplotlib.use('Agg')  # 使用非交互式后端
import matplotlib.pyplot as plt
import numpy as np
from typing import Optional, Tuple, List, Dict, Any
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
                   filename: Optional[str] = None) -> str:
        """
        简单的数据绘图，返回图片文件路径
        """
        try:
            # 创建图形
            fig, ax = plt.subplots(figsize=figsize)
            
            # 绘制数据
            ax.plot(data, line_style, linewidth=line_width, alpha=alpha)
            
            # 设置标题和标签
            ax.set_title(title, fontsize=14)
            ax.set_xlabel(xlabel, fontsize=12)
            ax.set_ylabel(ylabel, fontsize=12)
            
            # 显示网格
            if show_grid:
                ax.grid(True, alpha=0.3)
            
            plt.tight_layout()
            
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
                       colors: Optional[List[str]] = None) -> str:
        """
        绘制带边沿标记的图
        """
        fig, ax = plt.subplots(figsize=(12, 6))
        
        # 绘制原始数据
        ax.plot(data, 'b-', linewidth=1.5, alpha=0.8, label='Data')
        
        # 标记边沿位置
        colors = colors or ['red', 'green', 'orange', 'purple']
        titles = titles or [f'Edge {i+1}' for i in range(len(edge_positions))]
        
        for i, pos in enumerate(edge_positions):
            if 0 <= pos < len(data):
                color = colors[i % len(colors)]
                ax.axvline(x=pos, color=color, linestyle='--', 
                          alpha=0.7, label=titles[i])
                ax.plot(pos, data[pos], 'o', color=color, markersize=8)
        
        ax.set_title('Data with Edge Markers', fontsize=14)
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


    

