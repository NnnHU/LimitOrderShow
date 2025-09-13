# -*- coding: utf-8 -*-
"""
OI和资金费率功能测试脚本
测试新添加的持仓量和资金费率数据获取功能
"""

import asyncio
import time
from oi_funding_data import OIFundingDataManager
from config import Config

async def test_oi_funding_data():
    """测试OI和资金费率数据获取功能"""
    print("=" * 60)
    print("币安OI和资金费率数据获取测试")
    print("=" * 60)
    
    # 创建数据管理器
    manager = OIFundingDataManager()
    
    # 测试交易对
    test_symbols = Config.SYMBOLS
    
    for symbol in test_symbols:
        print(f"\n🔍 测试交易对: {symbol}")
        print("-" * 40)
        
        # 测试单独获取OI数据
        print("1. 测试获取持仓量数据...")
        start_time = time.time()
        oi_value = await manager.get_open_interest(symbol)
        oi_time = time.time() - start_time
        
        if oi_value is not None:
            print(f"   ✅ 持仓量: {oi_value:,.2f}")
        else:
            print("   ❌ 获取持仓量失败")
        print(f"   ⏱️ 耗时: {oi_time:.3f}秒")
        
        # 测试单独获取资金费率数据
        print("\n2. 测试获取资金费率数据...")
        start_time = time.time()
        funding_rate = await manager.get_funding_rate(symbol)
        funding_time = time.time() - start_time
        
        if funding_rate is not None:
            print(f"   ✅ 资金费率: {funding_rate:+.4f}%")
        else:
            print("   ❌ 获取资金费率失败")
        print(f"   ⏱️ 耗时: {funding_time:.3f}秒")
        
        # 测试同时获取OI和资金费率数据
        print("\n3. 测试同时获取OI和资金费率数据...")
        start_time = time.time()
        oi_value, funding_rate = await manager.get_oi_and_funding(symbol)
        combined_time = time.time() - start_time
        
        if oi_value is not None and funding_rate is not None:
            print(f"   ✅ 持仓量: {oi_value:,.2f}")
            print(f"   ✅ 资金费率: {funding_rate:+.4f}%")
        elif oi_value is not None:
            print(f"   ✅ 持仓量: {oi_value:,.2f}")
            print("   ❌ 获取资金费率失败")
        elif funding_rate is not None:
            print("   ❌ 获取持仓量失败")
            print(f"   ✅ 资金费率: {funding_rate:+.4f}%")
        else:
            print("   ❌ 获取OI和资金费率都失败")
        print(f"   ⏱️ 耗时: {combined_time:.3f}秒")
        
        # 测试缓存功能
        print("\n4. 测试缓存功能...")
        start_time = time.time()
        cached_oi, cached_funding = await manager.get_oi_and_funding(symbol)
        cached_time = time.time() - start_time
        
        print(f"   📝 缓存访问时间: {cached_time:.3f}秒")
        if cached_time < 0.1:
            print("   ✅ 缓存工作正常")
        else:
            print("   ⚠️ 缓存可能未生效")
    
    print("\n" + "=" * 60)
    print("测试完成")
    print("=" * 60)

def test_sync_functionality():
    """测试同步功能"""
    print("\n🔄 测试同步API功能...")
    print("-" * 40)
    
    manager = OIFundingDataManager()
    
    for symbol in Config.SYMBOLS:
        print(f"\n测试 {symbol} 同步获取...")
        start_time = time.time()
        
        oi_value, funding_rate = manager.get_oi_and_funding_sync(symbol)
        sync_time = time.time() - start_time
        
        if oi_value is not None and funding_rate is not None:
            print(f"   ✅ 同步获取成功")
            print(f"   📊 持仓量: {oi_value:,.2f}")
            print(f"   💰 资金费率: {funding_rate:+.4f}%")
        else:
            print("   ❌ 同步获取失败")
        print(f"   ⏱️ 同步耗时: {sync_time:.3f}秒")

if __name__ == "__main__":
    print("开始测试OI和资金费率功能...")
    
    # 运行异步测试
    asyncio.run(test_oi_funding_data())
    
    # 运行同步测试
    test_sync_functionality()
    
    print("\n🎉 所有测试完成！") 