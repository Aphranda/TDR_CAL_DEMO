import matplotlib.pyplot as plt
import numpy as np
import matplotlib.animation as animation

# 参数
f_ref = 100e6
pulser_freq = f_ref / 20  # 脉冲频率
sample_freq = (2048/20719) * f_ref  # 采样频率

# 脉冲周期
T_pulser = 1 / pulser_freq

# 定义脉冲上升沿波形（平滑阶跃函数）
t_edge = np.linspace(0, 200e-12, 2000)  # 200 ps 时间窗口
edge_waveform = 0.5 * (1 + np.tanh((t_edge - 100e-12) / 20e-12))

# 生成采样点
num_samples = 2000
sample_times = np.arange(num_samples) / sample_freq
sample_phase = (sample_times % T_pulser)

# 只保留落在上升沿窗口内的采样点
mask = (sample_phase >= 0) & (sample_phase <= 200e-12)
sample_times_edge = sample_phase[mask]
sample_values_edge = 0.5 * (1 + np.tanh((sample_times_edge - 100e-12) / 20e-12))

# 动画绘制
fig, ax = plt.subplots(figsize=(10,5))
ax.plot(t_edge*1e12, edge_waveform, label="真实上升沿波形")
scat = ax.scatter([], [], color="red", s=20, label="采样点")

ax.set_xlim(0, 200)
ax.set_ylim(-0.1, 1.1)
ax.set_xlabel("时间 (ps)")
ax.set_ylabel("幅度 (归一化)")
ax.set_title("脉冲上升沿的动态采样过程")
ax.legend()
ax.grid(True)

def update(frame):
    # 每帧增加一些采样点
    scat.set_offsets(np.c_[sample_times_edge[:frame]*1e12,
                           sample_values_edge[:frame]])
    return scat,

ani = animation.FuncAnimation(fig, update, frames=len(sample_times_edge),
                              interval=30, blit=True)

# 保存为 GIF
ani.save("sampling_edge.gif", writer="pillow")
print("动画已导出为 sampling_edge.gif")

# 保存为 HTML（可在浏览器中播放）
ani.save("sampling_edge.html", writer="html")
print("动画已导出为 sampling_edge.html")
