# -*- coding: utf-8 -*-
"""
调试预热状态
检查哪个数据源导致卡住，并提供解决方案
"""

import time
from config import Config
from data_manager import data_manager

def debug_warmup_status():
    """调试预热状态"""
    print("=" * 60)
    print("🔍 预热状态调试")
    print("=" * 60)
    
    # 获取当前状态
    status = data_manager.get_warmup_status()
    ready_count = 0
    total_count = len(Config.SYMBOLS) * 2
    
    print("详细预热状态:")
    print()
    
    for symbol, data in status.items():
        print(f"📊 {symbol}:")
        
        # 现货状态
        spot_status = data["现货"]
        spot_ready = "✅" if spot_status["预热完成"] else "❌"
        print(f"   现货: {spot_ready} 更新{spot_status['更新次数']}次, 运行{spot_status['运行时间']:.1f}秒")
        if spot_status["预热完成"]:
            ready_count += 1
        
        # 合约状态
        futures_status = data["合约"]
        futures_ready = "✅" if futures_status["预热完成"] else "❌"
        print(f"   合约: {futures_ready} 更新{futures_status['更新次数']}次, 运行{futures_status['运行时间']:.1f}秒")
        if futures_status["预热完成"]:
            ready_count += 1
        
        print()
    
    print(f"总体进度: {ready_count}/{total_count} 个数据源已就绪")
    
    # 分析问题
    print("\n" + "=" * 60)
    print("🔧 问题分析")
    print("=" * 60)
    
    not_ready_sources = []
    for symbol, data in status.items():
        if not data["现货"]["预热完成"]:
            not_ready_sources.append(f"{symbol}现货")
        if not data["合约"]["预热完成"]:
            not_ready_sources.append(f"{symbol}合约")
    
    if not_ready_sources:
        print(f"❌ 未完成预热的数据源: {', '.join(not_ready_sources)}")
        print()
        
        # 检查具体原因
        config = Config.DATA_WARMUP_CONFIG
        print("预热要求:")
        print(f"  - 等待时间: {config['启动等待时间']}秒")
        print(f"  - 更新次数: {config['最小更新次数']}次")
        print(f"  - 订单数量: {config['最小订单数量']}条")
        print()
        
        for symbol, data in status.items():
            for market_type in ["现货", "合约"]:
                market_data = data[market_type]
                if not market_data["预热完成"]:
                    print(f"🔍 {symbol}{market_type} 未完成原因分析:")
                    
                    # 检查等待时间
                    if market_data["运行时间"] < config['启动等待时间']:
                        print(f"   ⏰ 等待时间不足: {market_data['运行时间']:.1f}秒 < {config['启动等待时间']}秒")
                    
                    # 检查更新次数
                    if market_data["更新次数"] < config['最小更新次数']:
                        print(f"   🔄 更新次数不足: {market_data['更新次数']}次 < {config['最小更新次数']}次")
                    
                    # 检查订单数量（需要从manager获取）
                    manager = data_manager.get_manager(symbol, market_type == "合约")
                    if manager:
                        bids_count = len([qty for qty in manager.order_book["bids"].values() if qty >= manager.min_quantity])
                        asks_count = len([qty for qty in manager.order_book["asks"].values() if qty >= manager.min_quantity])
                        if bids_count < config['最小订单数量'] or asks_count < config['最小订单数量']:
                            print(f"   📊 订单数量不足: 买{bids_count}条/卖{asks_count}条 < {config['最小订单数量']}条")
                    
                    print()
    else:
        print("✅ 所有数据源都已完成预热")
    
    return ready_count, total_count, not_ready_sources

def suggest_solutions():
    """建议解决方案"""
    print("=" * 60)
    print("💡 解决方案建议")
    print("=" * 60)
    
    print("方案1: 🚀 立即启动（跳过预热）")
    print("   Config.DATA_WARMUP_CONFIG['启用预热检查'] = False")
    print("   优点: 立即可用，无需等待")
    print("   缺点: 可能发送初期不完整的数据")
    print()
    
    print("方案2: ⚡ 降低预热要求")
    print("   Config.set_warmup_preset('快速模式')  # 15秒等待")
    print("   或手动调整:")
    print("   Config.DATA_WARMUP_CONFIG['最小更新次数'] = 5")
    print("   Config.DATA_WARMUP_CONFIG['最小订单数量'] = 2")
    print()
    
    print("方案3: 🔄 重启WebSocket连接")
    print("   可能某个连接有问题，重启程序")
    print()
    
    print("方案4: 📊 检查网络和数据")
    print("   - 确认网络连接稳定")
    print("   - 确认币安API可访问")
    print("   - 某些币种的大单数据可能确实很少")

def auto_fix_warmup():
    """自动修复预热问题"""
    print("\n" + "=" * 60)
    print("🔧 自动修复尝试")
    print("=" * 60)
    
    ready_count, total_count, not_ready_sources = debug_warmup_status()
    
    if ready_count == total_count:
        print("✅ 所有数据源已就绪，无需修复")
        return True
    
    # 等待时间较长但更新次数少，可能是网络问题
    should_lower_requirements = False
    status = data_manager.get_warmup_status()
    
    for symbol, data in status.items():
        for market_type in ["现货", "合约"]:
            market_data = data[market_type]
            if (not market_data["预热完成"] and 
                market_data["运行时间"] > 60 and 
                market_data["更新次数"] < 10):
                should_lower_requirements = True
                break
    
    if should_lower_requirements:
        print("🔧 检测到长时间等待但更新次数少，自动降低要求...")
        Config.DATA_WARMUP_CONFIG['最小更新次数'] = 3
        Config.DATA_WARMUP_CONFIG['最小订单数量'] = 1
        print("   已调整: 最小更新次数=3, 最小订单数量=1")
        return False  # 需要继续等待
    
    return False

if __name__ == "__main__":
    debug_warmup_status()
    suggest_solutions()
    auto_fix_warmup() 