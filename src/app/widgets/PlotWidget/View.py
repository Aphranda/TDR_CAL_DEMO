# src/app/widgets/PlotWidget/View.py
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel
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
        main_layout = QVBoxLayout()
        self.setLayout(main_layout)
        
        # 创建绘图部件
        self.plot_widget = pg.PlotWidget()
        self.plot_widget.setMouseEnabled(x=True, y=False)  # 启用X和Y方向的鼠标操作
        self.plot_widget.setBackground('w')
        self.plot_widget.setTitle(self.title, color='b', size='12pt')
        self.plot_widget.showGrid(x=True, y=True)
        self.plot_widget.setLabel('left', '幅度', units='V')
        self.plot_widget.setLabel('bottom', '时间', units='s')
        
        # 获取ViewBox并设置默认模式为平移模式
        self.view_box = self.plot_widget.getViewBox()
        self.view_box.setMouseMode(pg.ViewBox.PanMode)  # 默认设置为平移模式
        
        # 设置鼠标操作模式
        self.plot_widget.setMenuEnabled(True)  # 启用右键菜单
        self.plot_widget.enableAutoRange()  # 启用自动范围
        
        # 重写鼠标事件处理
        self.view_box.mouseClickEvent = self.mouse_click_event
        self.view_box.mouseDragEvent = self.mouse_drag_event
        self.view_box.mouseReleaseEvent = self.mouse_release_event
        
        # 添加快捷键支持
        self.view_box.keyPressEvent = self.key_press_event
        
        # 设置坐标轴对齐方式
        self.set_axis_alignment()
        
        main_layout.addWidget(self.plot_widget)
        
        # 创建坐标显示标签
        self.coord_label = QLabel("X: -, Y: -")
        self.coord_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.coord_label.setStyleSheet("color: gray; font-size: 16px; padding: 2px;")
        main_layout.addWidget(self.coord_label)
        
        # 初始化绘图曲线
        self.plot_curve = self.plot_widget.plot(pen=pg.mkPen('b', width=2))
        
        # 连接鼠标移动信号
        self.proxy = pg.SignalProxy(self.plot_widget.scene().sigMouseMoved, 
                                  rateLimit=60, slot=self.mouse_moved)
        
        # 跟踪当前鼠标按钮状态
        self.current_button = None
    
    def mouse_click_event(self, event):
        """处理鼠标点击事件"""
        # 记录按下的鼠标按钮
        self.current_button = event.button()
        # 调用父类方法处理基本功能
        pg.ViewBox.mouseClickEvent(self.view_box, event)
    
    def mouse_drag_event(self, event, axis=None):
        """处理鼠标拖拽事件"""
        # 根据按下的鼠标按钮设置不同的模式
        if event.buttons() & Qt.MiddleButton:
            # 中键按下，设置为框选模式
            self.view_box.setMouseMode(pg.ViewBox.RectMode)
            # 调用父类方法处理拖拽
            pg.ViewBox.mouseDragEvent(self.view_box, event, axis)
        elif event.buttons() & Qt.LeftButton:
            # 左键按下，设置为平移模式
            self.view_box.setMouseMode(pg.ViewBox.PanMode)
            # 调用父类方法处理拖拽
            pg.ViewBox.mouseDragEvent(self.view_box, event, axis)
        else:
            # 其他按钮，调用父类方法
            pg.ViewBox.mouseDragEvent(self.view_box, event, axis)
    
    def mouse_release_event(self, event):
        """处理鼠标释放事件"""
        # 先调用父类方法完成框选操作
        pg.ViewBox.mouseReleaseEvent(self.view_box, event)
        
        # 只有在完成框选操作后才恢复默认模式
        # 如果是中键释放（框选模式），让父类方法先处理缩放
        if self.current_button == Qt.MiddleButton:
            # 延迟一小段时间再恢复模式，确保缩放操作完成
            pg.QtCore.QTimer.singleShot(50, self.restore_default_mode)
        else:
            # 其他按钮立即恢复默认模式
            self.restore_default_mode()
    
    def restore_default_mode(self):
        """恢复默认的平移模式"""
        self.view_box.setMouseMode(pg.ViewBox.PanMode)
        self.current_button = None
    
    def mouse_moved(self, event):
        """处理鼠标移动事件，显示坐标"""
        try:
            pos = event[0]  # 获取鼠标位置
            if self.plot_widget.sceneBoundingRect().contains(pos):
                mouse_point = self.plot_widget.getViewBox().mapSceneToView(pos)
                x, y = mouse_point.x(), mouse_point.y()
                
                # 获取坐标轴的完整标签信息
                bottom_axis = self.plot_widget.getAxis('bottom')
                left_axis = self.plot_widget.getAxis('left')
                
                # 获取坐标轴的单位前缀（如果有的话）
                x_label = bottom_axis.labelText
                y_label = left_axis.labelText
                
                # 直接显示原始值，让用户根据坐标轴标签理解单位
                self.coord_label.setText(f"{x_label}: {(x*1000):.3f}, {y_label}: {y:.3f}")
            else:
                self.coord_label.setText("X: -, Y: -")
        except:
            self.coord_label.setText("X: -, Y: -")
    
    def key_press_event(self, event):
        """处理键盘事件"""
        key = event.key()
        
        # 重置视图 (Home键或R键)
        if key in [pg.QtCore.Qt.Key_Home, pg.QtCore.Qt.Key_R]:
            self.plot_widget.autoRange()
            event.accept()
        
        # 平移模式 (P键)
        elif key == pg.QtCore.Qt.Key_P:
            self.view_box.setMouseMode(pg.ViewBox.PanMode)
            event.accept()
        
        # 框选模式 (Z键)
        elif key == pg.QtCore.Qt.Key_Z:
            self.view_box.setMouseMode(pg.ViewBox.RectMode)
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

    def set_view_range(self, x_min, x_max, y_min=None, y_max=None):
        """设置视图显示范围"""
        view_box = self.plot_widget.getViewBox()
        if y_min is not None and y_max is not None:
            view_box.setRange(xRange=(x_min, x_max), yRange=(y_min, y_max), padding=0)
        else:
            # 保持Y轴范围不变
            current_y_range = view_box.viewRange()[1]
            view_box.setRange(xRange=(x_min, x_max), yRange=current_y_range, padding=0)
    
    def auto_range(self):
        """自动调整视图范围"""
        self.plot_widget.autoRange()
