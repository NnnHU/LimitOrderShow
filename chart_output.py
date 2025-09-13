# -*- coding: utf-8 -*-
"""
Chart Output Module
Responsible for generating and sending chart-format market analysis.
This version uses a 3-row layout with a 4-column table row at the bottom.
All text content is in English, with specific color schemes and layout adjustments.
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
# from oi_funding_data import OIFundingDataManager # 註釋：移除不再需要的導入
import threading
from queue import Queue
import math

class ChartOutputManager:
    """Chart Output Manager"""
    
    def __init__(self):
        self.last_send_time = {}
        self.send_queue = Queue()
        self.send_lock = threading.Lock()
        # self.oi_funding_manager = OIFundingDataManager() # 註釋：移除不存在的管理器實例化
        
        # 註釋：將所有顏色配置集中到此處，方便統一修改。
        self.color_palettes = {
            "Spot": {
                "bids": "#00b894",  # Green
                "asks": "#ff7675"   # Red
            },
            "Futures": {
                "bids": "#3498db",  # Sky Blue (買單 - 冷色)
                "asks": "#f39c12"   # Orange (賣單 - 暖色，推薦搭配)
            },
            "Neutral": "#6c757d", # 中性/無數據時的顏色
            "FundingRate": {
                "positive": "#ff7675", # 紅色
                "negative": "#00b894"  # 綠色
            }
        }
        
        self._start_sender_thread()

    def _start_sender_thread(self):
        # 註釋：啟動背景執行緒，用於發送圖表
        def sender_worker():
            while True:
                try:
                    task = self.send_queue.get()
                    if task is None: break
                    fig, symbol, webhook_urls = task
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    try:
                        loop.run_until_complete(
                            self._send_chart_with_delay(fig, symbol, webhook_urls)
                        )
                    finally: loop.close()
                    self.send_queue.task_done()
                except Exception as e:
                    if Config.OUTPUT_OPTIONS["enable_console_output"]:
                        print(f"Sender thread error: {e}")
        
        sender_thread = threading.Thread(target=sender_worker, daemon=True)
        sender_thread.start()

    async def _send_chart_with_delay(self, fig, symbol: str, webhook_urls: List[str]):
        # 註釋：在發送圖表前，根據配置等待一段時間
        with self.send_lock:
            delay = Config.CHART_CONFIG.get("send_delay", 3)
            await asyncio.sleep(delay)
            if Config.OUTPUT_OPTIONS["enable_console_output"]:
                print(f"Sending {symbol} chart...")
            await self.send_chart_to_discord(fig, symbol, webhook_urls)
    
    def _add_depth_traces(self, fig, bids: List[Tuple], asks: List[Tuple], current_price: float, 
                          market_type: str, row: int, col: int, subplot_num: int):
        # 註釋：此函式負責添加市場深度圖（頂部圖表）
        colors = self.color_palettes.get(market_type, self.color_palettes["Spot"])
        all_orders = bids + asks
        if not all_orders: return

        quantities = [q for p, q in all_orders]
        min_qty, max_qty = min(quantities), max(quantities)
        min_bar_width, max_bar_width = 0.1, 0.3

        def get_bar_width(qty):
            if max_qty == min_qty: return (min_bar_width + max_bar_width) / 2
            log_min, log_max = math.log1p(min_qty), math.log1p(max_qty)
            if log_max == log_min: return (min_bar_width + max_bar_width) / 2
            normalized_log = (math.log1p(qty) - log_min) / (log_max - log_min)
            return min_bar_width + normalized_log * (max_bar_width - min_bar_width)

        corrected_asks = [order for order in all_orders if order[0] > current_price]
        corrected_bids = [order for order in all_orders if order[0] <= current_price]

        if corrected_asks:
            fig.add_trace(go.Bar(x=[q for p, q in corrected_asks], y=[f"${p:,.2f}" for p, q in corrected_asks], name=f"{market_type} Asks", orientation='h', marker_color=colors["asks"], width=[get_bar_width(q) for p, q in corrected_asks], hovertemplate=f"{market_type} Ask<br>Price: %{{y}}<br>Qty: %{{x:.2f}}<extra></extra>", opacity=0.8), row=row, col=col)
        if corrected_bids:
            fig.add_trace(go.Bar(x=[q for p, q in corrected_bids], y=[f"${p:,.2f}" for p, q in corrected_bids], name=f"{market_type} Bids", orientation='h', marker_color=colors["bids"], width=[get_bar_width(q) for p, q in corrected_bids], hovertemplate=f"{market_type} Bid<br>Price: %{{y}}<br>Qty: %{{x:.2f}}<extra></extra>", opacity=0.8), row=row, col=col)
        
        x_ref = f'x{subplot_num}' if subplot_num > 1 else 'x'
        y_ref = f'y{subplot_num}' if subplot_num > 1 else 'y'
        current_price_str = f"${current_price:,.2f}"
        fig.add_shape(type="line", x0=0, y0=current_price_str, x1=1, y1=current_price_str, xref=f"{x_ref} domain", yref=y_ref, line=dict(color='#ffffff', width=1, dash='dash'))
        fig.add_annotation(x=0.98, y=current_price_str, xref=f"{x_ref} domain", yref=y_ref, text=f"Current: {current_price_str}", showarrow=False, font=dict(color='#ffffff', size=10), xanchor="right", yanchor="bottom", bgcolor="rgba(0,0,0,0.5)")

    def _add_single_order_table(self, fig, orders: List[Tuple], market_type: str, order_type: str, row: int, col: int):
        # 註釋：此函式負責添加單一的掛單列表（賣或買）
        color = self.color_palettes.get(market_type, {}).get(order_type, 'white')
        orders.sort(key=lambda x: x[0], reverse=True)
        header_values = ['<b>Price (USDT)</b>', '<b>Quantity</b>']
        prices = [f"<b>${price:,.2f}</b>" for price, _ in orders]
        quantities = [f"<b>{qty:.3f}</b>" for _, qty in orders]
        font_colors = [[color] * len(orders), [color] * len(orders)]
        fig.add_trace(go.Table(header=dict(values=header_values, fill_color='#2a2a2a', font=dict(color='white', size=12), align='left'), cells=dict(values=[prices, quantities], fill_color='#1e1e1e', font=dict(color=font_colors, size=11), align='left', height=30)), row=row, col=col)

    def _add_oi_funding_annotation(self, fig, oi_value, funding_rate, row, col, subplot_num):
        # 註釋：(新) 在指定的子圖上添加 OI 和資金費率的註解
        if oi_value is None and funding_rate is None:
            return

        oi_text = f"<b>OI: {oi_value:,.0f}</b>" if oi_value is not None else ""
        fr_text = ""
        if funding_rate is not None:
            rate_color = self.color_palettes["FundingRate"]["positive"] if funding_rate >= 0 else self.color_palettes["FundingRate"]["negative"]
            fr_text = f"<b>Funding: <span style='color:{rate_color};'>{funding_rate:+.4f}%</span></b>"

        separator = " | " if oi_text and fr_text else ""
        annotation_text = f"{oi_text}{separator}{fr_text}"

        x_ref = f'x{subplot_num}' if subplot_num > 1 else 'x'
        y_ref = f'y{subplot_num}' if subplot_num > 1 else 'y'

        # *** MODIFICATION: Repositioned the annotation ***
        # 註釋：將註解放置在圖表下方，取代X軸標題的位置
        fig.add_annotation(
            x=0.5, y=-0.3, # 將Y位置設為負數，使其在圖表下方
            xref=f"{x_ref} domain", yref=f"{y_ref} domain",
            text=annotation_text, showarrow=False,
            font=dict(color='white', size=14), # 增大字體
            align="center", xanchor="center", yanchor="top",
        )


    def create_depth_chart(self, spot_manager: OrderBookManager, futures_manager: OrderBookManager):
        # 註釋：創建圖表的核心函式
        try:
            spot_data = spot_manager.get_market_data()
            futures_data = futures_manager.get_market_data()
            if not spot_data or not futures_data: return None

            symbol = futures_manager.symbol
            oi_value, funding_rate = None, None
            try:
                oi_url = f"https://fapi.binance.com/fapi/v1/openInterest?symbol={symbol.upper()}"
                oi_response = requests.get(oi_url, timeout=5)
                if oi_response.status_code == 200:
                    oi_data = oi_response.json()
                    oi_value = float(oi_data.get("openInterest", 0))

                funding_url = f"https://fapi.binance.com/fapi/v1/premiumIndex?symbol={symbol.upper()}"
                funding_response = requests.get(funding_url, timeout=5)
                if funding_response.status_code == 200:
                    funding_data = funding_response.json()
                    funding_rate = float(funding_data.get("lastFundingRate", 0)) * 100
            except Exception as e:
                if Config.OUTPUT_OPTIONS["enable_console_output"]:
                    print(f"Error fetching OI/Funding data: {e}")

            fig = make_subplots(
                rows=3, cols=4,
                specs=[
                    [{"type": "xy", "colspan": 2}, None, {"type": "xy", "colspan": 2}, None],
                    [{"type": "xy", "colspan": 2}, None, {"type": "xy", "colspan": 2}, None],
                    [{"type": "table"}, {"type": "table"}, {"type": "table"}, {"type": "table"}]
                ],
                row_heights=[0.45, 0.2, 0.35],
                column_widths=[0.25, 0.25, 0.25, 0.25],
                vertical_spacing=0.1,
                horizontal_spacing=0.04,
                subplot_titles=(
                    f"<b>Binance {spot_manager.symbol} Spot Market Depth</b>", 
                    f"<b>Binance {futures_manager.symbol} Futures Market Depth</b>",
                    f"<b>Spot Buy/Sell Ratio</b>", f"<b>Futures Buy/Sell Ratio</b>",
                    "<b>Spot Ask Book</b>", "<b>Spot Bid Book</b>", "<b>Futures Ask Book</b>", "<b>Futures Bid Book</b>"
                )
            )

            # --- PREPARE DATA ---
            spot_bids, spot_asks = spot_manager.get_filtered_orders(Config.CHART_CONFIG["display_order_count"])
            futures_bids, futures_asks = futures_manager.get_filtered_orders(Config.CHART_CONFIG["display_order_count"])
            
            all_spot_prices_set = {p for p, q in spot_bids} | {p for p, q in spot_asks} | {spot_data["mid_price"]}
            spot_y_axis_order = [f"${p:,.2f}" for p in sorted(list(all_spot_prices_set), reverse=True)]

            all_futures_prices_set = {p for p, q in futures_bids} | {p for p, q in futures_asks} | {futures_data["mid_price"]}
            futures_y_axis_order = [f"${p:,.2f}" for p in sorted(list(all_futures_prices_set), reverse=True)]
            
            # --- POPULATE GRID ---
            # *** MODIFICATION: Changed annotation call position ***
            self._add_depth_traces(fig, spot_bids, spot_asks, spot_data["mid_price"], "Spot", 1, 1, subplot_num=1)
            self._add_depth_traces(fig, futures_bids, futures_asks, futures_data["mid_price"], "Futures", 1, 3, subplot_num=2)
            
            self._add_ratio_chart(fig, spot_manager, "Spot", 2, 1)
            self._add_ratio_chart(fig, futures_manager, "Futures", 2, 3)
            # 註釋：將註解添加到 Ratio Chart 下方
            self._add_oi_funding_annotation(fig, oi_value, funding_rate, row=2, col=3, subplot_num=4)
            
            self._add_single_order_table(fig, spot_asks, "Spot", "asks", 3, 1)
            self._add_single_order_table(fig, spot_bids, "Spot", "bids", 3, 2)
            self._add_single_order_table(fig, futures_asks, "Futures", "asks", 3, 3)
            self._add_single_order_table(fig, futures_bids, "Futures", "bids", 3, 4)

            # --- UPDATE AXES & LAYOUT ---
            self._update_axes(fig, spot_y_axis_order, futures_y_axis_order)
            
            fig.update_layout(
                barmode='overlay', plot_bgcolor='#1e1e1e', paper_bgcolor='#1a1a1a',
                font=dict(color='#ffffff', size=12),
                height=Config.CHART_CONFIG.get("chart_height_final", 1600),
                width=Config.CHART_CONFIG["chart_width"], showlegend=True,
                legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1, font=dict(size=10)),
                title=dict(text=f"<b>Market Depth & Order Book Analysis - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} (UTC+8)</b>", font=dict(size=18, color='#ffffff'), x=0.5),
                margin=dict(l=40, r=40, t=100, b=40)
            )

            return fig

        except Exception as e:
            if Config.OUTPUT_OPTIONS["enable_console_output"]:
                print(f"Error creating chart: {e}")
            return None
    
    def _add_ratio_chart(self, fig, manager: OrderBookManager, market_type: str, row: int, col: int):
        # 註釋：此函式負責添加買賣比率圖
        ratios, ranges, colors = [], [], []
        market_colors = self.color_palettes.get(market_type, self.color_palettes["Spot"])

        for i, (lower, upper) in enumerate(Config.ANALYSIS_RANGES):
            ratio, _, _, _ = manager.calculate_depth_ratio_range(lower, upper) if i > 0 else manager.calculate_depth_ratio(upper)
            range_name = f"{lower}-{upper}%" if i > 0 else f"0-{upper}%"
            ratios.append(ratio if ratio is not None else 0)
            ranges.append(range_name)
            
            if ratio is None or ratio == 0: colors.append(self.color_palettes["Neutral"])
            elif ratio > 0: colors.append(market_colors['bids'])
            else: colors.append(market_colors['asks'])

        fig.add_trace(go.Bar(x=ranges, y=ratios, name=f"{market_type} Ratio", marker_color=colors, text=[f"{r:.3f}" for r in ratios], textposition='auto', textfont=dict(size=9, color='white'), hovertemplate=f"{market_type} Ratio<br>Range: %{{x}}<br>Ratio: %{{y:.3f}}<extra></extra>"), row=row, col=col)

    def _update_axes(self, fig, spot_y_order, futures_y_order):
        # 註釋：更新所有子圖的坐標軸
        fig.update_yaxes(type='category', categoryorder='array', categoryarray=spot_y_order, autorange='reversed', title_text="Price (USDT)", gridcolor='#3d3d3d', row=1, col=1)
        fig.update_xaxes(title_text="Quantity", gridcolor='#3d3d3d', zerolinecolor='#ffffff', row=1, col=1)
        fig.update_yaxes(type='category', categoryorder='array', categoryarray=futures_y_order, autorange='reversed', title_text="Price (USDT)", gridcolor='#3d3d3d', row=1, col=3)
        fig.update_xaxes(title_text="Quantity", gridcolor='#3d3d3d', zerolinecolor='#ffffff', row=1, col=3)
        fig.update_xaxes(title_text="Price Range", gridcolor='#3d3d3d', row=2, col=1)
        fig.update_yaxes(title_text="Buy/Sell Ratio", gridcolor='#3d3d3d', zerolinecolor='white', zerolinewidth=1, row=2, col=1)
        # *** MODIFICATION: Hide the x-axis title for the futures ratio chart ***
        fig.update_xaxes(title_text="", gridcolor='#3d3d3d', row=2, col=3)
        fig.update_yaxes(title_text="Buy/Sell Ratio", gridcolor='#3d3d3d', zerolinecolor='white', zerolinewidth=1, row=2, col=3)

    async def send_chart_to_discord(self, fig, symbol: str, webhook_urls: List[str]):
        # 註釋：發送圖表到 Discord
        if not fig or not webhook_urls: return
        try:
            timestamp = int(time.time())
            image_path = f"depth_chart_{symbol}_{timestamp}.{Config.CHART_CONFIG['format']}"
            fig.write_image(image_path, engine="kaleido", width=Config.CHART_CONFIG["chart_width"], height=Config.CHART_CONFIG.get("chart_height_final", 1600), scale=2, format=Config.CHART_CONFIG["format"])
            await asyncio.sleep(1)

            if not os.path.exists(image_path):
                print(f"Chart file generation failed: {image_path}")
                return
            content = f"## {symbol} Market Depth & Order Book Analysis - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} (UTC+8)"
            for i, url in enumerate(webhook_urls):
                if i > 0: await asyncio.sleep(Config.CHART_CONFIG.get("webhook_delay", 2))
                async with aiohttp.ClientSession() as session:
                    form = aiohttp.FormData()
                    form.add_field('content', content)
                    with open(image_path, 'rb') as f:
                        form.add_field('file', f.read(), filename=os.path.basename(image_path), content_type=f'image/{Config.CHART_CONFIG["format"]}')
                    async with session.post(url, data=form) as response:
                        if response.status in [200, 204]: print(f"Chart successfully sent to Discord webhook #{i+1}")
                        else: print(f"Failed to send chart to Discord webhook #{i+1}, status: {response.status}, message: {await response.text()}")
        except Exception as e: print(f"Error sending chart: {e}")
        finally:
            if not Config.OUTPUT_OPTIONS["save_charts_locally"] and os.path.exists(image_path):
                try: os.remove(image_path)
                except Exception as e: print(f"Failed to delete temp file: {e}")
            elif Config.OUTPUT_OPTIONS["save_charts_locally"]: print(f"Chart saved to: {image_path}")

    def should_send_now(self, symbol: str) -> bool:
        # 註釋：檢查是否到達發送時間
        current_time = time.time()
        interval = Config.SEND_INTERVALS["chart_output"]
        if current_time - self.last_send_time.get(symbol, 0) >= interval:
            self.last_send_time[symbol] = current_time
            return True
        return False

    async def process_and_send(self, spot_manager: OrderBookManager, futures_manager: OrderBookManager):
        # 註釋：處理數據並發送圖表的入口函式
        if not Config.is_output_enabled("chart_output") or not self.should_send_now(spot_manager.symbol):
            return
        try:
            fig = self.create_depth_chart(spot_manager, futures_manager)
            if fig and (webhooks := Config.get_webhooks(spot_manager.symbol, "chart_output")):
                self.send_queue.put((fig, spot_manager.symbol, webhooks))
                if Config.OUTPUT_OPTIONS["enable_console_output"]:
                    print(f"Added {spot_manager.symbol} chart to send queue")
        except Exception as e:
            if Config.OUTPUT_OPTIONS["enable_console_output"]:
                print(f"Error creating chart: {e}")

    def stop(self):
        """Stops the chart output manager."""
        self.send_queue.put(None)
        if Config.OUTPUT_OPTIONS["enable_console_output"]:
            print("Chart output manager stopped")

chart_output_manager = ChartOutputManager()
