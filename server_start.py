#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
服务器启动脚本
专门用于服务器部署，无需用户交互确认
"""

import sys
import os
import signal
import time
from main import MarketDepthMonitor, print_system_info

def signal_handler(sig, frame):
    """处理信号，优雅关闭"""
    print(f'\n收到信号 {sig}，正在关闭监控系统...')
    sys.exit(0)

def main():
    """主函数"""
    try:
        # 注册信号处理器
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
        
        print("=" * 60)
        print("币安市场深度监控系统 - 服务器模式启动")
        print("=" * 60)
        
        # 打印系统信息
        print_system_info()
        
        print("\n服务器模式：自动启动，无需确认")
        print("提示：使用 Ctrl+C 或发送 SIGTERM 信号来停止程序")
        print("=" * 60)
        
        # 创建并启动监控器
        monitor = MarketDepthMonitor()
        monitor.start()
        
    except KeyboardInterrupt:
        print("\n收到键盘中断，程序正在退出...")
    except Exception as e:
        print(f"\n程序发生异常: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main() 