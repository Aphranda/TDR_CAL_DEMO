# TDR_CAL_DEMO 数据格式与处理流程分析

## 1. BIN 文件原始数据格式

### 1.1 整体结构

- **存储方式**: 无文件头，纯原始二进制流 (raw binary)
- **字节序**: Little-endian (`<u4`)
- **数据单元**: 每个采样点占 **4 字节** (32 bits)
- **读取方法**: `np.fromfile(file_path, dtype=np.uint32)`
- **文件命名**: `{prefix}_{序号:04d}_{数据类型}_{通道名}.bin`
  - 例: `test_0001_uint32_adc1.bin`, `test_0001_uint32_adc2.bin`
- **双通道**: ADC1 和 ADC2 各存为独立文件

### 1.2 每个 uint32 值的位布局

```
Bit 31        Bit 20  Bit 19                                    Bit 0
   ↓              ↓      └───────────────────┬──────────────────┘
┌──┴──────┬───────┴─────────────────────────┴──────────────────┐
│  D31    │  D30 ~ D20           │  D19 ~ D0                    │
│ 1 bit   │  11 bits (保留)      │  20 bits (ADC 采样数据)      │
└─────────┴──────────────────────┴─────────────────────────────┘
```

| 位域 | 宽度 | 提取方式 | 含义 |
|------|------|---------|------|
| Bit 31 | 1 bit | `(val >> 31) & 1` | 有效数据标志: 1=有效, 0=无效。上升沿 (0→1) 标记有效数据段起始 |
| Bits 30~20 | 11 bits | 未使用 | 保留位，代码中未引用 |
| Bits 19~0 | 20 bits | `val & 0xFFFFF` | ADC 采样值 (高位在前) |

### 1.3 ADC 数据的两种解释模式

**无符号模式** (20-bit, 值域 0 ~ 1,048,575):

```python
adc_value = u32_val & 0xFFFFF   # 直接取低 20 位
```

**有符号模式** (signed, `config.use_signed18=True` 时):

将低 20 位按补码解释，第 19 位为符号位，符号扩展后值域: -524,288 ~ +524,287。

```python
mask = (1 << N) - 1
offset = 1 << (N - 1)
adc_signed = ((adc_unsigned + offset) & mask) - offset
```

### 1.4 可变位宽截取

通过 `config.adc_bit` (N, 默认 20, 范围 1~20) 可只取高位:

```
当 N=18: 取 bits 19~2 → 18 位 ADC 数值
当 N=16: 取 bits 19~4 → 16 位 ADC 数值
```

```python
# N < 20 时: 右移 (20-N) 位后取低 N 位
shift_bits = 20 - N
adc_value = (u32_val >> shift_bits) & ((1 << N) - 1)
```

---

## 2. 数据采集流程

```
┌──────────┐   TCP (bytes)    ┌──────────────┐   np.frombuffer   ┌──────────────┐
│ 硬件 ADC │ ───────────────→ │ bytes buffer │ ────────────────→ │ uint32 array │
└──────────┘                  └──────────────┘   dtype='<u4'     └──────┬───────┘
                                                                       │
                                                            ┌──────────┴──────────┐
                                                            │                     │
                                              bit31 = (val >> 31) & 1    adc = val & 0xFFFFF
                                              (有效标志 / 触发)           (20-bit ADC 数据)
```

参考: [ADCSample.py:282](src/app/core/ADCSample.py#L282)

---

## 3. 数据处理管道

### 3.1 完整管道步骤

```
uint32 array (.bin 文件)
  │
  ├─[步骤1] extract_adc_data()  → bit31[], adc_full[]     (DataProcessor:340)
  │
  ├─[步骤2] 边沿检测 → rise_idx = 0  (当前跳过检测)        (DataAnalyze:67)
  │
  ├─[步骤3] extract_data_segment() → 截取 n_points 个点    (DataProcessor:388)
  │         起始位置: rise_idx + start_index (0 + 70)
  │
  ├─[步骤4] sort_data_by_period() → 按触发周期排序         (DataProcessor:401)
  │         t_within_period = (采样索引 * t_sample) % t_trig
  │
  ├─[步骤5] remove_spikes_robust_final() → Hampel滤波去奇异点 (DataProcessor:505)
  │         阈值=3.0, 窗口=5
  │
  ├─[步骤6] find_rise_position() → 搜索上升沿位置          (EdgeDetector:294)
  │         Savitzky-Golay 平滑 → 滑动窗口 → 差分法 → 取最大幅度点
  │
  ├─[步骤7] align_data() → 数据对齐                         (DataProcessor:436)
  │         将上升沿 roll 到 alignment_idx = n_points // align_pos
  │
  ├─[步骤8] extract_roi() → 提取感兴趣区域                  (DataProcessor:441)
  │         roi_start ~ roi_end (默认 20%~30% 范围)
  │
  ├─[步骤9] compute_spectrum() → FFT 频谱分析               (DataProcessor:413)
  │         Hanning 窗 → rfft → 归一化
  │
  └─[步骤10] compute_difference() → 差分处理 + 频谱          (DataProcessor:432)
             diff_points=10, 然后 smooth(average_points=3)
```

参考: [DataAnalyze.py:47-156](src/app/core/DataAnalyze.py#L47-L156), [DataAnalyze.py:163-212](src/app/core/DataAnalyze.py#L163-L212)

### 3.2 典型数据段长度

```
一个采集 Block = 81920 + 100 = 82020 个采样点 (≈ 328 KB)
数据段起点 = block_start + 70 (start_index)
有效数据 = 81920 个点 (n_points)
```

参考: [Controller.py:315](src/app/widgets/DataAnalysisPanel/Controller.py#L315)

---

## 4. 关键配置参数

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `clock_freq` | 39.53858777 MHz | ADC 采样时钟 |
| `trigger_freq` | 10 MHz | 触发信号频率 |
| `n_points` | 81920 | 每段有效采样点数 |
| `start_index` | 70 | 有效数据段相对起始偏移 |
| `use_signed18` | True | 是否按有符号 18 位解释 ADC |
| `adc_bit` | 20 | ADC 提取位数 (1~20) |
| `diff_points` | 10 | 差分间隔点数 |
| `average_points` | 3 | 平滑窗口大小 |
| `search_method` | RISING(1) | 边沿搜索方法 (1=上升沿, 2=最大值) |
| `roi_start_tenths` | 20 | ROI 起始位置 (%) |
| `roi_end_tenths` | 30 | ROI 结束位置 (%) |
| `align_pos` | 2 | 对齐位置分母 (对齐到 n_points/2) |
| `min_edge_amplitude_ratio` | 0.5 | 边沿最小幅度比 |

参考: [ConfigManager.py:35-98](src/app/core/ConfigManager.py#L35-L98)

---

## 5. 导出参数计算

```python
t_sample  = 1 / clock_freq          # ≈ 25.29 ns  (采样间隔)
t_trig    = 1 / trigger_freq        # ≈ 100 ns    (触发周期)
fs_eff    = n_points / t_trig       # ≈ 819.2 GHz (等效采样率)
ts_eff    = 1 / fs_eff              # ≈ 1.22 ps   (等效时间分辨率)

roi_start = n_points * 20 / 100     # = 16384
roi_end   = n_points * 30 / 100     # = 24576
l_roi     = roi_end - roi_start     # = 8192
```

---

## 6. 校准模式

| 模式 | 字符串 | 说明 |
|------|--------|------|
| THRU | `"THRU"` | 直通校准 |
| LOAD | `"LOAD"` | 负载校准 |
| SHORT | `"SHORT"` | 短路校准 |
| OPEN | `"OPEN"` | 开路校准 |

四种模式使用相同的数据处理管道 (频谱分析)。

参考: [ConfigManager.py:19-23](src/app/core/ConfigManager.py#L19-L23)

---

## 7. 双通道处理策略

| ADC 模式 | ADC1 | ADC2 |
|----------|------|------|
| `ADC1_ONLY` | 独立处理，自行对齐 | 不处理 |
| `ADC2_ONLY` | 不处理 | 独立处理，自行对齐 |
| `BOTH_ADCS` | 先处理获取边沿位置 | 使用 ADC1 的边沿位置，不再独立对齐 |

双通道模式下 ADC1 也不做对齐 (`do_alignment=False`)，两个通道共用同一个 `rise_pos`。

参考: [DataAnalyze.py:250-271](src/app/core/DataAnalyze.py#L250-L271)

---

## 8. extract_basic_segment 详细解析

该方法是数据处理管道中**最核心的函数**，位于 [DataAnalyze.py:47-160](src/app/core/DataAnalyze.py#L47-L160)，负责将原始 uint32 数组转换为可供频谱分析的结构化数据。

### 8.1 函数签名

```python
def extract_basic_segment(self, u32_arr: np.ndarray, data_index: int = -1,
                          target_idx: Optional[int] = None,
                          do_alignment: bool = True) -> Optional[Dict[str, Any]]:
```

| 参数 | 类型 | 说明 |
|------|------|------|
| `u32_arr` | `np.ndarray` | 从 .bin 文件读取的原始 uint32 数组 |
| `data_index` | `int` | 文件索引，仅用于日志追踪 |
| `target_idx` | `Optional[int]` | 外部指定的边沿位置。不为 None 时跳过边沿搜索、跳过奇异点去除 |
| `do_alignment` | `bool` | 是否执行数据对齐。ADC1 为 True，ADC2/BOTH_ADCS 为 False |

### 8.2 返回值

```python
{
    'adc_full': np.ndarray,      # 全量 ADC 数据 (从 uint32 提取的完整数组)
    'y_roi': np.ndarray,         # ROI 区域数据 (最终输出，供频谱分析)
    'adc_full_mean': float,      # 全量 ADC 平均值 (传给 find_rise_position)
    'rise_pos': int,             # 搜索到的上升沿位置 (或传入的 target_idx)
    'y_sorted': np.ndarray,      # 按周期排序后的数据 (对齐前)
    'y_full': np.ndarray,        # 排序+对齐后的全段数据 (y_roi 的母体)
}
```

---

### 8.3 逐步流程

#### 步骤 1 — 提取 ADC 数据

```python
bit31, adc_full = self.data_processor.extract_adc_data(
    u32_arr, self.config.use_signed18, self.config.adc_bit
)
```

从每个 uint32 中分离 `bit31`（有效标志位）和 ADC 采样值。`adc_full` 是 `(N,)` 形状的 int32 数组，保留了原始时序。

> 注：`bit31` 在此方法中**实际未被使用**（步骤 2 被跳过）。它仅在外部 [Controller.py:294](src/app/widgets/DataAnalysisPanel/Controller.py#L294) 中被用于按段划分数据块。

#### 步骤 2 — 边沿检测（已跳过）

```python
rise_idx = 0   # 硬编码为 0，原有检测逻辑被注释
```

原本的设计是通过 `bit31` 上升沿定位有效数据起点，当前实现直接从数组第 0 位开始截取。

#### 步骤 3 — 截取数据段

```python
segment_adc = self.data_processor.extract_data_segment(
    adc_full, rise_idx, self.config.start_index, self.config.n_points
)
# start_capture = 0 + 70        → 跳过前 70 个点
# segment_adc = adc_full[70 : 70 + 81920]
```

截取逻辑（[DataProcessor.py:388-399](src/app/core/DataProcessor.py#L388-L399)）：

```
adc_full 全长 ≈ 82020
  ├─ [0 ~ 69]:              start_index 偏移 (跳过)
  ├─ [70 ~ 70+81919]:       有效数据 n_points=81920
  └─ [70+81920 ~ end]:      尾部余量 (约 30 点)
```

#### 步骤 4 — 按周期排序（等效时间采样）

```python
y_sorted, _ = self.data_processor.sort_data_by_period(
    segment_adc, self.config.t_sample, self.config.t_trig
)
# t_sample ≈ 25.29 ns (1 / 39.53858777 MHz)
# t_trig   ≈ 100 ns   (1 / 10 MHz)
```

排序逻辑（[DataProcessor.py:401-410](src/app/core/DataProcessor.py#L401-L410)）：

```python
t_within_period[i] = (i * t_sample) % t_trig   # 采样点在触发周期内的相对时间
sort_idx = np.argsort(t_within_period)          # 按相对时间升序排列
```

**原理**：81920 个时域采样点覆盖了多个触发周期，通过取模运算将每个点映射到同一周期内，再按时间排序，实现等效时间采样的波形重建。

```
原始 (时域):  [p0_t0, p0_t1, p0_t2, p0_t3, p0_t4, ...]  (t_sample 间隔)
排序后 (等效): [p0_t0, p1_t0, p2_t0, p3_t0, ..., p0_t1, p1_t1, ...]  (ts_eff 间隔)
                                                                ↑
                                              等效分辨率 ≈ 1.22 ps
```

#### 步骤 5 — 条件性奇异点去除

```python
enable_spike_removal = False
if not target_idx:
    enable_spike_removal = True

if enable_spike_removal:
    y_sorted_cleaned, spikes_detected = self.data_processor.remove_spikes_robust_final(
        y_sorted, threshold=3.0, window_size=5
    )
    y_sorted = y_sorted_cleaned
```

**触发条件**：`target_idx is None`（即外部未指定对齐位置时，说明当前是"自主搜索"模式）。

**设计意图**：

| 场景 | target_idx | 去奇异点 | 原因 |
|------|-----------|--------|------|
| ADC1 自主搜索 | `None` | **是** | 需从干净数据中搜索边沿，奇异点会干扰边沿检测 |
| ADC2 跟随 ADC1 | ADC1 的 `rise_pos` | 否 | 直接使用 ADC1 的对齐位置，无需搜索边沿 |
| BOTH_ADCS 模式 ADC1 | `None` | **是** | 仍需搜索边沿给 ADC2 用 |
| BOTH_ADCS 模式 ADC2 | ADC1 的 `rise_pos` | 否 | 复用 ADC1 结果 |

使用 Hampel 滤波器：滑动窗口内用中位数和 MAD 检测异常值，Z-score 超阈值 3.0 则替换为中位数。

#### 步骤 6 — 边沿位置搜索

```python
if target_idx is None:
    rise_pos = self.edge_detector.find_rise_position(
        y_sorted, self.config.search_method,
        np.mean(adc_full),                    # 全量 ADC 均值作为参考
        self.config.min_edge_amplitude_ratio  # 默认 0.5
    )
else:
    rise_pos = target_idx
```

搜索流程（[EdgeDetector.py:294-323](src/app/core/EdgeDetector.py#L294-L323)）：

1. **Savitzky-Golay 滤波** → 保留边沿特性的同时去除高频噪声
2. **判断底噪** → 若为纯底噪则直接走简化差分路径
3. **滑动窗口预筛选** → 窗口=5%数据长度，步进=3%，峰峰值超阈值则入选
4. **去均值异常窗口** → 均值偏离超过 2σ 的窗口被丢弃
5. **差分法精确搜索** → 在有效窗口内用差分定位，非极大值抑制，毛刺过滤
6. **取最大幅度候选点** → 返回幅度最大的上升沿位置

#### 步骤 7 — 数据对齐

```python
if do_alignment:
    alignment_idx = self.config.n_points // self.config.align_pos
    # = 81920 // 2 = 40960
    y_full = self.data_processor.align_data(y_sorted, rise_pos, alignment_idx)
else:
    y_full = y_sorted
```

对齐逻辑（[DataProcessor.py:436-439](src/app/core/DataProcessor.py#L436-L439)）：

```python
shift = (target_position - rise_pos) % len(sorted_data)
return np.roll(sorted_data, shift)
```

将上升沿位置循环移动到数组中央 (`n_points / 2`)，使得 ROI 区域始终在固定的相对位置，便于跨文件比较和平均。

```
对齐前:  [ ..., rise_pos=15000, ... ]   (边沿在任意位置)
对齐后:  [ ..., aligned_pos=40960, ... ] (边沿固定在中央)
```

#### 步骤 8 — 提取 ROI

```python
y_roi = self.data_processor.extract_roi(y_full, self.config.roi_start, self.config.roi_end)
# = y_full[16384 : 24576]   (默认 20%~30%)
```

ROI 区间占全段 10%（`roi_end_tenths - roi_start_tenths = 10`），共 8192 个点（默认配置下）。

---

### 8.4 控制流图

```
                    u32_arr (原始 uint32 数据)
                         │
                         ▼
              ┌─────────────────────┐
              │ extract_adc_data()  │  → bit31 (未使用), adc_full
              └────────┬────────────┘
                       │
              ┌────────▼────────────┐
              │ rise_idx = 0        │  (硬编码，跳过边沿检测)
              └────────┬────────────┘
                       │
              ┌────────▼────────────┐
              │ extract_data_segment│  → segment_adc[0:81920] (从偏移70开始)
              └────────┬────────────┘
                       │
              ┌────────▼────────────┐
              │ sort_data_by_period │  → y_sorted (等效时间重排)
              └────────┬────────────┘
                       │
                   target_idx?
                  /          \
               None          非 None
                │               │
       ┌────────▼────────┐     │
       │ 去奇异点 (Hampel) │     │  (跳过)
       └────────┬────────┘     │
                │               │
       ┌────────▼────────┐     │
       │ find_rise_pos() │     │
       └────────┬────────┘     │
                │               │
                └───► rise_pos ◄┘
                       │
                   do_alignment?
                  /            \
               True            False
                │                │
       ┌────────▼────────┐      │
       │ align_data()    │      │
       │ roll 到 n/2     │      │
       └────────┬────────┘      │
                │                │
                └───► y_full ◄──┘
                       │
              ┌────────▼────────┐
              │ extract_roi()   │  → y_roi = y_full[20%:30%]
              └────────┬────────┘
                       │
                       ▼
                   return {...}
```

---

### 8.5 三种模式下的调用方式

| 调用链 | do_alignment | target_idx | 去奇异点 |
|--------|-------------|------------|--------|
| **ADC1_ONLY**: ADC1 自主 | `True` | `None` | 是 |
| **ADC2_ONLY**: ADC2 自主 | `True` | `None` | 是 |
| **BOTH_ADCS**: ADC1 | `False` | `None` | 是 |
| **BOTH_ADCS**: ADC2 | `False` | ADC1 的 `rise_pos` | 否 |
| **双通道重对齐**: ADC1 | `True` | ADC1 的 `rise_pos` | 否 |
| **双通道重对齐**: ADC2 | `True` | 参考通道的 `rise_pos` | 否 |

关键点：**BOTH_ADCS 模式下两个通道都不做数据对齐**（`do_alignment=False`），ADC2 直接复用 ADC1 的上升沿位置。对齐操作被推迟到 `realign_dual_channel_averages()` 中统一处理。

---

## 9. 关键算法

### 9.1 周期排序

```python
t_within_period[i] = (i * t_sample) % t_trig
```
将时域采样点按其在触发周期内的相对时间重新排列，实现等效时间采样。

### 9.2 Hampel 滤波器 (去奇异点)

滑动窗口内计算中位数和 MAD (中位数绝对偏差)，使用 Z-score 检测异常:

```
Z = 0.6745 * (x[i] - median) / MAD
若 |Z| > threshold → 奇异点，替换为中位数
```

有 3 个 Numba JIT 编译版本: `hampel_filter_precompiled` (并行), `hampel_filter_simple` (简化), `hampel_filter_optimized` (最终版, 预分配缓冲)。

### 8.3 边沿检测

1. Savitzky-Golay 滤波 (`window_length=7, polyorder=3`) 平滑边沿
2. 滑动窗口预筛选 (窗口大小=5%数据长度, 步进=3%)
3. 峰峰值阈值过滤 → 去掉均值异常的窗口
4. 差分法精确搜索 → 非极大值抑制 → 毛刺过滤
5. 返回幅度最大的候选点作为边沿位置

### 8.4 FFT 频谱分析

1. 去均值 → Hanning 窗加权
2. `np.fft.rfft()` 实输入 FFT
3. 归一化: `|FFT| / (sum(window) / N * N)`

### 8.5 差分处理

```python
y_diff[i] = y[i + diff_points] - y[i]
```
一阶差分用于增强高频分量，差分结果再进行移动平均平滑。

---

## 9. 文件读取流程

```python
# Controller.py:287
uint32_arr = np.fromfile(file_path, dtype=np.uint32, count=read_size // 4)
bit31 = (uint32_arr >> 31) & 1                            # 提取有效标志
adc_data = uint32_arr & 0xFFFFF                           # 提取 ADC 数据 (18-bit)
# 或使用 DataProcessor.extract_adc_data() 完整提取
```

---

## 10. 数据保存流程

```python
# DataSaverWorker.py:140-141
data.tofile(filepath)  # numpy 数组直接写入二进制文件, uint32 / float64
```

保存格式与读取格式一致：无头部的 raw binary，每个元素 4 字节 (uint32) 或 8 字节 (float64)。
