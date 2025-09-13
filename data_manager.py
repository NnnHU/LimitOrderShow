# -*- coding: utf-8 -*-
"""
统一数据管理器
负责从币安API获取和维护订单簿数据，提供统一的数据接口
"""

import requests
import websocket
import json
import pandas as pd
import time
import threading
from typing import Dict, List, Optional, Tuple
from config import Config

class OrderBookManager:
    """订单簿管理器"""
    
    def __init__(self, symbol: str, is_futures: bool = False):
        self.symbol = symbol.upper()
        self.is_futures = is_futures
        self.order_book = {"bids": {}, "asks": {}}
        self.order_changes = {"bids": {}, "asks": {}}
        self.removed_orders = {"bids": {}, "asks": {}}
        self.last_update_id = 0
        # Set minimum quantity based on market type (spot/futures)
        market_type = "futures" if is_futures else "spot"
        self.min_quantity = Config.get_min_quantity(symbol, market_type)
        self._lock = threading.Lock()  # 添加线程锁保证数据安全
        
        # 数据预热相关属性
        self.update_count = 0           # WebSocket更新次数
        self.first_update_time = None   # 首次更新时间
        self.is_warmed_up = False       # 是否已预热完成

    def get_initial_snapshot(self, limit: int = 1000):
        """获取初始订单簿快照"""
        if self.is_futures:
            base_url = "https://fapi.binance.com"
            endpoint = "/fapi/v1/depth"
            params = {"symbol": self.symbol, "limit": limit}
        else:
            base_url = "https://api.binance.com"
            endpoint = "/api/v3/depth"
            params = {"symbol": self.symbol, "limit": limit}
            
        url = f"{base_url}{endpoint}"
        
        try:
            if Config.OUTPUT_OPTIONS["enable_console_output"]:
                print(f"正在获取{self.symbol} {'合约' if self.is_futures else '现货'}数据...")
            
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
            
            with self._lock:
                # 合约市场使用不同的lastUpdateId字段名
                if self.is_futures:
                    self.last_update_id = data.get("E", 0)
                else:
                    self.last_update_id = data["lastUpdateId"]
                
                # 初始化订单簿
                self.order_book["bids"].clear()
                self.order_book["asks"].clear()
                
                for price, qty in data["bids"]:
                    self.order_book["bids"][float(price)] = float(qty)
                for price, qty in data["asks"]:
                    self.order_book["asks"][float(price)] = float(qty)
            
            if Config.OUTPUT_OPTIONS["enable_console_output"]:
                print(f"{self.symbol} {'合约' if self.is_futures else '现货'}初始快照加载完成，lastUpdateId: {self.last_update_id}")
            
        except requests.exceptions.RequestException as e:
            raise Exception(f"网络请求错误: {str(e)}")
        except json.JSONDecodeError as e:
            raise Exception(f"JSON解析错误: {str(e)}, 响应内容: {response.text}")
        except Exception as e:
            raise Exception(f"获取{self.symbol}{'合约' if self.is_futures else '现货'}数据时出错: {str(e)}")

    def apply_update(self, bids_updates: List, asks_updates: List):
        """应用增量更新到订单簿"""
        with self._lock:
            # 记录更新次数和时间
            self.update_count += 1
            if self.first_update_time is None:
                self.first_update_time = time.time()
            
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
            
            # 检查是否完成预热
            if not self.is_warmed_up:
                self._check_warmup_status()

    def _check_warmup_status(self):
        """检查数据预热状态"""
        if not Config.DATA_WARMUP_CONFIG["enable_warmup_check"]:
            self.is_warmed_up = True
            return
        
        current_time = time.time()
        
        # 检查启动等待时间
        if self.first_update_time is None:
            return
            
        elapsed_time = current_time - self.first_update_time
        min_wait_time = Config.DATA_WARMUP_CONFIG["startup_wait_time"]
        
        # 检查更新次数
        min_updates = Config.DATA_WARMUP_CONFIG["min_update_count"]
        
        # 检查订单数量
        bids_count = len([qty for qty in self.order_book["bids"].values() if qty >= self.min_quantity])
        asks_count = len([qty for qty in self.order_book["asks"].values() if qty >= self.min_quantity])
        min_orders = Config.DATA_WARMUP_CONFIG["min_order_count"]
        
        # 所有条件都满足才算预热完成
        if (elapsed_time >= min_wait_time and 
            self.update_count >= min_updates and 
            bids_count >= min_orders and 
            asks_count >= min_orders):
            
            self.is_warmed_up = True
            if Config.OUTPUT_OPTIONS["enable_console_output"]:
                print(f"✅ {self.symbol} {'合约' if self.is_futures else '现货'}数据预热完成")
                print(f"   等待时间: {elapsed_time:.1f}秒, 更新次数: {self.update_count}, "
                      f"符合条件订单: 买{bids_count}条/卖{asks_count}条")

    def is_ready_for_output(self) -> bool:
        """检查是否准备好输出"""
        return self.is_warmed_up

    def get_market_data(self) -> Dict:
        """获取市场数据（线程安全）"""
        with self._lock:
            if not self.order_book["bids"] or not self.order_book["asks"]:
                return None
            
            highest_bid = max(self.order_book["bids"].keys())
            lowest_ask = min(self.order_book["asks"].keys())
            mid_price = (highest_bid + lowest_ask) / 2
            spread = lowest_ask - highest_bid
            
            return {
                "symbol": self.symbol,
                "is_futures": self.is_futures,
                "highest_bid": highest_bid,
                "lowest_ask": lowest_ask,
                "mid_price": mid_price,
                "spread": spread,
                "order_book": self.order_book.copy(),
                "order_changes": self.order_changes.copy(),
                "removed_orders": self.removed_orders.copy(),
                "min_quantity": self.min_quantity
            }

    def get_filtered_orders(self, limit: int = 10) -> Tuple[List[Tuple], List[Tuple]]:
        """获取过滤后的订单数据（用于图表显示）"""
        with self._lock:
            # 过滤并排序买单 - 买单按价格从高到低排序（降序）
            bids = [(price, qty) for price, qty in self.order_book["bids"].items() if qty >= self.min_quantity]
            bids = sorted(bids, reverse=True)
            
            # 过滤并排序卖单 - 卖单按价格从低到高排序（升序）
            asks = [(price, qty) for price, qty in self.order_book["asks"].items() if qty >= self.min_quantity]
            asks = sorted(asks, reverse=False)
            
            return bids[:limit], asks[:limit]

    def calculate_depth_ratio(self, price_range_percent: float = 1.0) -> Tuple:
        """计算距离当前价格一定百分比范围内的买卖比率"""
        with self._lock:
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

    def calculate_depth_ratio_range(self, lower_percent: float, upper_percent: float) -> Tuple:
        """计算指定价格范围内的买卖比率"""
        with self._lock:
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

    def clear_changes(self):
        """清空订单变化记录"""
        with self._lock:
            self.order_changes["bids"].clear()
            self.order_changes["asks"].clear()
            self.removed_orders["bids"].clear()
            self.removed_orders["asks"].clear()

class DataManager:
    """统一数据管理器"""
    
    def __init__(self):
        self.spot_managers = {}
        self.futures_managers = {}
        self._init_managers()

    def _init_managers(self):
        """初始化所有交易对的管理器"""
        for symbol in Config.SYMBOLS:
            self.spot_managers[symbol] = OrderBookManager(symbol, is_futures=False)
            self.futures_managers[symbol] = OrderBookManager(symbol, is_futures=True)

    def get_initial_snapshots(self):
        """获取所有初始快照"""
        try:
            if Config.OUTPUT_OPTIONS["enable_console_output"]:
                print("正在初始化订单簿...")
            
            for manager in list(self.spot_managers.values()) + list(self.futures_managers.values()):
                manager.get_initial_snapshot()
                
            if Config.OUTPUT_OPTIONS["enable_console_output"]:
                print("所有订单簿初始化完成")
                
        except Exception as e:
            print(f"初始化订单簿时出错: {e}")
            raise

    def get_manager(self, symbol: str, is_futures: bool = False) -> OrderBookManager:
        """获取指定的管理器"""
        if is_futures:
            return self.futures_managers.get(symbol)
        else:
            return self.spot_managers.get(symbol)

    def get_all_managers(self) -> Dict[str, Dict[str, OrderBookManager]]:
        """获取所有管理器"""
        return {
            "spot": self.spot_managers,
            "futures": self.futures_managers
        }

    def is_system_ready_for_output(self) -> bool:
        """检查整个系统是否准备好输出"""
        if not Config.DATA_WARMUP_CONFIG["enable_warmup_check"]:
            return True
        
        # 检查所有管理器是否都完成预热
        all_managers = list(self.spot_managers.values()) + list(self.futures_managers.values())
        ready_count = sum(1 for manager in all_managers if manager.is_ready_for_output())
        total_count = len(all_managers)
        
        is_ready = ready_count == total_count
        
        if Config.OUTPUT_OPTIONS["enable_console_output"] and not is_ready:
            # 只在第一次检查时显示状态，避免重复输出
            if not hasattr(self, '_warmup_status_shown'):
                print(f"📊 数据预热状态: {ready_count}/{total_count} 个数据源已就绪")
                self._warmup_status_shown = True
        
        return is_ready

    def get_warmup_status(self) -> Dict:
        """获取详细的预热状态"""
        status = {}
        for symbol in Config.SYMBOLS:
            spot_manager = self.get_manager(symbol, False)
            futures_manager = self.get_manager(symbol, True)
            
            status[symbol] = {
                "现货": {
                    "预热完成": spot_manager.is_ready_for_output(),
                    "更新次数": spot_manager.update_count,
                    "运行时间": time.time() - spot_manager.first_update_time if spot_manager.first_update_time else 0
                },
                "合约": {
                    "预热完成": futures_manager.is_ready_for_output(),
                    "更新次数": futures_manager.update_count,
                    "运行时间": time.time() - futures_manager.first_update_time if futures_manager.first_update_time else 0
                }
            }
        
        return status

    def process_websocket_message(self, message: str, is_futures: bool = None):
        """处理WebSocket消息"""
        try:
            data = json.loads(message)
            
            if "result" in data and "id" in data:
                if Config.OUTPUT_OPTIONS["enable_console_output"]:
                    print(f"订阅确认: {message}")
                return
            
            # 从stream名称中提取symbol和市场类型
            stream = data.get("stream", "")
            if "@depth" not in stream:
                return
                
            symbol = stream.split("@")[0].upper()
            
            # 使用传入的参数来判断市场类型
            if is_futures is None:
                # 如果没有传入参数，尝试从stream中判断（这个逻辑可能需要调整）
                is_futures = "fstream" in message.lower()
            
            manager = self.get_manager(symbol, is_futures)
            if not manager:
                return
            
            # 合约市场和现货市场的数据格式不同
            if is_futures:
                # 合约市场数据格式
                event_data = data.get("data", {})
                if "e" not in event_data or "E" not in event_data:
                    return
                    
                event_time = event_data["E"]
                
                # 合约市场使用事件时间戳作为更新ID
                if event_time > manager.last_update_id:
                    manager.apply_update(event_data.get("b", []), event_data.get("a", []))
                    manager.last_update_id = event_time
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
                elif first_update_id > manager.last_update_id + 1:
                    if Config.OUTPUT_OPTIONS["enable_console_output"]:
                        print(f"{symbol} {'合约' if is_futures else '现货'}数据不连续，需重新获取快照！")
                    manager.order_book["bids"].clear()
                    manager.order_book["asks"].clear()
                    manager.get_initial_snapshot()
                
        except Exception as e:
            if Config.OUTPUT_OPTIONS["enable_console_output"]:
                print(f"处理消息时出错: {e}")
                print(f"原始消息: {message}")

# 全局数据管理器实例
data_manager = DataManager() 