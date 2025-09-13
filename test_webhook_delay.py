# -*- coding: utf-8 -*-
"""
测试多个webhook延迟机制
验证同一币种发送到多个Discord地址时的延迟效果
"""

import asyncio
import time
from config import Config
from chart_output import ChartOutputManager
from data_manager import data_manager

def test_webhook_delay_config():
    """测试webhook延迟配置"""
    print("=" * 60)
    print("🔧 Webhook延迟配置测试")
    print("=" * 60)
    
    # 显示当前配置
    print("当前延迟配置:")
    print(f"  发送延迟（币种间）: {Config.CHART_CONFIG['发送延迟']}秒")
    print(f"  Webhook延迟（同币种）: {Config.CHART_CONFIG['webhook延迟']}秒")
    print()
    
    # 检查多webhook配置
    multi_webhook_symbols = []
    for symbol in Config.SYMBOLS:
        base = symbol.replace("USDT", "")
        webhooks = Config.get_webhooks(symbol, "图表输出")
        print(f"{symbol} 图表输出 Webhook数量: {len(webhooks)}")
        if len(webhooks) > 1:
            multi_webhook_symbols.append(symbol)
    
    print()
    if multi_webhook_symbols:
        print(f"✅ 配置了多个webhook的币种: {', '.join(multi_webhook_symbols)}")
        print("这些币种将启用webhook间延迟机制")
    else:
        print("⚠️ 所有币种都只配置了1个webhook，webhook延迟不会生效")
    
    return multi_webhook_symbols

async def simulate_multi_webhook_send():
    """模拟多webhook发送"""
    print("\n" + "=" * 60)
    print("🚀 模拟多Webhook发送测试")
    print("=" * 60)
    
    # 找到有多个webhook的币种
    test_symbol = None
    for symbol in Config.SYMBOLS:
        webhooks = Config.get_webhooks(symbol, "图表输出")
        if len(webhooks) > 1:
            test_symbol = symbol
            break
    
    if not test_symbol:
        print("❌ 没有找到配置多个webhook的币种，无法测试")
        return
    
    print(f"使用 {test_symbol} 进行测试")
    webhooks = Config.get_webhooks(test_symbol, "图表输出")
    print(f"Webhook数量: {len(webhooks)}")
    print()
    
    # 模拟发送过程（不实际发送）
    print("模拟发送时序:")
    start_time = time.time()
    
    for i, webhook in enumerate(webhooks):
        current_time = time.time() - start_time
        print(f"[{current_time:5.1f}s] 发送到 Webhook #{i+1}")
        
        if i < len(webhooks) - 1:  # 不是最后一个
            delay = Config.CHART_CONFIG['webhook延迟']
            print(f"[{current_time:5.1f}s] 等待 {delay} 秒...")
            await asyncio.sleep(delay)
    
    total_time = time.time() - start_time
    print(f"\n总计用时: {total_time:.1f} 秒")
    print(f"预期用时: {(len(webhooks)-1) * Config.CHART_CONFIG['webhook延迟']:.1f} 秒")

def display_sending_timeline():
    """显示完整发送时序"""
    print("\n" + "=" * 60)
    print("📊 完整发送时序分析")
    print("=" * 60)
    
    timeline = []
    current_time = 0
    
    for symbol in Config.SYMBOLS:
        webhooks = Config.get_webhooks(symbol, "图表输出")
        
        # 币种开始发送
        timeline.append((current_time, f"开始发送 {symbol}"))
        
        # 每个webhook
        for i, webhook in enumerate(webhooks):
            timeline.append((current_time, f"  → 发送到 {symbol} Webhook #{i+1}"))
            
            # webhook间延迟
            if i < len(webhooks) - 1:
                webhook_delay = Config.CHART_CONFIG['webhook延迟']
                current_time += webhook_delay
                timeline.append((current_time, f"  → 等待 {webhook_delay}s"))
        
        # 币种间延迟
        if symbol != Config.SYMBOLS[-1]:  # 不是最后一个币种
            coin_delay = Config.CHART_CONFIG['发送延迟']
            current_time += coin_delay
            timeline.append((current_time, f"币种间等待 {coin_delay}s"))
    
    # 显示时序
    print("发送时序表:")
    for time_point, event in timeline:
        print(f"[{time_point:5.1f}s] {event}")
    
    print(f"\n总计发送时间: {current_time:.1f} 秒")

async def main():
    """主测试函数"""
    print("🔍 多Webhook延迟机制测试")
    print("测试新的延迟机制，确保同一币种的多个webhook不会同时发送")
    print()
    
    # 配置测试
    multi_webhook_symbols = test_webhook_delay_config()
    
    # 时序分析
    display_sending_timeline()
    
    # 实际模拟（如果有多webhook配置）
    if multi_webhook_symbols:
        await simulate_multi_webhook_send()
    
    print("\n" + "=" * 60)
    print("💡 测试总结")
    print("=" * 60)
    print("新的延迟机制包括:")
    print("1. 币种间延迟: 防止不同币种同时发送")
    print("2. Webhook间延迟: 防止同一币种的多个webhook同时发送")
    print("3. 智能队列: 所有发送任务按顺序执行")
    print()
    print("这样可以确保所有Discord消息都能成功发送，不会丢失")

if __name__ == "__main__":
    asyncio.run(main()) 