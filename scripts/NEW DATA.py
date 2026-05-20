#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AD4080 高速数据采集与分析脚本
==============================
功能：通过 TCP/UDP 协议从远端客户端获取 ADC 采样数据，进行以下处理：
  1. 19-bit ADC 解码
  2. 等效时间采样恢复（equivalent-time recovery）
  3. 上升沿检测与波形对齐
  4. ROI 频谱分析、差分分析
  5. 可视化（原始波形 / 恢复波形 / 对齐波形）
  6. CSV 导出

硬件平台：AD4080 前端 + LMK 时钟 + AD9508 采样时钟分发
通信模式：TCP（readall / chunk 分块读取）或 UDP（单向推送）
"""

import argparse
import concurrent.futures
import math
import os
import socket
import struct
import time
from dataclasses import dataclass

# 避免在无桌面的 Linux 服务器上报 matplotlib 缓存目录错误
os.environ.setdefault("MPLCONFIGDIR", "/tmp/matplotlib")

import matplotlib.pyplot as plt
import numpy as np
from numpy.lib.stride_tricks import sliding_window_view


# =============================================================================
# 网络与硬件常量
# =============================================================================
SERVER_HOST = "192.168.1.30"     # 采集服务器 IP
SERVER_PORT = 15000              # 控制通道 TCP 端口
DEFAULT_UDP_PORT = 15001         # UDP 数据接收起始端口（多通道时依次递增）

RECV_CHUNK = 65536               # TCP 接收缓冲区大小（字节）
SAMPLES_PER_BLOCK = 81920        # 每次 DMA 传输的样本点数（1 block）
SAMPLE_BYTES = 4                 # 每个样本 4 字节（32-bit 小端，仅低 19-bit 有效）

# =============================================================================
# 处理与显示默认参数
# =============================================================================
DEFAULT_RECOVER_POINTS = SAMPLES_PER_BLOCK  # 默认用于等效时间恢复的点数
DEFAULT_RAW_PLOT_POINTS = SAMPLES_PER_BLOCK  # 默认原始波形绘图点数
AUTO_RECOVER_MAX_POINTS = 2_000_000         # 自动开启恢复的采样点数上限
AUTO_PLOT_MAX_POINTS = 500_000              # 自动开启绘图的采样点数上限
DEFAULT_PLOT_MAX_POINTS = 200_000           # 绘图最大点数（超过则降采样）
AUTO_DIAG_MAX_POINTS = 8_000_000            # 自动开启原始数据诊断的采样点数上限
DEFAULT_START_INDEX = 70                    # 等效时间恢复的起始偏移（跳过前端不稳定点）
DEFAULT_ALIGN_POS = 2                       # 对齐目标位置 = recover_points // align_pos
DEFAULT_ROI_START_PERCENT = 20.0            # ROI 起始位置（占恢复波形百分比）
DEFAULT_ROI_END_PERCENT = 30.0              # ROI 结束位置（占恢复波形百分比）
DEFAULT_DIFF_POINTS = 10                    # 差分步长
DEFAULT_AVERAGE_POINTS = 3                  # 差分后移动平均窗口大小
DEFAULT_SPIKE_WINDOW = 5                    # Hampel 滤波器半窗口大小
DEFAULT_SPIKE_THRESHOLD = 3.0               # Hampel 滤波器 z-score 阈值
DEFAULT_EDGE_AMPLITUDE_RATIO = 0.5          # 上升沿检测的最小相对幅度比

# Savitzky-Golay 边缘平滑核（7 点二次多项式，归一化）
SG_EDGE_KERNEL = np.array(
    [-2.0, 3.0, 6.0, 7.0, 6.0, 3.0, -2.0], dtype=np.float64
) / 21.0

# AD4080 19-bit 有效位掩码
VALUE_MASK_19 = 0x7FFFF

# =============================================================================
# 硬件通道映射
# =============================================================================

# 探针板 LMK 输出映射表（参考 image/channel_clk.png）
# 用户通道 N 对应第 N 个 AD4080 前端
# LMK 提供触发时钟；AD9508 的 output 0 和 2 为采样时钟
# LMK 控制命令格式：lmk_state <lmk编号> <lmk通道> <0|1>
CHANNEL_TO_LMK = {
    1: (1, 4),   # 用户通道1 → LMK1, channel 4
    2: (1, 5),   # 用户通道2 → LMK1, channel 5
    3: (1, 6),   # 用户通道3 → LMK1, channel 6
    4: (1, 7),   # 用户通道4 → LMK1, channel 7
    5: (1, 0),   # 用户通道5 → LMK1, channel 0
    6: (1, 1),   # 用户通道6 → LMK1, channel 1
    7: (1, 2),   # 用户通道7 → LMK1, channel 2
    8: (1, 3),   # 用户通道8 → LMK1, channel 3
}

# LMK 工作模式编码
LMK_MODE_BYPASS = 0     # 直通
LMK_MODE_DIV = 1        # 分频
LMK_MODE_DELAY = 2      # 延时
LMK_MODE_DIV_DELAY = 3  # 分频+延时

# 模式名称到编码的映射（支持多种别名）
LMK_MODE_NAME_TO_VALUE = {
    "bypass": LMK_MODE_BYPASS,
    "div": LMK_MODE_DIV,
    "divide": LMK_MODE_DIV,
    "divided": LMK_MODE_DIV,
    "delay": LMK_MODE_DELAY,
    "delayed": LMK_MODE_DELAY,
    "div-delay": LMK_MODE_DIV_DELAY,
    "div-and-delay": LMK_MODE_DIV_DELAY,
    "div+delay": LMK_MODE_DIV_DELAY,
    "divdelay": LMK_MODE_DIV_DELAY,
    "divided-and-delayed": LMK_MODE_DIV_DELAY,
    "divide-and-delay": LMK_MODE_DIV_DELAY,
}

# AD9508 前端编号到 (器件号, 通道号) 的映射
# AD9508 输出 0 和 2 作为 AD4080 的采样时钟
AD9508_FRONTEND_TO_DEVICE_CHANNELS = {
    1: ((1, 0),),   # 前端1 → 器件1 通道0
    2: ((1, 2),),   # 前端2 → 器件1 通道2
    3: ((2, 0),),   # 前端3 → 器件2 通道0
    4: ((2, 2),),   # 前端4 → 器件2 通道2
    5: ((3, 0),),   # 前端5 → 器件3 通道0
    6: ((3, 2),),   # 前端6 → 器件3 通道2
    7: ((4, 0),),   # 前端7 → 器件4 通道0
    8: ((4, 2),),   # 前端8 → 器件4 通道2
}


# =============================================================================
# TCP 通信基础工具
# =============================================================================

def send(sock, cmd):
    """发送一行控制命令（自动追加换行符）"""
    sock.sendall(cmd.encode() + b"\n")


class Reader:
    """TCP 流式读取器，内部维护接收缓冲区"""
    def __init__(self, sock):
        self.sock = sock
        self.buf = bytearray()

    def _recv(self):
        """从 socket 读取一块数据到内部缓冲区"""
        data = self.sock.recv(RECV_CHUNK)
        if not data:
            raise RuntimeError("socket closed")
        self.buf.extend(data)

    def read_exact(self, size):
        """读取精确 size 个字节"""
        while len(self.buf) < size:
            self._recv()

        out = bytes(self.buf[:size])
        del self.buf[:size]
        return out

    def read_line(self):
        """读取一行（以换行符分隔）"""
        while True:
            idx = self.buf.find(b"\n")

            if idx >= 0:
                line = self.buf[:idx]
                del self.buf[: idx + 1]
                return line.decode()

            self._recv()


# =============================================================================
# ADC 数据解码
# =============================================================================

def decode_19bit(raw_bytes):
    """将原始字节流解码为 19-bit ADC 有符号值
    - 输入：32-bit 小端 word
    - 取低 19 bit（VALUE_MASK_19）
    - 按 bit18 进行符号扩展（左移 13 位后算术右移 13 位）
    """
    words = np.frombuffer(raw_bytes, dtype=np.dtype("<u4"))
    adc = words.astype(np.int32, copy=True)
    np.bitwise_and(adc, VALUE_MASK_19, out=adc)
    np.left_shift(adc, 13, out=adc)   # 左移到 int32 最高 19 bit
    np.right_shift(adc, 13, out=adc)  # 算术右移完成符号扩展
    return adc


def compute_raw_diagnostics(raw_bytes):
    """计算原始字节的诊断统计（验证数据有效位）
    返回：raw19 范围、中间位非零数量、高位非零数量
    """
    words = np.frombuffer(raw_bytes, dtype=np.dtype("<u4"))
    raw19 = words & VALUE_MASK_19
    raw_mid_bits = (raw19 >> 5) & ((1 << 11) - 1)
    return {
        "raw_min": int(np.min(raw19)),
        "raw_max": int(np.max(raw19)),
        "raw_mid_nonzero": int(np.count_nonzero(raw_mid_bits)),
        "high_nonzero": int(np.count_nonzero(words >> 19)),
    }


# =============================================================================
# 等效时间采样恢复（Equivalent-Time Recovery）
# =============================================================================
# 原理：利用采样时钟与触发时钟的频率差，将多次采样的数据按相位重排，
#       实现远高于实时采样率的等效时间分辨率。
#       fs_eff = N × f_trigger（N 为参与恢复的采样点数）


def recover_equivalent_time(adc, clock_freq, trigger_freq):
    """执行等效时间恢复的完整流程：构建计划 → 重排数据"""
    plan = build_equivalent_time_plan(len(adc), clock_freq, trigger_freq)
    y_recovered = apply_equivalent_time_plan(np.asarray(adc), plan)
    return plan.t_recovered_s, y_recovered, plan.sort_idx


def save_recovered_csv(path, t_recovered, y_recovered, raw_recovered, sort_idx):
    """将恢复后的数据保存为 CSV（时间/ADC值/原始值/原始索引）"""
    out_mat = np.column_stack(
        [
            t_recovered,
            t_recovered * 1e9,
            y_recovered,
            raw_recovered,
            sort_idx,
        ]
    )
    np.savetxt(
        path,
        out_mat,
        delimiter=",",
        header="time_s,time_ns,adc,raw19,original_index",
        comments="",
        fmt=["%.12e", "%.9f", "%.0f", "%d", "%d"],
    )


@dataclass(frozen=True)
class EquivalentTimePlan:
    """等效时间恢复计划（不可变）"""
    point_count: int               # 参与恢复的点数
    fs_eff: float                  # 等效采样率 (Hz)
    ts_eff: float                  # 等效时间间隔 (s)
    sort_idx: np.ndarray           # 相位排序索引
    t_recovered_s: np.ndarray      # 排序后的非均匀时间轴
    t_uniform_s: np.ndarray        # 均匀插值后的时间轴


@dataclass(frozen=True)
class AnalysisConfig:
    """后处理分析参数（不可变）"""
    start_index: int               # 恢复起始偏移
    align_pos: int                 # 对齐位置分母
    roi_start_percent: float       # ROI 起始百分比
    roi_end_percent: float         # ROI 结束百分比
    diff_points: int               # 差分包络步长
    average_points: int            # 移动平均窗口
    spike_window: int              # Hampel 滤波器半窗口
    spike_threshold: float         # Hampel 滤波器阈值
    min_edge_amplitude_ratio: float  # 最小边沿幅度比
    edge_method: str               # 边沿检测方法："rising" 或 "max"


def validate_analysis_config(config):
    """校验分析配置参数的合法性"""
    if config.start_index < 0:
        raise SystemExit("--start-index must be >= 0")
    if config.align_pos <= 0:
        raise SystemExit("--align-pos must be > 0")
    if config.roi_start_percent < 0 or config.roi_start_percent >= 100:
        raise SystemExit("--roi-start-percent must be in [0, 100)")
    if config.roi_end_percent <= 0 or config.roi_end_percent > 100:
        raise SystemExit("--roi-end-percent must be in (0, 100]")
    if config.roi_start_percent >= config.roi_end_percent:
        raise SystemExit("--roi-start-percent must be < --roi-end-percent")
    if config.diff_points < 1:
        raise SystemExit("--diff-points must be > 0")
    if config.average_points < 1:
        raise SystemExit("--average-points must be > 0")
    if config.spike_window < 0:
        raise SystemExit("--spike-window must be >= 0")
    if config.spike_threshold <= 0:
        raise SystemExit("--spike-threshold must be > 0")
    if config.min_edge_amplitude_ratio <= 0:
        raise SystemExit("--min-edge-amplitude-ratio must be > 0")
    if config.edge_method not in ("rising", "max"):
        raise SystemExit("--edge-method must be rising or max")


def build_equivalent_time_plan(point_count, clock_freq, trigger_freq):
    """构建等效时间恢复计划
    - 计算每个采样点相对于触发周期的相位
    - 按相位排序得到等效时间重排索引
    - 等效采样率 fs_eff = point_count × trigger_freq
    """
    point_count = int(point_count)
    if point_count <= 0:
        raise ValueError("point_count must be > 0")

    sample_index = np.arange(point_count, dtype=np.float64)
    # 计算每个采样点在触发周期内的相位（0~1）
    phase_cycles = np.mod(sample_index * (trigger_freq / clock_freq), 1.0)
    sort_idx = np.argsort(phase_cycles, kind="stable")
    t_recovered_s = phase_cycles[sort_idx] / trigger_freq
    fs_eff = point_count * trigger_freq
    ts_eff = 1.0 / fs_eff
    t_uniform_s = np.arange(point_count, dtype=np.float64) * ts_eff
    return EquivalentTimePlan(
        point_count=point_count,
        fs_eff=fs_eff,
        ts_eff=ts_eff,
        sort_idx=sort_idx,
        t_recovered_s=t_recovered_s,
        t_uniform_s=t_uniform_s,
    )


def apply_equivalent_time_plan(adc_segment, plan):
    """按等效时间计划重排 ADC 数据"""
    return adc_segment[plan.sort_idx]


# =============================================================================
# 信号平滑与预处理
# =============================================================================

def convolve_same_edge(data, kernel):
    """执行 same-size 卷积（edge 填充模式），用于边缘保持平滑"""
    radius = kernel.size // 2
    data_float = np.asarray(data, dtype=np.float64)
    if data_float.size == 0 or radius == 0:
        return data_float.copy()
    padded = np.pad(data_float, (radius, radius), mode="edge")
    return np.convolve(padded, kernel, mode="valid")


def smooth_edge_signal(data):
    """使用 Savitzky-Golay 核对信号进行边缘保持平滑"""
    if len(data) < SG_EDGE_KERNEL.size:
        return np.asarray(data, dtype=np.float64).copy()
    return convolve_same_edge(data, SG_EDGE_KERNEL)


def smooth_uniform(data, window_size):
    """均匀移动平均平滑（窗口大小自动调整为奇数）"""
    data_float = np.asarray(data, dtype=np.float64)
    if data_float.size == 0 or window_size <= 1:
        return data_float.copy()
    window_size = int(window_size)
    if window_size % 2 == 0:
        window_size += 1  # 确保奇数窗口
    kernel = np.full(window_size, 1.0 / float(window_size), dtype=np.float64)
    return convolve_same_edge(data_float, kernel)


def remove_spikes_hampel_fast(data, window_size, threshold):
    data_float = np.asarray(data, dtype=np.float64)
    if window_size <= 0 or data_float.size < 2 * window_size + 1:
        return data_float.copy(), np.empty(0, dtype=np.int32)

    windows = sliding_window_view(data_float, 2 * window_size + 1)
    neighbors = np.concatenate(
        (windows[:, :window_size], windows[:, window_size + 1 :]), axis=1
    )
    medians = np.median(neighbors, axis=1)
    mad = np.median(np.abs(neighbors - medians[:, None]), axis=1)
    centers = windows[:, window_size]
    valid = mad > 1e-10
    z_scores = np.zeros_like(centers)
    z_scores[valid] = 0.6745 * (centers[valid] - medians[valid]) / mad[valid]
    spike_mask = np.abs(z_scores) > threshold
    spike_idx = np.flatnonzero(spike_mask).astype(np.int32) + window_size
    cleaned = data_float.copy()
    if spike_idx.size:
        cleaned[spike_idx] = medians[spike_mask]
    return cleaned, spike_idx


def is_spike_noise(data, candidate_pos, window_size=3):
    if candidate_pos < window_size or candidate_pos >= len(data) - window_size:
        return False
    left_window = data[candidate_pos - window_size : candidate_pos]
    right_window = data[candidate_pos + 1 : candidate_pos + window_size + 1]
    candidate_value = data[candidate_pos]
    left_avg = float(np.mean(left_window))
    right_avg = float(np.mean(right_window))
    if (
        candidate_value > left_avg * 1.5
        and candidate_value > right_avg * 1.5
        and abs(left_avg - right_avg) < (abs(left_avg) + abs(right_avg) + 1e-12) * 0.2
    ):
        return True
    return False


def judge_background_noise(data, segment_length=256, k=1.5):
    data_float = np.asarray(data, dtype=np.float64)
    if data_float.ndim != 1 or data_float.size == 0:
        return True
    if data_float.size < segment_length:
        segments = data_float.reshape(1, -1)
    else:
        usable = (data_float.size // segment_length) * segment_length
        segments = data_float[:usable].reshape(-1, segment_length)
    segment_rms = np.sqrt(np.mean(segments * segments, axis=1))
    noise_level = float(np.min(segment_rms))
    total_rms = float(np.sqrt(np.mean(data_float * data_float)))
    return total_rms < k * noise_level


def find_edges_by_differential(smoothed_data, is_rising=True):
    if len(smoothed_data) < 20:
        return []

    dy = np.diff(smoothed_data)
    if is_rising:
        interest = dy[dy > 0]
    else:
        interest = -dy[dy < 0]
    if interest.size == 0:
        return []

    threshold = float(np.percentile(interest, 80))
    if is_rising:
        peaks = np.flatnonzero(dy > threshold) + 1
    else:
        peaks = np.flatnonzero(dy < -threshold) + 1

    valid_candidates = []
    for peak in peaks:
        dy_pos = peak - 1
        start = max(0, dy_pos - 5)
        end = min(dy.size, dy_pos + 6)
        local_window = dy[start:end]
        if local_window.size == 0:
            continue
        local_idx = np.argmax(local_window) if is_rising else np.argmin(local_window)
        if start + local_idx != dy_pos:
            continue
        if peak < 10 or peak >= len(smoothed_data) - 10:
            continue
        pre_avg = float(np.mean(smoothed_data[peak - 10 : peak - 2]))
        post_avg = float(np.mean(smoothed_data[peak + 2 : peak + 10]))
        amplitude = post_avg - pre_avg if is_rising else pre_avg - post_avg
        if amplitude > 0:
            valid_candidates.append((int(peak), amplitude))
    valid_candidates.sort(key=lambda item: item[1], reverse=True)
    return valid_candidates


def find_edge_candidates(smoothed_data, is_rising=True, min_amplitude_ratio=0.5):
    if len(smoothed_data) < 20:
        return []
    if judge_background_noise(smoothed_data):
        return find_edges_by_differential(smoothed_data, is_rising)

    window_size = max(10, int(len(smoothed_data) * 0.05))
    step_size = max(5, int(len(smoothed_data) * 0.03))
    threshold = float(np.ptp(smoothed_data) * min_amplitude_ratio)
    if threshold <= 0:
        return find_edges_by_differential(smoothed_data, is_rising)

    candidate_windows = []
    for start in range(0, len(smoothed_data) - window_size, step_size):
        end = start + window_size
        window_p2p = float(np.ptp(smoothed_data[start:end]))
        if window_p2p > threshold:
            candidate_windows.append((start, end))
    if not candidate_windows:
        return find_edges_by_differential(smoothed_data, is_rising)

    window_means = np.array(
        [np.mean(smoothed_data[start:end]) for start, end in candidate_windows],
        dtype=np.float64,
    )
    mean_of_means = float(np.mean(window_means))
    std_of_means = float(np.std(window_means))
    valid_windows = []
    for idx, pair in enumerate(candidate_windows):
        if std_of_means == 0.0 or abs(window_means[idx] - mean_of_means) < 2.0 * std_of_means:
            valid_windows.append(pair)
    if not valid_windows:
        valid_windows = candidate_windows

    valid_candidates = []
    compare_window = max(5, int(len(smoothed_data) * 0.02))
    for start, end in valid_windows:
        window_data = smoothed_data[start:end]
        dy = np.diff(window_data)
        if dy.size == 0:
            continue
        if is_rising:
            dy_threshold = float(np.max(dy) * 0.3)
            candidate_indices = np.flatnonzero(dy > dy_threshold) + 1
        else:
            dy_threshold = float(np.min(dy) * 0.3)
            candidate_indices = np.flatnonzero(dy < dy_threshold) + 1

        for candidate in candidate_indices:
            global_pos = start + int(candidate)
            if global_pos < 20 or global_pos >= len(smoothed_data) - 20:
                continue
            if is_spike_noise(smoothed_data, global_pos, 3):
                continue
            pre_avg = float(
                np.mean(smoothed_data[max(0, global_pos - compare_window) : global_pos])
            )
            post_avg = float(
                np.mean(
                    smoothed_data[
                        global_pos : min(len(smoothed_data), global_pos + compare_window)
                    ]
                )
            )
            if abs(pre_avg - post_avg) < threshold * 0.1:
                continue
            if is_rising and post_avg > pre_avg:
                valid_candidates.append((global_pos, post_avg - pre_avg))
            elif (not is_rising) and post_avg < pre_avg:
                valid_candidates.append((global_pos, pre_avg - post_avg))

    if not valid_candidates:
        return find_edges_by_differential(smoothed_data, is_rising)
    return valid_candidates


def find_rise_position(sorted_data, edge_method, min_edge_amplitude_ratio):
    if len(sorted_data) == 0:
        return 0
    if edge_method == "max":
        return int(np.argmax(sorted_data))

    smoothed = smooth_edge_signal(sorted_data)
    candidates = find_edge_candidates(smoothed, True, min_edge_amplitude_ratio)
    if candidates:
        candidates.sort(key=lambda item: item[1], reverse=True)
        return int(candidates[0][0])
    if len(smoothed) > 1:
        return int(np.argmax(np.diff(smoothed)) + 1)
    return 0


def align_data(sorted_data, rise_pos, target_position):
    if len(sorted_data) == 0:
        return np.asarray(sorted_data, dtype=np.float64).copy()
    shift = (int(target_position) - int(rise_pos)) % len(sorted_data)
    return np.roll(sorted_data, shift)


def compute_difference(data, diff_points):
    if diff_points <= 0 or len(data) <= diff_points:
        return np.empty(0, dtype=np.float64)
    data_float = np.asarray(data, dtype=np.float64)
    return data_float[diff_points:] - data_float[:-diff_points]


def compute_spectrum(data, ts_eff):
    data_float = np.asarray(data, dtype=np.float64)
    if data_float.size == 0:
        return (
            np.empty(0, dtype=np.float64),
            np.empty(0, dtype=np.float64),
            np.empty(0, dtype=np.complex128),
        )
    data_centered = data_float - np.mean(data_float)
    window = np.hanning(data_centered.size)
    windowed_data = data_centered * window
    fft_result = np.fft.rfft(windowed_data)
    freq = np.fft.rfftfreq(data_centered.size, d=ts_eff)
    scale = float(np.sum(window))
    magnitude_linear = np.abs(fft_result) / (scale + 1e-12)
    return freq, magnitude_linear, fft_result


def percent_to_index(percent, size):
    if size <= 0:
        return 0
    idx = int(size * percent / 100.0)
    return max(0, min(size, idx))


def dominant_spectrum_peak(freq, magnitude):
    if freq.size <= 1 or magnitude.size <= 1:
        return None, None
    peak_idx = int(np.argmax(magnitude[1:]) + 1)
    return float(freq[peak_idx]), float(magnitude[peak_idx])


def analyze_recovered_waveform(y_recovered, plan, config):
    if y_recovered.size == 0:
        return None

    y_clean, spike_idx = remove_spikes_hampel_fast(
        y_recovered, config.spike_window, config.spike_threshold
    )
    rise_pos = find_rise_position(
        y_clean, config.edge_method, config.min_edge_amplitude_ratio
    )
    align_target = plan.point_count // config.align_pos
    y_aligned = align_data(y_clean, rise_pos, align_target)

    roi_start = percent_to_index(config.roi_start_percent, plan.point_count)
    roi_end = percent_to_index(config.roi_end_percent, plan.point_count)
    roi_end = max(roi_end, roi_start + 1)
    y_roi = y_aligned[roi_start:roi_end]

    y_full_diff = smooth_uniform(
        compute_difference(y_aligned, config.diff_points), config.average_points
    )
    y_roi_diff = smooth_uniform(
        compute_difference(y_roi, config.diff_points), config.average_points
    )
    freq_roi, mag_roi, _ = compute_spectrum(y_roi, plan.ts_eff)
    freq_diff, mag_diff, _ = compute_spectrum(y_roi_diff, plan.ts_eff)
    roi_peak_freq, roi_peak_mag = dominant_spectrum_peak(freq_roi, mag_roi)
    diff_peak_freq, diff_peak_mag = dominant_spectrum_peak(freq_diff, mag_diff)

    return {
        "spike_indices": spike_idx,
        "rise_pos": int(rise_pos),
        "align_target": int(align_target),
        "y_clean": y_clean,
        "y_aligned": y_aligned,
        "y_roi": y_roi,
        "y_full_diff": y_full_diff,
        "y_roi_diff": y_roi_diff,
        "roi_start": int(roi_start),
        "roi_end": int(roi_end),
        "freq_roi": freq_roi,
        "mag_roi": mag_roi,
        "freq_diff": freq_diff,
        "mag_diff": mag_diff,
        "roi_peak_freq": roi_peak_freq,
        "roi_peak_mag": roi_peak_mag,
        "diff_peak_freq": diff_peak_freq,
        "diff_peak_mag": diff_peak_mag,
    }


def choose_auto_mode(points, explicit_value, auto_limit):
    if explicit_value is not None:
        return explicit_value
    return points <= auto_limit


def downsample_for_plot(y, x=None, max_points=DEFAULT_PLOT_MAX_POINTS):
    if len(y) <= max_points:
        return x, y

    stride = max(1, math.ceil(len(y) / max_points))
    if x is None:
        return None, y[::stride]
    return x[::stride], y[::stride]


def parse_channels(channel_arg=None, channels_arg=""):
    if channels_arg:
        parts = [part.strip() for part in channels_arg.split(",")]
        channels = []
        for part in parts:
            if not part:
                continue
            ch = int(part, 0)
            if ch < 1 or ch > 8:
                raise SystemExit(f"invalid channel: {ch}")
            if ch not in channels:
                channels.append(ch)
        if not channels:
            raise SystemExit("--channels is empty")
        return channels

    if channel_arg is None:
        return [1]

    if channel_arg < 1 or channel_arg > 8:
        raise SystemExit("--channel must be 1..8")
    return [channel_arg]


def expand_comma_items(items):
    expanded = []
    for item in items:
        for part in item.split(","):
            part = part.strip()
            if part:
                expanded.append(part)
    return expanded


def build_link_mask(channels):
    mask = 0
    for channel in channels:
        mask |= 1 << (channel - 1)
    return mask


def parse_lmk_channel_args(items, state_name):
    toggles = []
    for item in expand_comma_items(items):
        channel = int(item, 0)
        if channel not in CHANNEL_TO_LMK:
            raise SystemExit(f"channel {channel} has no LMK mapping")
        state = 1 if state_name == "on" else 0
        toggles.append((channel, state))
    return toggles


def parse_lmk_div_args(items):
    dividers = []
    for item in expand_comma_items(items):
        fields = [field.strip() for field in item.split(":")]
        if len(fields) != 2:
            raise SystemExit(
                f"invalid clock div '{item}', expected channel:div"
            )
        channel = int(fields[0], 0)
        div = int(fields[1], 0)
        if channel not in CHANNEL_TO_LMK:
            raise SystemExit(f"channel {channel} has no LMK mapping")
        if div < 2 or div > 510 or (div & 1):
            raise SystemExit(
                f"invalid divider '{div}' in '{item}', use an even value in 2..510"
            )
        dividers.append((channel, div))
    return dividers


def parse_lmk_delay_args(items):
    delays = []
    for item in expand_comma_items(items):
        fields = [field.strip() for field in item.split(":")]
        if len(fields) != 2:
            raise SystemExit(
                f"invalid clock delay '{item}', expected channel:delay"
            )
        channel = int(fields[0], 0)
        delay = int(fields[1], 0)
        if channel not in CHANNEL_TO_LMK:
            raise SystemExit(f"channel {channel} has no LMK mapping")
        if delay < 0 or delay > 2250:
            raise SystemExit(
                f"invalid delay '{delay}' in '{item}', use a value in 0..2250 ps"
            )
        delays.append((channel, delay))
    return delays


def parse_lmk_mode_args(items):
    modes = []
    for item in expand_comma_items(items):
        fields = [field.strip() for field in item.split(":")]
        if len(fields) != 2:
            raise SystemExit(
                f"invalid clock mode '{item}', expected channel:mode"
            )
        channel = int(fields[0], 0)
        mode_name = (
            fields[1].strip().lower().replace(" ", "-").replace("_", "-")
        )
        if channel not in CHANNEL_TO_LMK:
            raise SystemExit(f"channel {channel} has no LMK mapping")
        if mode_name not in LMK_MODE_NAME_TO_VALUE:
            raise SystemExit(
                f"invalid mode '{fields[1]}' in '{item}', use bypass/div/delay/div-delay"
            )
        modes.append((channel, LMK_MODE_NAME_TO_VALUE[mode_name]))
    return modes


def parse_ad9508_frontend_args(items):
    frontends = []
    for item in expand_comma_items(items):
        frontend = int(item, 0)
        if frontend < 1 or frontend > 8:
            raise SystemExit("ad9508 frontend must be 1..8")
        if frontend not in frontends:
            frontends.append(frontend)
    return frontends


def parse_power_channel_args(items):
    channels = []
    for item in expand_comma_items(items):
        channel = int(item, 0)
        if channel < 1 or channel > 8:
            raise SystemExit("power channel must be 1..8")
        if channel not in channels:
            channels.append(channel)
    return channels


def run_control_commands(host, port, commands, timeout=5, require_okay=True):
    if not commands:
        return [], 0.0

    replies = []
    total_start = time.perf_counter()
    connect_start = time.perf_counter()
    with socket.create_connection((host, port), timeout=timeout) as sock:
        connect_elapsed = time.perf_counter() - connect_start
        sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        reader = Reader(sock)
        for cmd in commands:
            cmd_start = time.perf_counter()
            send(sock, cmd)
            reply = reader.read_line()
            cmd_elapsed = time.perf_counter() - cmd_start
            replies.append(
                {
                    "cmd": cmd,
                    "reply": reply,
                    "elapsed_s": cmd_elapsed,
                }
            )
            if require_okay and reply != "okay":
                raise RuntimeError(f"control command failed: {cmd} -> {reply}")
    if replies:
        replies[0]["connect_s"] = connect_elapsed
    return replies, time.perf_counter() - total_start


def apply_clock_toggles(host, port, toggles):
    commands = []
    for channel, state in toggles:
        lmk, lmk_channel = CHANNEL_TO_LMK[channel]
        commands.append(f"lmk_state {lmk} {lmk_channel} {state}")
    return run_control_commands(host, port, commands)


def apply_clock_configuration(host, port, toggles, modes, dividers, delays, raw_cmds):
    commands = []
    mode_by_channel = {}
    has_div = set()
    has_delay = set()

    for channel, mode in modes:
        mode_by_channel[channel] = mode
    for channel, div in dividers:
        has_div.add(channel)
    for channel, delay in delays:
        has_delay.add(channel)

    for channel in sorted(has_div | has_delay):
        if channel in mode_by_channel:
            continue
        if channel in has_div and channel in has_delay:
            mode_by_channel[channel] = LMK_MODE_DIV_DELAY
        elif channel in has_div:
            mode_by_channel[channel] = LMK_MODE_DIV
        else:
            mode_by_channel[channel] = LMK_MODE_DELAY

    for channel, mode in sorted(mode_by_channel.items()):
        lmk, lmk_channel = CHANNEL_TO_LMK[channel]
        commands.append(f"lmk_mode {lmk} {lmk_channel} {mode}")
    for channel, div in dividers:
        lmk, lmk_channel = CHANNEL_TO_LMK[channel]
        commands.append(f"lmk_div {lmk} {lmk_channel} {div}")
    for channel, delay in delays:
        lmk, lmk_channel = CHANNEL_TO_LMK[channel]
        commands.append(f"lmk_delay {lmk} {lmk_channel} {delay}")
    for channel, state in toggles:
        lmk, lmk_channel = CHANNEL_TO_LMK[channel]
        commands.append(f"lmk_state {lmk} {lmk_channel} {state}")
    commands.extend(raw_cmds)
    return run_control_commands(host, port, commands)


def apply_ad9508_configuration(host, port, off_frontends, on_frontends):
    commands = []
    for frontend in off_frontends:
        for dev, channel in AD9508_FRONTEND_TO_DEVICE_CHANNELS[frontend]:
            commands.append(f"ad9508_state {dev} {channel} 0")
    for frontend in on_frontends:
        for dev, channel in AD9508_FRONTEND_TO_DEVICE_CHANNELS[frontend]:
            commands.append(f"ad9508_state {dev} {channel} 1")
    return run_control_commands(host, port, commands)


def apply_power_configuration(host, port, off_channels, on_channels):
    commands = []
    for channel in off_channels:
        commands.append(f"power{channel} 0")
    for channel in on_channels:
        commands.append(f"power{channel} 1")
    return run_control_commands(host, port, commands)


def query_power_configuration(host, port, channels):
    commands = [f"power{channel}" for channel in channels]
    replies, elapsed = run_control_commands(host, port, commands, require_okay=False)
    for item in replies:
        if item["reply"] not in ("0", "1"):
            raise RuntimeError(
                f"power query failed: {item['cmd']} -> {item['reply']}"
            )
    return replies, elapsed


def read_link(sock, reader, channel, points, read_mode):
    need = points * SAMPLE_BYTES
    transfer_start = time.perf_counter()
    read_requests = 0

    if read_mode == "readall":
        read_requests = 1
        send(sock, f"readall{channel} {need}")
        hdr = reader.read_exact(4)
        (size,) = struct.unpack("!I", hdr)
        if size == 0:
            raise RuntimeError(f"empty read on link{channel}")
        data = reader.read_exact(size)
    else:
        data = bytearray()
        while len(data) < need:
            remain = need - len(data)
            send(sock, f"read{channel} {remain}")
            read_requests += 1

            hdr = reader.read_exact(4)
            (size,) = struct.unpack("!I", hdr)
            if size == 0:
                break
            data.extend(reader.read_exact(size))
        data = bytes(data)

    if len(data) < need:
        raise RuntimeError(
            f"short read on link{channel}: got {len(data) // SAMPLE_BYTES} points, want {points}"
        )

    transfer_elapsed = time.perf_counter() - transfer_start
    print(
        f"link{channel}: fetched {len(data)} bytes in {read_requests} read request(s), "
        f"transfer={transfer_elapsed:.3f}s"
    )

    return bytes(data[:need]), transfer_elapsed, read_requests


def recv_udp_capture(udp_sock, expected_bytes, channel, timeout_s, max_datagram):
    data = bytearray()
    packets = 0
    transfer_start = time.perf_counter()

    udp_sock.settimeout(timeout_s)

    while len(data) < expected_bytes:
        packet, _addr = udp_sock.recvfrom(max_datagram)
        if not packet:
            continue
        packets += 1
        data.extend(packet)

    transfer_elapsed = time.perf_counter() - transfer_start
    print(
        f"link{channel}: received {len(data)} bytes in {packets} udp packet(s), "
        f"transfer={transfer_elapsed:.3f}s"
    )

    return bytes(data[:expected_bytes]), transfer_elapsed, packets


def read_one_channel_tcp(host, port, channel, points, read_mode):
    connect_start = time.perf_counter()
    with socket.create_connection((host, port), timeout=5) as sock:
        connect_elapsed = time.perf_counter() - connect_start
        sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        reader = Reader(sock)
        raw, transfer_elapsed, read_requests = read_link(
            sock, reader, channel, points, read_mode
        )
        return {
            "raw": raw,
            "connect_s": connect_elapsed,
            "transfer_s": transfer_elapsed,
            "read_requests": read_requests,
        }


def read_one_channel_udp(
    host,
    port,
    channel,
    points,
    udp_port,
    udp_dst_mac,
    udp_payload,
    udp_timeout,
    udp_ifname,
    udp_bind_ip,
):
    expected_bytes = points * SAMPLE_BYTES

    connect_start = time.perf_counter()
    with socket.create_connection((host, port), timeout=5) as sock:
        connect_elapsed = time.perf_counter() - connect_start
        sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        reader = Reader(sock)
        bind_ip = udp_bind_ip or sock.getsockname()[0]

        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as udp_sock:
            udp_sock.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 8 * 1024 * 1024)
            udp_sock.bind((bind_ip, udp_port))

            trigger_start = time.perf_counter()
            send(
                sock,
                f"udp{channel} {bind_ip} {udp_port} {udp_dst_mac} "
                f"{udp_payload} 1 {udp_ifname}".rstrip(),
            )
            trigger_elapsed = time.perf_counter() - trigger_start
            raw, transfer_elapsed, udp_packets = recv_udp_capture(
                udp_sock,
                expected_bytes,
                channel,
                udp_timeout,
                max(65536, udp_payload + 256 if udp_payload > 0 else 65536),
            )

        ack = reader.read_line()
        if ack != "okay":
            raise RuntimeError(f"udp transfer failed on link{channel}: {ack}")

    return {
        "raw": raw,
        "connect_s": connect_elapsed,
        "trigger_s": trigger_elapsed,
        "transfer_s": transfer_elapsed,
        "udp_packets": udp_packets,
    }


def capture(
    host,
    port,
    points,
    channels,
    read_mode,
    data_mode,
    udp_port,
    udp_dst_mac,
    udp_payload,
    udp_timeout,
    udp_ifname,
    udp_bind_ip,
    skip_dma_reset=False,
):
    block_count = max(1, math.ceil(points / SAMPLES_PER_BLOCK))
    link_mask = build_link_mask(channels)
    total_start = time.perf_counter()

    connect_start = time.perf_counter()
    with socket.create_connection((host, port), timeout=5) as sock:
        control_connect_elapsed = time.perf_counter() - connect_start
        sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        reader = Reader(sock)
        sample_start = time.perf_counter()

        print(
            f"start sample: channels={channels} points={points} blocks={block_count} mask=0x{link_mask:x}"
        )
        send(sock, f"sample {block_count} 0x{link_mask:x}")
        ack = reader.read_line()
        if ack != "okay":
            raise RuntimeError(f"sample failed: {ack}")

        sample_elapsed = time.perf_counter() - sample_start
        print(f"sample stage took {sample_elapsed:.3f}s")

        transfer_start = time.perf_counter()
        results = {}

        if data_mode == "tcp":
            with concurrent.futures.ThreadPoolExecutor(
                max_workers=len(channels)
            ) as executor:
                future_map = {
                    executor.submit(
                        read_one_channel_tcp, host, port, channel, points, read_mode
                    ): channel
                    for channel in channels
                }
                for future in concurrent.futures.as_completed(future_map):
                    channel = future_map[future]
                    results[channel] = future.result()
        else:
            if not udp_dst_mac:
                raise RuntimeError("--udp-dst-mac is required in udp mode")

            with concurrent.futures.ThreadPoolExecutor(
                max_workers=len(channels)
            ) as executor:
                future_map = {}
                for idx, channel in enumerate(channels):
                    future = executor.submit(
                        read_one_channel_udp,
                        host,
                        port,
                        channel,
                        points,
                        udp_port + idx,
                        udp_dst_mac,
                        udp_payload,
                        udp_timeout,
                        udp_ifname,
                        udp_bind_ip,
                    )
                    future_map[future] = channel
                for future in concurrent.futures.as_completed(future_map):
                    channel = future_map[future]
                    results[channel] = future.result()

        transfer_total = time.perf_counter() - transfer_start

        reset_elapsed = 0.0
        if not skip_dma_reset:
            reset_start = time.perf_counter()
            send(sock, "dma_rst 1")
            ack = reader.read_line()
            if ack != "okay":
                raise RuntimeError(f"dma_rst failed: {ack}")
            reset_elapsed = time.perf_counter() - reset_start
            print(f"dma_rst stage took {reset_elapsed:.3f}s")

    total_elapsed = time.perf_counter() - total_start
    timings = {
        "control_connect_s": control_connect_elapsed,
        "sample_s": sample_elapsed,
        "transfer_total_s": transfer_total,
        "reset_s": reset_elapsed,
        "total_s": total_elapsed,
    }
    return results, timings


def format_output_csv(template, channel):
    if "{channel}" in template:
        return template.format(channel=channel)
    return template


def normalized_point_limit(limit, size):
    if limit <= 0:
        return size
    return min(size, limit)


def build_raw19_from_adc(adc):
    return np.bitwise_and(np.asarray(adc, dtype=np.int64), VALUE_MASK_19)


def save_analysis_csv(path, plan, analysis):
    point_count = plan.point_count
    roi_column = np.full(point_count, np.nan, dtype=np.float64)
    roi_column[analysis["roi_start"] : analysis["roi_end"]] = analysis["y_roi"]

    diff_column = np.full(point_count, np.nan, dtype=np.float64)
    diff_len = analysis["y_full_diff"].size
    if diff_len:
        diff_start = point_count - diff_len
        diff_column[diff_start:] = analysis["y_full_diff"]

    out_mat = np.column_stack(
        [
            plan.t_uniform_s,
            plan.t_uniform_s * 1e9,
            analysis["y_clean"],
            analysis["y_aligned"],
            roi_column,
            diff_column,
        ]
    )
    np.savetxt(
        path,
        out_mat,
        delimiter=",",
        header="time_s,time_ns,recovered_clean,aligned_adc,roi_adc,aligned_diff",
        comments="",
        fmt="%.12e",
    )


def print_channel_stats(channel, adc, diag):
    print(f"channel = {channel}")
    print("points =", len(adc))
    print("ADC 解码方式：32-bit 小端 word，取低 19 bit，按 bit18 符号扩展")
    print("min    =", int(np.min(adc)))
    print("max    =", int(np.max(adc)))
    print("mean   =", np.mean(adc))
    print("std    =", np.std(adc))
    if diag is not None:
        print(f"raw19 范围：0x{diag['raw_min']:05X} ~ 0x{diag['raw_max']:05X}")
        print(f"raw19[15:5] 非零数量：{diag['raw_mid_nonzero']}")
        print(f"word[31:19] 非零数量：{diag['high_nonzero']}")
    else:
        print("raw diagnostics skipped in fast mode")


def print_analysis_stats(channel, plan, config, analysis):
    rise_time_ns = analysis["rise_pos"] * plan.ts_eff * 1e9
    print(f"analysis link{channel}: start_index={config.start_index}")
    print(
        f"analysis link{channel}: rise_pos={analysis['rise_pos']} "
        f"rise_time={rise_time_ns:.3f} ns align_target={analysis['align_target']}"
    )
    print(
        f"analysis link{channel}: roi=[{analysis['roi_start']}, {analysis['roi_end']}) "
        f"spikes={analysis['spike_indices'].size} diff_points={config.diff_points}"
    )
    if analysis["roi_peak_freq"] is not None:
        print(
            f"analysis link{channel}: roi_peak={analysis['roi_peak_freq'] / 1e9:.3f} GHz "
            f"mag={analysis['roi_peak_mag']:.6g}"
        )
    if analysis["diff_peak_freq"] is not None:
        print(
            f"analysis link{channel}: diff_peak={analysis['diff_peak_freq'] / 1e9:.3f} GHz "
            f"mag={analysis['diff_peak_mag']:.6g}"
        )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default=SERVER_HOST)
    parser.add_argument("--port", type=int, default=SERVER_PORT)
    parser.add_argument("--points", "--point", dest="points", type=int, default=819200)
    parser.add_argument("--channel", type=int, default=None)
    parser.add_argument("--channels", default="")
    parser.add_argument("--clock-freq", type=float, default=39.53858777e6)
    parser.add_argument("--trigger-freq", type=float, default=10e6)
    parser.add_argument("--output-csv", default="ad4080_channel{channel}_recovered.csv")
    parser.add_argument(
        "--analysis-output-csv",
        default="ad4080_channel{channel}_analysis.csv",
    )
    parser.add_argument(
        "--save-csv",
        action="store_true",
        help="explicitly save recovered CSV files",
    )
    parser.add_argument(
        "--save-analysis-csv",
        action="store_true",
        help="save aligned/ROI/diff post-process CSV files",
    )
    parser.add_argument(
        "--read-mode", default="readall", choices=("readall", "chunk")
    )
    parser.add_argument("--data-mode", default="tcp", choices=("tcp", "udp"))
    parser.add_argument("--udp-port", type=int, default=DEFAULT_UDP_PORT)
    parser.add_argument("--udp-dst-mac", default="")
    parser.add_argument("--udp-payload", type=int, default=0)
    parser.add_argument("--udp-timeout", type=float, default=10.0)
    parser.add_argument("--udp-ifname", default="eth1")
    parser.add_argument("--udp-bind-ip", default="")
    parser.add_argument("--plot-max-points", type=int, default=DEFAULT_PLOT_MAX_POINTS)
    parser.add_argument(
        "--plot-raw-points",
        type=int,
        default=DEFAULT_RAW_PLOT_POINTS,
        help="raw waveform plot only uses the first N points; default 81920",
    )
    parser.add_argument(
        "--recover-points",
        type=int,
        default=DEFAULT_RECOVER_POINTS,
        help="equivalent-time recovery only uses the first N points; default 81920, 0 means all",
    )
    parser.add_argument(
        "--display-channel",
        type=int,
        default=None,
        help="which channel to plot/recover by default",
    )
    parser.add_argument(
        "--start-index",
        type=int,
        default=DEFAULT_START_INDEX,
        help="skip this many raw points before equivalent-time recovery",
    )
    parser.add_argument(
        "--align-pos",
        type=int,
        default=DEFAULT_ALIGN_POS,
        help="align recovered rising edge to recover_points // align_pos",
    )
    parser.add_argument(
        "--roi-start-percent",
        type=float,
        default=DEFAULT_ROI_START_PERCENT,
        help="ROI start in percent of recovered waveform length",
    )
    parser.add_argument(
        "--roi-end-percent",
        type=float,
        default=DEFAULT_ROI_END_PERCENT,
        help="ROI end in percent of recovered waveform length",
    )
    parser.add_argument(
        "--diff-points",
        type=int,
        default=DEFAULT_DIFF_POINTS,
        help="difference spacing used by the legacy post-process chain",
    )
    parser.add_argument(
        "--average-points",
        type=int,
        default=DEFAULT_AVERAGE_POINTS,
        help="moving-average window applied after differencing",
    )
    parser.add_argument(
        "--spike-window",
        type=int,
        default=DEFAULT_SPIKE_WINDOW,
        help="Hampel filter half-window size; 0 disables spike removal",
    )
    parser.add_argument(
        "--spike-threshold",
        type=float,
        default=DEFAULT_SPIKE_THRESHOLD,
        help="Hampel filter z-score threshold",
    )
    parser.add_argument(
        "--min-edge-amplitude-ratio",
        type=float,
        default=DEFAULT_EDGE_AMPLITUDE_RATIO,
        help="minimum relative edge amplitude used by rise detection",
    )
    parser.add_argument(
        "--edge-method",
        default="rising",
        choices=("rising", "max"),
        help="rising matches image/core edge search, max uses plain argmax",
    )
    parser.add_argument(
        "--skip-dma-reset",
        action="store_true",
        help="do not issue dma_rst after readback",
    )
    parser.add_argument(
        "--tri-off",
        action="append",
        default=[],
        metavar="CH",
        help="disable LMK output for channel CH and exit, e.g. --tri-off 1 or --tri-off 1,2,3,4",
    )
    parser.add_argument(
        "--tri-on",
        action="append",
        default=[],
        metavar="CH",
        help="enable LMK output for channel CH and exit, e.g. --tri-on 1 or --tri-on 1,2,3,4",
    )
    parser.add_argument(
        "--tri-raw",
        action="append",
        default=[],
        metavar="CMD",
        help="send raw control command and exit, e.g. 'lmk_state 1 4 0'",
    )
    parser.add_argument(
        "--tri-mode",
        action="append",
        default=[],
        metavar="CH:MODE",
        help="set LMK mode for channel CH and exit, MODE is bypass/div/delay/div-delay",
    )
    parser.add_argument(
        "--tri-div",
        action="append",
        default=[],
        metavar="CH:DIV",
        help="set divider for channel CH and exit; auto-selects div or div-delay mode if needed",
    )
    parser.add_argument(
        "--tri-delay",
        action="append",
        default=[],
        metavar="CH:DELAY",
        help="set delay in ps for channel CH and exit; auto-selects delay or div-delay mode if needed",
    )
    parser.add_argument(
        "--smp-off",
        action="append",
        default=[],
        metavar="DEV",
        help="disable AD9508 sample-clock frontends 1..8 and exit, e.g. --smp-off 1,2,3,4,5,6,7,8",
    )
    parser.add_argument(
        "--smp-on",
        action="append",
        default=[],
        metavar="DEV",
        help="enable AD9508 sample-clock frontends 1..8 and exit, e.g. --smp-on 1,2,3,4,5,6,7,8",
    )
    parser.add_argument(
        "--pow-off",
        action="append",
        default=[],
        metavar="CH",
        help="drive AD4080 power_enable inactive for channels 1..8 and exit, e.g. --pow-off 1,2",
    )
    parser.add_argument(
        "--pow-on",
        action="append",
        default=[],
        metavar="CH",
        help="drive AD4080 power_enable active for channels 1..8 and exit, e.g. --pow-on 1,2",
    )
    parser.add_argument(
        "--pow-stat",
        action="append",
        default=[],
        metavar="CH",
        help="query AD4080 power_enable state for channels 1..8 and exit, e.g. --pow-stat 1,2",
    )

    recover_group = parser.add_mutually_exclusive_group()
    recover_group.add_argument("--recover", dest="recover", action="store_true")
    recover_group.add_argument("--no-recover", dest="recover", action="store_false")
    parser.set_defaults(recover=None)

    plot_group = parser.add_mutually_exclusive_group()
    plot_group.add_argument("--plot", dest="plot", action="store_true")
    plot_group.add_argument("--no-plot", dest="plot", action="store_false")
    parser.set_defaults(plot=None)

    analysis_group = parser.add_mutually_exclusive_group()
    analysis_group.add_argument("--analyze", dest="analyze", action="store_true")
    analysis_group.add_argument("--no-analyze", dest="analyze", action="store_false")
    parser.set_defaults(analyze=None)

    args = parser.parse_args()

    channels = parse_channels(args.channel, args.channels)
    display_channel = args.display_channel or channels[0]
    if display_channel not in channels:
        raise SystemExit("--display-channel must be one of --channels")

    analysis_config = AnalysisConfig(
        start_index=args.start_index,
        align_pos=args.align_pos,
        roi_start_percent=args.roi_start_percent,
        roi_end_percent=args.roi_end_percent,
        diff_points=args.diff_points,
        average_points=args.average_points,
        spike_window=args.spike_window,
        spike_threshold=args.spike_threshold,
        min_edge_amplitude_ratio=args.min_edge_amplitude_ratio,
        edge_method=args.edge_method,
    )
    validate_analysis_config(analysis_config)

    if args.points <= 0:
        raise SystemExit("--points must be > 0")

    if args.trigger_freq <= 0:
        raise SystemExit("--trigger-freq must be > 0")
    if args.plot_max_points <= 0:
        raise SystemExit("--plot-max-points must be > 0")
    if args.plot_raw_points < 0:
        raise SystemExit("--plot-raw-points must be >= 0")
    if args.recover_points < 0:
        raise SystemExit("--recover-points must be >= 0")
    if args.udp_port <= 0 or args.udp_port > 65535:
        raise SystemExit("--udp-port must be 1..65535")
    if args.udp_payload < 0 or args.udp_payload > 65507:
        raise SystemExit("--udp-payload must be 0..65507")
    if args.udp_timeout <= 0:
        raise SystemExit("--udp-timeout must be > 0")
    if args.data_mode == "udp" and not args.udp_dst_mac:
        raise SystemExit("--udp-dst-mac is required when --data-mode udp")
    if args.data_mode == "udp" and args.udp_port + len(channels) - 1 > 65535:
        raise SystemExit("udp port range is too small for selected channels")

    recover_auto_points = (
        args.recover_points if args.recover_points > 0 else args.points
    )
    plot_auto_points = (
        args.plot_raw_points if args.plot_raw_points > 0 else args.points
    )
    do_recover = choose_auto_mode(
        recover_auto_points, args.recover, AUTO_RECOVER_MAX_POINTS
    )
    do_plot = choose_auto_mode(plot_auto_points, args.plot, AUTO_PLOT_MAX_POINTS)
    do_analysis = do_recover if args.analyze is None else args.analyze
    do_diag = args.points <= AUTO_DIAG_MAX_POINTS
    if do_analysis and not do_recover:
        raise SystemExit("analysis requires recovery; enable --recover or drop --analyze")

    script_start = time.perf_counter()
    clock_control_total = 0.0
    clock_control_replies = []
    clock_toggles = parse_lmk_channel_args(args.tri_on, "on")
    clock_toggles.extend(parse_lmk_channel_args(args.tri_off, "off"))
    clock_modes = parse_lmk_mode_args(args.tri_mode)
    clock_dividers = parse_lmk_div_args(args.tri_div)
    clock_delays = parse_lmk_delay_args(args.tri_delay)
    ad9508_off_frontends = parse_ad9508_frontend_args(args.smp_off)
    ad9508_on_frontends = parse_ad9508_frontend_args(args.smp_on)
    power_off_channels = parse_power_channel_args(args.pow_off)
    power_on_channels = parse_power_channel_args(args.pow_on)
    power_status_channels = parse_power_channel_args(args.pow_stat)
    control_only = bool(
        clock_toggles
        or clock_modes
        or clock_dividers
        or clock_delays
        or args.tri_raw
        or ad9508_off_frontends
        or ad9508_on_frontends
        or power_off_channels
        or power_on_channels
        or power_status_channels
    )

    if control_only:
        print("apply clock controls...")
        replies, elapsed = apply_clock_configuration(
            args.host,
            args.port,
            clock_toggles,
            clock_modes,
            clock_dividers,
            clock_delays,
            args.tri_raw,
        )
        clock_control_total += elapsed
        clock_control_replies.extend(replies)
        for item in replies:
            extra = ""
            if "connect_s" in item:
                extra = f" connect={item['connect_s']:.3f}s"
            print(
                f"{item['cmd']} -> {item['reply']}"
                f" cmd={item['elapsed_s']:.3f}s{extra}"
            )

    if ad9508_off_frontends or ad9508_on_frontends:
        print("apply ad9508 controls...")
        replies, elapsed = apply_ad9508_configuration(
            args.host, args.port, ad9508_off_frontends, ad9508_on_frontends
        )
        clock_control_total += elapsed
        clock_control_replies.extend(replies)
        for item in replies:
            extra = ""
            if "connect_s" in item:
                extra = f" connect={item['connect_s']:.3f}s"
            print(
                f"{item['cmd']} -> {item['reply']}"
                f" cmd={item['elapsed_s']:.3f}s{extra}"
            )

    if power_off_channels or power_on_channels:
        print("apply power controls...")
        replies, elapsed = apply_power_configuration(
            args.host, args.port, power_off_channels, power_on_channels
        )
        clock_control_total += elapsed
        clock_control_replies.extend(replies)
        for item in replies:
            extra = ""
            if "connect_s" in item:
                extra = f" connect={item['connect_s']:.3f}s"
            print(
                f"{item['cmd']} -> {item['reply']}"
                f" cmd={item['elapsed_s']:.3f}s{extra}"
            )

    if power_status_channels:
        print("query power states...")
        replies, elapsed = query_power_configuration(
            args.host, args.port, power_status_channels
        )
        clock_control_total += elapsed
        clock_control_replies.extend(replies)
        for item in replies:
            extra = ""
            if "connect_s" in item:
                extra = f" connect={item['connect_s']:.3f}s"
            channel = int(item["cmd"][5:])
            print(
                f"channel{channel}: power_enable={item['reply']}"
                f" cmd={item['elapsed_s']:.3f}s{extra}"
            )

    if control_only:
        script_total_s = time.perf_counter() - script_start
        print()
        print("===== CONTROL =====")
        print("mode = control-only")
        print(f"commands = {len(clock_control_replies)}")
        print(f"control_total = {clock_control_total:.3f}s")
        print(f"script_total = {script_total_s:.3f}s")
        return

    capture_results, timings = capture(
        args.host,
        args.port,
        args.points,
        channels,
        args.read_mode,
        args.data_mode,
        args.udp_port,
        args.udp_dst_mac,
        args.udp_payload,
        args.udp_timeout,
        args.udp_ifname,
        args.udp_bind_ip,
        skip_dma_reset=args.skip_dma_reset,
    )

    decoded = {}
    decode_total = 0.0
    diag_total = 0.0
    recover_total = 0.0
    csv_total = 0.0
    analysis_total = 0.0
    analysis_csv_total = 0.0
    for channel in channels:
        raw_bytes = capture_results[channel].pop("raw")
        diag_start = time.perf_counter()
        diag = compute_raw_diagnostics(raw_bytes) if do_diag else None
        diag_elapsed = time.perf_counter() - diag_start
        if do_diag:
            diag_total += diag_elapsed

        decode_start = time.perf_counter()
        adc = decode_19bit(raw_bytes)
        decode_elapsed = time.perf_counter() - decode_start
        decode_total += decode_elapsed

        entry = {
            "adc": adc,
            "diag": diag,
            "diag_s": diag_elapsed,
            "decode_s": decode_elapsed,
            "recover_s": 0.0,
            "csv_s": 0.0,
            "analysis_s": 0.0,
            "analysis_csv_s": 0.0,
            "recover_points": 0,
            "segment_start": analysis_config.start_index,
            "t_recovered": None,
            "y_recovered": None,
            "sort_idx": None,
            "analysis": None,
        }
        decoded[channel] = entry

    recover_points_used = 0
    recover_plan = None
    recover_plan_s = 0.0
    if do_recover:
        recover_limits = [
            max(0, decoded[channel]["adc"].size - analysis_config.start_index)
            for channel in channels
        ]
        recover_points_used = min(
            normalized_point_limit(args.recover_points, limit) for limit in recover_limits
        )
        if recover_points_used <= 0:
            raise RuntimeError(
                "not enough samples after --start-index for equivalent-time recovery"
            )

        recover_plan_start = time.perf_counter()
        recover_plan = build_equivalent_time_plan(
            recover_points_used, args.clock_freq, args.trigger_freq
        )
        recover_plan_s = time.perf_counter() - recover_plan_start
        recover_total += recover_plan_s

        for channel in channels:
            entry = decoded[channel]
            segment_start = analysis_config.start_index
            segment_end = segment_start + recover_plan.point_count
            recover_adc = entry["adc"][segment_start:segment_end]

            recover_start = time.perf_counter()
            y_recovered = apply_equivalent_time_plan(recover_adc, recover_plan)
            recover_elapsed = time.perf_counter() - recover_start
            entry["recover_s"] = recover_elapsed
            entry["recover_points"] = recover_plan.point_count
            entry["t_recovered"] = recover_plan.t_recovered_s
            entry["y_recovered"] = y_recovered
            entry["sort_idx"] = recover_plan.sort_idx
            recover_total += recover_elapsed

            if do_analysis:
                analysis_start = time.perf_counter()
                entry["analysis"] = analyze_recovered_waveform(
                    y_recovered, recover_plan, analysis_config
                )
                analysis_elapsed = time.perf_counter() - analysis_start
                entry["analysis_s"] = analysis_elapsed
                analysis_total += analysis_elapsed

            if args.save_csv:
                raw_recovered = build_raw19_from_adc(recover_adc)[recover_plan.sort_idx]
                output_csv = format_output_csv(args.output_csv, channel)
                csv_start = time.perf_counter()
                save_recovered_csv(
                    output_csv,
                    recover_plan.t_recovered_s,
                    y_recovered,
                    raw_recovered,
                    recover_plan.sort_idx,
                )
                csv_elapsed = time.perf_counter() - csv_start
                entry["csv_s"] = csv_elapsed
                csv_total += csv_elapsed
                entry["output_csv"] = output_csv

            if args.save_analysis_csv and entry["analysis"] is not None:
                analysis_csv_path = format_output_csv(args.analysis_output_csv, channel)
                analysis_csv_start = time.perf_counter()
                save_analysis_csv(analysis_csv_path, recover_plan, entry["analysis"])
                analysis_csv_elapsed = time.perf_counter() - analysis_csv_start
                entry["analysis_csv_s"] = analysis_csv_elapsed
                analysis_csv_total += analysis_csv_elapsed
                entry["output_analysis_csv"] = analysis_csv_path

    fs_eff = None
    ts_eff = None
    if recover_plan is not None:
        fs_eff = recover_plan.fs_eff
        ts_eff = recover_plan.ts_eff

    print()
    print("===== STAT =====")
    print("channels =", channels)
    print("display_channel =", display_channel)
    print("data_mode =", args.data_mode)
    print("read_mode =", args.read_mode)
    print("recover =", do_recover)
    print("analyze =", do_analysis)
    print("plot =", do_plot)
    if fs_eff is not None and ts_eff is not None:
        print(f"recover_points = {recover_points_used}")
        print(f"等效采样率：{fs_eff / 1e9:.3f} GHz")
        print(f"等效时间间隔：{ts_eff * 1e12:.3f} ps")
    else:
        print("等效采样率：skipped")
        print("等效时间间隔：skipped")

    for channel in channels:
        print()
        print_channel_stats(
            channel,
            decoded[channel]["adc"],
            decoded[channel]["diag"],
        )
        print(
            f"timing link{channel}: connect={capture_results[channel].get('connect_s', 0.0):.3f}s "
            f"transfer={capture_results[channel]['transfer_s']:.3f}s "
            f"diag={decoded[channel]['diag_s']:.3f}s "
            f"decode={decoded[channel]['decode_s']:.3f}s "
            f"recover={decoded[channel]['recover_s']:.3f}s "
            f"analysis={decoded[channel]['analysis_s']:.3f}s "
            f"csv={decoded[channel]['csv_s']:.3f}s "
            f"analysis_csv={decoded[channel]['analysis_csv_s']:.3f}s"
        )
        if "read_requests" in capture_results[channel]:
            print(f"read_requests = {capture_results[channel]['read_requests']}")
        if "trigger_s" in capture_results[channel]:
            print(f"udp_trigger = {capture_results[channel]['trigger_s']:.3f}s")
        if "udp_packets" in capture_results[channel]:
            print(f"udp_packets = {capture_results[channel]['udp_packets']}")
        if decoded[channel]["analysis"] is not None:
            print_analysis_stats(channel, recover_plan, analysis_config, decoded[channel]["analysis"])
        if decoded[channel].get("output_csv"):
            print(f"恢复结果保存：{decoded[channel]['output_csv']}")
            print(f"recover_points = {decoded[channel]['recover_points']}")
        if decoded[channel].get("output_analysis_csv"):
            print(f"分析结果保存：{decoded[channel]['output_analysis_csv']}")

    plot_prepare_s = 0.0
    plot_show_s = 0.0
    print()
    print(
        "timing: "
        f"control_total={clock_control_total:.3f}s "
        f"control_connect={timings['control_connect_s']:.3f}s "
        f"sample={timings['sample_s']:.3f}s "
        f"transfer_total={timings['transfer_total_s']:.3f}s "
        f"diag_total={diag_total:.3f}s "
        f"decode_total={decode_total:.3f}s "
        f"recover_total={recover_total:.3f}s "
        f"recover_plan={recover_plan_s:.3f}s "
        f"analysis_total={analysis_total:.3f}s "
        f"csv_total={csv_total:.3f}s "
        f"analysis_csv_total={analysis_csv_total:.3f}s "
        f"reset={timings['reset_s']:.3f}s "
        f"capture_e2e={timings['total_s']:.3f}s"
    )

    if do_plot:
        plot_prepare_start = time.perf_counter()
        plot_cols = 1 + int(do_recover) + int(do_analysis)
        fig, axes = plt.subplots(
            len(channels),
            plot_cols,
            figsize=(max(10, 5.5 * plot_cols), max(4, 3.2 * len(channels))),
            sharey=False,
        )
        axes_arr = np.array(axes, dtype=object)
        if axes_arr.ndim == 0:
            axes_arr = axes_arr.reshape(1, 1)
        elif axes_arr.ndim == 1:
            if len(channels) == 1:
                axes_arr = axes_arr.reshape(1, plot_cols)
            else:
                axes_arr = axes_arr.reshape(len(channels), 1)

        for row, channel in enumerate(channels):
            plot_entry = decoded[channel]
            col = 0
            ax_raw = axes_arr[row, col]
            col += 1

            raw_plot_points = normalized_point_limit(
                args.plot_raw_points, plot_entry["adc"].size
            )
            raw_slice = plot_entry["adc"][:raw_plot_points]
            raw_x, raw_y = downsample_for_plot(
                raw_slice,
                np.arange(raw_slice.size),
                max_points=args.plot_max_points,
            )
            if raw_x is None:
                raw_x = np.arange(raw_y.size)
            ax_raw.plot(raw_x, raw_y, linewidth=0.8)
            ax_raw.set_title(f"ADC Data in Capture Order (Link{channel})")
            ax_raw.set_xlabel("Sample Index")
            ax_raw.set_ylabel("ADC Code")
            ax_raw.grid(True, alpha=0.3)

            if do_recover:
                ax_rec = axes_arr[row, col]
                col += 1
                if plot_entry["y_recovered"] is not None:
                    rec_x, rec_y = downsample_for_plot(
                        plot_entry["y_recovered"],
                        plot_entry["t_recovered"] * 1e9,
                        max_points=args.plot_max_points,
                    )
                    ax_rec.plot(rec_x, rec_y, linewidth=0.8)
                ax_rec.set_title(f"Recovered TDR Curve (Link{channel})")
                ax_rec.set_xlabel("Time within Trigger Period (ns)")
                ax_rec.set_ylabel("ADC Code")
                ax_rec.grid(True, alpha=0.3)

            if do_analysis and plot_entry["analysis"] is not None:
                analysis = plot_entry["analysis"]
                ax_aligned = axes_arr[row, col]
                t_uniform_ns = recover_plan.t_uniform_s * 1e9
                aligned_x, aligned_y = downsample_for_plot(
                    analysis["y_aligned"],
                    t_uniform_ns,
                    max_points=args.plot_max_points,
                )
                ax_aligned.plot(
                    aligned_x, aligned_y, linewidth=0.9, label="aligned"
                )
                roi_slice = slice(analysis["roi_start"], analysis["roi_end"])
                roi_x, roi_y = downsample_for_plot(
                    analysis["y_aligned"][roi_slice],
                    t_uniform_ns[roi_slice],
                    max_points=max(2000, args.plot_max_points // 2),
                )
                ax_aligned.plot(roi_x, roi_y, linewidth=1.1, label="roi")
                ax_aligned.axvline(
                    t_uniform_ns[analysis["align_target"]],
                    color="tab:red",
                    linestyle="--",
                    linewidth=0.9,
                    label="rise target",
                )
                ax_aligned.axvline(
                    t_uniform_ns[analysis["roi_start"]],
                    color="tab:orange",
                    linestyle=":",
                    linewidth=0.9,
                )
                ax_aligned.axvline(
                    t_uniform_ns[min(analysis["roi_end"] - 1, recover_plan.point_count - 1)],
                    color="tab:orange",
                    linestyle=":",
                    linewidth=0.9,
                )
                ax_aligned.set_title(f"Aligned TDR + ROI (Link{channel})")
                ax_aligned.set_xlabel("Equivalent Time (ns)")
                ax_aligned.set_ylabel("ADC Code")
                ax_aligned.grid(True, alpha=0.3)
                ax_aligned.legend(loc="best", fontsize=8)

        plot_prepare_s = time.perf_counter() - plot_prepare_start
        fig.tight_layout()
        plot_show_start = time.perf_counter()
        plt.show()
        plot_show_s = time.perf_counter() - plot_show_start
        print(
            f"plot_timing: prepare={plot_prepare_s:.3f}s show_block={plot_show_s:.3f}s"
        )
    else:
        print("plot skipped in fast mode")

    script_total_s = time.perf_counter() - script_start
    print(
        "full_chain: "
        f"clock_control={clock_control_total:.3f}s "
        f"capture={timings['total_s']:.3f}s "
        f"diag={diag_total:.3f}s "
        f"decode={decode_total:.3f}s "
        f"recover={recover_total:.3f}s "
        f"analysis={analysis_total:.3f}s "
        f"csv={csv_total:.3f}s "
        f"analysis_csv={analysis_csv_total:.3f}s "
        f"plot_prepare={plot_prepare_s:.3f}s "
        f"plot_show={plot_show_s:.3f}s "
        f"script_total={script_total_s:.3f}s"
    )


if __name__ == "__main__":
    main()
