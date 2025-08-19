import os
import re
import glob
import numpy as np
import matplotlib.pyplot as plt
from tqdm import tqdm
import matplotlib
matplotlib.use("TkAgg")  # 可按需调整

SearchCenter_Rising = 1
SearchCenter_Max = 2

# ===== 参数 =====
input_dir         = 'CSV_Data0818_testonly'  # 要处理的文件夹
recursive         = True                  # 是否递归子文件夹
clock_freq        = 39.53858777e6         # 采样时钟 Hz
trigger_freq      = 10e6                  # 触发频率 Hz
N                 = 81920                 # 截取点数（单周期重构长度）
start_index       = 70                    # bit31上升沿后偏移
use_signed18      = True                  # True=18位有符号，False=无符号
show_up_to_GHz    = 50.0                  # 频域显示上限
SKIP_FIRST_VALUE  = True                  # 每个文件第一条数据不参与
EDGE_SEARCH_START = 1                     # 上升沿搜索从第2个样本开始(0-based)
diff_points       = 10                    # 差分间隔 y[n]-y[n-d]
SearchMethod      = SearchCenter_Rising

# ✅ 新增：对齐后按十分位截取 [start/10, end/10) 区间
roi_start_tenths  = 20
roi_end_tenths    = 30


# 输出CSV
output_csv        = 'Cable_S23.csv'

# ===== 推导量 =====
T_sample = 1.0 / clock_freq
T_trig   = 1.0 / trigger_freq
Fs_eff   = N / T_trig
Ts_eff   = 1.0 / Fs_eff

roi_start = int(N * roi_start_tenths / 100)
roi_end   = int(N * roi_end_tenths   / 100)
L_roi     = roi_end - roi_start
if L_roi <= diff_points:
    raise ValueError(f"截取长度 L_roi={L_roi} 必须大于 diff_points={diff_points}")

# ===== 工具：读取文件 =====
def load_u32_text_first_col(path, skip_first=True):
    encodings = ["utf-8", "utf-8-sig", "gbk", "latin1", "utf-16", "utf-16le", "utf-16be"]
    last_err = None
    for enc in encodings:
        try:
            vals = []
            with open(path, "r", encoding=enc, errors="strict") as f:
                for line in f:
                    s = line.strip()
                    if not s:
                        continue
                    m = re.search(r'(0x[0-9a-fA-F]+|\d+)', s)
                    if not m:
                        continue
                    vals.append(np.uint32(int(m.group(1), 0)))
            arr = np.asarray(vals, dtype=np.uint32)
            if skip_first and arr.size >= 1:
                arr = arr[1:]
            return arr
        except Exception as e:
            last_err = e
            continue
    raise last_err

# ===== 单文件处理 =====
def process_one_file(u32_arr):
    bit31 = ((u32_arr >> 31) & 0x1).astype(np.uint8)
    adc_18u = (u32_arr & ((1 << 20) - 1)).astype(np.uint32)
    if use_signed18:
        adc_18s = ((adc_18u + (1 << 19)) & ((1 << 20) - 1)) - (1 << 19)
        adc_full = adc_18s.astype(np.int32)
    else:
        adc_full = adc_18u.astype(np.int32)

    edge_idx = np.flatnonzero((bit31[1:] == 1) & (bit31[:-1] == 0))
    edge_idx = edge_idx[edge_idx >= EDGE_SEARCH_START]
    if edge_idx.size == 0:
        return None
    rise_idx = edge_idx[0] + 1

    start_capture = rise_idx + start_index
    if start_capture + N > u32_arr.size:
        return None
    segment_adc = adc_full[start_capture : start_capture + N]

    t_within_period = (np.arange(N, dtype=np.float64) * T_sample) % T_trig
    sort_idx = np.argsort(t_within_period)
    y_sorted = segment_adc[sort_idx]

    if SearchMethod == SearchCenter_Rising:
        adc_full_mean = np.mean(adc_full)
        rise_candidates = np.flatnonzero((y_sorted[10:] > adc_full_mean) & (y_sorted[:-10] <= adc_full_mean))
        if rise_candidates.size == 0:
            dy = np.diff(y_sorted.astype(np.float64))
            rise_pos = int(np.argmax(dy)) + 1
        else:
            rise_pos = int(rise_candidates[0])
    else:
        rise_pos = int(np.argmax(y_sorted))

    target_idx = N // 4
    shift = (target_idx - rise_pos) % N
    y_full = np.roll(y_sorted, shift)

    y_roi = y_full[roi_start:roi_end]

    y0 = y_roi.astype(np.float64)
    y0 -= np.mean(y0)
    win0 = np.hanning(L_roi)
    X0 = np.fft.rfft(y0 * win0)
    freq = np.fft.rfftfreq(L_roi, d=Ts_eff)
    scale0 = (np.sum(win0) / L_roi) * L_roi
    mag_linear = np.abs(X0) / (scale0 + 1e-12)

    if L_roi <= diff_points:
        return None
    y_diff = y_roi[diff_points:] - y_roi[:-diff_points]
    Nd = y_diff.size
    y_d = y_diff.astype(np.float64)
    y_d -= np.mean(y_d)
    win_d = np.hanning(Nd)
    Xd = np.fft.rfft(y_d * win_d)
    freq_d = np.fft.rfftfreq(Nd, d=Ts_eff)
    scale_d = (np.sum(win_d) / Nd) * Nd
    Xd_norm = Xd / (scale_d + 1e-12)
    mag_linear_d = np.abs(Xd_norm)

    return y_roi, freq, mag_linear, y_diff, freq_d, mag_linear_d, Xd_norm

# ===== 扫描文件 =====
pattern = os.path.join(input_dir, "**", "*.csv") if recursive else os.path.join(input_dir, "*.csv")
files = sorted(glob.glob(pattern, recursive=recursive))
if not files:
    raise FileNotFoundError("未找到csv文件")

# ===== 批处理 =====
ys, mags, ys_d, mags_d = [], [], [], []
freq_ref, freq_d_ref = None, None
sum_Xd = None
ok = 0

for f in tqdm(files, desc="Processing files", unit="file"):
    try:
        raw = load_u32_text_first_col(f, skip_first=SKIP_FIRST_VALUE)
        res = process_one_file(raw)
        if res is None:
            continue
        y_roi, freq, mag_linear, y_diff, freq_d, mag_linear_d, Xd_norm = res

        if freq_ref is None:
            freq_ref = freq
        if freq_d_ref is None:
            freq_d_ref = freq_d
            sum_Xd = np.zeros_like(Xd_norm, dtype=np.complex128)

        ys.append(y_roi.astype(np.float64))
        mags.append(mag_linear.astype(np.float64))
        ys_d.append(y_diff.astype(np.float64))
        mags_d.append(mag_linear_d.astype(np.float64))
        sum_Xd += Xd_norm
        ok += 1
    except Exception:
        continue

if ok == 0:
    raise RuntimeError("没有文件成功处理")

# ===== 平均 =====
y_avg = np.mean(np.vstack(ys), axis=0)
mag_avg_linear = np.mean(np.vstack(mags), axis=0)
mag_avg_db = 20 * np.log10(mag_avg_linear)

y_d_avg = np.mean(np.vstack(ys_d), axis=0)
mag_d_avg_linear = np.mean(np.vstack(mags_d), axis=0)
mag_d_avg_db = 20 * np.log10(mag_d_avg_linear)

t_roi_us  = (np.arange(L_roi) * Ts_eff) * 1e6
t_diff_us = t_roi_us[diff_points:]
mask  = freq_ref   <= (show_up_to_GHz * 1e9)
maskd = freq_d_ref <= (show_up_to_GHz * 1e9)

edge_in_roi = (N//4 - roi_start)

# ===== 原始ROI图 =====
fig, (ax_t, ax_f) = plt.subplots(2, 1, figsize=(12, 8))
if 0 <= edge_in_roi < L_roi:
    ax_t.axvline(t_roi_us[edge_in_roi], linestyle="--", linewidth=0.8)
ax_t.plot(t_roi_us, y_avg)
ax_t.set_title(f"Average Time-Domain ROI (across {ok} files)")
ax_f.plot(freq_ref[mask]/1e9, mag_avg_db[mask])
ax_f.set_title("Average Spectrum ROI")
plt.tight_layout()
plt.show()

# ===== 差分ROI图 =====
fig2, (ax_t2, ax_f2) = plt.subplots(2, 1, figsize=(12, 8))
if 0 <= edge_in_roi < L_roi and 0 <= edge_in_roi - diff_points < y_d_avg.size:
    ax_t2.axvline(t_roi_us[max(edge_in_roi - diff_points, 0)], linestyle="--", linewidth=0.8)
ax_t2.plot(t_diff_us, y_d_avg)
ax_t2.set_title("Differenced Time-Domain Average")
ax_f2.plot(freq_d_ref[maskd]/1e9, mag_d_avg_db[maskd])
ax_f2.set_title("Differenced Spectrum Average")
plt.tight_layout()
plt.show()

# ===== 差分ROI复数FFT平均保存 =====
avg_Xd = sum_Xd / ok
out_mat = np.column_stack([freq_d_ref, np.real(avg_Xd), np.imag(avg_Xd)])
np.savetxt(output_csv, out_mat, delimiter=",", header="freq_Hz,Re,Im", comments="", fmt="%.10e")

print(f"完成：共平均 {ok} 个文件的差分 ROI 复数 FFT。")
print(f"结果保存到：{os.path.abspath(output_csv)}")
