# -*- coding: utf-8 -*-
"""
测试延迟发送机制
验证多个币种图表发送时的延迟效果
"""

import asyncio
import time
from config import Config
from data_manager import data_manager
from chart_output import chart_output_manager

async def test_delay_mechanism():
    """测试延迟发送机制"""
    print("=" * 60)
    print("测试Discord延迟发送机制")
    print("=" * 60)
    
    # 临时设置较短的发送延迟用于测试
    original_delay = Config.CHART_CONFIG.get("发送延迟", 3)
    Config.CHART_CONFIG["发送延迟"] = 2  # 2秒延迟用于测试
    
    # 临时启用图表输出
    original_chart_enabled = Config.OUTPUT_OPTIONS["启用图表输出"] 
    Config.OUTPUT_OPTIONS["启用图表输出"] = True
    
    print(f"发送延迟设置: {Config.CHART_CONFIG['发送延迟']}秒")
    print(f"监控币种: {Config.SYMBOLS}")
    print()
    
    try:
        # 获取数据管理器的初始快照
        print("正在初始化数据...")
        data_manager.get_initial_snapshots()
        
        # 模拟同时触发多个币种的图表发送
        print("模拟同时发送多个币种的图表...")
        start_time = time.time()
        
        tasks = []
        for symbol in Config.SYMBOLS:
            spot_manager = data_manager.get_manager(symbol, False)
            futures_manager = data_manager.get_manager(symbol, True)
            
            if spot_manager and futures_manager:
                print(f"  提交 {symbol} 图表生成任务...")
                # 强制设置发送时间为0，确保会发送
                chart_output_manager.last_send_time[symbol] = 0
                
                task = chart_output_manager.process_and_send(spot_manager, futures_manager)
                tasks.append(task)
        
        # 等待所有任务完成
        if tasks:
            await asyncio.gather(*tasks)
        
        # 等待队列中的发送任务完成
        print("\n等待发送队列完成...")
        while not chart_output_manager.send_queue.empty():
            print(f"  队列中还有 {chart_output_manager.send_queue.qsize()} 个待发送任务")
            await asyncio.sleep(1)
        
        end_time = time.time()
        total_time = end_time - start_time
        
        print(f"\n总耗时: {total_time:.2f}秒")
        print(f"预期最小耗时: {len(Config.SYMBOLS) * Config.CHART_CONFIG['发送延迟']}秒")
        print("✅ 延迟发送机制测试完成")
        
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        # 恢复原始配置
        Config.CHART_CONFIG["发送延迟"] = original_delay
        Config.OUTPUT_OPTIONS["启用图表输出"] = original_chart_enabled
        
        # 停止图表输出管理器
        chart_output_manager.stop()

if __name__ == "__main__":
    asyncio.run(test_delay_mechanism()) 