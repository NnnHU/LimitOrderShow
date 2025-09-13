import asyncio
import json
import time
from typing import Dict, List, Optional, Union
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pandas as pd
from binance import AsyncClient, BinanceSocketManager
import aiohttp
import os
from datetime import datetime
import random

class RateLimiter:
    def __init__(self, max_requests: int = 10, time_window: int = 60):
        self.max_requests = max_requests
        self.time_window = time_window
        self.requests = []
        
    async def acquire(self):
        now = time.time()
        # 清理过期的请求记录
        self.requests = [req_time for req_time in self.requests if now - req_time < self.time_window]
        
        if len(self.requests) >= self.max_requests:
            # 计算需要等待的时间
            wait_time = self.requests[0] + self.time_window - now
            if wait_time > 0:
                await asyncio.sleep(wait_time)
                return await self.acquire()
        
        self.requests.append(now)
        return True

class OrderBookManagerUI:
    def __init__(self, symbol: str, is_futures: bool = False, min_quantity: float = None):
        self.symbol = symbol.upper()
        self.is_futures = is_futures
        self.order_book = {"bids": {}, "asks": {}}
        self.order_changes = {"bids": {}, "asks": {}}
        self.removed_orders = {"bids": {}, "asks": {}}
        self.last_update_id = 0
        self.min_quantity = min_quantity
        self.rate_limiter = RateLimiter(max_requests=5, time_window=60)  # 每分钟最多5个请求

    async def get_initial_snapshot(self, retry_count: int = 3, retry_delay: int = 10):
        """获取初始订单簿快照，带重试机制"""
        if self.is_futures:
            base_url = "https://fapi.binance.com"
            endpoint = "/fapi/v1/depth"
            futures_limit = 1000
            params = {"symbol": self.symbol, "limit": futures_limit}
        else:
            base_url = "https://api.binance.com"
            endpoint = "/api/v3/depth"
            params = {"symbol": self.symbol, "limit": 1000}
            
        url = f"{base_url}{endpoint}"
        
        for attempt in range(retry_count):
            try:
                print(f"正在获取{self.symbol} {'合约' if self.is_futures else '现货'}数据... (尝试 {attempt + 1}/{retry_count})")
                
                # 等待速率限制
                await self.rate_limiter.acquire()
                
                async with aiohttp.ClientSession() as session:
                    async with session.get(url, params=params) as response:
                        if response.status == 418 or response.status == 429:  # IP封禁或超出限制
                            wait_time = retry_delay * (attempt + 1)
                            print(f"请求被限制，等待{wait_time}秒后重试...")
                            await asyncio.sleep(wait_time)
                            continue
                            
                        if response.status != 200:
                            error_msg = f"REST API请求失败 - URL: {url}, 参数: {params}, 状态码: {response.status}"
                            text = await response.text()
                            if text:
                                error_msg += f", 响应内容: {text}"
                            raise Exception(error_msg)
                        
                        data = await response.json()
                
                if self.is_futures:
                    self.last_update_id = data.get("E", 0)
                else:
                    self.last_update_id = data["lastUpdateId"]
                
                self.order_book["bids"].clear()
                self.order_book["asks"].clear()
                
                for price, qty in data["bids"]:
                    self.order_book["bids"][float(price)] = float(qty)
                for price, qty in data["asks"]:
                    self.order_book["asks"][float(price)] = float(qty)
                
                print(f"{self.symbol} {'合约' if self.is_futures else '现货'}初始快照加载完成")
                return
                
            except Exception as e:
                if attempt < retry_count - 1:
                    wait_time = retry_delay * (attempt + 1)
                    print(f"获取数据失败，{wait_time}秒后重试: {str(e)}")
                    await asyncio.sleep(wait_time)
                else:
                    print(f"获取{self.symbol}{'合约' if self.is_futures else '现货'}数据时出错: {str(e)}")
                    raise

    def apply_update(self, bids_updates: List, asks_updates: List):
        """应用增量更新到订单簿"""
        def update_side(updates: List, side: str):
            for price, qty in updates:
                price = float(price)
                qty = float(qty)
                old_qty = self.order_book[side].get(price, 0)
                change = qty - old_qty
                
                if qty == 0:
                    self.order_book[side].pop(price, None)
                    if old_qty > self.min_quantity:
                        self.order_changes[side][price] = -old_qty
                        self.removed_orders[side][price] = old_qty
                else:
                    self.order_book[side][price] = qty
                    if abs(change) > self.min_quantity:
                        self.order_changes[side][price] = change

        update_side(bids_updates, "bids")
        update_side(asks_updates, "asks")

    def calculate_depth_ratio(self, price_range_percent: float = 1.0) -> tuple:
        """计算距离当前价格一定百分比范围内的买卖比率"""
        if not self.order_book["bids"] or not self.order_book["asks"]:
            return None, 0, 0, 0
        
        highest_bid = max(self.order_book["bids"].keys())
        lowest_ask = min(self.order_book["asks"].keys())
        mid_price = (highest_bid + lowest_ask) / 2
        
        lower_bound = mid_price * (1 - price_range_percent / 100)
        upper_bound = mid_price * (1 + price_range_percent / 100)
        
        bids_in_range = {price: qty for price, qty in self.order_book["bids"].items() if price >= lower_bound}
        bids_volume = sum(bids_in_range.values())
        
        asks_in_range = {price: qty for price, qty in self.order_book["asks"].items() if price <= upper_bound}
        asks_volume = sum(asks_in_range.values())
        
        delta = bids_volume - asks_volume
        total = bids_volume + asks_volume
        ratio = delta / total if total > 0 else 0
        
        return ratio, bids_volume, asks_volume, delta

    def calculate_depth_ratio_range(self, lower_percent: float, upper_percent: float) -> tuple:
        """计算指定价格范围内的买卖比率"""
        if not self.order_book["bids"] or not self.order_book["asks"]:
            return None, 0, 0, 0
        
        highest_bid = max(self.order_book["bids"].keys())
        lowest_ask = min(self.order_book["asks"].keys())
        mid_price = (highest_bid + lowest_ask) / 2
        
        lower_bound = mid_price * (1 - upper_percent / 100)
        upper_bound = mid_price * (1 + upper_percent / 100)
        inner_lower_bound = mid_price * (1 - lower_percent / 100)
        inner_upper_bound = mid_price * (1 + lower_percent / 100)
        
        bids_in_range = {price: qty for price, qty in self.order_book["bids"].items() 
                        if price >= lower_bound and price < inner_lower_bound}
        bids_volume = sum(bids_in_range.values())
        
        asks_in_range = {price: qty for price, qty in self.order_book["asks"].items() 
                        if price <= upper_bound and price > inner_upper_bound}
        asks_volume = sum(asks_in_range.values())
        
        delta = bids_volume - asks_volume
        total = bids_volume + asks_volume
        ratio = delta / total if total > 0 else 0
        
        return ratio, bids_volume, asks_volume, delta

    def get_order_book_data(self):
        """获取排序后的订单簿数据，并按最小数量阈值过滤"""
        # 过滤并排序买单 - 买单按价格从高到低排序（降序）
        bids = [(price, qty) for price, qty in self.order_book["bids"].items() if qty >= self.min_quantity]
        bids = sorted(bids, reverse=True)
        
        # 过滤并排序卖单 - 卖单按价格从低到高排序（升序）
        asks = [(price, qty) for price, qty in self.order_book["asks"].items() if qty >= self.min_quantity]
        asks = sorted(asks, reverse=False)
        
        return bids, asks

    def get_ratio_data(self):
        """获取不同范围的买卖比率数据"""
        ranges = [(0, 1), (1, 2.5), (2.5, 5), (5, 10)]
        ratios = []
        volumes = []
        
        for lower, upper in ranges:
            ratio, bids_vol, asks_vol, delta = self.calculate_depth_ratio_range(lower, upper)
            if ratio is not None:
                ratios.append(ratio)
                volumes.append((bids_vol, asks_vol))
            else:
                ratios.append(0)
                volumes.append((0, 0))
        
        return {
            "ranges": ['0-1%', '1-2.5%', '2.5-5%', '5-10%'],
            "ratios": ratios,
            "volumes": volumes
        }

class MarketDepthMonitorUI:
    def __init__(self, symbols: List[str], discord_webhooks: Dict[str, Dict[str, Union[str, List[str]]]], 
                 send_interval: int = 300, min_quantities: Dict[str, float] = None):
        self.min_quantities = min_quantities or {
            "BTC": 50.0,
            "ETH": 200.0,
            "DEFAULT": 1000.0
        }
        self.discord_webhooks = discord_webhooks
        self.spot_managers = {
            symbol: OrderBookManagerUI(symbol, min_quantity=self._get_min_quantity(symbol, "spot"))
            for symbol in symbols
        }
        self.futures_managers = {
            symbol: OrderBookManagerUI(symbol, is_futures=True, min_quantity=self._get_min_quantity(symbol, "futures"))
            for symbol in symbols
        }
        self.send_interval = send_interval
        self.last_send_time = 0

    def _get_min_quantity(self, symbol: str, market_type: str = "spot") -> float:
        """Get minimum quantity threshold based on trading pair and market type"""
        base_currency = symbol.replace("USDT", "").upper()
        currency_config = self.min_quantities.get(base_currency, self.min_quantities["DEFAULT"])
        
        # Handle both old format (single value) and new format (dict with spot/futures)
        if isinstance(currency_config, dict):
            return currency_config.get(market_type, currency_config.get("spot", 1000.0))
        else:
            # Backward compatibility for old format
            return currency_config

    def _get_webhook_urls(self, symbol: str) -> Union[str, List[str]]:
        """获取币种对应的webhook（不再区分现货和合约）"""
        base_currency = symbol.replace("USDT", "").upper()
        webhooks = self.discord_webhooks.get(base_currency, self.discord_webhooks["DEFAULT"])
        # 使用现货的webhook作为主要发送渠道
        return webhooks["现货"]

    def create_depth_chart(self, spot_manager: OrderBookManagerUI, futures_manager: OrderBookManagerUI):
        """创建深度图表，每边只显示前10个订单"""
        spot_bids, spot_asks = spot_manager.get_order_book_data()
        futures_bids, futures_asks = futures_manager.get_order_book_data()

        # 添加调试输出
        print(f"\n=== 调试：图表生成时的订单簿数据 ===")
        print(f"现货 {spot_manager.symbol} 数据：")
        print(f"买单前10条：{spot_bids[:10]}")
        print(f"卖单前10条：{spot_asks[:10]}")
        print(f"合约 {futures_manager.symbol} 数据：")
        print(f"买单前10条：{futures_bids[:10]}")
        print(f"卖单前10条：{futures_asks[:10]}")
        print("================================\n")

        # 获取当前价格（取买一卖一中间价）
        def get_current_price(bids, asks):
            if not bids or not asks:
                return None
            highest_bid = bids[0][0] if bids else None
            lowest_ask = asks[0][0] if asks else None  # 修复：asks现在按升序排列，第一个是最低价
            if highest_bid and lowest_ask:
                return (highest_bid + lowest_ask) / 2
            return highest_bid or lowest_ask

        spot_price = get_current_price(spot_bids, spot_asks)
        futures_price = get_current_price(futures_bids, futures_asks)

        # 限制每边只显示前10个订单
        spot_bids = spot_bids[:10]
        spot_asks = spot_asks[:10]  # 修复：取前10个最低价的卖单
        futures_bids = futures_bids[:10]
        futures_asks = futures_asks[:10]  # 修复：取前10个最低价的卖单

        # 计算价格范围以设置y轴
        def get_price_range(bids, asks):
            if not bids or not asks:
                return None, None
            min_price = min(bid[0] for bid in bids) * 0.95  # 留出一些边距
            max_price = max(ask[0] for ask in asks) * 1.05
            return min_price, max_price

        spot_min_price, spot_max_price = get_price_range(spot_bids, spot_asks)
        futures_min_price, futures_max_price = get_price_range(futures_bids, futures_asks)

        # 准备标题文本，处理价格可能为None的情况
        spot_title = f"{spot_manager.symbol} 现货市场深度 (前10档)"
        futures_title = f"{futures_manager.symbol} 合约市场深度 (前10档)"
        if spot_price is not None:
            spot_title += f"\n当前价格: ${spot_price:,.2f}"
        if futures_price is not None:
            futures_title += f"\n当前价格: ${futures_price:,.2f}"

        fig = make_subplots(rows=1, cols=2,
                           subplot_titles=(spot_title, futures_title))

        # 设置统一的柱形图宽度
        bar_width = 0.8

        # 现货市场深度图
        if spot_price is not None:
            fig.add_hline(y=spot_price, line_width=2, line_dash="dash", line_color="yellow", row=1, col=1,
                         annotation_text=f"${spot_price:,.2f}", 
                         annotation_position="bottom right",
                         annotation=dict(font_size=10, font_color="yellow"))

        fig.add_trace(
            go.Bar(
                x=[qty for _, qty in spot_asks],
                y=[price for price, _ in spot_asks],
                name="现货卖单",
                orientation='h',
                marker_color='#ff7675',
                text=[f"${price:,.2f}\n{qty:.3f} BTC" for price, qty in spot_asks],
                textposition='auto',
                width=bar_width
            ),
            row=1, col=1
        )

        fig.add_trace(
            go.Bar(
                x=[-qty for _, qty in spot_bids],  # 买单向左延伸（负方向）
                y=[price for price, _ in spot_bids],
                name="现货买单",
                orientation='h',
                marker_color='#00b894',
                text=[f"${price:,.2f}\n{qty:.3f} BTC" for price, qty in spot_bids],
                textposition='auto',
                width=bar_width
            ),
            row=1, col=1
        )

        # 合约市场深度图
        if futures_price is not None:
            fig.add_hline(y=futures_price, line_width=2, line_dash="dash", line_color="yellow", row=1, col=2,
                         annotation_text=f"${futures_price:,.2f}",
                         annotation_position="bottom right",
                         annotation=dict(font_size=10, font_color="yellow"))

        fig.add_trace(
            go.Bar(
                x=[qty for _, qty in futures_asks],
                y=[price for price, _ in futures_asks],
                name="合约卖单",
                orientation='h',
                marker_color='#ffa502',
                text=[f"${price:,.2f}\n{qty:.3f} BTC" for price, qty in futures_asks],
                textposition='auto',
                width=bar_width
            ),
            row=1, col=2
        )

        fig.add_trace(
            go.Bar(
                x=[-qty for _, qty in futures_bids],  # 买单向左延伸（负方向）
                y=[price for price, _ in futures_bids],
                name="合约买单",
                orientation='h',
                marker_color='#2e86de',
                text=[f"${price:,.2f}\n{qty:.3f} BTC" for price, qty in futures_bids],
                textposition='auto',
                width=bar_width
            ),
            row=1, col=2
        )

        fig.update_layout(
            plot_bgcolor='#2d2d2d',
            paper_bgcolor='#1a1a1a',
            font=dict(color='#ffffff'),
            height=800,
            showlegend=True,
            barmode='overlay',
            legend=dict(
                font=dict(color='#ffffff'),
                bgcolor='#2d2d2d',
                bordercolor='#3d3d3d'
            ),
            bargap=0.1  # 调整柱形图之间的间距
        )

        # 更新两个子图的坐标轴范围和格式
        for i, (min_price, max_price) in enumerate([(spot_min_price, spot_max_price), 
                                                  (futures_min_price, futures_max_price)], 1):
            if min_price is not None and max_price is not None:
                fig.update_yaxes(
                    title_text="价格 (USDT)",
                    gridcolor='#3d3d3d',
                    zerolinecolor='#3d3d3d',
                    range=[min_price, max_price],
                    tickformat="$,.0f",  # 添加美元符号和千位分隔符
                    row=1, col=i
                )
            
            fig.update_xaxes(
                title_text="数量 (BTC) - 买单←  →卖单",
                gridcolor='#3d3d3d',
                zerolinecolor='#ffffff',  # 让零轴更明显
                zerolinewidth=2,
                row=1, col=i
            )

        return fig

    def create_ratio_chart(self, spot_manager: OrderBookManagerUI, futures_manager: OrderBookManagerUI):
        """创建买卖比率图表"""
        spot_data = spot_manager.get_ratio_data()
        futures_data = futures_manager.get_ratio_data()

        fig = make_subplots(rows=1, cols=2,
                           subplot_titles=(f"{spot_manager.symbol} 现货市场买卖比率",
                                         f"{futures_manager.symbol} 合约市场买卖比率"))

        # 现货市场比率图
        fig.add_trace(
            go.Bar(
                x=spot_data["ranges"],
                y=spot_data["ratios"],
                name="现货比率",
                marker_color=[
                    '#00b894' if ratio > 0 else '#ff7675'
                    for ratio in spot_data["ratios"]
                ],
                text=[f"{ratio:.3f}" for ratio in spot_data["ratios"]],
                textposition='auto',
            ),
            row=1, col=1
        )

        # 合约市场比率图
        fig.add_trace(
            go.Bar(
                x=futures_data["ranges"],
                y=futures_data["ratios"],
                name="合约比率",
                marker_color=[
                    '#2e86de' if ratio > 0 else '#ffa502'
                    for ratio in futures_data["ratios"]
                ],
                text=[f"{ratio:.3f}" for ratio in futures_data["ratios"]],
                textposition='auto',
            ),
            row=1, col=2
        )

        fig.update_layout(
            plot_bgcolor='#2d2d2d',
            paper_bgcolor='#1a1a1a',
            font=dict(color='#ffffff'),
            height=400,
            showlegend=True,
            legend=dict(
                font=dict(color='#ffffff'),
                bgcolor='#2d2d2d',
                bordercolor='#3d3d3d'
            )
        )

        for i in range(1, 3):
            fig.update_xaxes(
                title_text="价格范围",
                gridcolor='#3d3d3d',
                zerolinecolor='#3d3d3d',
                row=1, col=i
            )
            fig.update_yaxes(
                title_text="买卖比率",
                gridcolor='#3d3d3d',
                zerolinecolor='#3d3d3d',
                row=1, col=i
            )

        return fig

    async def send_to_discord(self, content: str, files: List[str], webhook_url: Union[str, List[str]]):
        """发送消息和图片到Discord"""
        if isinstance(webhook_url, str):
            webhook_url = [webhook_url]

        for url in webhook_url:
            try:
                async with aiohttp.ClientSession() as session:
                    form = aiohttp.FormData()
                    form.add_field('content', content)
                    
                    for i, file_path in enumerate(files):
                        try:
                            with open(file_path, 'rb') as f:
                                form.add_field(
                                    f'file{i}',
                                    f.read(),
                                    filename=os.path.basename(file_path),
                                    content_type='image/png'
                                )
                        except FileNotFoundError:
                            print(f"文件未找到: {file_path}")
                            continue
                    
                    async with session.post(url, data=form) as response:
                        if response.status in [200, 204]:  # Discord API 成功状态码
                            print(f"消息已成功发送到Discord")
                        else:
                            print(f"发送到Discord失败，状态码: {response.status}")
                            response_text = await response.text()
                            print(f"错误详情: {response_text}")
                            
            except Exception as e:
                print(f"发送到Discord时出错: {e}")

    async def process_depth_update(self, msg):
        """处理深度数据更新"""
        try:
            if "stream" not in msg:
                return

            stream = msg["stream"]
            if "@depth" not in stream:
                return

            symbol = stream.split("@")[0].upper()
            is_futures = "fstream" in stream

            manager = self.futures_managers[symbol] if is_futures else self.spot_managers[symbol]
            data = msg["data"]

            if is_futures:
                if "e" not in data or "E" not in data:
                    return
                event_time = data["E"]
                if event_time > manager.last_update_id:
                    manager.apply_update(data.get("b", []), data.get("a", []))
                    manager.last_update_id = event_time
            else:
                if "U" not in data or "u" not in data:
                    return
                first_update_id = data["U"]
                final_update_id = data["u"]

                if first_update_id <= manager.last_update_id + 1 <= final_update_id:
                    manager.apply_update(data["b"], data["a"])
                    manager.last_update_id = final_update_id
                elif first_update_id > manager.last_update_id + 1:
                    print(f"{symbol} {'合约' if is_futures else '现货'}数据不连续，需重新获取快照！")
                    await manager.get_initial_snapshot()

            current_time = time.time()
            if current_time - self.last_send_time >= self.send_interval:
                await self.generate_and_send_charts()
                self.last_send_time = current_time

        except Exception as e:
            print(f"处理深度数据更新时出错: {e}")

    async def generate_and_send_charts(self):
        """生成并发送图表到Discord"""
        try:
            for symbol in self.spot_managers.keys():
                spot_manager = self.spot_managers[symbol]
                futures_manager = self.futures_managers[symbol]

                # 创建深度图表
                depth_fig = self.create_depth_chart(spot_manager, futures_manager)
                depth_image = f"depth_{symbol}_{int(time.time())}.png"
                depth_fig.write_image(depth_image, engine="kaleido")

                # 创建比率图表
                ratio_fig = self.create_ratio_chart(spot_manager, futures_manager)
                ratio_image = f"ratio_{symbol}_{int(time.time())}.png"
                ratio_fig.write_image(ratio_image, engine="kaleido")

                # 确保文件已经生成
                if not os.path.exists(depth_image) or not os.path.exists(ratio_image):
                    print("等待图表文件生成...")
                    await asyncio.sleep(1)  # 等待文件生成

                # 生成消息内容
                timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                content = f"# {symbol} 市场深度分析 - {timestamp}\n"

                # 只发送到一个webhook列表
                webhooks = self._get_webhook_urls(symbol)
                
                # 检查文件是否存在
                files_to_send = []
                if os.path.exists(depth_image):
                    files_to_send.append(depth_image)
                if os.path.exists(ratio_image):
                    files_to_send.append(ratio_image)

                if files_to_send:
                    await self.send_to_discord(content, files_to_send, webhooks)

                # 清理临时文件
                for file in [depth_image, ratio_image]:
                    try:
                        if os.path.exists(file):
                            os.remove(file)
                    except Exception as e:
                        print(f"删除文件 {file} 时出错: {e}")

                # 清空订单变化记录
                for manager in [spot_manager, futures_manager]:
                    manager.order_changes["bids"].clear()
                    manager.order_changes["asks"].clear()
                    manager.removed_orders["bids"].clear()
                    manager.removed_orders["asks"].clear()

        except Exception as e:
            print(f"生成和发送图表时出错: {e}")
            import traceback
            print(traceback.format_exc())

    async def start(self):
        """启动市场深度监控"""
        try:
            # 初始化所有订单簿
            print("正在初始化订单簿...")
            init_tasks = []
            for manager in list(self.spot_managers.values()) + list(self.futures_managers.values()):
                init_tasks.append(manager.get_initial_snapshot())
            await asyncio.gather(*init_tasks)

            # 创建Binance客户端
            client = await AsyncClient.create()
            bm = BinanceSocketManager(client)

            # 订阅现货和合约的WebSocket流
            tasks = []
            
            # 现货WebSocket
            spot_streams = [f"{symbol.lower()}@depth" for symbol in self.spot_managers.keys()]
            spot_socket = bm.multiplex_socket(spot_streams)
            tasks.append(self._handle_socket(spot_socket))

            # 合约WebSocket
            futures_streams = [f"{symbol.lower()}@depth" for symbol in self.futures_managers.keys()]
            futures_socket = bm.futures_multiplex_socket(futures_streams)
            tasks.append(self._handle_socket(futures_socket))

            print("WebSocket连接已启动，开始接收数据...")
            await asyncio.gather(*tasks)

        except Exception as e:
            print(f"启动监控时出错: {e}")
        finally:
            await client.close_connection()

    async def _handle_socket(self, socket):
        """处理WebSocket连接"""
        async with socket as s:
            while True:
                msg = await s.recv()
                await self.process_depth_update(msg)

if __name__ == "__main__":
    # 配置监控的交易对和Discord Webhook
    symbols = ["BTCUSDT"]
    
    # 配置每个币种的最小数量阈值
    MIN_QUANTITIES = {
        "BTC": 50.0,
        "ETH": 200.0,
        "DEFAULT": 1000.0
    }
    
    # Discord配置 - 简化为只使用一个webhook列表
    DISCORD_WEBHOOKS = {
        "BTC": {
            "现货": [
                "https://discord.com/api/webhooks/1379448500177211543/7yJMdGXvGsYhR2eD_n8MbTDlZ8Nw34WcKVi2t_V6sdJ3All-ICwZARXA0oaw7ZzOKIGh",
            ],
            "合约": []  # 不再使用
        },
        "ETH": {
            "现货": [
                "https://discord.com/api/webhooks/1379314766094532618/3Np-4gLX9S8zAZ8VdHycht7_JQXCMqQ6a3-Y1a0_rkJVr1dRlAlYY5VA2BC6uye5m26n"
            ],
            "合约": []  # 不再使用
        },
        "DEFAULT": {
            "现货": [
                "https://discord.com/api/webhooks/1350837714601377792/Gdmxej07wvWgJXxQ3qSqV8o-7Oaw5xc1kHGDw1K3sgXfrVuk6PsiUHymvVn-fU4GeMsd"
            ],
            "合约": []  # 不再使用
        }
    }
    
    # 发送间隔配置（秒）
    SEND_INTERVAL = 10  # 改为10秒用于快速测试

    # 创建并启动监控器
    monitor = MarketDepthMonitorUI(
        symbols=symbols,
        discord_webhooks=DISCORD_WEBHOOKS,
        send_interval=SEND_INTERVAL,
        min_quantities=MIN_QUANTITIES
    )

    # 运行异步事件循环
    try:
        asyncio.run(monitor.start())
    except KeyboardInterrupt:
        print("\n用户中断程序")
