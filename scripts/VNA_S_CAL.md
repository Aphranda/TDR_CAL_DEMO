根据MATLAB代码中的详细校准步骤，我将误差参数与校准件类型进行更细致的匹配：

### 误差参数与校准件类型详细对应表

| 误差参数 | 参数描述 | 计算使用的校准件组合 | 具体测量条件 | 端口配置 |
|---------|---------|-------------------|------------|---------|
| **EDF** | 前向方向性误差 | **PORT1: OPEN + SHORT + LOAD**<br>• OPEN: Port1开路, Port2负载<br>• SHORT: Port1短路, Port2负载<br>• LOAD: Port1负载, Port2开路 | M3, M1, M5测量值 | Port1 TX → Port1 RX |
| **ERF** | 前向反射跟踪误差 | **PORT1: OPEN + SHORT + LOAD**<br>• OPEN: Port1开路, Port2负载<br>• SHORT: Port1短路, Port2负载<br>• LOAD: Port1负载, Port2开路 | M3, M1, M5测量值 | Port1 TX → Port1 RX |
| **ESF** | 前向源匹配误差 | **PORT1: OPEN + SHORT + LOAD**<br>• OPEN: Port1开路, Port2负载<br>• SHORT: Port1短路, Port2负载<br>• LOAD: Port1负载, Port2开路 | M3, M1, M5测量值 | Port1 TX → Port1 RX |
| **EXF** | 前向隔离误差 | **THROUGH直通**<br>• Port1↔Port2直通 | M9测量值 | Port1 TX → Port2 RX |
| **ELF** | 前向负载匹配误差 | **THROUGH直通**<br>• Port1↔Port2直通 | M10, M5测量值 | Port1 TX → Port1 RX |
| **ETF** | 前向传输跟踪误差 | **THROUGH直通**<br>• Port1↔Port2直通 | M9, M6测量值 | Port1 TX → Port2 RX |
| **EDR** | 反向方向性误差 | **PORT2: OPEN + SHORT + LOAD**<br>• OPEN: Port2开路, Port1负载<br>• SHORT: Port2短路, Port1负载<br>• LOAD: Port2负载, Port1开路 | M4, M2, M7测量值 | Port2 TX → Port2 RX |
| **ERR** | 反向反射跟踪误差 | **PORT2: OPEN + SHORT + LOAD**<br>• OPEN: Port2开路, Port1负载<br>• SHORT: Port2短路, Port1负载<br>• LOAD: Port2负载, Port1开路 | M4, M2, M7测量值 | Port2 TX → Port2 RX |
| **ESR** | 反向源匹配误差 | **PORT2: OPEN + SHORT + LOAD**<br>• OPEN: Port2开路, Port1负载<br>• SHORT: Port2短路, Port1负载<br>• LOAD: Port2负载, Port1开路 | M4, M2, M7测量值 | Port2 TX → Port2 RX |
| **EXR** | 反向隔离误差 | **THROUGH直通**<br>• Port1↔Port2直通 | M11测量值 | Port2 TX → Port1 RX |
| **ELR** | 反向负载匹配误差 | **THROUGH直通**<br>• Port1↔Port2直通 | M12, M7测量值 | Port2 TX → Port2 RX |
| **ETR** | 反向传输跟踪误差 | **THROUGH直通**<br>• Port1↔Port2直通 | M11, M8测量值 | Port2 TX → Port1 RX |

### 校准步骤执行顺序表

| 步骤 | 校准件连接 | 测量数据 | 用途 |
|------|-----------|---------|------|
| 1 | **THROUGH直通**<br>Port1↔Port2直通 | M10, M9, M12, M11 | 获取传输路径基准值 |
| 2 | **PORT1 OPEN**<br>Port1开路, Port2负载 | M3, M6 | 前向开路标准 |
| 3 | **PORT1 SHORT**<br>Port1短路, Port2负载 | M1 | 前向短路标准 |
| 4 | **PORT2 OPEN**<br>Port2开路, Port1负载 | M4, M8 | 反向开路标准 |
| 5 | **PORT2 SHORT**<br>Port2短路, Port1负载 | M2 | 反向短路标准 |
| 6 | **PORT1 LOAD**<br>Port1负载, Port2开路 | M5 | 前向负载标准 |
| 7 | **PORT2 LOAD**<br>Port2负载, Port1开路 | M7 | 反向负载标准 |

### 测量数据标识说明

- **M1**: Port1短路, Port2负载时S11测量
- **M2**: Port2短路, Port1负载时S22测量
- **M3**: Port1开路, Port2负载时S11测量
- **M4**: Port2开路, Port1负载时S22测量
- **M5**: Port1负载, Port2开路时S11测量
- **M6**: Port1开路, Port2负载时S21测量
- **M7**: Port2负载, Port1开路时S22测量
- **M8**: Port2开路, Port1负载时S12测量
- **M9**: 直通时前向S21测量
- **M10**: 直通时前向S11测量
- **M11**: 直通时反向S12测量
- **M12**: 直通时反向S22测量

这种细致的分类确保了每个误差参数都能准确对应到特定的校准件类型和测量条件。