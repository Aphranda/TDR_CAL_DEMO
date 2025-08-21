# src/app/widgets/PlotWidget/Controller.py
from PyQt5.QtCore import QObject
import numpy as np
import pyqtgraph as pg

class PlotWidgetController(QObject):
    def __init__(self, model, view):
        super().__init__()
        self.model = model
        self.view = view
        self.setup_default_alignment()  # 设置默认对齐方式
        self.setup_connections()
    
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
        pass
    
    def update_plot(self, x_data, y_data, clear_existing=True):
        """更新绘图数据"""
        if clear_existing:
            self.view.clear_plot()
        
        self.view.plot_data(x_data, y_data)
    
    def update_time_domain_plot(self, time_data, amplitude_data):
        """更新时域绘图"""
        self.update_plot(time_data, amplitude_data)
        # 设置时域坐标轴标签
        self.view.set_labels("时间", "幅度")
    
    def update_frequency_domain_plot(self, freq_data, magnitude_data, phase_data=None):
        """更新频域绘图"""
        self.update_plot(freq_data, magnitude_data)
        # 设置频域坐标轴标签
        self.view.set_labels("频率", "幅度")
        
        if phase_data is not None:
            # 如果有相位数据，可以添加到第二个Y轴
            pass

    def plot_time_domain(self, time_data, amplitude_data, x_label="时间", y_label="幅度", units_x="s", units_y="V"):
        """绘制时域数据"""
        self.update_plot(time_data, amplitude_data)
        self.view.set_labels(x_label, y_label, units_x, units_y)
        self.view.plot_widget.setTitle("时域信号", color='b', size='12pt')

    def plot_frequency_domain(self, freq_data, magnitude_data, x_label="频率", y_label="幅度", units_x="Hz", units_y="dB"):
        """绘制频域数据"""
        self.update_plot(freq_data, magnitude_data)
        self.view.set_labels(x_label, y_label, units_x, units_y)
        self.view.plot_widget.setTitle("频域信号", color='b', size='12pt')

    def plot_diff_time_domain(self, time_data, diff_data, x_label="时间", y_label="差分幅度", units_x="s", units_y="V"):
        """绘制差分时域数据"""
        self.update_plot(time_data, diff_data)
        self.view.set_labels(x_label, y_label, units_x, units_y)
        self.view.plot_widget.setTitle("差分时域信号", color='b', size='12pt')

    def plot_diff_frequency_domain(self, freq_data, diff_mag_data, x_label="频率", y_label="差分幅度", units_x="Hz", units_y="dB"):
        """绘制差分频域数据"""
        self.update_plot(freq_data, diff_mag_data)
        self.view.set_labels(x_label, y_label, units_x, units_y)
        self.view.plot_widget.setTitle("差分频域信号", color='b', size='12pt')

    def add_vertical_line(self, x_position, color='red', style='dashed', label=''):
        """添加垂直标记线"""
        try:
            # 创建无限线
            pen = pg.mkPen(color, width=1, style=pg.QtCore.Qt.DashLine if style == 'dashed' else pg.QtCore.Qt.SolidLine)
            line = pg.InfiniteLine(pos=x_position, angle=90, pen=pen, movable=False)
            self.view.plot_widget.addItem(line)
            
            if label:
                # 添加文本标签
                text = pg.TextItem(text=label, color=color, anchor=(0.5, 1))
                y_range = self.view.plot_widget.getViewBox().viewRange()[1]
                text.setPos(x_position, y_range[1] * 0.9)  # 放在y轴90%的位置
                self.view.plot_widget.addItem(text)
                
            return line
            
        except Exception as e:
            print(f"添加标记线失败: {e}")
            return None

    def add_horizontal_line(self, y_position, color='red', style='dashed', label=''):
        """添加水平标记线"""
        try:
            # 创建无限线
            pen = pg.mkPen(color, width=1, style=pg.QtCore.Qt.DashLine if style == 'dashed' else pg.QtCore.Qt.SolidLine)
            line = pg.InfiniteLine(pos=y_position, angle=0, pen=pen, movable=False)
            self.view.plot_widget.addItem(line)
            
            if label:
                # 添加文本标签
                text = pg.TextItem(text=label, color=color, anchor=(1, 0.5))
                x_range = self.view.plot_widget.getViewBox().viewRange()[0]
                text.setPos(x_range[1] * 0.9, y_position)  # 放在x轴90%的位置
                self.view.plot_widget.addItem(text)
                
            return line
            
        except Exception as e:
            print(f"添加标记线失败: {e}")
            return None

    def clear_markers(self):
        """清除所有标记线"""
        try:
            # 获取所有无限线并移除
            for item in self.view.plot_widget.allChildItems():
                if isinstance(item, pg.InfiniteLine):
                    self.view.plot_widget.removeItem(item)
                elif isinstance(item, pg.TextItem):
                    self.view.plot_widget.removeItem(item)
                    
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
