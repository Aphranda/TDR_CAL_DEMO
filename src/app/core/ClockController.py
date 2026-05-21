# src/app/core/ClockController.py
import time
from typing import Optional, Tuple, Dict, Any, List

class ClockController:
    """时钟控制类 — 对齐 NEW DATA.py 硬件协议

    LMK 提供触发时钟，AD9508 提供采样时钟。
    默认使用通道 4 (Port1) 和通道 5 (Port2)。

    LMK 命令格式: lmk_state/mode/div/delay <lmk器件> <lmk通道> <值>
    AD9508 命令格式: ad9508_state <器件号> <通道号> <0|1>
    """

    # ---- 硬件映射表（来自 scripts/NEW DATA.py） ----

    # 用户通道 → (LMK器件号, LMK输出通道)
    CHANNEL_TO_LMK = {
        1: (1, 4), 2: (1, 5), 3: (1, 6), 4: (1, 7),
        5: (1, 0), 6: (1, 1), 7: (1, 2), 8: (1, 3),
    }

    # AD9508 前端编号 → ((器件号, 通道号), ...)
    AD9508_FRONTEND_TO_DEVICE_CHANNELS = {
        1: ((1, 0),), 2: ((1, 2),), 3: ((2, 0),), 4: ((2, 2),),
        5: ((3, 0),), 6: ((3, 2),), 7: ((4, 0),), 8: ((4, 2),),
    }

    # LMK 工作模式
    LMK_MODE_BYPASS = 0
    LMK_MODE_DIV = 1
    LMK_MODE_DELAY = 2
    LMK_MODE_DIV_DELAY = 3

    LMK_MODE_NAMES = {
        "bypass": 0, "div": 1, "divide": 1, "divided": 1,
        "delay": 2, "delayed": 2,
        "div-delay": 3, "div-and-delay": 3, "div+delay": 3,
        "divdelay": 3, "divided-and-delayed": 3, "divide-and-delay": 3,
    }

    # 默认通道（Port1=Ch4, Port2=Ch5）
    DEFAULT_CHANNELS = [4, 5]

    # ---- S 参数模式定义（Port1=Ch4, Port2=Ch5） ----

    S_MODES = {
        'S11': {
            'description': '端口1反射测量 (Ch4触发, Ch4采样)',
            'trigger':   {4: True, 5: False},
            'sample':    {4: True, 5: False},
        },
        'S21': {
            'description': '端口1→端口2传输测量 (Ch4触发, Ch5采样)',
            'trigger':   {4: True, 5: False},
            'sample':    {4: False, 5: True},
        },
        'S12': {
            'description': '端口2→端口1传输测量 (Ch5触发, Ch4采样)',
            'trigger':   {4: False, 5: True},
            'sample':    {4: True, 5: False},
        },
        'S22': {
            'description': '端口2反射测量 (Ch5触发, Ch5采样)',
            'trigger':   {4: False, 5: True},
            'sample':    {4: False, 5: True},
        },
    }

    # =========================================================================
    # 构造与基础方法
    # =========================================================================

    def __init__(self, tcp_client=None):
        self.tcp_client = tcp_client
        self.clock_states = {
            'trigger_ch4': False,
            'trigger_ch5': False,
            'sample_ch4': False,
            'sample_ch5': False,
        }
        self.current_mode = None

    def set_tcp_client(self, tcp_client):
        """设置TCP客户端"""
        self.tcp_client = tcp_client

    # =========================================================================
    # 底层命令发送
    # =========================================================================

    def _send_cmd(self, cmd: str) -> Tuple[bool, str]:
        """发送一条控制命令并读取一行应答"""
        if not self.tcp_client or not self.tcp_client.connected:
            return False, "TCP客户端未连接"
        try:
            ok, msg = self.tcp_client.send(cmd + "\n")
            if not ok:
                return False, f"发送失败: {msg}"
            time.sleep(0.02)
            success, response = self.tcp_client.receive(max_retries=1, base_timeout=1.0)
            if success:
                return True, response.strip()
            return False, response
        except Exception as e:
            return False, f"命令 '{cmd}' 发送失败: {e}"

    # ---- LMK 触发时钟控制 ----

    def _send_lmk_state(self, channel: int, enable: bool) -> Tuple[bool, str]:
        """设置 LMK 触发时钟输出状态 → lmk_state <lmk> <lmk_ch> <0|1>"""
        if channel not in self.CHANNEL_TO_LMK:
            return False, f"通道 {channel} 无 LMK 映射"
        lmk, lmk_ch = self.CHANNEL_TO_LMK[channel]
        return self._send_cmd(f"lmk_state {lmk} {lmk_ch} {1 if enable else 0}")

    def _send_lmk_mode(self, channel: int, mode: int) -> Tuple[bool, str]:
        """设置 LMK 通道模式 → lmk_mode <lmk> <lmk_ch> <mode>"""
        if channel not in self.CHANNEL_TO_LMK:
            return False, f"通道 {channel} 无 LMK 映射"
        lmk, lmk_ch = self.CHANNEL_TO_LMK[channel]
        return self._send_cmd(f"lmk_mode {lmk} {lmk_ch} {mode}")

    def _send_lmk_div(self, channel: int, div: int) -> Tuple[bool, str]:
        """设置 LMK 分频值（偶数 2..510） → lmk_div <lmk> <lmk_ch> <div>"""
        if channel not in self.CHANNEL_TO_LMK:
            return False, f"通道 {channel} 无 LMK 映射"
        lmk, lmk_ch = self.CHANNEL_TO_LMK[channel]
        return self._send_cmd(f"lmk_div {lmk} {lmk_ch} {div}")

    def _send_lmk_delay(self, channel: int, delay_ps: int) -> Tuple[bool, str]:
        """设置 LMK 延时（ps） → lmk_delay <lmk> <lmk_ch> <delay>"""
        if channel not in self.CHANNEL_TO_LMK:
            return False, f"通道 {channel} 无 LMK 映射"
        lmk, lmk_ch = self.CHANNEL_TO_LMK[channel]
        return self._send_cmd(f"lmk_delay {lmk} {lmk_ch} {delay_ps}")

    # ---- AD9508 采样时钟控制 ----

    def _send_ad9508_state(self, frontend: int, enable: bool) -> Tuple[bool, str]:
        """设置 AD9508 采样时钟输出 → ad9508_state <dev> <ch> <0|1>"""
        if frontend not in self.AD9508_FRONTEND_TO_DEVICE_CHANNELS:
            return False, f"前端 {frontend} 无 AD9508 映射"
        for dev, ch in self.AD9508_FRONTEND_TO_DEVICE_CHANNELS[frontend]:
            ok, msg = self._send_cmd(f"ad9508_state {dev} {ch} {1 if enable else 0}")
            if not ok:
                return False, msg
        return True, "okay"

    # ---- 电源控制 ----

    def _send_power(self, channel: int, enable: bool) -> Tuple[bool, str]:
        """设置 AD4080 前端电源 → power<channel> <0|1>"""
        return self._send_cmd(f"power{channel} {1 if enable else 0}")

    # =========================================================================
    # 旧的 send_clock_command（保留为兼容层）
    # =========================================================================

    def send_clock_command(self, clock_type: int, channel: int, enable: int) -> Tuple[bool, str]:
        """旧的时钟控制接口，内部映射到新协议"""
        if clock_type not in [1, 2]:
            return False, "时钟类型错误，必须是1(触发)或2(采样)"
        if enable not in [0, 1]:
            return False, "使能状态错误，必须是0或1"

        # 旧的通道 1/2/3 映射到新的用户通道
        # 保持向后兼容的映射: clock_type=1 ch2→trigger_port1, ch3→trigger_port2
        #                       clock_type=2 ch1→sample_port2, ch3→sample_port1
        enable_bool = enable == 1
        if clock_type == 1:  # 触发
            if channel == 2:
                return self._send_lmk_state(4, enable_bool)
            elif channel == 3:
                return self._send_lmk_state(5, enable_bool)
        elif clock_type == 2:  # 采样
            if channel == 3:
                return self._send_ad9508_state(4, enable_bool)
            elif channel == 1:
                return self._send_ad9508_state(5, enable_bool)
        return False, f"不支持的 clock_type={clock_type}, channel={channel}"

    # =========================================================================
    # 状态管理
    # =========================================================================

    def _update_clock_state(self, clock_type: int, channel: int, enable: int):
        state_key = self._get_state_key(clock_type, channel)
        if state_key:
            self.clock_states[state_key] = (enable == 1)

    def _get_state_key(self, clock_type: int, channel: int) -> Optional[str]:
        if clock_type == 1:
            if channel == 2: return 'trigger_ch4'
            elif channel == 3: return 'trigger_ch5'
        elif clock_type == 2:
            if channel == 3: return 'sample_ch4'
            elif channel == 1: return 'sample_ch5'
        return None

    def get_clock_state(self, clock_type: int, channel: int) -> Optional[bool]:
        state_key = self._get_state_key(clock_type, channel)
        return self.clock_states.get(state_key) if state_key else None

    def get_current_mode(self) -> Optional[str]:
        return self.current_mode

    def get_mode_info(self, mode: str) -> Optional[Dict[str, Any]]:
        return self.S_MODES.get(mode.upper())

    def list_available_modes(self) -> Dict[str, str]:
        return {mode: info['description'] for mode, info in self.S_MODES.items()}

    # =========================================================================
    # S 参数模式设置
    # =========================================================================

    def _apply_s_mode(self, mode: str) -> Tuple[bool, str]:
        """应用 S 参数模式：电源 → LMK 触发时钟 → AD9508 采样时钟"""
        mode = mode.upper()
        if mode not in self.S_MODES:
            return False, f"不支持的S参数模式: {mode}"

        cfg = self.S_MODES[mode]
        results = []

        # 0. 先打开通道电源（CH4 和 CH5）
        for ch in self.DEFAULT_CHANNELS:
            ok, msg = self._send_power(ch, True)
            results.append((ok, msg))
            time.sleep(0.02)

        # 1. 配置 LMK 触发时钟
        for ch, on in cfg['trigger'].items():
            ok, msg = self._send_lmk_state(ch, on)
            results.append((ok, msg))
            time.sleep(0.02)

        # 2. 配置 AD9508 采样时钟
        for ch, on in cfg['sample'].items():
            ok, msg = self._send_ad9508_state(ch, on)
            results.append((ok, msg))
            time.sleep(0.02)

        all_ok = all(success for success, _ in results)
        messages = [msg for _, msg in results]

        if all_ok:
            self.current_mode = mode
            # 更新内部状态
            for ch, on in cfg['trigger'].items():
                self.clock_states[f'trigger_ch{ch}'] = on
            for ch, on in cfg['sample'].items():
                self.clock_states[f'sample_ch{ch}'] = on
            return True, f"成功设置 {mode} 模式: {cfg['description']}"
        else:
            return False, f"设置 {mode} 模式失败: {'; '.join(messages)}"

    def set_s_mode(self, mode: str) -> Tuple[bool, str]:
        """设置 S 参数测量模式 (S11/S12/S21/S22)"""
        return self._apply_s_mode(mode)

    def set_s11_mode(self) -> Tuple[bool, str]:
        """S11: 端口1反射测量"""
        return self.set_s_mode('S11')

    def set_s12_mode(self) -> Tuple[bool, str]:
        """S12: 端口2→端口1传输测量"""
        return self.set_s_mode('S12')

    def set_s21_mode(self) -> Tuple[bool, str]:
        """S21: 端口1→端口2传输测量"""
        return self.set_s_mode('S21')

    def set_s22_mode(self) -> Tuple[bool, str]:
        """S22: 端口2反射测量"""
        return self.set_s_mode('S22')

    # =========================================================================
    # 全开 / 全关
    # =========================================================================

    def enable_all_clocks(self) -> Tuple[bool, str]:
        """启用所有通道：电源 → 触发时钟 → 采样时钟"""
        results = []
        for ch in self.DEFAULT_CHANNELS:
            ok, msg = self._send_power(ch, True)
            results.append((ok, msg))
            time.sleep(0.02)
            ok, msg = self._send_lmk_state(ch, True)
            results.append((ok, msg))
            time.sleep(0.02)
            ok, msg = self._send_ad9508_state(ch, True)
            results.append((ok, msg))
            time.sleep(0.02)

        all_ok = all(success for success, _ in results)
        if all_ok:
            self.current_mode = 'ALL'
            for ch in self.DEFAULT_CHANNELS:
                self.clock_states[f'trigger_ch{ch}'] = True
                self.clock_states[f'sample_ch{ch}'] = True
            return True, "所有时钟已启用"
        messages = [msg for _, msg in results]
        return all_ok, "; ".join(messages)

    def disable_all_clocks(self) -> Tuple[bool, str]:
        """禁用所有通道的触发和采样时钟"""
        results = []
        for ch in self.DEFAULT_CHANNELS:
            ok, msg = self._send_lmk_state(ch, False)
            results.append((ok, msg))
            time.sleep(0.02)
            ok, msg = self._send_ad9508_state(ch, False)
            results.append((ok, msg))
            time.sleep(0.02)

        all_ok = all(success for success, _ in results)
        if all_ok:
            self.current_mode = None
            for ch in self.DEFAULT_CHANNELS:
                self.clock_states[f'trigger_ch{ch}'] = False
                self.clock_states[f'sample_ch{ch}'] = False
            return True, "所有时钟已禁用"
        messages = [msg for _, msg in results]
        return all_ok, "; ".join(messages)

    # =========================================================================
    # 新增公共方法：单通道控制
    # =========================================================================

    def enable_channel(self, channel: int) -> Tuple[bool, str]:
        """启用单个通道的触发时钟"""
        ok, msg = self._send_lmk_state(channel, True)
        if ok:
            self.clock_states[f'trigger_ch{channel}'] = True
        return ok, msg

    def disable_channel(self, channel: int) -> Tuple[bool, str]:
        """禁用单个通道的触发时钟"""
        ok, msg = self._send_lmk_state(channel, False)
        if ok:
            self.clock_states[f'trigger_ch{channel}'] = False
        return ok, msg

    def set_clock_mode(self, channel: int, mode: int) -> Tuple[bool, str]:
        """设置 LMK 通道模式 (0=bypass, 1=div, 2=delay, 3=div+delay)"""
        return self._send_lmk_mode(channel, mode)

    def set_clock_mode_by_name(self, channel: int, mode_name: str) -> Tuple[bool, str]:
        """按名称设置 LMK 通道模式 (bypass/div/delay/div-delay)"""
        key = mode_name.strip().lower().replace(" ", "-").replace("_", "-")
        if key not in self.LMK_MODE_NAMES:
            return False, f"不支持的模式名: {mode_name}"
        return self._send_lmk_mode(channel, self.LMK_MODE_NAMES[key])

    def set_clock_divider(self, channel: int, div: int) -> Tuple[bool, str]:
        """设置 LMK 分频值（偶数 2..510）"""
        return self._send_lmk_div(channel, div)

    def set_clock_delay(self, channel: int, delay_ps: int) -> Tuple[bool, str]:
        """设置 LMK 延时（ps）"""
        return self._send_lmk_delay(channel, delay_ps)

    def set_power(self, channel: int, enable: bool) -> Tuple[bool, str]:
        """设置 AD4080 前端电源"""
        return self._send_power(channel, enable)

    # =========================================================================
    # 状态查询与验证
    # =========================================================================

    def get_status(self) -> Dict[str, Any]:
        """获取当前时钟状态"""
        return {
            'current_mode': self.current_mode,
            'trigger_ch4': self.clock_states['trigger_ch4'],
            'trigger_ch5': self.clock_states['trigger_ch5'],
            'sample_ch4': self.clock_states['sample_ch4'],
            'sample_ch5': self.clock_states['sample_ch5'],
            'tcp_connected': self.tcp_client is not None and self.tcp_client.connected,
        }

    def validate_configuration(self, mode: str) -> Tuple[bool, str]:
        """验证当前配置是否匹配指定 S 参数模式"""
        mode = mode.upper()
        if mode not in self.S_MODES:
            return False, f"不支持的S参数模式: {mode}"

        cfg = self.S_MODES[mode]
        trigger_ok = all(
            self.clock_states.get(f'trigger_ch{ch}') == on
            for ch, on in cfg['trigger'].items()
        )
        sample_ok = all(
            self.clock_states.get(f'sample_ch{ch}') == on
            for ch, on in cfg['sample'].items()
        )

        if trigger_ok and sample_ok:
            return True, f"当前配置匹配 {mode} 模式"
        return False, f"当前配置不匹配 {mode} 模式"

    def cleanup(self):
        """清理资源"""
        self.tcp_client = None
        self.clock_states = {
            'trigger_ch4': False,
            'trigger_ch5': False,
            'sample_ch4': False,
            'sample_ch5': False,
        }
        self.current_mode = None
