import requests
import websocket
import json
import pandas as pd
import time
import threading
from typing import Dict, List, Optional, Union

class OrderBookManager:
    def __init__(self, symbol: str, is_futures: bool = False, min_quantity: float = None):
        self.symbol = symbol.upper()
        self.is_futures = is_futures
        self.order_book = {"bids": {}, "asks": {}}
        self.order_changes = {"bids": {}, "asks": {}}
        self.removed_orders = {"bids": {}, "asks": {}}
        self.last_update_id = 0
        self.min_quantity = min_quantity

    def get_initial_snapshot(self, limit: int = 5000):
        """获取初始订单簿快照"""
        if self.is_futures:
            base_url = "https://fapi.binance.com"
            endpoint = "/fapi/v1/depth"
            # 合约市场的limit参数只能是5, 10, 20, 50, 100, 500, 1000
            futures_limit = 1000  # 使用合约市场支持的最大值
            params = {"symbol": self.symbol, "limit": futures_limit}
        else:
            base_url = "https://api.binance.com"
            endpoint = "/api/v3/depth"
            params = {"symbol": self.symbol, "limit": limit}
            
        url = f"{base_url}{endpoint}"
        
        try:
            print(f"正在获取{self.symbol} {'合约' if self.is_futures else '现货'}数据...")
            print(f"请求URL: {url}")
            print(f"请求参数: {params}")
            
            headers = {
                'User-Agent': 'Mozilla/5.0',
                'Accept': 'application/json'
            }
            
            response = requests.get(url, params=params, headers=headers)
            
            if response.status_code != 200:
                error_msg = f"REST API请求失败 - URL: {url}, 参数: {params}, 状态码: {response.status_code}"
                if response.text:
                    error_msg += f", 响应内容: {response.text}"
                raise Exception(error_msg)
            
            data = response.json()
            # 合约市场使用不同的lastUpdateId字段名
            if self.is_futures:
                self.last_update_id = data.get("E", 0)  # 合约市场使用E作为更新ID
            else:
                self.last_update_id = data["lastUpdateId"]
            
            # 初始化订单簿
            self.order_book["bids"].clear()
            self.order_book["asks"].clear()
            
            for price, qty in data["bids"]:
                self.order_book["bids"][float(price)] = float(qty)
            for price, qty in data["asks"]:
                self.order_book["asks"][float(price)] = float(qty)
            
            print(f"{self.symbol} {'合约' if self.is_futures else '现货'}初始快照加载完成，lastUpdateId: {self.last_update_id}")
            
        except requests.exceptions.RequestException as e:
            raise Exception(f"网络请求错误: {str(e)}")
        except json.JSONDecodeError as e:
            raise Exception(f"JSON解析错误: {str(e)}, 响应内容: {response.text}")
        except Exception as e:
            raise Exception(f"获取{self.symbol}{'合约' if self.is_futures else '现货'}数据时出错: {str(e)}")

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

    def generate_market_analysis(self) -> str:
        """生成市场分析文本"""
        if not self.order_book["bids"] or not self.order_book["asks"]:
            return "订单簿数据不足，无法分析"

        market_type = "合约" if self.is_futures else "现货"
        highest_bid = max(self.order_book["bids"].keys())
        lowest_ask = min(self.order_book["asks"].keys())
        mid_price = (highest_bid + lowest_ask) / 2
        spread = lowest_ask - highest_bid

        # 构建订单簿摘要
        order_book_summary = f"**币安{market_type} {self.symbol} 订单簿摘要** (数量 > {self.min_quantity}，前10条):\n\n"
        
        # 添加卖出订单信息
        order_book_summary += self._format_orders("asks", reverse=True)
        
        # 添加买入订单信息
        order_book_summary += "\n" + self._format_orders("bids", reverse=True)
        
        # 计算各个范围的买卖比率
        ratios = {
            "0-1%": self.calculate_depth_ratio(1.0),
            "1-2.5%": self.calculate_depth_ratio_range(1.0, 2.5),
            "2.5-5%": self.calculate_depth_ratio_range(2.5, 5.0),
            "5-10%": self.calculate_depth_ratio_range(5.0, 10.0)
        }
        
        # 构建完整消息
        message = f"==================================================================\n\n"
        message += f"**币安{market_type} {self.symbol} 市场深度分析** - {time.strftime('%Y-%m-%d %H:%M:%S')}\n\n"
        message += f"当前价格: ${highest_bid:.2f} (最高买价) / ${lowest_ask:.2f} (最低卖价) / ${mid_price:.2f} (中间价)\n"
        message += f"当前价差: ${spread:.2f}\n\n"
        message += order_book_summary + "\n"
        
        # 添加各个范围的比率分析
        for range_name, (ratio, bids_vol, asks_vol, delta) in ratios.items():
            if ratio is not None:
                message += f"{range_name}价格范围内买卖比率: {ratio:.4f}\n"
                message += f"买量: {bids_vol:.4f}, 卖量: {asks_vol:.4f}, 差值: {delta:.4f}\n\n"
        
        return message

    def _format_orders(self, side: str, reverse: bool = False) -> str:
        """格式化订单信息"""
        df = pd.DataFrame(list(self.order_book[side].items()), columns=["price", "quantity"])
        df = df[df["quantity"] > self.min_quantity].sort_values(by="price", ascending=not reverse)
        df = df.head(10)
        
        title = "卖出订单 (Asks):" if side == "asks" else "买入订单 (Bids):"
        result = f"**{title}**\n"
        
        if df.empty:
            result += f"无符合条件的{title[:-1]}\n"
        else:
            for _, row in df.iterrows():
                price = row['price']
                change_str = ""
                if price in self.order_changes[side]:
                    change = self.order_changes[side][price]
                    sign = "+" if change > 0 else ""
                    change_str = f" ({sign}{change:.4f})"
                result += f"价格: ${price:.2f}, 数量: {row['quantity']:.4f}{change_str}\n"
        
        # 添加已移除的订单信息
        if self.removed_orders[side]:
            result += f"\n**已移除的{title[:-1]}:**\n"
            removed_items = sorted(self.removed_orders[side].items(), reverse=reverse)
            for price, qty in removed_items:
                result += f"价格: ${price:.2f}, 原数量: {qty:.4f} (已完全移除)\n"
        
        return result

class MarketDepthMonitor:
    def __init__(self, symbols: List[str], discord_webhooks: Dict[str, Dict[str, Union[str, List[str]]]], 
                 send_interval: int = 300, min_quantities: Dict[str, float] = None):
        self.min_quantities = min_quantities or {
            "BTC": 50.0,
            "ETH": 500.0,
            "DEFAULT": 1000.0
        }
        self.discord_webhooks = discord_webhooks
        self.spot_managers = {
            symbol: OrderBookManager(symbol, min_quantity=self._get_min_quantity(symbol, "spot"))
            for symbol in symbols
        }
        self.futures_managers = {
            symbol: OrderBookManager(symbol, is_futures=True, min_quantity=self._get_min_quantity(symbol, "futures"))
            for symbol in symbols
        }
        self.send_interval = send_interval
        self.last_send_time = 0

    def _get_min_quantity(self, symbol: str, market_type: str = "spot") -> float:
        """Get minimum quantity threshold based on trading pair and market type"""
        # Extract base currency from symbol (e.g., BTC from BTCUSDT)
        base_currency = symbol.replace("USDT", "").upper()
        currency_config = self.min_quantities.get(base_currency, self.min_quantities["DEFAULT"])
        
        # Handle both old format (single value) and new format (dict with spot/futures)
        if isinstance(currency_config, dict):
            return currency_config.get(market_type, currency_config.get("spot", 1000.0))
        else:
            # Backward compatibility for old format
            return currency_config

    def _get_webhook_urls(self, symbol: str, is_futures: bool) -> Union[str, List[str]]:
        """获取指定币种和市场类型的webhook URL(s)"""
        base_currency = symbol.replace("USDT", "").upper()
        market_type = "合约" if is_futures else "现货"
        
        # 如果币种有特定的webhook配置，使用它；否则使用默认配置
        webhooks = self.discord_webhooks.get(base_currency, self.discord_webhooks["DEFAULT"])
        return webhooks[market_type]

    def send_to_discord(self, content: str, webhook_url: Union[str, List[str]]):
        """发送消息到Discord Webhook(s)"""
        if isinstance(webhook_url, list):
            # 如果是webhook列表，发送到所有地址
            for url in webhook_url:
                try:
                    response = requests.post(url, json={"content": content})
                    if response.status_code == 204:
                        print(f"消息已成功发送到Discord: {url}")
                    else:
                        print(f"发送到Discord失败，状态码: {response.status_code}, URL: {url}")
                except Exception as e:
                    print(f"发送到Discord时出错: {e}, URL: {url}")
        else:
            # 单个webhook地址
            try:
                response = requests.post(webhook_url, json={"content": content})
                if response.status_code == 204:
                    print(f"消息已成功发送到Discord")
                else:
                    print(f"发送到Discord失败，状态码: {response.status_code}")
            except Exception as e:
                print(f"发送到Discord时出错: {e}")

    def on_message(self, ws, message):
        """处理WebSocket消息"""
        try:
            data = json.loads(message)
            
            if "result" in data and "id" in data:
                print(f"订阅确认: {message}")
                return
            
            # 从stream名称中提取symbol和市场类型
            stream = data.get("stream", "")
            if "@depth" not in stream:
                return
                
            symbol = stream.split("@")[0].upper()
            is_futures = "fstream" in ws.url
            
            manager = self.futures_managers[symbol] if is_futures else self.spot_managers[symbol]
            
            # 合约市场和现货市场的数据格式不同
            if is_futures:
                # 合约市场数据格式
                event_data = data.get("data", {})
                if "e" not in event_data or "E" not in event_data:
                    return
                    
                event_time = event_data["E"]
                first_update_id = event_data.get("U", 0)
                final_update_id = event_data.get("u", 0)
                
                # 合约市场使用事件时间戳作为更新ID
                if event_time > manager.last_update_id:
                    manager.apply_update(event_data.get("b", []), event_data.get("a", []))
                    manager.last_update_id = event_time
                    
                    current_time = time.time()
                    if current_time - self.last_send_time >= self.send_interval:
                        self._send_all_analyses()
                        self.last_send_time = current_time
            else:
                # 现货市场数据格式
                if "data" not in data:
                    return
                    
                event_data = data["data"]
                if "U" not in event_data or "u" not in event_data:
                    return
                    
                first_update_id = event_data["U"]
                final_update_id = event_data["u"]
                
                if first_update_id <= manager.last_update_id + 1 <= final_update_id:
                    manager.apply_update(event_data["b"], event_data["a"])
                    manager.last_update_id = final_update_id
                    
                    current_time = time.time()
                    if current_time - self.last_send_time >= self.send_interval:
                        self._send_all_analyses()
                        self.last_send_time = current_time
                
                elif first_update_id > manager.last_update_id + 1:
                    print(f"{symbol} {'合约' if is_futures else '现货'}数据不连续，需重新获取快照！")
                    manager.order_book["bids"].clear()
                    manager.order_book["asks"].clear()
                    manager.get_initial_snapshot()
                
        except Exception as e:
            print(f"处理消息时出错: {e}")
            print(f"原始消息: {message}")

    def _send_all_analyses(self):
        """发送所有市场的分析结果"""
        try:
            # 分别处理每个币种的现货和合约数据
            for symbol in self.spot_managers.keys():
                # 获取现货分析
                spot_manager = self.spot_managers[symbol]
                spot_analysis = spot_manager.generate_market_analysis()
                spot_webhooks = self._get_webhook_urls(symbol, False)
                
                # 获取合约分析
                futures_manager = self.futures_managers[symbol]
                futures_analysis = futures_manager.generate_market_analysis()
                futures_webhooks = self._get_webhook_urls(symbol, True)
                
                # 发送现货分析
                if spot_analysis and spot_webhooks:
                    message = f"# {symbol} 现货市场深度分析\n\n{spot_analysis}"
                    self.send_to_discord(message, spot_webhooks)
                
                # 发送合约分析
                if futures_analysis and futures_webhooks:
                    message = f"# {symbol} 合约市场深度分析\n\n{futures_analysis}"
                    self.send_to_discord(message, futures_webhooks)
                
                # 清空订单变化记录
                spot_manager.order_changes["bids"].clear()
                spot_manager.order_changes["asks"].clear()
                spot_manager.removed_orders["bids"].clear()
                spot_manager.removed_orders["asks"].clear()
                
                futures_manager.order_changes["bids"].clear()
                futures_manager.order_changes["asks"].clear()
                futures_manager.removed_orders["bids"].clear()
                futures_manager.removed_orders["asks"].clear()
                
        except Exception as e:
            print(f"发送分析报告时出错: {e}")

    def start(self):
        """启动市场深度监控"""
        try:
            # 初始化所有订单簿
            print("正在初始化订单簿...")
            for manager in list(self.spot_managers.values()) + list(self.futures_managers.values()):
                manager.get_initial_snapshot()
            
            # 创建WebSocket连接
            spot_streams = [f"{symbol.lower()}@depth" for symbol in self.spot_managers.keys()]
            futures_streams = [f"{symbol.lower()}@depth" for symbol in self.futures_managers.keys()]
            
            def create_websocket(url, streams):
                ws = websocket.WebSocketApp(
                    url,
                    on_message=self.on_message,
                    on_error=lambda ws, error: print(f"WebSocket错误: {error}"),
                    on_close=lambda ws, code, msg: print("WebSocket连接关闭"),
                    on_open=lambda ws: ws.send(json.dumps({
                        "method": "SUBSCRIBE",
                        "params": streams,
                        "id": 1
                    }))
                )
                return ws
            
            # 启动spot和futures的WebSocket
            if spot_streams:
                spot_ws = create_websocket("wss://stream.binance.com:9443/stream", spot_streams)
                threading.Thread(target=spot_ws.run_forever, daemon=True).start()
            
            if futures_streams:
                futures_ws = create_websocket("wss://fstream.binance.com/stream", futures_streams)
                threading.Thread(target=futures_ws.run_forever, daemon=True).start()
            
            print("WebSocket连接已启动，开始接收数据...")
            
        except Exception as e:
            print(f"启动监控时出错: {e}")

if __name__ == "__main__":
    # 配置监控的交易对和Discord Webhook
    symbols = ["BTCUSDT","ETHUSDT"]  # 可以添加更多交易对，例如 "BNBUSDT", "ETHUSDT"
    
    # 配置每个币种的最小数量阈值
    MIN_QUANTITIES = {
        "BTC": 50.0,    # BTC最小数量为50
        "ETH": 500.0,   # ETH最小数量为500
        "BNB": 1000.0,  # BNB最小数量为1000
        "DEFAULT": 1000.0  # 其他币种的默认最小数量
    }
    
    # Discord配置 - 可以为每个币种设置不同的webhook
    DISCORD_WEBHOOKS = {
        # BTC的webhook配置
        "BTC": {
            "现货": [  # 现货可以配置多个webhook地址
                "https://discord.com/api/webhooks/1350837714601377792/Gdmxej07wvWgJXxQ3qSqV8o-7Oaw5xc1kHGDw1K3sgXfrVuk6PsiUHymvVn-fU4GeMsd",
                "https://discordapp.com/api/webhooks/1367897839916683365/T9FOLGaqf1Hg-LEblt_WcMUfk__ZGwxjWzjlrd2tlHLEruJGTSFzvv8f5iHw-HW8Y29z"
            ],
            "合约": [  # 合约可以配置多个webhook地址
                "https://discord.com/api/webhooks/1350837714601377792/Gdmxej07wvWgJXxQ3qSqV8o-7Oaw5xc1kHGDw1K3sgXfrVuk6PsiUHymvVn-fU4GeMsd",
                "https://discord.com/api/webhooks/1379657654447636651/EquA1jpi8kkPvW3piihBoKFtlvccJOtjAkYSDQBijwsE8RIkTSlPBBgvKZurxUVw96D8"
            ]
        },
        # ETH的webhook配置
        "ETH": {
            "现货": [  # 现货可以配置多个webhook地址
                "https://discord.com/api/webhooks/1379314747929001985/r0LJJsNE_VC2eKJ5339XaM7UJ1h9ivllXpzTcHVygPyl0PMrP8aHoScrYmcC51Bi8jTQ"
            ],
            "合约": [  # 合约可以配置多个webhook地址
                "https://discord.com/api/webhooks/1379657849843744848/dEiv8taSib2HISO83Zw0G8thLW-EQ2_JgSBV_g3pC2cMgHFRgrICyjJZ9RoRwnTG8VAI"
            ]
        },
        # 默认webhook配置（用于未特别指定的币种）
        "DEFAULT": {
            "现货": [  # 现货可以配置多个webhook地址
                "https://discord.com/api/webhooks/1350837714601377792/Gdmxej07wvWgJXxQ3qSqV8o-7Oaw5xc1kHGDw1K3sgXfrVuk6PsiUHymvVn-fU4GeMsd"
            ],
            "合约": [  # 合约可以配置多个webhook地址
                "https://discord.com/api/webhooks/1350837714601377792/Gdmxej07wvWgJXxQ3qSqV8o-7Oaw5xc1kHGDw1K3sgXfrVuk6PsiUHymvVn-fU4GeMsd"
            ]
        }
    }
    
    # 发送间隔配置（秒）
    SEND_INTERVAL = 300  # 设置为60秒，你可以根据需要修改这个值
    
    try:
        # 创建MarketDepthMonitor实例时传入最小数量配置和Discord配置
        monitor = MarketDepthMonitor(
            symbols=symbols,
            discord_webhooks=DISCORD_WEBHOOKS,
            send_interval=SEND_INTERVAL,
            min_quantities=MIN_QUANTITIES
        )
        monitor.start()
        
        print(f"程序已启动，将每{SEND_INTERVAL}秒发送一次分析报告...")
        print("当前币种最小数量阈值设置：")
        for symbol, qty in MIN_QUANTITIES.items():
            print(f"- {symbol}: {qty}")
        print("\nDiscord Webhook配置：")
        for currency, webhooks in DISCORD_WEBHOOKS.items():
            print(f"- {currency}:")
            for market_type, urls in webhooks.items():
                if isinstance(urls, list):
                    print(f"  - {market_type}:")
                    for i, url in enumerate(urls, 1):
                        print(f"    {i}. {url}")
                else:
                    print(f"  - {market_type}: {urls}")
        
        # 保持主线程运行
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n用户中断程序")
    except Exception as e:
        print(f"发生异常: {e}") 