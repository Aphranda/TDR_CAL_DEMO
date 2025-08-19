# src/app/widgets/PlotWidget/Controller.py
from PyQt5.QtCore import QObject
import numpy as np

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
