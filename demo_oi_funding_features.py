# -*- coding: utf-8 -*-
"""
OI和资金费率功能演示脚本
展示新添加的币安合约持仓量和资金费率功能
"""

import asyncio
import time
from oi_funding_data import OIFundingDataManager
from config import Config

def print_separator(title):
    """打印分隔符"""
    print("\n" + "=" * 60)
    print(f"  {title}")
    print("=" * 60)

def print_subsection(title):
    """打印子标题"""
    print(f"\n📋 {title}")
    print("-" * 40)

async def demo_oi_funding_features():
    """演示OI和资金费率功能"""
    
    print_separator("币安市场深度监控系统 - OI和资金费率功能演示")
    
    print("🎯 新功能概述:")
    print("   1. 获取币安合约的持仓量(OI)数据")
    print("   2. 获取币安合约的资金费率数据")
    print("   3. 将OI和资金费率显示在Discord图表上")
    print("   4. 支持实时更新和缓存机制")
    
    # 创建数据管理器
    manager = OIFundingDataManager()
    
    print_subsection("实时数据获取演示")
    
    for symbol in Config.SYMBOLS:
        print(f"\n💰 {symbol} 合约数据:")
        
        # 获取数据
        start_time = time.time()
        oi_value, funding_rate = await manager.get_oi_and_funding(symbol)
        elapsed_time = time.time() - start_time
        
        if oi_value is not None:
            print(f"   📊 持仓量 (OI): {oi_value:,.0f}")
        else:
            print("   ❌ 持仓量获取失败")
            
        if funding_rate is not None:
            print(f"   💵 资金费率: {funding_rate:+.4f}%")
            # 分析资金费率
            if funding_rate > 0:
                print("       └─ 正资金费率 → 多头支付空头")
            elif funding_rate < 0:
                print("       └─ 负资金费率 → 空头支付多头")
            else:
                print("       └─ 零资金费率 → 无资金费用")
        else:
            print("   ❌ 资金费率获取失败")
            
        print(f"   ⏱️ 获取耗时: {elapsed_time:.3f}秒")
    
    print_subsection("缓存机制演示")
    
    # 测试缓存
    symbol = Config.SYMBOLS[0] if Config.SYMBOLS else "BTCUSDT"
    print(f"再次获取 {symbol} 数据（应该使用缓存）...")
    
    start_time = time.time()
    cached_oi, cached_funding = await manager.get_oi_and_funding(symbol)
    cached_time = time.time() - start_time
    
    print(f"   ⚡ 缓存访问时间: {cached_time:.3f}秒")
    if cached_time < 0.1:
        print("   ✅ 缓存系统工作正常")
    else:
        print("   ⚠️ 缓存可能未生效")
    
    print_subsection("图表显示功能")
    
    print("📈 新的图表功能包括:")
    print("   • 合约市场深度图标题显示OI和资金费率")
    print("   • 主图表标题包含汇总的OI和资金费率信息")
    print("   • 自动格式化显示（千位分隔符、正负号等）")
    print("   • 优雅降级（如果数据获取失败，图表仍正常显示）")
    
    # 展示标题格式
    if oi_value is not None and funding_rate is not None:
        print(f"\n🎨 图表标题示例:")
        print(f"   子图标题: '{symbol} Futures Market Depth'")
        print(f"            'OI: {oi_value:,.0f} | Funding: {funding_rate:+.4f}%'")
        print(f"   主标题: 'Binance Market Depth & Order Book Analysis'")
        print(f"          'Futures OI: {oi_value:,.0f} | Funding Rate: {funding_rate:+.4f}%'")
    
    print_subsection("系统集成状态")
    
    print("🔧 已完成的集成:")
    print("   ✅ chart_output.py - 图表输出模块已更新")
    print("   ✅ oi_funding_data.py - 新的数据获取模块")
    print("   ✅ 同步和异步API支持")
    print("   ✅ 错误处理和降级机制")
    print("   ✅ 数据缓存减少API调用")
    
    print("\n📝 使用说明:")
    print("   1. 现有的主程序 main.py 无需修改")
    print("   2. 图表将自动包含OI和资金费率信息")
    print("   3. Discord消息会显示完整的市场数据")
    print("   4. 系统具备良好的容错性")
    
    print_separator("演示完成")
    print("🎉 OI和资金费率功能已成功添加到系统中！")
    print("现在您可以运行主程序来看到包含这些数据的图表。")

if __name__ == "__main__":
    asyncio.run(demo_oi_funding_features()) 