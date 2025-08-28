import numpy as np
import matplotlib.pyplot as plt
from scipy.fft import fft, fftfreq, ifft
from scipy.signal import find_peaks, butter, filtfilt

def generate_10mhz_signal_with_10ps_rise(sample_rate=100e9, duration=100e-9, frequency=10e6):
    """
    生成10MHz信号，上升沿为10ps
    
    参数:
    sample_rate: 采样率 (Hz) - 需要足够高以捕捉10ps上升沿
    duration: 信号持续时间 (秒)
    frequency: 信号频率 (Hz)
    """
    t = np.linspace(0, duration, int(sample_rate * duration), endpoint=False)
    
    # 生成10MHz正弦波
    signal = 0.5 * (1 + np.sin(2 * np.pi * frequency * t))
    
    # 在信号中间添加10ps的上升沿
    rise_time = 10e-12  # 10ps
    rise_start = duration / 2 - rise_time / 2
    rise_end = duration / 2 + rise_time / 2
    
    # 找到上升沿区域的索引
    rise_mask = (t >= rise_start) & (t <= rise_end)
    
    # 创建理想的阶跃上升沿
    ideal_step = np.zeros_like(t)
    ideal_step[t >= rise_start] = 1.0
    
    # 将理想上升沿与正弦波结合
    signal_with_rise = signal.copy()
    rise_region = ideal_step[rise_mask] * 0.5  # 调整幅度
    signal_with_rise[rise_mask] = signal[rise_mask] + rise_region
    
    # 归一化
    signal_with_rise = np.clip(signal_with_rise, 0, 1)
    
    return t, signal_with_rise, rise_start, rise_end

def generate_gaussian_10ps_rise(sample_rate=200e9, duration=200e-12):
    """
    生成高斯形状的10ps上升沿信号
    """
    t = np.linspace(0, duration, int(sample_rate * duration), endpoint=False)
    
    # 高斯上升沿参数
    rise_time = 10e-12  # 10ps
    center_time = duration / 2
    sigma = rise_time / (2 * np.sqrt(2 * np.log(2)))  # 转换为高斯sigma
    
    # 生成高斯上升沿
    signal = 0.5 * (1 + scipy.special.erf((t - center_time) / (sigma * np.sqrt(2))))
    
    return t, signal, center_time - rise_time/2, center_time + rise_time/2

def compute_difference(data: np.ndarray, diff_points: int = 1) -> np.ndarray:
    """计算数据的差分"""
    if diff_points >= len(data):
        diff_points = len(data) - 1
    return data[diff_points:] - data[:-diff_points]

def analyze_frequency_domain(t, signal, sample_rate, apply_diff=False, diff_points=1):
    """
    分析信号的频域特性并增强显示
    """
    # 如果需要，先进行差分处理
    if apply_diff:
        signal_to_analyze = compute_difference(signal, diff_points)
        t_to_analyze = t[diff_points:]  # 时间轴也要相应调整
    else:
        signal_to_analyze = signal
        t_to_analyze = t
    
    # 执行FFT
    n = len(signal_to_analyze)
    yf = fft(signal_to_analyze)
    xf = fftfreq(n, 1 / sample_rate)
    
    # 取正频率部分
    positive_freq_mask = xf > 0
    xf_positive = xf[positive_freq_mask]
    yf_positive = np.abs(yf[positive_freq_mask])
    
    # 应用对数尺度增强显示
    yf_log = 20 * np.log10(yf_positive + 1e-10)  # 避免log(0)
    
    return xf_positive, yf_positive, yf_log, yf, signal_to_analyze, t_to_analyze

def detect_rising_edge_from_frequency(signal, sample_rate, high_freq_threshold=0.8, 
                                     apply_diff=False, diff_points=1):
    """
    利用频域特性检测上升沿位置
    """
    n = len(signal)
    
    # 如果需要，先进行差分处理
    if apply_diff:
        signal_to_analyze = compute_difference(signal, diff_points)
    else:
        signal_to_analyze = signal
    
    # 执行FFT
    yf = fft(signal_to_analyze)
    xf = fftfreq(len(signal_to_analyze), 1 / sample_rate)
    
    # 找到高频成分的阈值
    magnitudes = np.abs(yf)
    max_magnitude = np.max(magnitudes)
    
    # 创建高频滤波器 - 针对10ps上升沿需要更高的截止频率
    high_freq_filter = np.ones_like(yf, dtype=complex)
    # 10ps上升沿对应的带宽约为35GHz，设置合适的截止频率
    cutoff_freq = 50e9  # 50GHz截止频率
    high_freq_filter[np.abs(xf) < cutoff_freq] = 0
    
    # 应用滤波器并执行逆FFT
    filtered_yf = yf * high_freq_filter
    filtered_signal = np.real(ifft(filtered_yf))
    
    # 找到高频能量最大的位置（对应上升沿）
    high_freq_energy = np.abs(filtered_signal) ** 2
    
    # 使用滑动窗口找到能量集中区域
    # 对于10ps上升沿，使用更小的窗口
    window_size = max(10, int(0.001 * sample_rate))  # 更小的窗口以适应快速变化
    
    if window_size > len(high_freq_energy):
        window_size = len(high_freq_energy) // 20
    
    if window_size % 2 == 0:  # 确保窗口大小为奇数
        window_size += 1
    
    smoothed_energy = np.convolve(high_freq_energy, np.ones(window_size)/window_size, mode='same')
    
    # 找到能量峰值
    peaks, properties = find_peaks(smoothed_energy, 
                                  height=np.max(smoothed_energy)*0.1,
                                  distance=window_size*2)
    
    if len(peaks) > 0:
        # 找到最显著的峰值
        peak_heights = smoothed_energy[peaks]
        main_peak_index = peaks[np.argmax(peak_heights)]
        
        # 调整时间索引（如果进行了差分处理）
        if apply_diff:
            main_peak_index += diff_points
        
        rising_edge_time = main_peak_index / sample_rate
        return rising_edge_time, filtered_signal, high_freq_energy, signal_to_analyze
    else:
        return None, filtered_signal, high_freq_energy, signal_to_analyze

def plot_enhanced_frequency_domain_high_speed(t, signal, xf, yf_linear, yf_log, 
                                            actual_rise_start, actual_rise_end,
                                            detected_rise_time=None, filtered_signal=None,
                                            diff_signal=None, t_diff=None, apply_diff=False):
    """
    绘制高速信号的频域显示
    """
    if apply_diff:
        fig, axes = plt.subplots(5, 1, figsize=(12, 20))
    else:
        fig, axes = plt.subplots(4, 1, figsize=(12, 16))
    
    # 时域信号 - 聚焦在上升沿附近
    axes[0].plot(t * 1e12, signal, label='原始信号')  # 时间单位转换为ps
    axes[0].axvline(x=actual_rise_start * 1e12, color='r', linestyle='--', alpha=0.7, label='实际上升开始')
    axes[0].axvline(x=actual_rise_end * 1e12, color='g', linestyle='--', alpha=0.7, label='实际上升结束')
    
    if detected_rise_time is not None:
        axes[0].axvline(x=detected_rise_time * 1e12, color='m', linestyle='-', linewidth=2, 
                       label=f'检测到的上升沿: {detected_rise_time*1e12:.2f}ps')
    
    axes[0].set_title('时域信号 - 10ps上升沿')
    axes[0].set_xlabel('时间 (ps)')
    axes[0].set_ylabel('幅度')
    axes[0].grid(True)
    axes[0].legend()
    axes[0].set_xlim([(actual_rise_start - 50e-12) * 1e12, (actual_rise_end + 50e-12) * 1e12])
    
    # 差分信号（如果应用了差分）
    if apply_diff and diff_signal is not None and t_diff is not None:
        axes[1].plot(t_diff * 1e12, diff_signal, label='差分信号', color='orange')
        axes[1].set_title('差分处理后的信号')
        axes[1].set_xlabel('时间 (ps)')
        axes[1].set_ylabel('差分幅度')
        axes[1].grid(True)
        axes[1].legend()
        axes[1].set_xlim([(actual_rise_start - 50e-12) * 1e12, (actual_rise_end + 50e-12) * 1e12])
        plot_index = 2
    else:
        plot_index = 1
    
    # 线性频域 - 显示更高频率范围
    axes[plot_index].plot(xf / 1e9, yf_linear)  # 频率单位转换为GHz
    axes[plot_index].set_title('频域显示 (线性尺度)')
    axes[plot_index].set_xlabel('频率 (GHz)')
    axes[plot_index].set_ylabel('幅度')
    axes[plot_index].grid(True)
    axes[plot_index].set_xlim(0, min(100, max(xf)/1e9))  # 显示到100GHz
    
    # 对数频域
    axes[plot_index+1].plot(xf / 1e9, yf_log)
    axes[plot_index+1].set_title('频域显示 (对数尺度)')
    axes[plot_index+1].set_xlabel('频率 (GHz)')
    axes[plot_index+1].set_ylabel('幅度 (dB)')
    axes[plot_index+1].grid(True)
    axes[plot_index+1].set_xlim(0, min(100, max(xf)/1e9))
    
    # 高频能量分布
    if filtered_signal is not None:
        time_for_energy = t[:len(filtered_signal)]
        axes[plot_index+2].plot(time_for_energy * 1e12, np.abs(filtered_signal) ** 2, 
                               label='高频能量', color='purple')
        axes[plot_index+2].set_title('高频能量分布')
        axes[plot_index+2].set_xlabel('时间 (ps)')
        axes[plot_index+2].set_ylabel('高频能量')
        axes[plot_index+2].grid(True)
        axes[plot_index+2].legend()
        axes[plot_index+2].set_xlim([(actual_rise_start - 50e-12) * 1e12, (actual_rise_end + 50e-12) * 1e12])
        
        if detected_rise_time is not None:
            axes[plot_index+2].axvline(x=detected_rise_time * 1e12, color='m', linestyle='-', linewidth=2,
                           label=f'检测位置: {detected_rise_time*1e12:.2f}ps')
            axes[plot_index+2].legend()
    
    plt.tight_layout()
    plt.show()

def demonstrate_10ps_rising_edge():
    """
    演示10ps上升沿的检测
    """
    # 设置参数
    sample_rate = 500e9  # 500GS/s采样率，满足10ps上升沿的奈奎斯特要求
    duration = 200e-12   # 200ps持续时间
    frequency = 10e6     # 10MHz信号
    
    print(f"采样率: {sample_rate/1e9:.0f} GS/s")
    print(f"上升沿: 10ps")
    print(f"信号频率: {frequency/1e6:.0f} MHz")
    
    # 生成信号
    t, signal, actual_rise_start, actual_rise_end = generate_10mhz_signal_with_10ps_rise(
        sample_rate, duration, frequency)
    
    # 添加一些噪声
    noise = np.random.normal(0, 0.01, len(signal))
    signal_noisy = signal + noise
    
    # 分析频域（有差分）
    print("\n=== 有差分处理 ===")
    diff_points = 3  # 较小的差分点数
    xf_diff, yf_linear_diff, yf_log_diff, yf_full_diff, diff_signal, t_diff = analyze_frequency_domain(
        t, signal_noisy, sample_rate, apply_diff=True, diff_points=diff_points)
    
    detected_rise_time, filtered_signal, high_freq_energy, signal_to_analyze = detect_rising_edge_from_frequency(
        signal_noisy, sample_rate, apply_diff=True, diff_points=diff_points)
    
    # 绘制结果
    plot_enhanced_frequency_domain_high_speed(
        t, signal_noisy, xf_diff, yf_linear_diff, yf_log_diff,
        actual_rise_start, actual_rise_end,
        detected_rise_time, filtered_signal,
        diff_signal, t_diff, apply_diff=True)
    
    # 显示关键信息
    print(f"实际上升沿时间: {actual_rise_start*1e12:.2f}ps - {actual_rise_end*1e12:.2f}ps")
    print(f"上升沿持续时间: {(actual_rise_end - actual_rise_start)*1e12:.2f}ps")
    
    if detected_rise_time is not None:
        error = abs(detected_rise_time - actual_rise_start)
        print(f"检测到的上升沿时间: {detected_rise_time*1e12:.2f}ps")
        print(f"检测误差: {error*1e12:.2f}ps")
        
        # 计算理论最小误差（基于采样率）
        theoretical_error = 1 / sample_rate
        print(f"理论最小误差 (基于采样率): {theoretical_error*1e12:.2f}ps")
        
        if error <= theoretical_error * 2:
            print("✓ 检测精度接近理论极限")
        else:
            print("✗ 检测精度有待提高")
    
    # 分析频域特性
    max_freq_index = np.argmax(yf_linear_diff)
    max_freq = xf_diff[max_freq_index]
    print(f"\n频域分析:")
    print(f"主要频率成分: {max_freq/1e9:.2f} GHz")
    
    # 计算10ps上升沿的理论带宽
    theoretical_bandwidth = 0.35 / (10e-12)  # 0.35/tr
    print(f"10ps上升沿的理论带宽: {theoretical_bandwidth/1e9:.2f} GHz")
    
    # 找到-3dB点
    max_magnitude = np.max(yf_linear_diff)
    threshold_3db = max_magnitude / np.sqrt(2)
    above_3db = yf_linear_diff > threshold_3db
    if np.any(above_3db):
        bandwidth_3db = np.max(xf_diff[above_3db]) - np.min(xf_diff[above_3db])
        print(f"实测3dB带宽: {bandwidth_3db/1e9:.2f} GHz")

# 运行演示
demonstrate_10ps_rising_edge()
