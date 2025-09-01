# src/app/core/ClockController.py
import time
from typing import Optional, Tuple, Dict, Any

class ClockController:
    """时钟控制类，用于控制Port1和Port2的触发时钟和采样时钟"""
    
    # S参数测量模式定义
    S_MODES = {
        'S11': {
            'description': '端口1反射测量',
            'trigger': {'port1': True, 'port2': False},
            'sample': {'port1': True, 'port2': False}
        },
        'S21': {
            'description': '端口1到端口2传输测量',
            'trigger': {'port1': True, 'port2': False},
            'sample': {'port1': False, 'port2': True}
        },
        'S12': {
            'description': '端口2到端口1传输测量',
            'trigger': {'port1': False, 'port2': True},
            'sample': {'port1': True, 'port2': False}
        },
        'S22': {
            'description': '端口2反射测量',
            'trigger': {'port1': False, 'port2': True},
            'sample': {'port1': False, 'port2': True}
        }
    }
    
    def __init__(self, tcp_client=None):
        self.tcp_client = tcp_client
        self.clock_states = {
            'trigger_port1': False,
            'trigger_port2': False,
            'sample_port1': False,
            'sample_port2': False
        }
        self.current_mode = None  # 当前S参数模式
    
    def set_tcp_client(self, tcp_client):
        """设置TCP客户端"""
        self.tcp_client = tcp_client
    
    def send_clock_command(self, clock_type: int, channel: int, enable: int) -> Tuple[bool, str]:
        """
        发送时钟控制命令
        
        参数:
            clock_type: 时钟类型 (1=触发信号, 2=采样信号)
            channel: 通道号 (1-7)
            enable: 使能状态 (0=关闭, 1=开启)
        
        返回:
            (成功状态, 消息)
        """
        if not self.tcp_client or not self.tcp_client.connected:
            return False, "TCP客户端未连接"
        
        if clock_type not in [1, 2]:
            return False, "时钟类型错误，必须是1(触发)或2(采样)"
        
        if channel not in range(1, 8):
            return False, "通道号错误，必须是1-7"
        
        if enable not in [0, 1]:
            return False, "使能状态错误，必须是0或1"
        
        # 构建命令: Lmk 1 1 1
        command = f"lmk_state {clock_type} {channel} {enable}\r\n"  # 添加回车换行符
        
        try:
            # 使用TcpClient的send方法发送命令
            self.tcp_client.send(command)
            time.sleep(0.1)
            success, response = self.tcp_client.send(command)
            if success:
                # 更新状态
                self._update_clock_state(clock_type, channel, enable)
                return True, f"时钟控制成功: {command.strip()}"
            else:
                return False, f"时钟控制失败: {response}"
        except Exception as e:
            return False, f"发送命令时发生错误: {str(e)}"
    
    def _update_clock_state(self, clock_type: int, channel: int, enable: int):
        """更新时钟状态"""
        state_key = self._get_state_key(clock_type, channel)
        if state_key:
            self.clock_states[state_key] = (enable == 1)
    
    def _get_state_key(self, clock_type: int, channel: int) -> Optional[str]:
        """获取状态字典的键"""
        if clock_type == 1:  # 触发信号
            if channel == 1:
                return 'trigger_port1'
            elif channel == 2:
                return 'trigger_port2'
        elif clock_type == 2:  # 采样信号
            if channel == 1:
                return 'sample_port1'
            elif channel == 2:
                return 'sample_port2'
        return None
    
    def get_clock_state(self, clock_type: int, channel: int) -> Optional[bool]:
        """获取时钟状态"""
        state_key = self._get_state_key(clock_type, channel)
        return self.clock_states.get(state_key) if state_key else None
    
    def get_current_mode(self) -> Optional[str]:
        """获取当前S参数模式"""
        return self.current_mode
    
    def get_mode_info(self, mode: str) -> Optional[Dict[str, Any]]:
        """获取指定模式的信息"""
        return self.S_MODES.get(mode.upper())
    
    def list_available_modes(self) -> Dict[str, str]:
        """获取所有可用的S参数模式"""
        return {mode: info['description'] for mode, info in self.S_MODES.items()}
    
    def set_s_mode(self, mode: str) -> Tuple[bool, str]:
        """
        设置S参数测量模式
        
        参数:
            mode: S参数模式 (S11, S12, S21, S22)
        
        返回:
            (成功状态, 消息)
        """
        mode = mode.upper()
        if mode not in self.S_MODES:
            return False, f"不支持的S参数模式: {mode}"
        
        mode_config = self.S_MODES[mode]
        
        
        results = []
        
        # 配置触发时钟
        if mode_config['trigger']['port1']:
            success, message = self.send_clock_command(1, 2, 1)  # 触发 Port1
            time.sleep(0.1)
            success, message = self.send_clock_command(1, 3, 0)  # 关闭 Port2
            results.append((success, message))
            time.sleep(0.1)
        if mode_config['trigger']['port2']:
            success, message = self.send_clock_command(1, 3, 1)  # 触发 Port2
            time.sleep(0.1)
            success, message = self.send_clock_command(1, 2, 0)  # 关闭 Port1
            results.append((success, message))
            time.sleep(0.1)
        
        # 配置采样时钟
        if mode_config['sample']['port1']:
            success, message = self.send_clock_command(2, 3, 1)  # 采样 Port1
            results.append((success, message))
            time.sleep(0.1)
        if mode_config['sample']['port2']:
            success, message = self.send_clock_command(2, 1, 1)  # 采样 Port2
            results.append((success, message))
            time.sleep(0.1)
        
        # 检查所有命令是否成功
        all_success = all(success for success, _ in results)
        messages = [msg for _, msg in results]
        
        if all_success:
            self.current_mode = mode
            return True, f"成功设置 {mode} 模式: {mode_config['description']}"
        else:
            return False, f"设置 {mode} 模式失败: {'; '.join(messages)}"
    
    def set_s11_mode(self) -> Tuple[bool, str]:
        """设置S11模式（端口1反射测量）"""
        return self.set_s_mode('S11')
    
    def set_s12_mode(self) -> Tuple[bool, str]:
        """设置S12模式（端口1到端口2传输测量）"""
        return self.set_s_mode('S12')
    
    def set_s21_mode(self) -> Tuple[bool, str]:
        """设置S21模式（端口2到端口1传输测量）"""
        return self.set_s_mode('S21')
    
    def set_s22_mode(self) -> Tuple[bool, str]:
        """设置S22模式（端口2反射测量）"""
        return self.set_s_mode('S22')
    
    def enable_all_clocks(self) -> Tuple[bool, str]:
        """启用所有时钟"""
        results = []
        for clock_type in [1, 2]:
            for channel in [1, 2]:
                success, message = self.send_clock_command(clock_type, channel, 1)
                results.append((success, message))
                time.sleep(0.1)  # 短暂延迟
        
        # 检查所有命令是否成功
        all_success = all(success for success, _ in results)
        messages = [msg for _, msg in results]
        
        if all_success:
            self.current_mode = 'ALL'  # 特殊模式标识
            return all_success, "所有时钟已启用"
        else:
            return all_success, "; ".join(messages)
    
    def disable_all_clocks(self) -> Tuple[bool, str]:
        """禁用所有时钟"""
        results = []
        for clock_type in [1, 2]:
            for channel in [1, 2]:
                success, message = self.send_clock_command(clock_type, channel, 0)
                results.append((success, message))
                time.sleep(0.1)  # 短暂延迟
        
        # 检查所有命令是否成功
        all_success = all(success for success, _ in results)
        messages = [msg for _, msg in results]
        
        if all_success:
            self.current_mode = None
            return all_success, "所有时钟已禁用"
        else:
            return all_success, "; ".join(messages)
    
    def get_status(self) -> Dict[str, Any]:
        """获取当前时钟状态"""
        return {
            'current_mode': self.current_mode,
            'trigger_port1': self.clock_states['trigger_port1'],
            'trigger_port2': self.clock_states['trigger_port2'],
            'sample_port1': self.clock_states['sample_port1'],
            'sample_port2': self.clock_states['sample_port2'],
            'tcp_connected': self.tcp_client is not None and self.tcp_client.connected
        }
    
    def validate_configuration(self, mode: str) -> Tuple[bool, str]:
        """
        验证当前配置是否匹配指定模式
        
        参数:
            mode: 要验证的S参数模式
        
        返回:
            (是否匹配, 消息)
        """
        mode = mode.upper()
        if mode not in self.S_MODES:
            return False, f"不支持的S参数模式: {mode}"
        
        mode_config = self.S_MODES[mode]
        current_states = self.clock_states
        
        # 检查触发时钟配置
        trigger_match = (
            current_states['trigger_port1'] == mode_config['trigger']['port1'] and
            current_states['trigger_port2'] == mode_config['trigger']['port2']
        )
        
        # 检查采样时钟配置
        sample_match = (
            current_states['sample_port1'] == mode_config['sample']['port1'] and
            current_states['sample_port2'] == mode_config['sample']['port2']
        )
        
        if trigger_match and sample_match:
            return True, f"当前配置匹配 {mode} 模式"
        else:
            return False, f"当前配置不匹配 {mode} 模式"
    
    def cleanup(self):
        """清理资源"""
        self.tcp_client = None
        self.clock_states = {
            'trigger_port1': False,
            'trigger_port2': False,
            'sample_port1': False,
            'sample_port2': False
        }
        self.current_mode = None
