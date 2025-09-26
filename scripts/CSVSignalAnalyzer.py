# scripts/simple_csv_plotter.py
import matplotlib
matplotlib.use('TkAgg')  # 使用TkAgg后端
import matplotlib.pyplot as plt
import pandas as pd
import numpy as np
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
import os
import sys

class SimpleCSVPlotter:
    """简单的CSV文件绘图器"""
    
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("CSV简单绘图器")
        self.root.geometry("800x600")
        
        self.data = None
        self.current_file = None
        
        self.setup_ui()
    
    def setup_ui(self):
        """设置用户界面"""
        # 主框架
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # 文件选择区域
        file_frame = ttk.LabelFrame(main_frame, text="文件选择", padding="5")
        file_frame.grid(row=0, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=5)
        
        self.file_label = ttk.Label(file_frame, text="未选择文件")
        self.file_label.grid(row=0, column=0, sticky=(tk.W, tk.E), padx=5)
        
        ttk.Button(file_frame, text="选择CSV文件", 
                  command=self.load_csv_file).grid(row=0, column=1, padx=5)
        
        # 绘图选项区域
        options_frame = ttk.LabelFrame(main_frame, text="绘图选项", padding="5")
        options_frame.grid(row=1, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=5)
        
        ttk.Label(options_frame, text="标题:").grid(row=0, column=0, sticky=tk.W, padx=5)
        self.title_entry = ttk.Entry(options_frame, width=30)
        self.title_entry.grid(row=0, column=1, padx=5)
        self.title_entry.insert(0, "CSV数据图")
        
        ttk.Label(options_frame, text="X轴标签:").grid(row=1, column=0, sticky=tk.W, padx=5)
        self.xlabel_entry = ttk.Entry(options_frame, width=30)
        self.xlabel_entry.grid(row=1, column=1, padx=5)
        self.xlabel_entry.insert(0, "样本点")
        
        ttk.Label(options_frame, text="Y轴标签:").grid(row=2, column=0, sticky=tk.W, padx=5)
        self.ylabel_entry = ttk.Entry(options_frame, width=30)
        self.ylabel_entry.grid(row=2, column=1, padx=5)
        self.ylabel_entry.insert(0, "幅度")
        
        # 按钮区域
        button_frame = ttk.Frame(main_frame)
        button_frame.grid(row=2, column=0, columnspan=2, pady=10)
        
        ttk.Button(button_frame, text="绘制图形", 
                  command=self.plot_data).grid(row=0, column=0, padx=5)
        
        ttk.Button(button_frame, text="保存图片", 
                  command=self.save_plot).grid(row=0, column=1, padx=5)
        
        ttk.Button(button_frame, text="显示统计", 
                  command=self.show_stats).grid(row=0, column=2, padx=5)
        
        ttk.Button(button_frame, text="检测上升沿", 
                  command=self.detect_rising_edges).grid(row=0, column=3, padx=5)
        
        ttk.Button(button_frame, text="清除图形", 
                  command=self.clear_plot).grid(row=0, column=4, padx=5)
        
        # 配置权重
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        main_frame.columnconfigure(0, weight=1)
        main_frame.rowconfigure(3, weight=1)
    
    def detect_rising_edges(self):
        """检测并打印上升沿位置及间距"""
        if self.data is None:
            messagebox.showwarning("警告", "请先选择CSV文件")
            return
        
        try:
            # 获取数据列
            columns = list(self.data.columns)
            
            # 找出数字列（排除可能的索引列）
            numeric_columns = []
            for col in columns:
                if self.data[col].dtype in [np.int64, np.float64]:
                    numeric_columns.append(col)
            
            if not numeric_columns:
                messagebox.showwarning("警告", "未找到数字数据列")
                return
            
            # 创建新窗口显示上升沿信息
            edge_window = tk.Toplevel(self.root)
            edge_window.title("上升沿检测结果")
            edge_window.geometry("700x500")
            
            # 创建文本框和滚动条
            text_frame = ttk.Frame(edge_window, padding="10")
            text_frame.pack(fill=tk.BOTH, expand=True)
            
            text_widget = tk.Text(text_frame, wrap=tk.WORD)
            scrollbar = ttk.Scrollbar(text_frame, orient=tk.VERTICAL, command=text_widget.yview)
            text_widget.configure(yscrollcommand=scrollbar.set)
            
            text_widget.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
            scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
            
            # 检测每个数字列的上升沿
            result_text = "上升沿检测结果:\n\n"
            
            for col in numeric_columns:
                result_text += f"列 '{col}' 的上升沿分析:\n"
                result_text += "="*50 + "\n"
                
                # 检测上升沿
                rising_edges = self._find_rising_edges(self.data[col])
                
                if len(rising_edges) > 0:
                    # 计算上升沿间距
                    edge_distances = self._calculate_edge_distances(rising_edges)
                    
                    # 显示每个上升沿的详细信息
                    for i, edge_idx in enumerate(rising_edges):
                        # 获取上升沿前后的值
                        prev_val = self.data[col].iloc[edge_idx-1] if edge_idx > 0 else "N/A"
                        curr_val = self.data[col].iloc[edge_idx]
                        
                        result_text += f"上升沿 {i+1}: 位置 {edge_idx}, "
                        result_text += f"值变化 {prev_val} -> {curr_val}\n"
                    
                    result_text += "\n上升沿间距分析:\n"
                    result_text += "-"*30 + "\n"
                    
                    # 显示间距信息
                    total_distance = 0
                    valid_distances = []
                    
                    for i, distance in enumerate(edge_distances):
                        if distance is not None:
                            result_text += f"间距 {i+1}: 上升沿 {i+1} 到 {i+2} 的距离 = {distance} 个样本点\n"
                            total_distance += distance
                            valid_distances.append(distance)
                    
                    # 显示统计信息
                    if valid_distances:
                        result_text += "\n间距统计:\n"
                        result_text += f"总间距数: {len(valid_distances)}\n"
                        result_text += f"平均间距: {np.mean(valid_distances):.2f} 个样本点\n"
                        result_text += f"最大间距: {np.max(valid_distances)} 个样本点\n"
                        result_text += f"最小间距: {np.min(valid_distances)} 个样本点\n"
                        result_text += f"间距标准差: {np.std(valid_distances):.2f} 个样本点\n"
                    
                    result_text += f"\n总共找到 {len(rising_edges)} 个上升沿\n\n"
                else:
                    result_text += "未找到上升沿\n\n"
                
                result_text += "\n" + "="*50 + "\n\n"
            
            # 在数据中添加上升沿标记（用于绘图）
            self._mark_edges_in_data(numeric_columns[0])  # 默认标记第一列
            
            text_widget.insert(tk.END, result_text)
            text_widget.config(state=tk.DISABLED)  # 设置为只读
            
            # 添加按钮框架
            button_frame = ttk.Frame(edge_window)
            button_frame.pack(pady=10)
            
            # 添加复制按钮
            copy_button = ttk.Button(button_frame, text="复制结果", 
                                   command=lambda: self._copy_to_clipboard(result_text))
            copy_button.grid(row=0, column=0, padx=5)
            
            # 添加保存按钮
            save_button = ttk.Button(button_frame, text="保存结果", 
                                   command=lambda: self._save_edge_analysis(result_text))
            save_button.grid(row=0, column=1, padx=5)
            
        except Exception as e:
            messagebox.showerror("错误", f"检测上升沿失败: {e}")
    
    def _find_rising_edges(self, data_series):
        """在数据序列中查找上升沿位置"""
        rising_edges = []
        
        for i in range(1, len(data_series)):
            # 检测从0到1的跳变
            if data_series.iloc[i-1] == 0 and data_series.iloc[i] == 1:
                rising_edges.append(i)
        
        return rising_edges
    
    def _calculate_edge_distances(self, rising_edges):
        """计算相邻上升沿之间的距离"""
        distances = []
        
        if len(rising_edges) < 2:
            return distances
        
        for i in range(len(rising_edges) - 1):
            distance = rising_edges[i + 1] - rising_edges[i]
            distances.append(distance)
        
        return distances
    
    def _mark_edges_in_data(self, column_name):
        """在数据中标记上升沿位置"""
        if 'Is_Edge' in self.data.columns:
            self.data = self.data.drop('Is_Edge', axis=1)
        
        # 检测上升沿
        rising_edges = self._find_rising_edges(self.data[column_name])
        
        # 创建边缘标记列
        self.data['Is_Edge'] = 0
        for edge_idx in rising_edges:
            self.data.at[edge_idx, 'Is_Edge'] = 1
    
    def _copy_to_clipboard(self, text):
        """复制文本到剪贴板"""
        self.root.clipboard_clear()
        self.root.clipboard_append(text)
        messagebox.showinfo("成功", "结果已复制到剪贴板")
    
    def _save_edge_analysis(self, text):
        """保存上升沿分析结果到文件"""
        if self.current_file is None:
            messagebox.showwarning("警告", "没有文件可参考保存路径")
            return
        
        filepath = filedialog.asksaveasfilename(
            title="保存上升沿分析结果",
            defaultextension=".txt",
            filetypes=[("Text files", "*.txt"), ("All files", "*.*")],
            initialfile=f"{os.path.splitext(os.path.basename(self.current_file))[0]}_edge_analysis.txt"
        )
        
        if filepath:
            try:
                with open(filepath, 'w', encoding='utf-8') as f:
                    f.write(text)
                messagebox.showinfo("成功", f"分析结果已保存到:\n{filepath}")
            except Exception as e:
                messagebox.showerror("错误", f"保存文件失败: {e}")
    
    def load_csv_file(self):
        """加载CSV文件"""
        filepath = filedialog.askopenfilename(
            title="选择CSV文件",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")]
        )
        
        if filepath:
            try:
                # 读取数据（跳过注释行）
                self.data = pd.read_csv(filepath, comment='#')
                self.current_file = filepath
                
                # 更新文件标签
                filename = os.path.basename(filepath)
                self.file_label.config(text=filename)
                
                # 自动设置标题
                if 'Title' in self._parse_metadata(filepath):
                    metadata = self._parse_metadata(filepath)
                    self.title_entry.delete(0, tk.END)
                    self.title_entry.insert(0, metadata.get('Title', 'CSV数据图'))
                
                messagebox.showinfo("成功", f"成功加载文件: {filename}\n数据形状: {self.data.shape}")
                
            except Exception as e:
                messagebox.showerror("错误", f"加载CSV文件失败: {e}")
    
    def _parse_metadata(self, filepath):
        """解析CSV文件中的元数据注释"""
        metadata = {}
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                lines = f.readlines()
            
            for line in lines:
                line = line.strip()
                if line.startswith('#'):
                    content = line[1:].strip()
                    if ':' in content:
                        key, value = content.split(':', 1)
                        metadata[key.strip()] = value.strip()
                else:
                    break
                    
        except Exception as e:
            print(f"解析元数据失败: {e}")
            
        return metadata
    
    def plot_data(self):
        """绘制数据"""
        if self.data is None:
            messagebox.showwarning("警告", "请先选择CSV文件")
            return
        
        try:
            # 创建图形
            plt.figure(figsize=(10, 6))
            
            # 获取数据列
            columns = list(self.data.columns)
            x_col = columns[0] if 'Sample_Point' in columns else columns[0]
            y_cols = [col for col in columns if col != x_col and col != 'Is_Edge']
            
            # 绘制数据
            colors = ['blue', 'red', 'green', 'orange', 'purple']
            for i, y_col in enumerate(y_cols):
                color = colors[i % len(colors)]
                plt.plot(self.data[x_col], self.data[y_col], 
                        color=color, linewidth=1.5, label=y_col)
            
            # 如果有边沿标记，特殊处理
            if 'Is_Edge' in columns:
                edge_points = self.data[self.data['Is_Edge'] == 1]
                if not edge_points.empty:
                    plt.scatter(edge_points[x_col], edge_points[y_cols[0]], 
                               color='red', s=50, zorder=5, label='边沿点')
            
            # 设置标题和标签
            plt.title(self.title_entry.get(), fontsize=14)
            plt.xlabel(self.xlabel_entry.get(), fontsize=12)
            plt.ylabel(self.ylabel_entry.get(), fontsize=12)
            
            # 添加图例和网格
            plt.legend()
            plt.grid(True, alpha=0.3)
            
            # 调整布局并显示
            plt.tight_layout()
            plt.show()
            
        except Exception as e:
            messagebox.showerror("错误", f"绘图失败: {e}")
    
    def save_plot(self):
        """保存当前图形为图片"""
        if self.data is None:
            messagebox.showwarning("警告", "没有数据可保存")
            return
        
        filepath = filedialog.asksaveasfilename(
            title="保存图片",
            defaultextension=".png",
            filetypes=[("PNG files", "*.png"), ("PDF files", "*.pdf"), ("All files", "*.*")]
        )
        
        if filepath:
            try:
                # 重新绘制并保存
                plt.figure(figsize=(10, 6))
                
                columns = list(self.data.columns)
                x_col = columns[0] if 'Sample_Point' in columns else columns[0]
                y_cols = [col for col in columns if col != x_col and col != 'Is_Edge']
                
                colors = ['blue', 'red', 'green', 'orange', 'purple']
                for i, y_col in enumerate(y_cols):
                    color = colors[i % len(colors)]
                    plt.plot(self.data[x_col], self.data[y_col], 
                            color=color, linewidth=1.5, label=y_col)
                
                if 'Is_Edge' in columns:
                    edge_points = self.data[self.data['Is_Edge'] == 1]
                    if not edge_points.empty:
                        plt.scatter(edge_points[x_col], edge_points[y_cols[0]], 
                                   color='red', s=50, zorder=5, label='边沿点')
                
                plt.title(self.title_entry.get(), fontsize=14)
                plt.xlabel(self.xlabel_entry.get(), fontsize=12)
                plt.ylabel(self.ylabel_entry.get(), fontsize=12)
                plt.legend()
                plt.grid(True, alpha=0.3)
                plt.tight_layout()
                
                plt.savefig(filepath, dpi=150, bbox_inches='tight')
                plt.close()
                
                messagebox.showinfo("成功", f"图片已保存到:\n{filepath}")
                
            except Exception as e:
                messagebox.showerror("错误", f"保存图片失败: {e}")
    
    def show_stats(self):
        """显示数据统计信息"""
        if self.data is None:
            messagebox.showwarning("警告", "没有数据可统计")
            return
        
        # 创建新窗口显示统计信息
        stats_window = tk.Toplevel(self.root)
        stats_window.title("数据统计信息")
        stats_window.geometry("500x400")
        
        # 创建文本框显示统计信息
        text_frame = ttk.Frame(stats_window, padding="10")
        text_frame.pack(fill=tk.BOTH, expand=True)
        
        text_widget = tk.Text(text_frame, wrap=tk.WORD)
        scrollbar = ttk.Scrollbar(text_frame, orient=tk.VERTICAL, command=text_widget.yview)
        text_widget.configure(yscrollcommand=scrollbar.set)
        

        text_widget.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # 添加统计信息
        stats_text = f"文件: {os.path.basename(self.current_file)}\n"
        stats_text += f"数据形状: {self.data.shape}\n\n"
        stats_text += "统计信息:\n"
        stats_text += str(self.data.describe())
        
        text_widget.insert(tk.END, stats_text)
        text_widget.config(state=tk.DISABLED)  # 设置为只读
    
    def clear_plot(self):
        """清除当前图形"""
        plt.close('all')  # 关闭所有matplotlib图形窗口
        messagebox.showinfo("提示", "已清除所有图形")
    
    def run(self):
        """运行应用程序"""
        self.root.mainloop()


def main():
    """主函数"""
    # 检查命令行参数
    if len(sys.argv) > 1:
        # 命令行模式
        filepath = sys.argv[1]
        plotter = SimpleCSVPlotter()
        
        # 直接加载文件
        if os.path.exists(filepath):
            try:
                plotter.data = pd.read_csv(filepath, comment='#')
                plotter.current_file = filepath
                plotter.file_label.config(text=os.path.basename(filepath))
                
                # 自动检测上升沿
                plotter.detect_rising_edges()
                # 自动绘图
                plotter.plot_data()
            except Exception as e:
                print(f"错误: {e}")
                sys.exit(1)
        
        # 显示GUI
        plotter.run()
    else:
        # GUI模式
        plotter = SimpleCSVPlotter()
        plotter.run()


if __name__ == "__main__":
    main()
