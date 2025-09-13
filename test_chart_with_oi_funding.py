# -*- coding: utf-8 -*-
"""
图表生成功能测试脚本（包含OI和资金费率）
测试修改后的图表输出功能，验证OI和资金费率是否正确显示
"""

import asyncio
import time
import os
from config import Config
from data_manager import DataManager
from chart_output import ChartOutputManager

async def test_chart_with_oi_funding():
    """测试包含OI和资金费率的图表生成功能"""
    print("=" * 60)
    print("图表生成功能测试（包含OI和资金费率）")
    print("=" * 60)
    
    # 创建数据管理器和图表输出管理器
    data_manager = DataManager()
    chart_manager = ChartOutputManager()
    
    try:
        # 初始化订单簿数据
        print("🔄 正在初始化订单簿数据...")
        data_manager.get_initial_snapshots()
        print("✅ 订单簿数据初始化完成")
        
        # 等待数据稳定
        print("\n⏳ 等待数据稳定...")
        await asyncio.sleep(3)
        
        # 处理每个交易对
        for symbol in Config.SYMBOLS:
            print(f"\n📊 生成 {symbol} 图表...")
            print("-" * 40)
            
            # 获取管理器
            spot_manager = data_manager.get_manager(symbol, False)
            futures_manager = data_manager.get_manager(symbol, True)
            
            if not spot_manager or not futures_manager:
                print(f"❌ 无法获取 {symbol} 的管理器")
                continue
            
            # 检查数据是否可用
            spot_data = spot_manager.get_market_data()
            futures_data = futures_manager.get_market_data()
            
            if not spot_data or not futures_data:
                print(f"❌ {symbol} 数据不足，跳过图表生成")
                continue
            
            print(f"✅ {symbol} 数据检查通过")
            print(f"   现货中间价: ${spot_data['mid_price']:,.2f}")
            print(f"   合约中间价: ${futures_data['mid_price']:,.2f}")
            
            # 获取OI和资金费率数据
            oi_value, funding_rate = await chart_manager.oi_funding_manager.get_oi_and_funding(symbol)
            
            if oi_value is not None:
                print(f"   📈 持仓量: {oi_value:,.0f}")
            else:
                print("   ❌ 无法获取持仓量数据")
            
            if funding_rate is not None:
                print(f"   💰 资金费率: {funding_rate:+.4f}%")
            else:
                print("   ❌ 无法获取资金费率数据")
            
            # 生成图表
            print(f"\n🎨 正在生成 {symbol} 图表...")
            start_time = time.time()
            
            fig = chart_manager.create_depth_chart(spot_manager, futures_manager)
            
            chart_time = time.time() - start_time
            
            if fig:
                print(f"✅ 图表生成成功，耗时: {chart_time:.3f}秒")
                
                # 保存图表到本地文件进行验证
                timestamp = int(time.time())
                test_image_path = f"test_chart_{symbol}_{timestamp}.png"
                
                try:
                    fig.write_image(
                        test_image_path, 
                        engine="kaleido", 
                        width=Config.CHART_CONFIG["chart_width"], 
                        height=Config.CHART_CONFIG.get("chart_height_final", 1600), 
                        scale=2, 
                        format="png"
                    )
                    
                    if os.path.exists(test_image_path):
                        file_size = os.path.getsize(test_image_path)
                        print(f"✅ 测试图表已保存: {test_image_path}")
                        print(f"   📁 文件大小: {file_size:,} 字节")
                        
                        # 可选：删除测试文件
                        keep_test_files = True  # 设置为False可自动删除测试文件
                        if not keep_test_files:
                            os.remove(test_image_path)
                            print("🗑️ 已删除测试文件")
                    else:
                        print("❌ 图表文件生成失败")
                        
                except Exception as e:
                    print(f"❌ 保存图表时出错: {e}")
            else:
                print("❌ 图表生成失败")
        
        print("\n" + "=" * 60)
        print("图表生成测试完成")
        print("=" * 60)
        
    except Exception as e:
        print(f"❌ 测试过程中出错: {e}")
        import traceback
        traceback.print_exc()

def test_manual_oi_funding_display():
    """手动测试OI和资金费率数据显示格式"""
    print("\n🎯 测试OI和资金费率显示格式...")
    print("-" * 40)
    
    # 模拟不同的数据组合
    test_cases = [
        (85615.42, -0.0011, "正常数据"),
        (150000.0, 0.0025, "正资金费率"),
        (None, -0.0050, "仅有资金费率"),
        (75000.0, None, "仅有持仓量"),
        (None, None, "无数据"),
    ]
    
    for oi, funding, description in test_cases:
        print(f"\n📝 {description}:")
        
        # 构建标题（模拟图表标题生成逻辑）
        futures_title = "<b>BTCUSDT Futures Market Depth</b>"
        if oi is not None and funding is not None:
            futures_title += f"<br><span style='font-size:12px;color:#f1c40f;'>OI: {oi:,.0f} | Funding: {funding:+.4f}%</span>"
        elif oi is not None:
            futures_title += f"<br><span style='font-size:12px;color:#f1c40f;'>OI: {oi:,.0f}</span>"
        elif funding is not None:
            futures_title += f"<br><span style='font-size:12px;color:#f1c40f;'>Funding: {funding:+.4f}%</span>"
        
        print(f"   标题: {futures_title}")
        
        # 构建主标题
        main_title = "<b>Binance Market Depth & Order Book Analysis - 2024-01-01 12:00:00 (UTC+8)</b>"
        if oi is not None or funding is not None:
            main_title += "<br><span style='font-size:14px;color:#e74c3c;'>"
            if oi is not None and funding is not None:
                main_title += f"Futures OI: {oi:,.0f} | Funding Rate: {funding:+.4f}%"
            elif oi is not None:
                main_title += f"Futures Open Interest: {oi:,.0f}"
            elif funding is not None:
                main_title += f"Futures Funding Rate: {funding:+.4f}%"
            main_title += "</span>"
        
        print(f"   主标题: {main_title[:100]}...")

if __name__ == "__main__":
    print("开始测试图表生成功能（包含OI和资金费率）...")
    
    # 手动测试显示格式
    test_manual_oi_funding_display()
    
    # 运行完整的图表生成测试
    asyncio.run(test_chart_with_oi_funding())
    
    print("\n🎉 所有测试完成！") 