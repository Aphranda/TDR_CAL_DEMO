# src/app/widgets/PlotWidget/Controller.py
from PyQt5.QtCore import QObject
import numpy as np
import pyqtgraph as pg
from PyQt5.QtCore import Qt

class PlotWidgetController(QObject):
    def __init__(self, model, view):
        super().__init__()
        self.model = model
        self.view = view
        self.setup_default_alignment()  # 设置默认对齐方式
        self.setup_connections()

        self.roi_start = None
        self.roi_end = None
        self.roi_lines = []  # 存储ROI标记线
        self.marker_lines = []  # 存储所有标记线
        self.marker_texts = []  # 存储所有标记文本
    
    def setup_default_alignment(self):
        """设置默认的坐标轴对齐方式"""
        # 设置坐标轴基本对齐
        self.view.set_axis_alignment()
        
        # 设置坐标轴位置（默认：左侧和底部）
        self.view.set_axis_position('left', 'bottom')
        
        # 设置坐标轴标签对齐方式（默认：居中对齐）
        # 注意：这里使用更安全的方式设置对齐
        self.view.plot_widget.setLabel('bottom', self.view.plot_widget.getAxis('bottom').labelText, 
                                    **{'horizontalAlignment': 'center'})
        self.view.plot_widget.setLabel('left', self.view.plot_widget.getAxis('left').labelText, 
                                    **{'verticalAlignment': 'center'})
    
    def setup_connections(self):
        """设置信号连接"""
        # 连接鼠标移动信号到坐标显示
        self.view.plot_widget.scene().sigMouseMoved.connect(self.on_mouse_moved)
    
    def on_mouse_moved(self, pos):
        """处理鼠标移动事件"""
        # 这个函数现在由View自己处理，这里保持空实现或移除
        pass
    
    def update_plot(self, x_data, y_data, clear_existing=True):
        """更新绘图数据"""
        if clear_existing:
            self.view.clear_plot()
        
        self.view.plot_data(x_data, y_data)
    
    def update_time_domain_plot(self, time_data, amplitude_data, roi_start=None, roi_end=None):
        """更新时域绘图，支持ROI参数"""
        self.update_plot(time_data, amplitude_data)
        # 设置时域坐标轴标签
        self.view.set_labels("时间", "幅度")
        
        # # 如果有ROI参数，设置ROI范围
        # if roi_start is not None and roi_end is not None:
        #     self.set_roi_range(roi_start, roi_end)
    
    def update_frequency_domain_plot(self, freq_data, magnitude_data, phase_data=None):
        """更新频域绘图"""
        self.update_plot(freq_data, magnitude_data)
        # 设置频域坐标轴标签
        self.view.set_labels("频率", "幅度")
        
        if phase_data is not None:
            # 如果有相位数据，可以添加到第二个Y轴
            pass

    def plot_time_domain(self, time_data, amplitude_data, x_label="时间", y_label="幅度", 
                        units_x="s", units_y="V", roi_start=None, roi_end=None):
        """绘制时域数据，支持ROI参数"""
        self.update_plot(time_data, amplitude_data)
        self.view.set_labels(x_label, y_label, units_x, units_y)
        self.view.plot_widget.setTitle("时域信号", color='b', size='12pt')
        
        # 如果有ROI参数，设置ROI范围
        # if roi_start is not None and roi_end is not None:
        #     self.set_roi_range(roi_start, roi_end)

    def plot_frequency_domain(self, freq_data, magnitude_data, x_label="频率", y_label="幅度", units_x="Hz", units_y="dB"):
        """绘制频域数据"""
        self.update_plot(freq_data, magnitude_data)
        self.view.set_labels(x_label, y_label, units_x, units_y)
        self.view.plot_widget.setTitle("频域信号", color='b', size='12pt')

    def plot_diff_time_domain(self, time_data, diff_data, x_label="时间", y_label="差分幅度", units_x="ns", units_y="V"):
        """绘制差分时域数据"""
        self.update_plot(time_data, diff_data)
        self.view.set_labels(x_label, y_label, units_x, units_y)
        self.view.plot_widget.setTitle("差分时域信号", color='b', size='12pt')

    def plot_diff_frequency_domain(self, freq_data, diff_mag_data, x_label="频率", y_label="差分幅度", units_x="Hz", units_y="dB"):
        """绘制差分频域数据"""
        self.update_plot(freq_data, diff_mag_data)
        self.view.set_labels(x_label, y_label, units_x, units_y)
        self.view.plot_widget.setTitle("差分频域信号", color='b', size='12pt')

    def add_marker_line(self, x_position, y_position=None, color='red', style='dashed', label='', width=2, angle=90):
        """添加标记线 - 支持垂直或水平线，以及文本标签"""
        try:
            # 创建无限线
            pen_style = Qt.DashLine if style == 'dashed' else \
                        Qt.DotLine if style == 'dotted' else \
                        Qt.DashDotLine if style == 'dashdot' else \
                        Qt.SolidLine
            
            # 创建无限线，设置较低的Z值确保在背景层
            line = pg.InfiniteLine(pos=x_position if angle == 90 else y_position, 
                                angle=angle, 
                                pen=pg.mkPen(color, width=width, style=pen_style))
            line.setZValue(-10)  # 设置较低的Z值，确保在背景层
            
            self.view.plot_widget.addItem(line)
            self.marker_lines.append(line)
            
            if label:
                # 添加文本标签，也设置较低的Z值
                text = pg.TextItem(text=label, color=color, anchor=(0.5, 1) if angle == 90 else (1, 0.5))
                
                # 设置文本位置
                if angle == 90:  # 垂直线
                    text.setPos(x_position, y_position if y_position is not None else 0)
                else:  # 水平线
                    text.setPos(x_position if x_position is not None else 0, y_position)
                
                text.setZValue(-5)  # 文本也设置较低的Z值，但比线稍高
                
                # 设置字体样式
                font = text.textItem.font()
                font.setPointSize(8)  # 使用稍小的字体
                font.setBold(True)
                text.textItem.setFont(font)
                
                self.view.plot_widget.addItem(text)
                self.marker_texts.append(text)
            
            return line
            
        except Exception as e:
            print(f"添加标记线失败: {e}")
            return None

    def clear_markers(self):
        """清除所有标记线和文本"""
        try:
            # 移除所有标记线
            for line in self.marker_lines:
                self.view.plot_widget.removeItem(line)
            
            # 移除所有标记文本
            for text in self.marker_texts:
                self.view.plot_widget.removeItem(text)
            
            # 清空列表
            self.marker_lines = []
            self.marker_texts = []
            
            # 同时清除ROI标记
            self.clear_roi_markers()
                    
        except Exception as e:
            print(f"清除标记线失败: {e}")

    def set_custom_alignment(self, horizontal='center', vertical='center', 
                           left_pos='left', bottom_pos='bottom'):
        """
        设置自定义对齐方式
        
        参数:
            horizontal: 水平对齐 ('left', 'center', 'right')
            vertical: 垂直对齐 ('top', 'center', 'bottom')
            left_pos: 左侧坐标轴位置 ('left', 'right')
            bottom_pos: 底部坐标轴位置 ('bottom', 'top')
        """
        self.view.set_axis_alignment()
        self.view.set_axis_position(left_pos, bottom_pos)
        
        # 使用安全的方式设置标签对齐
        if horizontal in ['left', 'center', 'right']:
            self.view.plot_widget.setLabel('bottom', self.view.plot_widget.getAxis('bottom').labelText, 
                                        **{'horizontalAlignment': horizontal})
        
        if vertical in ['top', 'center', 'bottom']:
            self.view.plot_widget.setLabel('left', self.view.plot_widget.getAxis('left').labelText, 
                                        **{'verticalAlignment': vertical})
    
    def set_axis_visibility(self, show_top=False, show_right=False, 
                          show_bottom=True, show_left=True):
        """
        设置坐标轴可见性
        
        参数:
            show_top: 是否显示顶部坐标轴
            show_right: 是否显示右侧坐标轴
            show_bottom: 是否显示底部坐标轴
            show_left: 是否显示左侧坐标轴
        """
        top_axis = self.view.plot_widget.getAxis('top')
        right_axis = self.view.plot_widget.getAxis('right')
        bottom_axis = self.view.plot_widget.getAxis('bottom')
        left_axis = self.view.plot_widget.getAxis('left')
        
        if top_axis:
            top_axis.setVisible(show_top)
        if right_axis:
            right_axis.setVisible(show_right)
        if bottom_axis:
            bottom_axis.setVisible(show_bottom)
        if left_axis:
            left_axis.setVisible(show_left)

    def export_plot(self, file_path):
        """导出绘图到文件"""
        return self.view.export_plot(file_path)

    def set_roi_range(self, roi_start, roi_end):
        """设置ROI范围"""
        self.roi_start = roi_start
        self.roi_end = roi_end
        self.update_roi_display()
    
    def update_roi_display(self):
        """更新ROI显示"""
        self.clear_roi_markers()
        
        if self.roi_start is not None and self.roi_end is not None:
            # 添加ROI开始和结束的垂直标记线
            start_line = self.add_marker_line(self.roi_start, color='green', style='dashed', label='ROI Start')
            end_line = self.add_marker_line(self.roi_end, color='red', style='dashed', label='ROI End')
            
            if start_line:
                self.roi_lines.append(start_line)
            if end_line:
                self.roi_lines.append(end_line)
            
            # 设置视图范围以显示ROI区域
            self.set_view_to_roi()
    
    def set_view_to_roi(self, padding=0.1):
        """调整视图以显示ROI区域"""
        if self.roi_start is not None and self.roi_end is not None:
            # 计算带padding的显示范围
            roi_range = abs(self.roi_end - self.roi_start)
            x_min = self.roi_start - roi_range * padding
            x_max = self.roi_end + roi_range * padding
            
            # 获取Y轴数据范围
            view_box = self.view.plot_widget.getViewBox()
            y_range = view_box.viewRange()[1]
            
            # 设置视图范围
            view_box.setRange(xRange=(x_min, x_max), yRange=y_range, padding=0)
    
    def clear_roi_markers(self):
        """清除ROI标记线"""
        for line in self.roi_lines:
            try:
                self.view.plot_widget.removeItem(line)
            except:
                pass
        self.roi_lines = []
    
    def reset_view(self):
        """重置视图到完整数据范围"""
        self.view.plot_widget.autoRange()
        self.clear_roi_markers()
        self.roi_start = None
        self.roi_end = None
