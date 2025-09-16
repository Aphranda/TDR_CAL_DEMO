# src/app/core/DebugPlotter.py
import matplotlib
matplotlib.use('TkAgg')  # 使用交互式后端
import matplotlib.pyplot as plt
import numpy as np
from typing import Optional, Tuple, List, Dict, Any
import logging
import tempfile
import os
import subprocess
from datetime import datetime
import glob

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
        self.save_dir = save_dir or "scripts\\temp\\test_raw"
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
                   save_data: bool = True) -> str:
        """
        简单的数据绘图，返回图片文件路径
        
        新增功能:
        - 可选保存原始数据到.npy文件
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
                filename = f"debug_plot_{timestamp}"
            
            image_path = os.path.join(self.save_dir, f"{filename}.png")
            
            # 保存图片
            plt.savefig(image_path, dpi=100, bbox_inches='tight')
            plt.close(fig)
            
            # 保存原始数据
            if save_data:
                data_path = os.path.join(self.save_dir, f"{filename}.npy")
                np.save(data_path, data)
                logger.debug(f"原始数据已保存: {data_path}")
            
            # 自动打开图片
            if self.auto_open:
                self._open_image(image_path)
            
            logger.debug(f"调试图片已保存: {image_path}")
            return image_path
            
        except Exception as e:
            logger.error(f"调试绘图失败: {e}")
            return ""
    
    def import_and_plot(self, data_path: str, 
                       title: str = "Imported Data Plot", 
                       xlabel: str = "Sample Points", 
                       ylabel: str = "Amplitude",
                       show_grid: bool = True,
                       figsize: Tuple[int, int] = (10, 6),
                       line_style: str = 'b-',
                       line_width: float = 1.5,
                       alpha: float = 1.0,
                       filename: Optional[str] = None,
                       interactive: bool = True) -> str:
        """
        从文件导入数据并绘图
        
        Args:
            data_path: 数据文件路径(.npy格式)
            interactive: 是否显示交互式图形窗口
            其他参数与simple_plot相同
            
        Returns:
            生成的图片文件路径
        """
        try:
            # 加载数据
            if not os.path.exists(data_path):
                logger.error(f"数据文件不存在: {data_path}")
                return ""
                
            data = np.load(data_path)
            logger.debug(f"已从 {data_path} 加载数据，形状: {data.shape}")
            
            # 生成文件名
            if filename is None:
                base_name = os.path.splitext(os.path.basename(data_path))[0]
                filename = f"imported_plot_{base_name}"
            
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
            
            image_path = os.path.join(self.save_dir, f"{filename}.png")
            
            # 保存图片
            plt.savefig(image_path, dpi=100, bbox_inches='tight')
            
            # 如果要求交互式显示，则显示图形窗口
            if interactive:
                plt.show()
            else:
                plt.close(fig)
            
            # 自动打开图片
            if self.auto_open and not interactive:
                self._open_image(image_path)
            
            logger.debug(f"调试图片已保存: {image_path}")
            return image_path
            
        except Exception as e:
            logger.error(f"导入数据绘图失败: {e}")
            return ""
    
    def import_folder_and_plot(self, folder_path: str, 
                              pattern: str = "*.npy",
                              title_pattern: str = "Data from {}",
                              xlabel: str = "Sample Points", 
                              ylabel: str = "Amplitude",
                              show_grid: bool = True,
                              figsize: Tuple[int, int] = (10, 6),
                              line_style: str = 'b-',
                              line_width: float = 1.5,
                              alpha: float = 1.0,
                              interactive: bool = True) -> List[str]:
        """
        从文件夹导入所有.npy文件并批量绘图
        
        Args:
            folder_path: 文件夹路径
            pattern: 文件匹配模式，默认为*.npy
            title_pattern: 标题模式，{}会被替换为文件名
            interactive: 是否显示交互式图形窗口
            其他参数与simple_plot相同
            
        Returns:
            生成的图片文件路径列表
        """
        try:
            # 检查文件夹是否存在
            if not os.path.exists(folder_path):
                logger.error(f"文件夹不存在: {folder_path}")
                return []
            
            # 获取所有匹配的文件
            search_pattern = os.path.join(folder_path, pattern)
            npy_files = glob.glob(search_pattern)
            
            if not npy_files:
                logger.warning(f"在 {folder_path} 中没有找到 {pattern} 文件")
                return []
            
            logger.info(f"找到 {len(npy_files)} 个 .npy 文件，开始批量绘图...")
            
            # 批量处理文件
            image_paths = []
            for file_path in npy_files:
                # 从文件名生成标题
                file_name = os.path.splitext(os.path.basename(file_path))[0]
                title = title_pattern.format(file_name)
                
                # 绘制图形
                image_path = self.import_and_plot(
                    data_path=file_path,
                    title=title,
                    xlabel=xlabel,
                    ylabel=ylabel,
                    show_grid=show_grid,
                    figsize=figsize,
                    line_style=line_style,
                    line_width=line_width,
                    alpha=alpha,
                    filename=f"batch_plot_{file_name}",
                    interactive=interactive
                )
                
                if image_path:
                    image_paths.append(image_path)
            
            logger.info(f"批量绘图完成，共生成 {len(image_paths)} 张图片")
            return image_paths
            
        except Exception as e:
            logger.error(f"批量导入绘图失败: {e}")
            return []
    
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
                       interactive: bool = True) -> str:
        """
        绘制带边沿标记的图
        
        Args:
            interactive: 是否显示交互式图形窗口
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
        
        # 如果要求交互式显示，则显示图形窗口
        if interactive:
            plt.show()
        else:
            plt.close(fig)
        
        if self.auto_open and not interactive:
            self._open_image(filepath)
        
        return filepath

if __name__ == "__main__":
    # 创建绘图器实例
    plotter = DebugPlotter()
    
    # 测试单个文件导入（交互式显示）
    path = "scripts\\temp\\test_raw\\debug_plot_20250916_093058.npy"
    new_image_path = plotter.import_and_plot(
        path, 
        title="重新绘制的数据", 
        interactive=True
    )
    
    # 测试文件夹批量导入（非交互式，仅保存图片）
    folder_path = "scripts\\temp\\test_raw"
    image_paths = plotter.import_folder_and_plot(
        folder_path, 
        interactive=True
    )
    
    print(f"生成了 {len(image_paths)} 张图片")
