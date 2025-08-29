# src/app/widgets/PlotWidget/View.py
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout
from PyQt5.QtCore import Qt
import pyqtgraph as pg
import platform
import ctypes
if platform.system()=='Windows' and int(platform.release()) >= 8:   
    ctypes.windll.shcore.SetProcessDpiAwareness(True)

class PlotWidgetView(QWidget):
    def __init__(self, title="Plot"):
        super().__init__()
        self.title = title
        self.setup_ui()
    
    def setup_ui(self):
        layout = QHBoxLayout()
        self.setLayout(layout)
        
        # 创建绘图部件
        self.plot_widget = pg.PlotWidget()
        self.plot_widget.setMouseEnabled(x=True, y=True)  # 启用X和Y方向的鼠标操作
        self.plot_widget.setBackground('w')
        self.plot_widget.setTitle(self.title, color='b', size='12pt')
        self.plot_widget.showGrid(x=True, y=True)
        self.plot_widget.setLabel('left', '幅度', units='V')
        self.plot_widget.setLabel('bottom', '时间', units='s')
        
        # 启用框选放大功能
        self.plot_widget.getViewBox().setMouseMode(pg.ViewBox.RectMode)  # 设置为矩形选择模式
        
        # 设置鼠标操作模式
        self.plot_widget.setMenuEnabled(True)  # 启用右键菜单
        self.plot_widget.enableAutoRange()  # 启用自动范围
        
        # 添加快捷键支持
        self.plot_widget.getViewBox().keyPressEvent = self.key_press_event
        
        # 设置坐标轴对齐方式
        self.set_axis_alignment()
        
        layout.addWidget(self.plot_widget)
        
        # 初始化绘图曲线
        self.plot_curve = self.plot_widget.plot(pen=pg.mkPen('b', width=2))
        
        # 添加状态提示
        self.status_label = pg.TextItem(text="按住鼠标左键拖动进行框选放大", color=(100, 100, 100), anchor=(0, 1))
        self.status_label.setPos(0, 0)
        self.plot_widget.addItem(self.status_label)
    
    def key_press_event(self, event):
        """处理键盘事件"""
        key = event.key()
        
        # 重置视图 (Home键或R键)
        if key in [pg.QtCore.Qt.Key_Home, pg.QtCore.Qt.Key_R]:
            self.plot_widget.autoRange()
            event.accept()
        
        # 平移模式 (P键)
        elif key == pg.QtCore.Qt.Key_P:
            self.plot_widget.getViewBox().setMouseMode(pg.ViewBox.PanMode)
            self.status_label.setText("平移模式: 按住鼠标左键拖动")
            event.accept()
        
        # 框选模式 (Z键)
        elif key == pg.QtCore.Qt.Key_Z:
            self.plot_widget.getViewBox().setMouseMode(pg.ViewBox.RectMode)
            self.status_label.setText("框选模式: 按住鼠标左键拖动进行放大")
            event.accept()
        
        else:
            event.ignore()
    
    def set_axis_alignment(self):
        """设置坐标轴对齐方式"""
        # 获取坐标轴对象
        bottom_axis = self.plot_widget.getAxis('bottom')
        left_axis = self.plot_widget.getAxis('left')
        top_axis = self.plot_widget.getAxis('top')
        right_axis = self.plot_widget.getAxis('right')
        
        # 设置底部坐标轴对齐方式
        if bottom_axis:
            bottom_axis.setStyle(
                tickTextOffset=10,  # 刻度文本偏移
                tickTextWidth=30,   # 刻度文本宽度
                tickTextHeight=15,  # 刻度文本高度
                autoExpandTextSpace=True  # 自动扩展文本空间
            )
        
        # 设置左侧坐标轴对齐方式
        if left_axis:
            left_axis.setStyle(
                tickTextOffset=10,  # 刻度文本偏移
                tickTextWidth=30,   # 刻度文本宽度
                tickTextHeight=15,  # 刻度文本高度
                autoExpandTextSpace=True  # 自动扩展文本空间
            )
        
        # 隐藏顶部和右侧坐标轴（可选）
        if top_axis:
            top_axis.setVisible(False)
        if right_axis:
            right_axis.setVisible(False)
    
    def set_axis_position(self, left_pos='left', bottom_pos='bottom'):
        """
        设置坐标轴位置
        
        参数:
            left_pos: 左侧坐标轴位置 ('left', 'right', 或具体位置值)
            bottom_pos: 底部坐标轴位置 ('bottom', 'top', 或具体位置值)
        """
        # 获取坐标轴对象
        bottom_axis = self.plot_widget.getAxis('bottom')
        left_axis = self.plot_widget.getAxis('left')
        
        if bottom_axis:
            if bottom_pos == 'top':
                bottom_axis.setStyle(axisPen=bottom_axis.pen(), tickLength=-5)
            elif isinstance(bottom_pos, (int, float)):
                bottom_axis.setPos(bottom_pos)
        
        if left_axis:
            if left_pos == 'right':
                left_axis.setStyle(axisPen=left_axis.pen(), tickLength=-5)
            elif isinstance(left_pos, (int, float)):
                left_axis.setPos(left_pos)
    
    def set_axis_label_alignment(self, horizontal='center', vertical='center'):
        """
        设置坐标轴标签对齐方式
        
        参数:
            horizontal: 水平对齐 ('left', 'center', 'right')
            vertical: 垂直对齐 ('top', 'center', 'bottom')
        """
        # 设置底部坐标轴标签对齐
        if horizontal == 'left':
            self.plot_widget.setLabel('bottom', self.plot_widget.getAxis('bottom').labelText, 
                                    **{'horizontalAlignment': 'left'})
        elif horizontal == 'center':
            self.plot_widget.setLabel('bottom', self.plot_widget.getAxis('bottom').labelText, 
                                    **{'horizontalAlignment': 'center'})
        elif horizontal == 'right':
            self.plot_widget.setLabel('bottom', self.plot_widget.getAxis('bottom').labelText, 
                                    **{'horizontalAlignment': 'right'})
        
        # 设置左侧坐标轴标签对齐
        if vertical == 'top':
            self.plot_widget.setLabel('left', self.plot_widget.getAxis('left').labelText, 
                                    **{'verticalAlignment': 'top'})
        elif vertical == 'center':
            self.plot_widget.setLabel('left', self.plot_widget.getAxis('left').labelText, 
                                    **{'verticalAlignment': 'center'})
        elif vertical == 'bottom':
            self.plot_widget.setLabel('left', self.plot_widget.getAxis('left').labelText, 
                                    **{'verticalAlignment': 'bottom'})
    
    def plot_data(self, x_data, y_data):
        """绘制数据"""
        self.plot_curve.setData(x_data, y_data)
    
    def clear_plot(self):
        """清除绘图"""
        self.plot_widget.clear()
        self.plot_curve = self.plot_widget.plot(pen=pg.mkPen('b', width=2))
        # 重新添加状态提示
        self.status_label = pg.TextItem(text="按住鼠标左键拖动进行框选放大", color=(100, 100, 100), anchor=(0, 1))
        self.status_label.setPos(0, 0)
        self.plot_widget.addItem(self.status_label)
    
    def set_labels(self, x_label, y_label, units_x="", units_y=""):
        """设置坐标轴标签和单位"""
        if units_x:
            self.plot_widget.setLabel('bottom', x_label, units=units_x, **{'horizontalAlignment': 'center'})
        else:
            self.plot_widget.setLabel('bottom', x_label, **{'horizontalAlignment': 'center'})
        
        if units_y:
            self.plot_widget.setLabel('left', y_label, units=units_y, **{'verticalAlignment': 'center'})
        else:
            self.plot_widget.setLabel('left', y_label, **{'verticalAlignment': 'center'})

    def export_plot(self, file_path):
        """导出绘图到文件"""
        try:
            # 使用pyqtgraph的导出功能
            exporter = pg.exporters.ImageExporter(self.plot_widget.scene())
            exporter.export(file_path)
            return True
        except Exception as e:
            print(f"导出图片失败: {e}")
            return False
