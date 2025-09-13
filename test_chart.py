# -*- coding: utf-8 -*-
"""
专门测试图表生成的脚本
"""

import asyncio
from data_manager import data_manager
from chart_output import chart_output_manager
from config import Config

async def test_chart_generation():
    """测试图表生成"""
    print("=" * 60)
    print("测试图表生成")
    print("=" * 60)
    
    try:
        # 初始化数据管理器
        print("正在初始化数据管理器...")
        data_manager.get_initial_snapshots()
        
        # 获取BTC管理器
        btc_spot = data_manager.get_manager('BTCUSDT', False)
        btc_futures = data_manager.get_manager('BTCUSDT', True)
        
        if not btc_spot or not btc_futures:
            print("❌ 无法获取管理器")
            return
            
        print("✅ 数据管理器初始化完成")
        
        # 获取市场数据
        spot_data = btc_spot.get_market_data()
        futures_data = btc_futures.get_market_data()
        
        if spot_data and futures_data:
            print(f"现货中间价: ${spot_data['mid_price']:,.2f}")
            print(f"合约中间价: ${futures_data['mid_price']:,.2f}")
            
            # 获取过滤后的订单
            spot_bids, spot_asks = btc_spot.get_filtered_orders(5)
            futures_bids, futures_asks = btc_futures.get_filtered_orders(5)
            
            print(f"现货：买单{len(spot_bids)}条，卖单{len(spot_asks)}条")
            print(f"合约：买单{len(futures_bids)}条，卖单{len(futures_asks)}条")
            
            # 生成图表
            print("正在生成图表...")
            fig = chart_output_manager.create_depth_chart(btc_spot, btc_futures)
            
            if fig:
                print("✅ 图表生成成功")
                
                # 保存测试图表
                test_filename = "test_new_layout.png"
                fig.write_image(test_filename, engine="kaleido")
                print(f"📊 测试图表已保存: {test_filename}")
                
                # 发送到Discord
                webhooks = Config.get_webhooks('BTCUSDT', '图表输出')
                if webhooks:
                    print("正在发送到Discord...")
                    await chart_output_manager.send_chart_to_discord(fig, 'BTCUSDT', webhooks)
                    print("✅ 发送完成")
                else:
                    print("⚠️ 未配置webhook")
            else:
                print("❌ 图表生成失败")
        else:
            print("❌ 无法获取市场数据")
            
    except Exception as e:
        print(f"❌ 测试出错: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_chart_generation()) 