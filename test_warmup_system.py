# -*- coding: utf-8 -*-
"""
测试数据预热机制
验证系统在数据预热完成前不会发送消息
"""

import asyncio
import time
from config import Config
from data_manager import data_manager

async def test_warmup_mechanism():
    """测试数据预热机制"""
    print("=" * 60)
    print("测试数据预热机制")
    print("=" * 60)
    
    # 显示预热配置
    print("预热配置:")
    print(f"  - 启用预热检查: {Config.DATA_WARMUP_CONFIG['启用预热检查']}")
    print(f"  - 启动等待时间: {Config.DATA_WARMUP_CONFIG['启动等待时间']}秒")
    print(f"  - 最小更新次数: {Config.DATA_WARMUP_CONFIG['最小更新次数']}次")
    print(f"  - 最小订单数量: {Config.DATA_WARMUP_CONFIG['最小订单数量']}条")
    print()
    
    try:
        # 获取数据管理器的初始快照
        print("正在初始化数据...")
        data_manager.get_initial_snapshots()
        
        print("\n监控预热状态...")
        start_time = time.time()
        check_count = 0
        
        # 模拟等待预热完成的过程
        while not data_manager.is_system_ready_for_output():
            check_count += 1
            elapsed = time.time() - start_time
            
            if check_count % 5 == 0:  # 每5次检查显示一次状态
                print(f"⏳ 预热中... 已运行 {elapsed:.1f}秒")
                
                # 显示详细状态
                status = data_manager.get_warmup_status()
                for symbol, data in status.items():
                    spot_ready = "✅" if data["现货"]["预热完成"] else "⏳"
                    futures_ready = "✅" if data["合约"]["预热完成"] else "⏳"
                    print(f"   {symbol}: 现货{spot_ready}({data['现货']['更新次数']}次) "
                          f"合约{futures_ready}({data['合约']['更新次数']}次)")
            
            await asyncio.sleep(1)
            
            # 防止无限等待
            if elapsed > 300:  # 5分钟超时
                print("❌ 预热超时！")
                break
        
        end_time = time.time()
        total_time = end_time - start_time
        
        if data_manager.is_system_ready_for_output():
            print(f"\n✅ 系统预热完成！总耗时: {total_time:.1f}秒")
            
            # 显示最终状态
            final_status = data_manager.get_warmup_status()
            print("\n最终预热状态:")
            for symbol, data in final_status.items():
                print(f"  {symbol}:")
                print(f"    现货: 更新{data['现货']['更新次数']}次, 运行{data['现货']['运行时间']:.1f}秒")
                print(f"    合约: 更新{data['合约']['更新次数']}次, 运行{data['合约']['运行时间']:.1f}秒")
        else:
            print(f"\n❌ 系统预热未完成，耗时: {total_time:.1f}秒")
        
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()

async def test_disabled_warmup():
    """测试禁用预热检查的情况"""
    print("\n" + "=" * 60)
    print("测试禁用预热检查")
    print("=" * 60)
    
    # 临时禁用预热检查
    original_setting = Config.DATA_WARMUP_CONFIG["启用预热检查"]
    Config.DATA_WARMUP_CONFIG["启用预热检查"] = False
    
    try:
        print("预热检查已禁用")
        
        # 检查系统是否立即就绪
        is_ready = data_manager.is_system_ready_for_output()
        print(f"系统是否就绪: {'是' if is_ready else '否'}")
        
        if is_ready:
            print("✅ 禁用预热检查时系统立即就绪")
        else:
            print("❌ 禁用预热检查但系统仍未就绪")
            
    finally:
        # 恢复原始设置
        Config.DATA_WARMUP_CONFIG["启用预热检查"] = original_setting
        print(f"预热检查设置已恢复: {original_setting}")

if __name__ == "__main__":
    asyncio.run(test_warmup_mechanism())
    asyncio.run(test_disabled_warmup()) 