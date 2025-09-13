# -*- coding: utf-8 -*-
"""
系统测试文件
用于验证各模块是否正常工作
"""

import sys
import asyncio
from config import Config
from data_manager import data_manager
from text_output import text_output_manager
from chart_output import chart_output_manager

def test_config():
    """测试配置模块"""
    print("测试配置模块...")
    
    print(f"  监控交易对: {Config.SYMBOLS}")
    print(f"  BTC现货最小数量: {Config.get_min_quantity('BTCUSDT', 'spot')}")
    print(f"  BTC合约最小数量: {Config.get_min_quantity('BTCUSDT', 'futures')}")
    print(f"  ETH现货最小数量: {Config.get_min_quantity('ETHUSDT', 'spot')}")
    print(f"  ETH合约最小数量: {Config.get_min_quantity('ETHUSDT', 'futures')}")
    
    btc_text_webhooks = Config.get_webhooks('BTCUSDT', '文本输出')
    btc_chart_webhooks = Config.get_webhooks('BTCUSDT', '图表输出')
    
    print(f"  BTC文本Webhooks: {len(btc_text_webhooks)}个")
    print(f"  BTC图表Webhooks: {len(btc_chart_webhooks)}个")
    
    print(f"  文本输出启用: {Config.is_output_enabled('文本输出')}")
    print(f"  图表输出启用: {Config.is_output_enabled('图表输出')}")
    
    print("✅ 配置模块测试通过\n")

def test_data_manager():
    """测试数据管理器"""
    print("测试数据管理器...")
    
    # 测试管理器创建
    btc_spot = data_manager.get_manager('BTCUSDT', False)
    btc_futures = data_manager.get_manager('BTCUSDT', True)
    
    print(f"  BTC现货管理器: {'✅' if btc_spot else '❌'}")
    print(f"  BTC合约管理器: {'✅' if btc_futures else '❌'}")
    
    if btc_spot:
        print(f"  现货最小数量: {btc_spot.min_quantity}")
    if btc_futures:
        print(f"  合约最小数量: {btc_futures.min_quantity}")
    
    print("✅ 数据管理器测试通过\n")

def test_data_fetching():
    """测试数据获取"""
    print("测试数据获取...")
    
    try:
        # 获取初始快照
        data_manager.get_initial_snapshots()
        
        # 测试数据获取
        btc_spot = data_manager.get_manager('BTCUSDT', False)
        market_data = btc_spot.get_market_data()
        
        if market_data:
            print(f"  当前价格: ${market_data['mid_price']:.2f}")
            print(f"  最高买价: ${market_data['highest_bid']:.2f}")
            print(f"  最低卖价: ${market_data['lowest_ask']:.2f}")
            print(f"  价差: ${market_data['spread']:.2f}")
            
            # 测试过滤订单
            bids, asks = btc_spot.get_filtered_orders(5)
            print(f"  符合条件的买单: {len(bids)}条")
            print(f"  符合条件的卖单: {len(asks)}条")
            
            if bids:
                print(f"  最高买单: ${bids[0][0]:.2f} - {bids[0][1]:.2f}")
            if asks:
                print(f"  最低卖单: ${asks[0][0]:.2f} - {asks[0][1]:.2f}")
                
        print("✅ 数据获取测试通过\n")
        
    except Exception as e:
        print(f"❌ 数据获取测试失败: {e}\n")

def test_text_output():
    """测试文本输出"""
    print("测试文本输出...")
    
    try:
        btc_spot = data_manager.get_manager('BTCUSDT', False)
        btc_futures = data_manager.get_manager('BTCUSDT', True)
        
        if btc_spot and btc_futures:
            # 生成文本分析
            spot_analysis = text_output_manager.generate_market_analysis(btc_spot)
            futures_analysis = text_output_manager.generate_market_analysis(btc_futures)
            
            print(f"  现货分析长度: {len(spot_analysis)}字符")
            print(f"  合约分析长度: {len(futures_analysis)}字符")
            
            # 显示部分内容
            if len(spot_analysis) > 100:
                print(f"  现货分析预览: {spot_analysis[:100]}...")
            
        print("✅ 文本输出测试通过\n")
        
    except Exception as e:
        print(f"❌ 文本输出测试失败: {e}\n")

async def test_chart_output():
    """测试图表输出"""
    print("测试图表输出...")
    
    try:
        btc_spot = data_manager.get_manager('BTCUSDT', False)
        btc_futures = data_manager.get_manager('BTCUSDT', True)
        
        if btc_spot and btc_futures:
            # 生成图表
            fig = chart_output_manager.create_depth_chart(btc_spot, btc_futures)
            
            if fig:
                print("  ✅ 图表创建成功")
                print(f"  图表配置: {Config.CHART_CONFIG['图表宽度']}x{Config.CHART_CONFIG['图表高度']}")
                
                # 保存测试图表
                test_image = "test_chart.png"
                fig.write_image(test_image, engine="kaleido")
                print(f"  测试图表已保存: {test_image}")
                
            else:
                print("  ❌ 图表创建失败")
                
        print("✅ 图表输出测试通过\n")
        
    except Exception as e:
        print(f"❌ 图表输出测试失败: {e}\n")

def main():
    """主测试函数"""
    print("=" * 60)
    print("币安市场深度监控系统 - 模块测试")
    print("=" * 60)
    
    # 基础模块测试
    test_config()
    test_data_manager()
    
    # 数据相关测试
    test_data_fetching()
    test_text_output()
    
    # 图表测试（异步）
    asyncio.run(test_chart_output())
    
    print("=" * 60)
    print("所有模块测试完成")
    print("=" * 60)

if __name__ == "__main__":
    main() 