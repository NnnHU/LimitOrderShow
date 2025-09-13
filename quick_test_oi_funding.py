# -*- coding: utf-8 -*-
"""
快速测试主程序的OI和资金费率功能
测试完整的图表生成和发送流程
"""

import asyncio
import time
from config import Config
from data_manager import DataManager
from chart_output import ChartOutputManager

async def quick_test_main_functionality():
    """快速测试主程序功能"""
    print("=" * 60)
    print("主程序OI和资金费率功能快速测试")
    print("=" * 60)
    
    # 临时设置图表保存到本地，这样我们可以验证图表内容
    original_save_setting = Config.OUTPUT_OPTIONS["save_charts_locally"]
    Config.OUTPUT_OPTIONS["save_charts_locally"] = True
    
    try:
        # 创建管理器
        data_manager = DataManager()
        chart_manager = ChartOutputManager()
        
        # 初始化数据
        print("🔄 初始化数据管理器...")
        data_manager.get_initial_snapshots()
        
        # 等待数据稳定
        await asyncio.sleep(2)
        
        # 模拟数据处理
        print("\n📊 开始处理图表...")
        for symbol in Config.SYMBOLS:
            spot_manager = data_manager.get_manager(symbol, False)
            futures_manager = data_manager.get_manager(symbol, True)
            
            if spot_manager and futures_manager:
                print(f"\n🎯 处理 {symbol}...")
                
                # 检查数据
                spot_data = spot_manager.get_market_data()
                futures_data = futures_manager.get_market_data()
                
                if spot_data and futures_data:
                    print(f"✅ {symbol} 数据可用")
                    
                    # 使用图表管理器处理
                    try:
                        # 模拟异步处理
                        await chart_manager.process_and_send(spot_manager, futures_manager)
                        print(f"✅ {symbol} 图表处理完成")
                    except Exception as e:
                        print(f"❌ {symbol} 图表处理出错: {e}")
                else:
                    print(f"⚠️ {symbol} 数据不足")
        
        print("\n🎉 测试完成！")
        
        # 检查生成的文件
        import os
        import glob
        
        png_files = glob.glob("depth_chart_*.png")
        if png_files:
            print(f"\n📁 生成的图表文件:")
            for file in png_files:
                file_size = os.path.getsize(file)
                print(f"   - {file} ({file_size:,} bytes)")
        else:
            print("\n⚠️ 没有找到生成的图表文件")
            
    except Exception as e:
        print(f"❌ 测试过程中出错: {e}")
        import traceback
        traceback.print_exc()
    finally:
        # 恢复原始设置
        Config.OUTPUT_OPTIONS["save_charts_locally"] = original_save_setting

if __name__ == "__main__":
    print("开始快速测试主程序功能...")
    asyncio.run(quick_test_main_functionality()) 