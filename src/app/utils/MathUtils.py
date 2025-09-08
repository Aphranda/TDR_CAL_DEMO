# src/app/utils/MathUtils.py
import numpy as np
import logging

logger = logging.getLogger(__name__)

class MathUtils:
    """数学计算工具类"""
    
    @staticmethod
    def invert_bits_uint32(data: np.ndarray) -> np.ndarray:
        """
        将uint32数组中的所有位取反（按位NOT操作）
        
        Args:
            data: 输入的uint32数组
            
        Returns:
            np.ndarray: 位取反后的uint32数组
            
        Raises:
            ValueError: 如果输入不是uint32类型
        """
        if not isinstance(data, np.ndarray):
            raise ValueError("输入必须是numpy数组")
            
        if data.dtype != np.uint32:
            raise ValueError(f"输入数据类型必须是uint32，当前是{data.dtype}")
        
        try:
            # 使用按位NOT操作符 ~ 进行位取反
            inverted_data = ~data
            
            logger.debug(f"成功对uint32数组进行位取反，数组形状: {data.shape}")
            return inverted_data
            
        except Exception as e:
            logger.error(f"位取反操作失败: {str(e)}")
            raise
    
    @staticmethod
    def invert_bits_uint32_safe(data: np.ndarray) -> np.ndarray:
        """
        安全的uint32位取反操作，自动处理数据类型转换
        
        Args:
            data: 输入的数组，可以是任何整数类型
            
        Returns:
            np.ndarray: 位取反后的uint32数组
        """
        if not isinstance(data, np.ndarray):
            data = np.array(data)
        
        # 确保数据是uint32类型
        if data.dtype != np.uint32:
            try:
                data = data.astype(np.uint32)
                logger.debug(f"将数据类型转换为uint32: {data.dtype} -> uint32")
            except Exception as e:
                logger.error(f"数据类型转换失败: {str(e)}")
                raise
        
        return MathUtils.invert_bits_uint32(data)

# 为了方便使用，提供模块级别的函数
def invert_uint32_bits(data: np.ndarray) -> np.ndarray:
    """模块级别的uint32位取反函数"""
    return MathUtils.invert_bits_uint32(data)

def invert_uint32_bits_safe(data: np.ndarray) -> np.ndarray:
    """模块级别的安全uint32位取反函数"""
    return MathUtils.invert_bits_uint32_safe(data)
