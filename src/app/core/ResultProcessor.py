# src/app/core/ResultProcessor.py
import numpy as np
from typing import Dict, Any, List, Tuple, Optional
import logging

logger = logging.getLogger(__name__)

class ResultProcessor:
    """结果处理器类"""
    
    def __init__(self, config):
        self.config = config
    
    def calculate_averages(self, results: Dict[str, Any]) -> Dict[str, Any]:
        """计算平均值"""
        averages = {}
      
        # ROI平均值
        averages['y_full_avg'] = np.mean(np.vstack(results['ys_full']), axis=0)
        averages['y_avg'] = np.mean(np.vstack(results['ys']), axis=0)
        averages['mag_avg_linear'] = np.mean(np.vstack(results['mags']), axis=0)
        averages['mag_avg_db'] = 20 * np.log10(averages['mag_avg_linear'])
      
        # 差分平均值
        averages['y_d_full_avg'] = np.mean(np.vstack(results['ys_d_full']), axis=0)
        averages['y_d_avg'] = np.mean(np.vstack(results['ys_d']), axis=0)
        averages['mag_d_avg_linear'] = np.mean(np.vstack(results['mags_d']), axis=0)
        averages['mag_d_avg_db'] = 20 * np.log10(averages['mag_d_avg_linear'])
      
        # 复数FFT平均值
        averages['avg_Xd'] = results['sum_Xd'] / results['success_count']
      
        return averages
    
    def get_output_filename(self, base_output_csv: str) -> str:
        """根据校准模式生成输出文件名"""
        import os
        base_name = os.path.splitext(base_output_csv)[0]
        extension = os.path.splitext(base_output_csv)[1]
      
        # 根据校准模式添加后缀
        mode_suffix = f"_{self.config.cal_mode.lower()}"
        return f"{base_name}{mode_suffix}{extension}"
    
    def prepare_statistics(self, results: Dict[str, Any]) -> Dict[str, Any]:
        """准备统计信息"""
        stats = {
            'total_files': results['total_files'],
            'successful_files': results['success_count'],
            'success_rate': results['success_count'] / results['total_files'],
            'calibration_mode': self.config.cal_mode,
            'config': {
                'input_dir': self.config.input_dir,
                'clock_freq': self.config.clock_freq,
                'trigger_freq': self.config.trigger_freq,
                'n_points': self.config.n_points,
                'roi_range': f"{self.config.roi_start_tenths}%-{self.config.roi_end_tenths}%",
                'cal_mode': self.config.cal_mode
            }
        }
        return stats
