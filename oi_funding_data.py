# -*- coding: utf-8 -*-
"""
OI and Funding Rate Data Module
负责获取币安合约的持仓量(OI)数据和资金费率数据
"""

import requests
import aiohttp
import asyncio
import time
from typing import Dict, Optional, Tuple
from config import Config

class OIFundingDataManager:
    """OI和资金费率数据管理器"""
    
    def __init__(self):
        self.cache = {}
        self.cache_timeout = 30  # 缓存30秒
        
    async def get_open_interest(self, symbol: str) -> Optional[float]:
        """
        获取指定合约的持仓量(OI)数据
        
        Args:
            symbol: 交易对符号 (e.g., 'BTCUSDT')
            
        Returns:
            float: 持仓量数值，获取失败返回None
        """
        cache_key = f"oi_{symbol}"
        current_time = time.time()
        
        # 检查缓存
        if cache_key in self.cache:
            cached_data, timestamp = self.cache[cache_key]
            if current_time - timestamp < self.cache_timeout:
                return cached_data
        
        try:
            url = "https://fapi.binance.com/fapi/v1/openInterest"
            params = {"symbol": symbol.upper()}
            
            async with aiohttp.ClientSession() as session:
                async with session.get(url, params=params) as response:
                    if response.status == 200:
                        data = await response.json()
                        oi_value = float(data.get("openInterest", 0))
                        
                        # 更新缓存
                        self.cache[cache_key] = (oi_value, current_time)
                        
                        if Config.OUTPUT_OPTIONS["enable_console_output"]:
                            print(f"获取{symbol}持仓量: {oi_value:,.2f}")
                            
                        return oi_value
                    else:
                        if Config.OUTPUT_OPTIONS["enable_console_output"]:
                            print(f"获取{symbol}持仓量失败，状态码: {response.status}")
                        return None
                        
        except Exception as e:
            if Config.OUTPUT_OPTIONS["enable_console_output"]:
                print(f"获取{symbol}持仓量时出错: {e}")
            return None
    
    async def get_funding_rate(self, symbol: str) -> Optional[float]:
        """
        获取指定合约的资金费率数据
        
        Args:
            symbol: 交易对符号 (e.g., 'BTCUSDT')
            
        Returns:
            float: 资金费率数值(百分比)，获取失败返回None
        """
        cache_key = f"funding_{symbol}"
        current_time = time.time()
        
        # 检查缓存
        if cache_key in self.cache:
            cached_data, timestamp = self.cache[cache_key]
            if current_time - timestamp < self.cache_timeout:
                return cached_data
        
        try:
            url = "https://fapi.binance.com/fapi/v1/premiumIndex"
            params = {"symbol": symbol.upper()}
            
            async with aiohttp.ClientSession() as session:
                async with session.get(url, params=params) as response:
                    if response.status == 200:
                        data = await response.json()
                        funding_rate = float(data.get("lastFundingRate", 0)) * 100  # 转换为百分比
                        
                        # 更新缓存
                        self.cache[cache_key] = (funding_rate, current_time)
                        
                        if Config.OUTPUT_OPTIONS["enable_console_output"]:
                            print(f"获取{symbol}资金费率: {funding_rate:.4f}%")
                            
                        return funding_rate
                    else:
                        if Config.OUTPUT_OPTIONS["enable_console_output"]:
                            print(f"获取{symbol}资金费率失败，状态码: {response.status}")
                        return None
                        
        except Exception as e:
            if Config.OUTPUT_OPTIONS["enable_console_output"]:
                print(f"获取{symbol}资金费率时出错: {e}")
            return None
    
    async def get_oi_and_funding(self, symbol: str) -> Tuple[Optional[float], Optional[float]]:
        """
        同时获取持仓量和资金费率数据
        
        Args:
            symbol: 交易对符号 (e.g., 'BTCUSDT')
            
        Returns:
            Tuple[Optional[float], Optional[float]]: (持仓量, 资金费率百分比)
        """
        try:
            # 并发获取两个数据
            oi_task = self.get_open_interest(symbol)
            funding_task = self.get_funding_rate(symbol)
            
            oi_value, funding_rate = await asyncio.gather(oi_task, funding_task)
            
            return oi_value, funding_rate
            
        except Exception as e:
            if Config.OUTPUT_OPTIONS["enable_console_output"]:
                print(f"同时获取{symbol}的OI和资金费率时出错: {e}")
            return None, None
    
    def get_oi_and_funding_sync(self, symbol: str) -> Tuple[Optional[float], Optional[float]]:
        """
        同步方式获取持仓量和资金费率数据（用于非异步环境）
        
        Args:
            symbol: 交易对符号 (e.g., 'BTCUSDT')
            
        Returns:
            Tuple[Optional[float], Optional[float]]: (持仓量, 资金费率百分比)
        """
        try:
            # 创建新的事件循环来运行异步方法
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                return loop.run_until_complete(self.get_oi_and_funding(symbol))
            finally:
                loop.close()
        except Exception as e:
            if Config.OUTPUT_OPTIONS["enable_console_output"]:
                print(f"同步获取{symbol}的OI和资金费率时出错: {e}")
            return None, None
    
    def clear_cache(self):
        """清空缓存"""
        self.cache.clear() 