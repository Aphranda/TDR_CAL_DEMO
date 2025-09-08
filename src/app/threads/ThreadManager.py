# src/app/threads/ThreadManager.py
from PyQt5.QtCore import QObject
from typing import Dict, List

class ThreadManager(QObject):
    """线程管理器，用于统一管理所有工作线程"""
    
    def __init__(self):
        super().__init__()
        self.active_threads = {}  # 存储活跃线程
    
    def register_thread(self, thread_id, thread_object):
        """注册线程"""
        self.active_threads[thread_id] = thread_object
    
    def unregister_thread(self, thread_id):
        """注销线程"""
        if thread_id in self.active_threads:
            del self.active_threads[thread_id]
    
    def stop_all_threads(self):
        """停止所有线程"""
        for thread_id, thread in self.active_threads.items():
            if hasattr(thread, 'stop'):
                thread.stop()
            if hasattr(thread, 'quit'):
                thread.quit()
        
        self.active_threads.clear()
    
    def get_active_thread_count(self):
        """获取活跃线程数量"""
        return len(self.active_threads)
