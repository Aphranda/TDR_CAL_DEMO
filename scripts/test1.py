import pandas as pd
import matplotlib.pyplot as plt
import glob
import os

def plot_multiple_csv_files(folder_path=None, file_pattern="*.csv", figsize=(12, 6)):
    """
    导入多个CSV文件并叠加绘制图表
    
    参数:
    folder_path: CSV文件所在文件夹路径，如果为None则使用当前目录
    file_pattern: 文件匹配模式，默认为所有csv文件
    figsize: 图表尺寸
    """
    
    # 设置文件夹路径
    if folder_path is None:
        folder_path = "."
    
    # 获取所有CSV文件
    search_pattern = os.path.join(folder_path, file_pattern)
    csv_files = glob.glob(search_pattern)
    
    if not csv_files:
        print(f"在 {folder_path} 中没有找到匹配 {file_pattern} 的文件")
        return
    
    print(f"找到 {len(csv_files)} 个CSV文件:")
    for file in csv_files:
        print(f"  - {os.path.basename(file)}")
    
    # 创建图表
    plt.figure(figsize=figsize)
    
    # 读取并绘制每个CSV文件
    for i, file_path in enumerate(csv_files):
        try:
            # 读取CSV文件
            df = pd.read_csv(file_path)
            
            # 检查必要的列是否存在
            if 'Time(us)' not in df.columns or 'Amplitude' not in df.columns:
                print(f"警告: 文件 {os.path.basename(file_path)} 缺少必要的列")
                continue
            
            # 绘制数据
            plt.plot(df['Time(us)'], df['Amplitude'], 
                    label=os.path.basename(file_path), 
                    linewidth=1.5,
                    alpha=0.7)
            
            print(f"成功加载: {os.path.basename(file_path)} - {len(df)} 个数据点")
            
        except Exception as e:
            print(f"读取文件 {os.path.basename(file_path)} 时出错: {e}")
    
    # 设置图表属性
    plt.xlabel('Time (μs)', fontsize=12)
    plt.ylabel('Amplitude', fontsize=12)
    plt.title('Multiple CSV Files Overlay Plot', fontsize=14)
    plt.grid(True, alpha=0.3)
    plt.legend(bbox_to_anchor=(1.05, 1), loc='upper left')
    plt.tight_layout()
    
    # 显示图表
    plt.show()

# 使用方法示例
if __name__ == "__main__":
    # 方法1: 使用当前目录的所有CSV文件
    plot_multiple_csv_files()
    

    plot_multiple_csv_files(folder_path=r"data\results\test\Noise suppression\TEST1\data_ali")
    
    # 方法3: 使用特定的文件模式
    # plot_multiple_csv_files(file_pattern="data_*.csv")
