# -*- coding: utf-8 -*-
"""
图表输出模块
负责生成和发送图表格式的市场分析，重新设计图表显示
"""

import plotly.graph_objects as go
from plotly.subplots import make_subplots
import requests
import time
import os
import aiohttp
import asyncio
from typing import Dict, List, Tuple
from datetime import datetime
from config import Config
from data_manager import OrderBookManager
import threading
from queue import Queue

class ChartOutputManager:
    """图表输出管理器"""
    
    def __init__(self):
        self.last_send_time = {}  # 每个币种单独记录发送时间
        self.send_queue = Queue()  # 发送队列
        self.send_lock = threading.Lock()  # 发送锁
        self._start_sender_thread()  # 启动发送线程

    def _start_sender_thread(self):
        """启动发送线程"""
        def sender_worker():
            while True:
                try:
                    # 从队列中获取发送任务
                    task = self.send_queue.get()
                    if task is None:  # 停止信号
                        break
                    
                    fig, symbol, webhook_urls = task
                    
                    # 执行发送任务
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    try:
                        loop.run_until_complete(
                            self._send_chart_with_delay(fig, symbol, webhook_urls)
                        )
                    finally:
                        loop.close()
                    
                    self.send_queue.task_done()
                    
                except Exception as e:
                    if Config.OUTPUT_OPTIONS["启用控制台输出"]:
                        print(f"发送线程错误: {e}")
        
        sender_thread = threading.Thread(target=sender_worker, daemon=True)
        sender_thread.start()

    async def _send_chart_with_delay(self, fig, symbol: str, webhook_urls: List[str]):
        """带延迟的图表发送"""
        with self.send_lock:
            # 在发送前等待，确保与之前的发送间隔足够
            delay = Config.CHART_CONFIG.get("发送延迟", 3)  # 从配置中获取延迟时间，默认3秒
            await asyncio.sleep(delay)
            
            if Config.OUTPUT_OPTIONS["启用控制台输出"]:
                print(f"正在发送 {symbol} 图表...")
            
            await self.send_chart_to_discord(fig, symbol, webhook_urls)

    def create_depth_chart(self, spot_manager: OrderBookManager, futures_manager: OrderBookManager):
        """创建深度图表"""
        try:
            # 获取过滤后的订单数据
            spot_bids, spot_asks = spot_manager.get_filtered_orders(Config.CHART_CONFIG["显示订单数量"])
            futures_bids, futures_asks = futures_manager.get_filtered_orders(Config.CHART_CONFIG["显示订单数量"])

            # 获取市场数据
            spot_data = spot_manager.get_market_data()
            futures_data = futures_manager.get_market_data()
            
            if not spot_data or not futures_data:
                return None

            spot_price = spot_data["mid_price"]
            futures_price = futures_data["mid_price"]

            # 调试输出
            if Config.OUTPUT_OPTIONS["启用控制台输出"]:
                print(f"\n=== 图表数据调试 ===")
                print(f"现货买单前{len(spot_bids)}条: {spot_bids}")
                print(f"现货卖单前{len(spot_asks)}条: {spot_asks}")
                print(f"合约买单前{len(futures_bids)}条: {futures_bids}")
                print(f"合约卖单前{len(futures_asks)}条: {futures_asks}")
                print("==================\n")

            # 创建子图
            fig = make_subplots(
                rows=2, cols=2,
                subplot_titles=(
                    f"{spot_manager.symbol} 现货市场深度 (前{Config.CHART_CONFIG['显示订单数量']}档)\n当前价格: ${spot_price:,.2f}",
                    f"{futures_manager.symbol} 合约市场深度 (前{Config.CHART_CONFIG['显示订单数量']}档)\n当前价格: ${futures_price:,.2f}",
                    f"{spot_manager.symbol} 现货市场深度",
                    f"{futures_manager.symbol} 合约市场深度"
                ),
                specs=[[{"secondary_y": False}, {"secondary_y": False}],
                       [{"secondary_y": False}, {"secondary_y": False}]]
            )

            # 现货市场深度图 (第1行第1列)
            self._add_depth_traces(fig, spot_bids, spot_asks, spot_price, "现货", 1, 1)
            
            # 合约市场深度图 (第1行第2列)
            self._add_depth_traces(fig, futures_bids, futures_asks, futures_price, "合约", 1, 2)
            
            # 现货比率分析图 (第2行第1列)
            self._add_ratio_chart(fig, spot_manager, "现货", 2, 1)
            
            # 合约比率分析图 (第2行第2列)
            self._add_ratio_chart(fig, futures_manager, "合约", 2, 2)

            # 更新布局
            fig.update_layout(
                plot_bgcolor='#1e1e1e',
                paper_bgcolor='#1a1a1a',
                font=dict(color='#ffffff', size=10),
                height=Config.CHART_CONFIG["图表高度"],
                width=Config.CHART_CONFIG["图表宽度"],
                showlegend=True,
                barmode='overlay',
                legend=dict(
                    font=dict(color='#ffffff'),
                    bgcolor='rgba(45,45,45,0.8)',
                    bordercolor='#3d3d3d',
                    x=0.01,
                    y=0.99
                ),
                title=dict(
                    text=f"市场深度分析 - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
                    font=dict(size=16, color='#ffffff'),
                    x=0.5
                )
            )

            # 更新坐标轴
            self._update_axes(fig)

            return fig

        except Exception as e:
            if Config.OUTPUT_OPTIONS["启用控制台输出"]:
                print(f"创建图表时出错: {e}")
            return None

    def _add_depth_traces(self, fig, bids: List[Tuple], asks: List[Tuple], current_price: float, 
                         market_type: str, row: int, col: int):
        """添加深度图表轨迹"""
        color_scheme = {
            "现货": {"bids": "#00b894", "asks": "#ff7675"},
            "合约": {"bids": "#2e86de", "asks": "#ffa502"}
        }
        
        colors = color_scheme.get(market_type, color_scheme["现货"])

        # 添加卖单（右侧正值）
        if asks:
            fig.add_trace(
                go.Bar(
                    x=[qty for _, qty in asks],
                    y=[price for price, _ in asks],
                    name=f"{market_type}卖单",
                    orientation='h',
                    marker_color=colors["asks"],
                    text=[f"${price:,.0f}<br>{qty:.1f}" for price, qty in asks],
                    textposition='auto',
                    textfont=dict(size=8),
                    hovertemplate=f"{market_type}卖单<br>价格: $%{{y:,.0f}}<br>数量: %{{x:.2f}}<extra></extra>",
                    opacity=0.8
                ),
                row=row, col=col
            )

        # 添加买单（右侧正值）
        if bids:
            fig.add_trace(
                go.Bar(
                    x=[qty for _, qty in bids],  # 买单也用正值，不再使用负值
                    y=[price for price, _ in bids],
                    name=f"{market_type}买单",
                    orientation='h',
                    marker_color=colors["bids"],
                    text=[f"${price:,.0f}<br>{qty:.1f}" for price, qty in bids],
                    textposition='auto',
                    textfont=dict(size=8),
                    hovertemplate=f"{market_type}买单<br>价格: $%{{y:,.0f}}<br>数量: %{{x:.2f}}<extra></extra>",
                    opacity=0.8
                ),
                row=row, col=col
            )

        # 添加当前价格线
        if current_price:
            fig.add_hline(
                y=current_price,
                line_width=2,
                line_dash="dash",
                line_color="yellow",
                row=row, col=col,
                annotation_text=f"${current_price:,.0f}",
                annotation_position="bottom right",
                annotation=dict(font_size=10, font_color="yellow")
            )

    def _add_ratio_chart(self, fig, manager: OrderBookManager, market_type: str, row: int, col: int):
        """添加买卖比率图表"""
        ratios = []
        ranges = []
        colors = []
        
        for i, (lower, upper) in enumerate(Config.ANALYSIS_RANGES):
            if i == 0:
                ratio, _, _, _ = manager.calculate_depth_ratio(upper)
                range_name = f"0-{upper}%"
            else:
                ratio, _, _, _ = manager.calculate_depth_ratio_range(lower, upper)
                range_name = f"{lower}-{upper}%"
            
            ratios.append(ratio if ratio is not None else 0)
            ranges.append(range_name)
            
            # 根据比率设置颜色
            if ratio is None or ratio == 0:
                colors.append('#6c757d')  # 灰色
            elif ratio > 0:
                colors.append('#00b894' if market_type == "现货" else '#2e86de')  # 绿色或蓝色
            else:
                colors.append('#ff7675' if market_type == "现货" else '#ffa502')  # 红色或橙色

        fig.add_trace(
            go.Bar(
                x=ranges,
                y=ratios,
                name=f"{market_type}比率",
                marker_color=colors,
                text=[f"{ratio:.3f}" for ratio in ratios],
                textposition='auto',
                textfont=dict(size=9),
                hovertemplate=f"{market_type}买卖比率<br>范围: %{{x}}<br>比率: %{{y:.3f}}<extra></extra>"
            ),
            row=row, col=col
        )

    def _update_axes(self, fig):
        """更新坐标轴设置"""
        # 深度图表的坐标轴 (第1行)
        for col in [1, 2]:
            fig.update_xaxes(
                title_text="数量",
                gridcolor='#3d3d3d',
                zerolinecolor='#ffffff',
                zerolinewidth=2,
                tickfont=dict(size=8),
                row=1, col=col
            )
            fig.update_yaxes(
                title_text="价格 (USDT)",
                gridcolor='#3d3d3d',
                zerolinecolor='#3d3d3d',
                tickformat="$,.0f",
                tickfont=dict(size=8),
                row=1, col=col
            )

        # 比率图表的坐标轴 (第2行)
        for col in [1, 2]:
            fig.update_xaxes(
                title_text="价格范围",
                gridcolor='#3d3d3d',
                zerolinecolor='#3d3d3d',
                tickfont=dict(size=8),
                row=2, col=col
            )
            fig.update_yaxes(
                title_text="买卖比率",
                gridcolor='#3d3d3d',
                zerolinecolor='#3d3d3d',
                tickfont=dict(size=8),
                row=2, col=col
            )

    async def send_chart_to_discord(self, fig, symbol: str, webhook_urls: List[str]):
        """发送图表到Discord - 增强版：多个webhook之间也有延迟"""
        if not fig or not webhook_urls:
            return

        try:
            # 生成图表文件
            timestamp = int(time.time())
            image_path = f"depth_chart_{symbol}_{timestamp}.{Config.CHART_CONFIG['格式']}"
            
            fig.write_image(
                image_path, 
                engine="kaleido",
                width=Config.CHART_CONFIG["图表宽度"],
                height=Config.CHART_CONFIG["图表高度"],
                format=Config.CHART_CONFIG["格式"]
            )

            # 等待文件生成
            await asyncio.sleep(1)

            if not os.path.exists(image_path):
                if Config.OUTPUT_OPTIONS["启用控制台输出"]:
                    print(f"图表文件生成失败: {image_path}")
                return

            # 发送到Discord - 多个webhook之间添加延迟
            timestamp_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            content = f"# {symbol} 市场深度图表分析 - {timestamp_str}"

            # 按顺序发送到每个webhook，避免同时发送
            for i, url in enumerate(webhook_urls):
                try:
                    # 在发送前添加延迟（除了第一个）
                    if i > 0:
                        webhook_delay = Config.CHART_CONFIG.get("webhook延迟", 2)  # 默认2秒
                        if Config.OUTPUT_OPTIONS["启用控制台输出"]:
                            print(f"等待 {webhook_delay} 秒后发送到下一个webhook...")
                        await asyncio.sleep(webhook_delay)
                    
                    async with aiohttp.ClientSession() as session:
                        form = aiohttp.FormData()
                        form.add_field('content', content)
                        
                        with open(image_path, 'rb') as f:
                            form.add_field(
                                'file',
                                f.read(),
                                filename=os.path.basename(image_path),
                                content_type=f'image/{Config.CHART_CONFIG["格式"]}'
                            )
                        
                        async with session.post(url, data=form) as response:
                            if response.status in [200, 204]:
                                if Config.OUTPUT_OPTIONS["启用控制台输出"]:
                                    print(f"图表已成功发送到Discord webhook #{i+1}/{len(webhook_urls)}")
                            else:
                                if Config.OUTPUT_OPTIONS["启用控制台输出"]:
                                    print(f"发送图表到Discord webhook #{i+1}失败，状态码: {response.status}")
                                    
                except Exception as e:
                    if Config.OUTPUT_OPTIONS["启用控制台输出"]:
                        print(f"发送图表到Discord webhook #{i+1}时出错: {e}")

            # 清理临时文件（如果不需要保存到本地）
            if not Config.OUTPUT_OPTIONS["保存图表到本地"]:
                try:
                    if os.path.exists(image_path):
                        os.remove(image_path)
                except Exception as e:
                    if Config.OUTPUT_OPTIONS["启用控制台输出"]:
                        print(f"删除临时文件失败: {e}")
            else:
                if Config.OUTPUT_OPTIONS["启用控制台输出"]:
                    print(f"图表已保存到: {image_path}")

        except Exception as e:
            if Config.OUTPUT_OPTIONS["启用控制台输出"]:
                print(f"发送图表时出错: {e}")

    def should_send_now(self, symbol: str) -> bool:
        """检查指定币种是否应该发送图表"""
        current_time = time.time()
        interval = Config.SEND_INTERVALS["图表输出"]
        
        # 为每个币种单独记录发送时间
        if symbol not in self.last_send_time:
            self.last_send_time[symbol] = 0
        
        if current_time - self.last_send_time[symbol] >= interval:
            self.last_send_time[symbol] = current_time
            return True
        return False

    async def process_and_send(self, spot_manager: OrderBookManager, futures_manager: OrderBookManager):
        """处理并发送图表"""
        if not Config.is_output_enabled("图表输出"):
            return
            
        symbol = spot_manager.symbol
        
        if not self.should_send_now(symbol):
            return

        try:
            # 创建图表
            fig = self.create_depth_chart(spot_manager, futures_manager)
            
            if fig:
                # 获取webhook URLs
                webhooks = Config.get_webhooks(symbol, "图表输出")
                
                if webhooks:
                    # 将发送任务添加到队列中，而不是立即发送
                    self.send_queue.put((fig, symbol, webhooks))
                    
                    if Config.OUTPUT_OPTIONS["启用控制台输出"]:
                        print(f"已将 {symbol} 图表添加到发送队列")
                
        except Exception as e:
            if Config.OUTPUT_OPTIONS["启用控制台输出"]:
                print(f"处理和发送图表时出错: {e}")

    def stop(self):
        """停止图表输出管理器"""
        # 发送停止信号到队列
        self.send_queue.put(None)
        
        if Config.OUTPUT_OPTIONS["启用控制台输出"]:
            print("图表输出管理器已停止")

# 全局图表输出管理器实例
chart_output_manager = ChartOutputManager() 