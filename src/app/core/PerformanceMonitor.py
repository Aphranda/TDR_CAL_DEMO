# src/app/core/PerformanceMonitor.py
import time
import functools
import tracemalloc
import logging
import statistics
from typing import Callable, Any, Optional, Dict, List
from collections import defaultdict

logger = logging.getLogger(__name__)


class PerformanceMonitor:
    """
    性能监控装饰器类，用于检测函数执行时间、内存使用等性能指标
    提供详细的性能分析和报告
    """
    
    # 类级别的性能统计
    _performance_stats = defaultdict(list)
    _call_count = defaultdict(int)
    
    def __init__(self, 
                 enable_time: bool = True,
                 enable_memory: bool = True,
                 enable_logging: bool = True,
                 log_level: int = logging.INFO,
                 threshold_ms: Optional[float] = None,
                 detailed_memory: bool = False,
                 track_calls: bool = True,
                 use_print: bool = True):  # 新增参数，控制是否使用print
        """
        初始化性能监控器
        
        Args:
            enable_time: 是否启用时间监控
            enable_memory: 是否启用内存监控
            enable_logging: 是否启用日志记录
            log_level: 日志级别
            threshold_ms: 时间阈值(毫秒)，超过此阈值才记录日志
            detailed_memory: 是否启用详细内存分析
            track_calls: 是否跟踪调用统计
            use_print: 是否使用print直接输出（新增）
        """
        self.enable_time = enable_time
        self.enable_memory = enable_memory
        self.enable_logging = enable_logging
        self.log_level = log_level
        self.threshold_ms = threshold_ms
        self.detailed_memory = detailed_memory
        self.track_calls = track_calls
        self.use_print = use_print  # 新增
        
        # 初始化内存跟踪
        if self.enable_memory:
            tracemalloc.start()
    
    def __call__(self, func: Callable) -> Callable:
        """
        装饰器调用方法
        """
        @functools.wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            # 性能数据字典
            performance_data = {
                'function_name': func.__name__,
                'timestamp': time.time(),
                'args_count': len(args),
                'kwargs_count': len(kwargs)
            }
            
            # 记录开始时间
            if self.enable_time:
                start_time = time.perf_counter()
            
            # 记录开始内存
            if self.enable_memory:
                snapshot1 = tracemalloc.take_snapshot()
            
            try:
                # 执行被装饰的函数
                result = func(*args, **kwargs)
                
                # 记录结束时间
                if self.enable_time:
                    end_time = time.perf_counter()
                    execution_time_ms = (end_time - start_time) * 1000
                    performance_data['execution_time_ms'] = execution_time_ms
                    performance_data['success'] = True
                
                # 记录结束内存
                if self.enable_memory:
                    snapshot2 = tracemalloc.take_snapshot()
                    top_stats = snapshot2.compare_to(snapshot1, 'lineno')
                    
                    # 获取内存使用统计
                    memory_usage = sum(stat.size for stat in top_stats)
                    performance_data['memory_usage_bytes'] = memory_usage
                    performance_data['memory_stats'] = top_stats
                    
                    if self.detailed_memory:
                        performance_data['detailed_memory'] = self._analyze_memory_usage(top_stats)
                
                # 记录性能数据
                self._log_performance(performance_data)
                
                # 更新统计信息
                if self.track_calls and self.enable_time:
                    self._update_stats(performance_data)
                
                return result
                
            except Exception as e:
                # 记录异常情况下的性能数据
                if self.enable_time:
                    end_time = time.perf_counter()
                    execution_time_ms = (end_time - start_time) * 1000
                    performance_data['execution_time_ms'] = execution_time_ms
                
                performance_data['error'] = str(e)
                performance_data['success'] = False
                
                self._log_performance(performance_data, is_error=True)
                
                # 更新统计信息（包括错误情况）
                if self.track_calls and self.enable_time:
                    self._update_stats(performance_data)
                
                raise e
        
        return wrapper
    
    def _analyze_memory_usage(self, memory_stats) -> Dict:
        """详细分析内存使用情况"""
        analysis = {
            'total_memory_bytes': sum(stat.size for stat in memory_stats),
            'top_allocations': [],
            'by_file': defaultdict(int),
            'by_traceback': defaultdict(int)
        }
        
        # 分析前10个内存分配
        for i, stat in enumerate(memory_stats[:10]):
            analysis['top_allocations'].append({
                'rank': i + 1,
                'size_bytes': stat.size,
                'size_mb': stat.size / (1024 * 1024),
                'traceback': str(stat.traceback),
                'filename': stat.traceback._frames[0][0] if stat.traceback._frames else 'unknown'
            })
        
        # 按文件分组统计
        for stat in memory_stats:
            if stat.traceback._frames:
                filename = stat.traceback._frames[0][0]
                analysis['by_file'][filename] += stat.size
        
        return analysis
    
    def _update_stats(self, performance_data: Dict) -> None:
        """更新性能统计"""
        func_name = performance_data['function_name']
        execution_time = performance_data.get('execution_time_ms', 0)
        
        self._performance_stats[func_name].append(execution_time)
        self._call_count[func_name] += 1
    
    def _log_performance(self, performance_data: Dict, is_error: bool = False) -> None:
        """
        记录性能数据到日志
        """
        if not self.enable_logging:
            return
        
        func_name = performance_data['function_name']
        
        # 检查时间阈值
        if (self.threshold_ms is not None and 
            'execution_time_ms' in performance_data and
            performance_data['execution_time_ms'] < self.threshold_ms):
            return
        
        # 构建详细的日志消息
        log_lines = []
        
        # 头部信息
        status = "ERROR" if is_error else "SUCCESS" if performance_data.get('success', False) else "UNKNOWN"
        log_lines.append(f"=== PERFORMANCE REPORT: {func_name} [{status}] ===")
        
        # 时间信息
        if 'execution_time_ms' in performance_data:
            time_ms = performance_data['execution_time_ms']
            log_lines.append(f"⏰ Execution Time: {time_ms:.2f} ms")
            
            # 时间分类
            if time_ms < 10:
                time_category = "VERY FAST"
            elif time_ms < 100:
                time_category = "FAST"
            elif time_ms < 1000:
                time_category = "MODERATE"
            elif time_ms < 5000:
                time_category = "SLOW"
            else:
                time_category = "VERY SLOW"
            log_lines.append(f"   Category: {time_category}")
        
        # 内存信息
        if 'memory_usage_bytes' in performance_data:
            memory_bytes = performance_data['memory_usage_bytes']
            memory_mb = memory_bytes / (1024 * 1024)
            log_lines.append(f"💾 Memory Usage: {memory_mb:.3f} MB ({memory_bytes} bytes)")
            
            # 内存分类
            if memory_bytes < 1024:  # 1KB
                memory_category = "TINY"
            elif memory_bytes < 1024 * 1024:  # 1MB
                memory_category = "SMALL"
            elif memory_bytes < 10 * 1024 * 1024:  # 10MB
                memory_category = "MODERATE"
            elif memory_bytes < 100 * 1024 * 1024:  # 100MB
                memory_category = "LARGE"
            else:
                memory_category = "HUGE"
            log_lines.append(f"   Category: {memory_category}")
        
        # 详细内存分析
        if self.detailed_memory and 'detailed_memory' in performance_data:
            detailed = performance_data['detailed_memory']
            log_lines.append("📊 Detailed Memory Analysis:")
            log_lines.append(f"   Total Memory: {detailed['total_memory_bytes'] / (1024 * 1024):.3f} MB")
            
            if detailed['top_allocations']:
                log_lines.append("   Top Memory Allocations:")
                for alloc in detailed['top_allocations'][:3]:  # 只显示前3个
                    log_lines.append(f"     #{alloc['rank']}: {alloc['size_mb']:.3f} MB - {alloc['filename']}")
        
        # 错误信息
        if is_error and 'error' in performance_data:
            log_lines.append(f"❌ Error: {performance_data['error']}")
        
        # 参数信息
        log_lines.append(f"📋 Parameters: {performance_data['args_count']} args, {performance_data['kwargs_count']} kwargs")
        
        # 时间戳
        log_lines.append(f"🕒 Timestamp: {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(performance_data['timestamp']))}")
        
        # 性能建议
        if 'execution_time_ms' in performance_data:
            suggestion = self._get_performance_suggestion(performance_data)
            if suggestion:
                log_lines.append(f"💡 Suggestion: {suggestion}")
        
        log_lines.append("=" * 50)
        
        # 记录日志
        log_message = "\n".join(log_lines)
        
        # 使用print输出（新增）
        if self.use_print:
            print(log_message)
        else:
            # 原有的logging方式
            log_level = logging.ERROR if is_error else self.log_level
            logger.log(log_level, log_message)
    
    def _get_performance_suggestion(self, performance_data: Dict) -> str:
        """根据性能数据提供建议"""
        time_ms = performance_data.get('execution_time_ms', 0)
        memory_bytes = performance_data.get('memory_usage_bytes', 0)
        
        suggestions = []
        
        # 时间相关建议
        if time_ms > 1000:  # 超过1秒
            suggestions.append("考虑优化算法或使用缓存")
        elif time_ms > 100:  # 超过100ms
            suggestions.append("检查是否有不必要的计算")
        
        # 内存相关建议
        if memory_bytes > 10 * 1024 * 1024:  # 超过10MB
            suggestions.append("检查内存泄漏或使用更高效的数据结构")
        elif memory_bytes > 1 * 1024 * 1024:  # 超过1MB
            suggestions.append("考虑使用生成器或流式处理")
        
        return "; ".join(suggestions) if suggestions else ""
    
    @classmethod
    def get_stats_summary(cls) -> str:
        """获取性能统计摘要"""
        if not cls._performance_stats:
            return "No performance data collected yet."
        
        summary_lines = ["=== PERFORMANCE STATISTICS SUMMARY ==="]
        
        for func_name, times in cls._performance_stats.items():
            call_count = cls._call_count[func_name]
            if times:
                avg_time = statistics.mean(times)
                max_time = max(times)
                min_time = min(times)
                std_dev = statistics.stdev(times) if len(times) > 1 else 0
                
                summary_lines.append(f"\n📊 {func_name}:")
                summary_lines.append(f"   Calls: {call_count}")
                summary_lines.append(f"   Avg Time: {avg_time:.2f} ms")
                summary_lines.append(f"   Min Time: {min_time:.2f} ms")
                summary_lines.append(f"   Max Time: {max_time:.2f} ms")
                summary_lines.append(f"   Std Dev: {std_dev:.2f} ms")
                
                # 性能评级
                if avg_time < 10:
                    rating = "⭐️⭐️⭐️⭐️⭐️ (Excellent)"
                elif avg_time < 50:
                    rating = "⭐️⭐️⭐️⭐️ (Good)"
                elif avg_time < 100:
                    rating = "⭐️⭐️⭐️ (Average)"
                elif avg_time < 500:
                    rating = "⭐️⭐️ (Needs Improvement)"
                else:
                    rating = "⭐️ (Critical)"
                summary_lines.append(f"   Rating: {rating}")
        
        summary_lines.append("=" * 50)
        return "\n".join(summary_lines)
    
    @classmethod
    def clear_stats(cls):
        """清除性能统计"""
        cls._performance_stats.clear()
        cls._call_count.clear()
    
    @classmethod
    def timeit(cls, func: Callable) -> Callable:
        """类方法装饰器，仅监控时间"""
        return cls(enable_time=True, enable_memory=False, use_print=True)(func)
    
    @classmethod
    def memoryit(cls, func: Callable) -> Callable:
        """类方法装饰器，仅监控内存"""
        return cls(enable_time=False, enable_memory=True, use_print=True)(func)
    
    @classmethod
    def profile(cls, func: Callable) -> Callable:
        """类方法装饰器，全面监控（时间和内存）"""
        return cls(enable_time=True, enable_memory=True, use_print=True)(func)
    
    @classmethod
    def detailed_profile(cls, func: Callable) -> Callable:
        """类方法装饰器，详细性能分析"""
        return cls(enable_time=True, enable_memory=True, detailed_memory=True, use_print=True)(func)


# 便捷的单例实例 - 修改为使用print输出
performance_monitor = PerformanceMonitor(use_print=True)
timeit = PerformanceMonitor.timeit
memoryit = PerformanceMonitor.memoryit
profile = PerformanceMonitor.profile
detailed_profile = PerformanceMonitor.detailed_profile
