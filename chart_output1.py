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

class ChartOutputManager:
    """图表输出管理器"""
    
    def __init__(self):
        self.last_send_time = 0

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

            # 创建2行布局：第1行2列，第2行4列
            fig = make_subplots(
                rows=2, cols=4,
                subplot_titles=(
                    f"{spot_manager.symbol} 现货市场深度 (前{Config.CHART_CONFIG['显示订单数量']}档)\n当前价格: ${spot_price:,.2f}",
                    f"{futures_manager.symbol} 合约市场深度 (前{Config.CHART_CONFIG['显示订单数量']}档)\n当前价格: ${futures_price:,.2f}",
                    None,  # 第1行第3列空
                    None,  # 第1行第4列空
                    "现货订单详情",
                    "现货买卖比率",
                    "合约订单详情", 
                    "合约买卖比率"
                ),
                specs=[
                    [{"colspan": 2}, None, {"colspan": 2}, None],  # 第1行：深度图各占2列
                    [{}, {}, {}, {}]  # 第2行：4个单独的区域
                ],
                row_heights=[0.6, 0.4],  # 上方60%，下方40%
                vertical_spacing=0.12,
                horizontal_spacing=0.08
            )

            # 第1行：深度图表
            self._add_depth_traces(fig, spot_bids, spot_asks, spot_price, "现货", 1, 1)
            self._add_depth_traces(fig, futures_bids, futures_asks, futures_price, "合约", 1, 3)
            
            # 第2行：4个区域
            self._add_order_lists(fig, spot_bids, spot_asks, "现货", 2, 1)  # 现货订单详情
            self._add_ratio_chart(fig, spot_manager, "现货", 2, 2)           # 现货买卖比率
            self._add_order_lists(fig, futures_bids, futures_asks, "合约", 2, 3)  # 合约订单详情
            self._add_ratio_chart(fig, futures_manager, "合约", 2, 4)        # 合约买卖比率

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

    def _add_order_lists(self, fig, bids: List[Tuple], asks: List[Tuple], market_type: str, row: int, col: int):
        """添加订单列表文本"""
        # 创建一个空的散点图作为载体
        fig.add_trace(
            go.Scatter(
                x=[0],
                y=[0],
                mode='markers',
                marker=dict(size=0, opacity=0),
                showlegend=False,
                hoverinfo='skip'
            ),
            row=row, col=col
        )

        # 构建订单列表文本 - 使用纯文本格式
        text_lines = []
        
        # 添加买单标题和数据
        text_lines.append("买单 (Bids):")
        if bids:
            for i, (price, qty) in enumerate(bids[:5]):  # 只显示前5条
                text_lines.append(f"${price:,.0f} - {qty:.1f}")
        else:
            text_lines.append("暂无符合条件的买单")
        
        text_lines.append("")  # 空行分隔
        
        # 添加卖单标题和数据
        text_lines.append("卖单 (Asks):")
        if asks:
            for i, (price, qty) in enumerate(asks[:5]):  # 只显示前5条
                text_lines.append(f"${price:,.0f} - {qty:.1f}")
        else:
            text_lines.append("暂无符合条件的卖单")

        # 获取当前子图的domain信息，直接使用paper坐标
        if row == 2 and col == 1:  # 现货订单详情
            # 第2行第1列，使用paper坐标
            xref, yref = "paper", "paper"
            x, y = 0.125, 0.2  # 第1列的中心位置
        elif row == 2 and col == 3:  # 合约订单详情
            # 第2行第3列，使用paper坐标
            xref, yref = "paper", "paper"
            x, y = 0.75, 0.2  # 调整第3列的中心位置（更靠右）
        else:
            return  # 只处理订单详情区域

        # 构建最终文本，使用正确的HTML格式
        final_text = "<br>".join(text_lines)
        
        # 添加文本注释
        fig.add_annotation(
            text=final_text,
            xref=xref,
            yref=yref,
            x=x,
            y=y,
            xanchor="center",
            yanchor="middle",
            showarrow=False,
            font=dict(size=9, color='#ffffff', family="Courier New"),
            bgcolor='rgba(45,45,45,0.9)',
            bordercolor='#3d3d3d',
            borderwidth=1,
            align="left"
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
        for col in [1, 3]:  # 现货在第1列，合约在第3列
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

        # 第2行：订单列表和比率图的坐标轴
        for col in [1, 3]:  # 订单列表（第1、3列） - 隐藏坐标轴
            fig.update_xaxes(
                showgrid=False,
                showticklabels=False,
                zeroline=False,
                range=[0, 1],
                row=2, col=col
            )
            fig.update_yaxes(
                showgrid=False,
                showticklabels=False,
                zeroline=False,
                range=[0, 1],
                row=2, col=col
            )
            
        for col in [2, 4]:  # 比率图表（第2、4列）
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
        """发送图表到Discord"""
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

            # 发送到Discord
            timestamp_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            content = f"# {symbol} 市场深度图表分析 - {timestamp_str}"

            for url in webhook_urls:
                try:
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
                                    print(f"图表已成功发送到Discord")
                            else:
                                if Config.OUTPUT_OPTIONS["启用控制台输出"]:
                                    print(f"发送图表到Discord失败，状态码: {response.status}")
                                    
                except Exception as e:
                    if Config.OUTPUT_OPTIONS["启用控制台输出"]:
                        print(f"发送图表到Discord时出错: {e}")

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

    def should_send_now(self) -> bool:
        """检查是否应该发送图表"""
        current_time = time.time()
        interval = Config.SEND_INTERVALS["图表输出"]
        
        if current_time - self.last_send_time >= interval:
            self.last_send_time = current_time
            return True
        return False

    async def process_and_send(self, spot_manager: OrderBookManager, futures_manager: OrderBookManager):
        """处理并发送图表"""
        if not Config.is_output_enabled("图表输出"):
            return
            
        if not self.should_send_now():
            return

        try:
            symbol = spot_manager.symbol
            
            # 创建图表
            fig = self.create_depth_chart(spot_manager, futures_manager)
            
            if fig:
                # 获取webhook URLs
                webhooks = Config.get_webhooks(symbol, "图表输出")
                
                if webhooks:
                    await self.send_chart_to_discord(fig, symbol, webhooks)
                
        except Exception as e:
            if Config.OUTPUT_OPTIONS["启用控制台输出"]:
                print(f"处理和发送图表时出错: {e}")

# 全局图表输出管理器实例
chart_output_manager = ChartOutputManager() 