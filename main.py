# -*- coding: utf-8 -*-
"""
主程序入口
整合所有模块，管理WebSocket连接和数据流
"""

import websocket
import json
import threading
import time
import asyncio
import argparse
from concurrent.futures import ThreadPoolExecutor
from typing import Dict, List
from config import Config
from data_manager import data_manager
from text_output import text_output_manager
from chart_output import chart_output_manager

class MarketDepthMonitor:
    """市场深度监控主程序"""
    
    def __init__(self):
        self.running = False
        self.websockets = []
        self.data_manager = data_manager
        self.text_output = text_output_manager
        self.chart_output = chart_output_manager
        # 创建线程池用于处理图表输出
        self.chart_executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="chart-")

    def on_message_spot(self, ws, message):
        """处理现货WebSocket消息"""
        try:
            # 将消息传递给数据管理器处理（标记为现货）
            self.data_manager.process_websocket_message(message, is_futures=False)
            
            # 检查是否需要发送输出
            self._check_and_send_outputs()
            
        except Exception as e:
            if Config.OUTPUT_OPTIONS["enable_console_output"]:
                print(f"处理现货WebSocket消息时出错: {e}")

    def on_message_futures(self, ws, message):
        """处理合约WebSocket消息"""
        try:
            # 将消息传递给数据管理器处理（标记为合约）
            self.data_manager.process_websocket_message(message, is_futures=True)
            
            # 检查是否需要发送输出
            self._check_and_send_outputs()
            
        except Exception as e:
            if Config.OUTPUT_OPTIONS["enable_console_output"]:
                print(f"处理合约WebSocket消息时出错: {e}")

    def on_error(self, ws, error):
        """处理WebSocket错误"""
        if Config.OUTPUT_OPTIONS["enable_console_output"]:
            print(f"WebSocket错误: {error}")

    def on_close(self, ws, close_status_code, close_msg):
        """处理WebSocket关闭"""
        if Config.OUTPUT_OPTIONS["enable_console_output"]:
            print(f"WebSocket连接关闭: {close_status_code}, {close_msg}")

    def on_open(self, ws):
        """处理WebSocket连接打开"""
        if Config.OUTPUT_OPTIONS["enable_console_output"]:
            print("WebSocket连接已建立")

    def _run_chart_async(self, spot_manager, futures_manager):
        """在新的事件循环中运行异步图表输出"""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(
                self.chart_output.process_and_send(spot_manager, futures_manager)
            )
        except Exception as e:
            if Config.OUTPUT_OPTIONS["enable_console_output"]:
                print(f"图表输出处理时出错: {e}")
        finally:
            loop.close()

    def _check_and_send_outputs(self):
        """检查并发送输出"""
        try:
            # 首先检查系统是否完成数据预热
            if not self.data_manager.is_system_ready_for_output():
                return
            
            # 处理每个交易对
            for symbol in Config.SYMBOLS:
                spot_manager = self.data_manager.get_manager(symbol, False)
                futures_manager = self.data_manager.get_manager(symbol, True)
                
                if not spot_manager or not futures_manager:
                    continue
                
                # 双重检查：确保该交易对的数据已预热完成
                if not (spot_manager.is_ready_for_output() and futures_manager.is_ready_for_output()):
                    continue
                
                # 处理文本输出（同步）
                if Config.is_output_enabled("text_output"):
                    self.text_output.process_and_send(spot_manager, futures_manager)
                
                # 处理图表输出（使用线程池异步处理）
                if Config.is_output_enabled("chart_output"):
                    self.chart_executor.submit(self._run_chart_async, spot_manager, futures_manager)
                
        except Exception as e:
            if Config.OUTPUT_OPTIONS["enable_console_output"]:
                print(f"检查和发送输出时出错: {e}")

    def create_websocket(self, url: str, streams: List[str], message_handler=None):
        """创建WebSocket连接"""
        def run_websocket():
            ws = websocket.WebSocketApp(
                url,
                on_message=message_handler or self.on_message,
                on_error=self.on_error,
                on_close=self.on_close,
                on_open=lambda ws: self._subscribe_streams(ws, streams)
            )
            ws.run_forever()
        
        thread = threading.Thread(target=run_websocket, daemon=True)
        thread.start()
        return thread

    def _subscribe_streams(self, ws, streams: List[str]):
        """订阅WebSocket流"""
        subscribe_message = {
            "method": "SUBSCRIBE",
            "params": streams,
            "id": 1
        }
        ws.send(json.dumps(subscribe_message))
        
        if Config.OUTPUT_OPTIONS["enable_console_output"]:
            print(f"已订阅流: {streams}")

    async def start_async_loop(self):
        """启动异步事件循环"""
        while self.running:
            await asyncio.sleep(1)

    def start(self):
        """启动监控"""
        try:
            self.running = True
            
            if Config.OUTPUT_OPTIONS["enable_console_output"]:
                print("=" * 60)
                print("币安市场深度监控系统启动")
                print("=" * 60)
                print(f"监控交易对: {Config.SYMBOLS}")
                print(f"文本输出间隔: {Config.SEND_INTERVALS['text_output']}秒")
                print(f"图表输出间隔: {Config.SEND_INTERVALS['chart_output']}秒")
                print(f"文本输出: {'启用' if Config.is_output_enabled('text_output') else '禁用'}")
                print(f"图表输出: {'启用' if Config.is_output_enabled('chart_output') else '禁用'}")
                print("=" * 60)

            # 初始化数据管理器
            self.data_manager.get_initial_snapshots()

            # 创建WebSocket连接
            websocket_threads = []
            
            # 现货WebSocket
            if Config.SYMBOLS:
                spot_streams = [f"{symbol.lower()}@depth" for symbol in Config.SYMBOLS]
                spot_url = "wss://stream.binance.com:9443/stream"
                spot_thread = self.create_websocket(spot_url, spot_streams, self.on_message_spot)
                websocket_threads.append(spot_thread)
                
                if Config.OUTPUT_OPTIONS["enable_console_output"]:
                    print(f"现货WebSocket已启动: {spot_url}")

            # 合约WebSocket  
            if Config.SYMBOLS:
                futures_streams = [f"{symbol.lower()}@depth" for symbol in Config.SYMBOLS]
                futures_url = "wss://fstream.binance.com/stream"
                futures_thread = self.create_websocket(futures_url, futures_streams, self.on_message_futures)
                websocket_threads.append(futures_thread)
                
                if Config.OUTPUT_OPTIONS["enable_console_output"]:
                    print(f"合约WebSocket已启动: {futures_url}")

            # 启动异步事件循环
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            try:
                loop.run_until_complete(self.start_async_loop())
            except KeyboardInterrupt:
                if Config.OUTPUT_OPTIONS["enable_console_output"]:
                    print("\n收到中断信号，正在关闭...")
            finally:
                loop.close()

        except Exception as e:
            if Config.OUTPUT_OPTIONS["enable_console_output"]:
                print(f"启动监控时出错: {e}")
            raise
        finally:
            self.stop()

    def stop(self):
        """停止监控"""
        self.running = False
        
        # 停止图表输出管理器
        if hasattr(self, 'chart_output'):
            self.chart_output.stop()
        
        # 关闭线程池
        if hasattr(self, 'chart_executor'):
            self.chart_executor.shutdown(wait=True)
            
        if Config.OUTPUT_OPTIONS["enable_console_output"]:
            print("市场深度监控系统已停止")

def print_system_info():
    """打印系统信息"""
    print("\n" + "=" * 60)
    print("币安市场深度监控系统")
    print("=" * 60)
    print("系统配置:")
    print(f"  - 监控交易对: {', '.join(Config.SYMBOLS)}")
    print(f"  - 文本输出: {'启用' if Config.is_output_enabled('text_output') else '禁用'}")
    print(f"  - 图表输出: {'启用' if Config.is_output_enabled('chart_output') else '禁用'}")
    print(f"  - 控制台输出: {'启用' if Config.OUTPUT_OPTIONS['enable_console_output'] else '禁用'}")
    print(f"  - 保存图表到本地: {'是' if Config.OUTPUT_OPTIONS['save_charts_locally'] else '否'}")
    
    print("\n发送间隔:")
    print(f"  - 文本分析: {Config.SEND_INTERVALS['text_output']}秒")
    print(f"  - 图表分析: {Config.SEND_INTERVALS['chart_output']}秒")
    
    print("\n最小数量阈值:")
    for currency, min_qty in Config.MIN_QUANTITIES.items():
        if currency != "DEFAULT":
            print(f"  - {currency}: {min_qty}")
    
    print("\nWebhook配置:")
    for currency, webhooks in Config.DISCORD_WEBHOOKS.items():
        if currency == "DEFAULT":
            continue
        print(f"  - {currency}:")
        for output_type, urls in webhooks.items():
            if urls:
                print(f"    - {output_type}: {len(urls)}个webhook")
    
    print("\n图表设置:")
    print(f"  - 显示订单数量: {Config.CHART_CONFIG['display_order_count']}档")
    print(f"  - 图表尺寸: {Config.CHART_CONFIG['chart_width']}x{Config.CHART_CONFIG['chart_height']}")
    print(f"  - 图表格式: {Config.CHART_CONFIG['format']}")
    print(f"  - 发送延迟: {Config.CHART_CONFIG['send_delay']}秒")
    
    print("\n数据预热设置:")
    print(f"  - 启用预热检查: {'是' if Config.DATA_WARMUP_CONFIG['enable_warmup_check'] else '否'}")
    if Config.DATA_WARMUP_CONFIG['enable_warmup_check']:
        print(f"  - 启动等待时间: {Config.DATA_WARMUP_CONFIG['startup_wait_time']}秒")
        print(f"  - 最小更新次数: {Config.DATA_WARMUP_CONFIG['min_update_count']}次")
        print(f"  - 最小订单数量: {Config.DATA_WARMUP_CONFIG['min_order_count']}条")
    print("=" * 60)

if __name__ == "__main__":
    try:
        # 解析命令行参数
        parser = argparse.ArgumentParser(description='币安市场深度监控系统')
        parser.add_argument('--no-input', action='store_true', 
                          help='跳过交互确认，直接启动监控（用于服务器部署）')
        parser.add_argument('--quiet', action='store_true',
                          help='静默模式，不显示系统信息')
        args = parser.parse_args()
        
        # 打印系统信息（除非是静默模式）
        if not args.quiet:
            print_system_info()
        
        # 等待用户确认（除非使用了--no-input参数）
        if not args.no_input:
            input("\n按回车键开始监控...")
        else:
            print("\n自动启动模式，开始监控...")
        
        # 创建并启动监控器
        monitor = MarketDepthMonitor()
        monitor.start()
        
    except KeyboardInterrupt:
        print("\n用户中断程序")
    except Exception as e:
        print(f"\n程序发生异常: {e}")
        import traceback
        traceback.print_exc() 