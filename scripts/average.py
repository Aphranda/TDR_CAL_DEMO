import pandas as pd
import numpy as np
import os
import glob


def average_csv_files(folder_path, output_filename='averaged_data.csv'):
    """
    读取文件夹中的所有CSV文件，对Amplitude列进行平均
    
    参数:
    folder_path: 包含CSV文件的文件夹路径
    output_filename: 输出文件名
    """
    
    # 获取文件夹中所有的CSV文件
    csv_files = glob.glob(os.path.join(folder_path, "*.csv"))
    
    if not csv_files:
        print(f"在文件夹 {folder_path} 中没有找到CSV文件")
        return
    
    print(f"找到 {len(csv_files)} 个CSV文件")
    
    # 读取第一个文件作为基准
    first_file = pd.read_csv(csv_files[0])
    time_column = first_file['Time(us)']
    
    # 初始化振幅数据数组
    amplitude_data = np.zeros((len(time_column), len(csv_files)))
    
    # 读取所有文件的振幅数据
    for i, file in enumerate(csv_files):
        try:
            df = pd.read_csv(file)
            # 确保时间列一致
            if not np.array_equal(df['Time(us)'], time_column):
                print(f"警告: 文件 {file} 的时间列与其他文件不一致")
                continue
            amplitude_data[:, i] = df['Amplitude']
            print(f"已读取文件: {os.path.basename(file)}")
        except Exception as e:
            print(f"读取文件 {file} 时出错: {e}")
    
    # 计算平均值
    averaged_amplitude = np.mean(amplitude_data, axis=1)
    
    # 创建结果DataFrame
    result_df = pd.DataFrame({
        'Time(us)': time_column,
        'Amplitude': averaged_amplitude
    })
    
    # 保存结果
    result_df.to_csv(output_filename, index=False)
    print(f"平均数据已保存到: {output_filename}")
    
    # 显示统计信息
    print(f"\n统计信息:")
    print(f"时间点数量: {len(time_column)}")
    print(f"平均振幅范围: {averaged_amplitude.min():.2f} 到 {averaged_amplitude.max():.2f}")
    
    return result_df

def main():
    # 设置文件夹路径
    folder_path = r"data\results\test\Noise suppression\TEST1\20位数据\10000次平均结果"
    
    # 如果路径为空，使用当前目录
    if not folder_path:
        folder_path = "."
    
    # 检查文件夹是否存在
    if not os.path.exists(folder_path):
        print(f"错误: 文件夹 {folder_path} 不存在")
        return
    
    # 执行平均计算
    try:
        result = average_csv_files(folder_path)
        
        # 显示前几行结果
        if result is not None:
            print("\n前5行平均数据:")
            print(result.head())
            
    except Exception as e:
        print(f"处理过程中出错: {e}")

if __name__ == "__main__":
    main()
