# -*- coding: utf-8 -*-
"""
Text Output Module
Responsible for generating and sending text-format market analysis, maintaining original output format
"""

import requests
import pandas as pd
import time
from typing import Dict, List, Union
from config import Config
from data_manager import OrderBookManager

class TextOutputManager:
    """Text Output Manager"""
    
    def __init__(self):
        self.last_send_time = 0

    def generate_market_analysis(self, manager: OrderBookManager) -> str:
        """Generate market analysis text (maintaining original format)"""
        market_data = manager.get_market_data()
        if not market_data:
            return "Insufficient order book data for analysis"

        symbol = market_data["symbol"]
        is_futures = market_data["is_futures"]
        highest_bid = market_data["highest_bid"]
        lowest_ask = market_data["lowest_ask"]
        mid_price = market_data["mid_price"]
        spread = market_data["spread"]
        order_book = market_data["order_book"]
        order_changes = market_data["order_changes"]
        removed_orders = market_data["removed_orders"]
        min_quantity = market_data["min_quantity"]

        market_type = "Futures" if is_futures else "Spot"

        # Build order book summary
        order_book_summary = f"**Binance {market_type} {symbol} Order Book Summary** (Quantity > {min_quantity}, Top 10):\n\n"
        
        # Add sell order information
        order_book_summary += self._format_orders(order_book, order_changes, removed_orders, "asks", reverse=True)
        
        # Add buy order information
        order_book_summary += "\n" + self._format_orders(order_book, order_changes, removed_orders, "bids", reverse=True)
        
        # Calculate buy/sell ratios for various ranges
        ratios = {}
        for i, (lower, upper) in enumerate(Config.ANALYSIS_RANGES):
            if i == 0:
                # First range uses simple ratio calculation
                ratio, bids_vol, asks_vol, delta = manager.calculate_depth_ratio(upper)
                range_name = f"0-{upper}%"
            else:
                # Other ranges use range ratio calculation
                ratio, bids_vol, asks_vol, delta = manager.calculate_depth_ratio_range(lower, upper)
                range_name = f"{lower}-{upper}%"
            
            ratios[range_name] = (ratio, bids_vol, asks_vol, delta)
        
        # Build complete message
        message = f"==================================================================\n\n"
        message += f"**Binance {market_type} {symbol} Market Depth Analysis** - {time.strftime('%Y-%m-%d %H:%M:%S')}\n\n"
        message += f"Current Price: ${highest_bid:.2f} (Highest Bid) / ${lowest_ask:.2f} (Lowest Ask) / ${mid_price:.2f} (Mid Price)\n"
        message += f"Current Spread: ${spread:.2f}\n\n"
        message += order_book_summary + "\n"
        
        # Add ratio analysis for various ranges
        for range_name, (ratio, bids_vol, asks_vol, delta) in ratios.items():
            if ratio is not None:
                message += f"{range_name} Price Range Buy/Sell Ratio: {ratio:.4f}\n"
                message += f"Bid Volume: {bids_vol:.4f}, Ask Volume: {asks_vol:.4f}, Delta: {delta:.4f}\n\n"
        
        return message

    def _format_orders(self, order_book: Dict, order_changes: Dict, removed_orders: Dict, 
                      side: str, reverse: bool = False) -> str:
        """Format order information (maintaining original format)"""
        # Use first symbol's spot market threshold as default for backward compatibility
        min_quantity = Config.get_min_quantity(list(Config.SYMBOLS)[0], "spot")
        
        df = pd.DataFrame(list(order_book[side].items()), columns=["price", "quantity"])
        df = df[df["quantity"] > min_quantity].sort_values(by="price", ascending=not reverse)
        df = df.head(10)
        
        title = "Sell Orders (Asks):" if side == "asks" else "Buy Orders (Bids):"
        result = f"**{title}**\n"
        
        if df.empty:
            result += f"No qualifying {title[:-1]}\n"
        else:
            for _, row in df.iterrows():
                price = row['price']
                change_str = ""
                if price in order_changes[side]:
                    change = order_changes[side][price]
                    sign = "+" if change > 0 else ""
                    change_str = f" ({sign}{change:.4f})"
                result += f"Price: ${price:.2f}, Quantity: {row['quantity']:.4f}{change_str}\n"
        
        # Add removed order information
        if removed_orders[side]:
            result += f"\n**Removed {title[:-1]}:**\n"
            removed_items = sorted(removed_orders[side].items(), reverse=reverse)
            for price, qty in removed_items:
                result += f"Price: ${price:.2f}, Original Quantity: {qty:.4f} (Completely Removed)\n"
        
        return result

    def send_to_discord(self, content: str, webhook_urls: List[str]):
        """Send message to Discord Webhook(s)"""
        if not webhook_urls:
            return
            
        for url in webhook_urls:
            try:
                response = requests.post(url, json={"content": content})
                if response.status_code == 204:
                    if Config.OUTPUT_OPTIONS["enable_console_output"]:
                        print(f"Text message successfully sent to Discord")
                else:
                    if Config.OUTPUT_OPTIONS["enable_console_output"]:
                        print(f"Failed to send to Discord, status code: {response.status_code}, URL: {url}")
            except Exception as e:
                if Config.OUTPUT_OPTIONS["enable_console_output"]:
                    print(f"Error sending to Discord: {e}, URL: {url}")

    def should_send_now(self) -> bool:
        """Check if text analysis should be sent now"""
        current_time = time.time()
        interval = Config.SEND_INTERVALS["text_output"]
        
        if current_time - self.last_send_time >= interval:
            self.last_send_time = current_time
            return True
        return False

    def process_and_send(self, spot_manager: OrderBookManager, futures_manager: OrderBookManager):
        """Process and send analysis results"""
        if not Config.is_output_enabled("text_output"):
            return
            
        if not self.should_send_now():
            return

        try:
            symbol = spot_manager.symbol
            
            # Generate spot analysis
            spot_analysis = self.generate_market_analysis(spot_manager)
            spot_webhooks = Config.get_webhooks(symbol, "text_output")
            
            # Generate futures analysis
            futures_analysis = self.generate_market_analysis(futures_manager)
            futures_webhooks = Config.get_webhooks(symbol, "text_output")
            
            # Send spot analysis
            if spot_analysis and spot_webhooks:
                message = f"# {symbol} Spot Market Depth Analysis\n\n{spot_analysis}"
                if Config.OUTPUT_OPTIONS["enable_console_output"]:
                    print("=== Spot Market Analysis ===")
                    print(message)
                    print("============================")
                self.send_to_discord(message, spot_webhooks)
            
            # Send futures analysis
            if futures_analysis and futures_webhooks:
                message = f"# {symbol} Futures Market Depth Analysis\n\n{futures_analysis}"
                if Config.OUTPUT_OPTIONS["enable_console_output"]:
                    print("=== Futures Market Analysis ===")
                    print(message)
                    print("===============================")
                self.send_to_discord(message, futures_webhooks)
            
            # Clear order change records
            spot_manager.clear_changes()
            futures_manager.clear_changes()
            
        except Exception as e:
            if Config.OUTPUT_OPTIONS["enable_console_output"]:
                print(f"Error sending text analysis report: {e}")

# Global text output manager instance
text_output_manager = TextOutputManager() 