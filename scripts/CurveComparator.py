import numpy as np
import matplotlib.pyplot as plt
import pandas as pd
from matplotlib.widgets import Cursor, Button, TextBox

class CurveComparator:
    """增强版曲线比较分析工具，支持标记点和参考线功能"""
    
    def __init__(self):
        self.freq1 = None
        self.mag1 = None
        self.freq2 = None
        self.mag2 = None
        self.diff_freq = None
        self.diff_mag = None
        self.markers = []  # 存储标记点信息
        self.h_lines = []  # 存储水平参考线
        self.v_lines = []  # 存储垂直参考线
        self.fig = None
        self.ax1 = None
        self.ax2 = None
        self.cursor = None
        self.h_line_axis_choice = 'original'  # 水平线默认添加到原始曲线图
        self.v_line_axis_choice = 'original'  # 垂直线默认添加到原始曲线图
        
    def load_curve_data(self, file_path):
        """从文件加载曲线数据"""
        try:
            data = pd.read_csv(file_path, header=0)
            frequency = data.iloc[:, 0].values
            magnitude = data.iloc[:, 1].values
            return frequency, magnitude
        except Exception as e:
            print(f"加载文件时出错: {e}")
            return None, None

    def subtract_curves(self, freq1, mag1, freq2, mag2):
        """将两条曲线相减（确保频率点对齐）"""
        if not np.array_equal(freq1, freq2):
            print("警告：频率点不完全相同，进行插值对齐")
            mag1_interp = np.interp(freq2, freq1, mag1)
            return freq2, mag1_interp - mag2
        else:
            return freq1, mag1 - mag2

    def add_marker(self, freq, ax, curve_type):
        """添加标记点"""
        if curve_type == 'original':
            idx = np.abs(self.freq1 - freq).argmin()
            mag_val1 = self.mag1[idx]
            mag_val2 = self.mag2[idx]
            marker_info = {
                'freq': freq,
                'mag1': mag_val1,
                'mag2': mag_val2,
                'diff': mag_val1 - mag_val2,
                'type': 'original',
                'marker_obj': ax.plot(freq, mag_val1, 'ko', markersize=8, markeredgewidth=2)[0]
            }
        else:  # difference
            idx = np.abs(self.diff_freq - freq).argmin()
            diff_val = self.diff_mag[idx]
            marker_info = {
                'freq': freq,
                'diff': diff_val,
                'type': 'difference',
                'marker_obj': ax.plot(freq, diff_val, 'ko', markersize=8, markeredgewidth=2)[0]
            }
        
        self.markers.append(marker_info)
        # self.update_info_display()
        return marker_info

    def add_horizontal_line(self, y_value, ax_type):
        """添加水平参考线"""
        if ax_type == 'original':
            ax = self.ax1
            intersections = self.find_horizontal_intersections(y_value, self.freq1, self.mag1, self.mag2)
        else:  # difference
            ax = self.ax2
            intersections = self.find_horizontal_intersections(y_value, self.diff_freq, self.diff_mag)
        
        line_obj = ax.axhline(y=y_value, color='purple', linestyle='--', alpha=0.7, linewidth=1.5)
        
        h_line_info = {
            'y_value': y_value,
            'ax_type': ax_type,
            'line_obj': line_obj,
            'intersections': intersections,
            'text_objs': []
        }
        
        # 添加交点标记和文本
        for i, (freq, mag) in enumerate(intersections):
            marker = ax.plot(freq, mag, 'mo', markersize=6)[0]
            text = ax.text(freq, mag, f'  {freq:.2f}GHz\n  {mag:.2f}dB', 
                          fontsize=8, bbox=dict(facecolor='white', alpha=0.7))
            h_line_info['text_objs'].extend([marker, text])
        
        self.h_lines.append(h_line_info)
        # self.update_info_display()
        return h_line_info

    def add_vertical_line(self, x_value, ax_type):
        """添加垂直参考线"""
        if ax_type == 'original':
            ax = self.ax1
            y1_val = np.interp(x_value, self.freq1, self.mag1)
            y2_val = np.interp(x_value, self.freq2, self.mag2)
            intersections = [(x_value, y1_val), (x_value, y2_val)]
        else:  # difference
            ax = self.ax2
            y_val = np.interp(x_value, self.diff_freq, self.diff_mag)
            intersections = [(x_value, y_val)]
        
        line_obj = ax.axvline(x=x_value, color='orange', linestyle='--', alpha=0.7, linewidth=1.5)
        
        v_line_info = {
            'x_value': x_value,
            'ax_type': ax_type,
            'line_obj': line_obj,
            'intersections': intersections,
            'text_objs': []
        }
        
        # 添加交点标记和文本
        for i, (freq, mag) in enumerate(intersections):
            marker = ax.plot(freq, mag, 'co', markersize=6)[0]
            text = ax.text(freq, mag, f'  {freq:.2f}GHz\n  {mag:.2f}dB', 
                          fontsize=8, bbox=dict(facecolor='white', alpha=0.7))
            v_line_info['text_objs'].extend([marker, text])
        
        self.v_lines.append(v_line_info)
        # self.update_info_display()
        return v_line_info

    def find_horizontal_intersections(self, y_value, freq_data, *mag_arrays):
        """查找与水平线的交点"""
        intersections = []
        for mag_data in mag_arrays:
            for i in range(len(freq_data)-1):
                if (mag_data[i] - y_value) * (mag_data[i+1] - y_value) <= 0:
                    # 线性插值
                    x1, x2 = freq_data[i], freq_data[i+1]
                    y1, y2 = mag_data[i], mag_data[i+1]
                    if y2 != y1:  # 避免除以零
                        t = (y_value - y1) / (y2 - y1)
                        intersect_x = x1 + t * (x2 - x1)
                        intersections.append((intersect_x, y_value))
        return intersections

    def update_info_display(self):
        """Update information display in English"""
        if hasattr(self, 'info_text'):
            self.info_text.remove()
        
        info_str = "=== MARKER POINTS ===\n"
        for i, marker in enumerate(self.markers):
            if marker['type'] == 'original':
                info_str += f"M{i+1}: {marker['freq']:.3f}GHz - " \
                        f"Curve1: {marker['mag1']:.2f}dB, " \
                        f"Curve2: {marker['mag2']:.2f}dB, " \
                        f"Diff: {marker['diff']:.2f}dB\n"
            else:
                info_str += f"M{i+1}: {marker['freq']:.3f}GHz - " \
                        f"Difference: {marker['diff']:.2f}dB\n"
        
        info_str += "\n=== HORIZONTAL REFERENCE LINES ===\n"
        for i, h_line in enumerate(self.h_lines):
            info_str += f"H{i+1}: y={h_line['y_value']:.2f}dB ({h_line['ax_type']}) - "
            info_str += f"{len(h_line['intersections'])} intersection(s)\n"
            for j, (freq, mag) in enumerate(h_line['intersections']):
                info_str += f"    Intersection {j+1}: {freq:.3f}GHz, {mag:.2f}dB\n"
        
        info_str += "\n=== VERTICAL REFERENCE LINES ===\n"
        for i, v_line in enumerate(self.v_lines):
            info_str += f"V{i+1}: x={v_line['x_value']:.2f}GHz ({v_line['ax_type']}) - "
            info_str += f"{len(v_line['intersections'])} intersection(s)\n"
            for j, (freq, mag) in enumerate(v_line['intersections']):
                info_str += f"    Intersection {j+1}: {freq:.3f}GHz, {mag:.2f}dB\n"
        
        self.info_text = self.fig.text(0.02, 0.02, info_str, fontsize=9,
                                    bbox=dict(facecolor='white', alpha=0.9))


    def on_click(self, event):
        """鼠标点击事件处理"""
        if event.inaxes in [self.ax1, self.ax2] and event.button == 1:
            if event.inaxes == self.ax1:
                marker = self.add_marker(event.xdata, self.ax1, 'original')
            else:
                marker = self.add_marker(event.xdata, self.ax2, 'difference')
            
            self.fig.canvas.draw()

    def clear_all(self, event):
        """清除所有标记点和参考线"""
        # 清除标记点
        for marker in self.markers:
            marker['marker_obj'].remove()
        self.markers = []
        
        # 清除水平线
        for h_line in self.h_lines:
            h_line['line_obj'].remove()
            for obj in h_line['text_objs']:
                obj.remove()
        self.h_lines = []
        
        # 清除垂直线
        for v_line in self.v_lines:
            v_line['line_obj'].remove()
            for obj in v_line['text_objs']:
                obj.remove()
        self.v_lines = []
        
        if hasattr(self, 'info_text'):
            self.info_text.remove()
        
        self.fig.canvas.draw()

    def on_h_line_submit(self, text):
        """处理水平线输入"""
        try:
            y_value = float(text)
            self.add_horizontal_line(y_value, self.h_line_axis_choice)
            self.fig.canvas.draw()
        except ValueError:
            print("请输入有效的数字")

    def on_v_line_submit(self, text):
        """处理垂直线输入"""
        try:
            x_value = float(text)
            self.add_vertical_line(x_value, self.v_line_axis_choice)
            self.fig.canvas.draw()
        except ValueError:
            print("请输入有效的数字")

    def toggle_h_axis_choice(self, event):
        """切换水平线添加的坐标轴"""
        self.h_line_axis_choice = 'difference' if self.h_line_axis_choice == 'original' else 'original'
        self.ax_h_line_choice.label.set_text('Difference' if self.h_line_axis_choice == 'difference' else 'Original')
        self.fig.canvas.draw()

    def toggle_v_axis_choice(self, event):
        """切换垂直线添加的坐标轴"""
        self.v_line_axis_choice = 'difference' if self.v_line_axis_choice == 'original' else 'original'
        self.ax_v_line_choice.label.set_text('Difference' if self.v_line_axis_choice == 'difference' else 'Original')
        self.fig.canvas.draw()

    def plot_curves(self, title="Curve Comparison"):
        """绘制带标记点和参考线功能的曲线"""
        self.fig, (self.ax1, self.ax2) = plt.subplots(2, 1, figsize=(16, 12))
        
        # 绘制原始曲线（使用英文标签避免乱码）
        self.ax1.plot(self.freq1, self.mag1, 'b-', label='Curve1 (AMP_20db)', linewidth=2)
        self.ax1.plot(self.freq2, self.mag2, 'r-', label='Curve2 (Thru_0dB)', linewidth=2)
        self.ax1.set_xlabel('Frequency (GHz)')
        self.ax1.set_ylabel('Magnitude (dB)')
        self.ax1.set_title('Original Curves')
        self.ax1.legend()
        self.ax1.grid(True, alpha=0.3)
        
        # 绘制差值曲线（使用英文标签避免乱码）
        self.ax2.plot(self.diff_freq, self.diff_mag, 'g-', 
                     label='Difference (Curve1 - Curve2)', linewidth=2)
        self.ax2.set_xlabel('Frequency (GHz)')
        self.ax2.set_ylabel('Magnitude Difference (dB)')
        self.ax2.set_title('Curve Difference')
        self.ax2.legend()
        self.ax2.grid(True, alpha=0.3)
        
        # 添加光标
        self.cursor = Cursor(self.ax1, useblit=True, color='red', linewidth=1)
        self.cursor2 = Cursor(self.ax2, useblit=True, color='red', linewidth=1)
        
        # 添加控制面板
        self.add_control_panel()
        
        # 连接点击事件
        self.fig.canvas.mpl_connect('button_press_event', self.on_click)
        
        plt.suptitle(title, fontsize=16)
        plt.tight_layout(rect=[0, 0.08, 1, 0.95])
        plt.show()

    def add_control_panel(self):
        """添加带按钮和输入框的控制面板"""
        # 清除按钮
        ax_clear = plt.axes([0.85, 0.01, 0.1, 0.04])
        btn_clear = Button(ax_clear, 'Clear All')
        btn_clear.on_clicked(self.clear_all)
        
        # 水平线控制
        plt.figtext(0.02, 0.96, 'Horizontal Line (dB):', fontsize=10)
        ax_h_line = plt.axes([0.15, 0.96, 0.1, 0.03])
        self.h_line_text = TextBox(ax_h_line, '', initial='0.0')
        self.h_line_text.on_submit(self.on_h_line_submit)
        
        # 水平线坐标轴选择
        ax_h_choice = plt.axes([0.26, 0.96, 0.1, 0.03])
        self.ax_h_line_choice = Button(ax_h_choice, 'Original')
        self.ax_h_line_choice.on_clicked(self.toggle_h_axis_choice)
        
        # 垂直线控制
        plt.figtext(0.02, 0.92, 'Vertical Line (GHz):', fontsize=10)
        ax_v_line = plt.axes([0.15, 0.92, 0.1, 0.03])
        self.v_line_text = TextBox(ax_v_line, '', initial='5.0')
        self.v_line_text.on_submit(self.on_v_line_submit)
        
        # 垂直线坐标轴选择
        ax_v_choice = plt.axes([0.26, 0.92, 0.1, 0.03])
        self.ax_v_line_choice = Button(ax_v_choice, 'Original')
        self.ax_v_line_choice.on_clicked(self.toggle_v_axis_choice)

# 主程序
if __name__ == "__main__":
    comparator = CurveComparator()
    
    # 文件路径
    file_path1 = r"data\results\plots\AMP\AMP_20db_diff_frequency_domain.csv"
    file_path2 = r"data\results\plots\Thru\Thru_0dB_diff_frequency_domain.csv"
    
    # 加载数据
    freq1, mag1 = comparator.load_curve_data(file_path1)
    freq2, mag2 = comparator.load_curve_data(file_path2)
    
    if freq1 is not None and freq2 is not None:
        # 计算差值
        diff_freq, diff_mag = comparator.subtract_curves(freq1, mag1, freq2, mag2)
        
        comparator.freq1 = freq1
        comparator.mag1 = mag1
        comparator.freq2 = freq2
        comparator.mag2 = mag2
        comparator.diff_freq = diff_freq
        comparator.diff_mag = diff_mag
        
        # 绘制结果
        comparator.plot_curves("AMP_20db vs Thru_0dB Curve Comparison Analysis")
        
        # 保存差值结果
        output_data = np.column_stack((diff_freq, diff_mag))
        np.savetxt(r"scripts\temp\difference_curve.csv", output_data, 
                  delimiter=",", header="Frequency(GHz),Difference_Magnitude(dB)", 
                  comments='', fmt='%.15e,%.15e')
        print("差值结果已保存到 difference_curve.csv")
        
        print("\n使用说明:")
        print("1. 在曲线上左键点击添加标记点")
        print("2. 输入dB值添加水平参考线")
        print("3. 输入GHz值添加垂直参考线")
        print("4. 点击坐标轴选择按钮切换添加参考线的图表")
        print("5. 点击'Clear All'清除所有标记和参考线")
        print("6. 所有交点数据会显示在图表下方")
        
    else:
        print("数据加载失败，请检查文件路径")
