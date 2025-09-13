# -*- coding: utf-8 -*-
"""
快速测试脚本
运行监控系统几分钟后自动停止
"""

import time
import threading
from main import MarketDepthMonitor
from config import Config

def run_test():
    """运行测试"""
    print("=" * 60)
    print("快速测试 - 币安市场深度监控系统")
    print("=" * 60)
    print("配置状态:")
    print(f"  - 文本输出: {'启用' if Config.is_output_enabled('文本输出') else '禁用'}")
    print(f"  - 图表输出: {'启用' if Config.is_output_enabled('图表输出') else '禁用'}")
    print(f"  - 图表输出间隔: {Config.SEND_INTERVALS['图表输出']}秒")
    print("=" * 60)
    
    # 创建监控器
    monitor = MarketDepthMonitor()
    
    # 在单独线程中启动监控
    def start_monitor():
        try:
            monitor.start()
        except Exception as e:
            print(f"监控启动出错: {e}")
    
    monitor_thread = threading.Thread(target=start_monitor, daemon=True)
    monitor_thread.start()
    
    # 运行120秒（2分钟）
    test_duration = 120
    print(f"测试将运行 {test_duration} 秒...")
    
    try:
        time.sleep(test_duration)
    except KeyboardInterrupt:
        print("\n用户中断测试")
    finally:
        print("停止监控...")
        monitor.stop()
        print("测试完成")

if __name__ == "__main__":
    run_test() 