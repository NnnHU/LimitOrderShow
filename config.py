# -*- coding: utf-8 -*-
"""
Unified Configuration File
Manages all configuration parameters including trading pairs, thresholds, Discord webhooks, output options, etc.
"""

from typing import Dict, List, Union

class Config:
    """Configuration class managing all configuration parameters"""
    
    # Monitored trading pairs
    SYMBOLS = ["BTCUSDT","ETHUSDT", "SOLUSDT"]
    #,"ETHUSDT", "SOLUSDT"
    
    # Minimum quantity threshold configuration - separate settings for spot and futures markets
    MIN_QUANTITIES = {
        "BTC": {
            "spot": 50.0,      # BTC spot market minimum quantity
            "futures": 100.0    # BTC futures market minimum quantity
        },
        "ETH": {
            "spot": 200.0,     # ETH spot market minimum quantity
            "futures": 400.0   # ETH futures market minimum quantity
        },
        "SOL": {
            "spot": 3000.0,    # SOL spot market minimum quantity
            "futures": 2500.0  # SOL futures market minimum quantity
        },
        "BNB": {
            "spot": 1000.0,    # BNB spot market minimum quantity
            "futures": 800.0   # BNB futures market minimum quantity
        },
        "DEFAULT": {
            "spot": 1000.0,    # Default spot market minimum quantity
            "futures": 800.0   # Default futures market minimum quantity
        }
    }
    
    # Discord Webhook configuration
    DISCORD_WEBHOOKS = {
        # BTC webhook configuration
        #"https://discord.com/api/webhooks/1380247581808132187/wt_n_w1xsWz0EW-V0S4IUT9ngg_uTCC2-C72n1Am2Nja_iwKP3FW5b8HXpIt2yPMAPD3" 测试用地址
        #"https://discord.com/api/webhooks/1350837714601377792/Gdmxej07wvWgJXxQ3qSqV8o-7Oaw5xc1kHGDw1K3sgXfrVuk6PsiUHymvVn-fU4GeMsd",
        #"https://discord.com/api/webhooks/1379448500177211543/7yJMdGXvGsYhR2eD_n8MbTDlZ8Nw34WcKVi2t_V6sdJ3All-ICwZARXA0oaw7ZzOKIGh"
        "BTC": {
            "text_output": [
                "https://discord.com/api/webhooks/1350837714601377792/Gdmxej07wvWgJXxQ3qSqV8o-7Oaw5xc1kHGDw1K3sgXfrVuk6PsiUHymvVn-fU4GeMsd",
                "https://discord.com/api/webhooks/1379657654447636651/EquA1jpi8kkPvW3piihBoKFtlvccJOtjAkYSDQBijwsE8RIkTSlPBBgvKZurxUVw96D8"
            ],
            "chart_output": [
                "https://discord.com/api/webhooks/1350837714601377792/Gdmxej07wvWgJXxQ3qSqV8o-7Oaw5xc1kHGDw1K3sgXfrVuk6PsiUHymvVn-fU4GeMsd",
                "https://discord.com/api/webhooks/1379448500177211543/7yJMdGXvGsYhR2eD_n8MbTDlZ8Nw34WcKVi2t_V6sdJ3All-ICwZARXA0oaw7ZzOKIGh"
            ]
        },
        # ETH webhook configuration  
        "ETH": {
            "text_output": [
                "https://discord.com/api/webhooks/1379314747929001985/r0LJJsNE_VC2eKJ5339XaM7UJ1h9ivllXpzTcHVygPyl0PMrP8aHoScrYmcC51Bi8jTQ"
            ],
            "chart_output": [
                "https://discord.com/api/webhooks/1350837714601377792/Gdmxej07wvWgJXxQ3qSqV8o-7Oaw5xc1kHGDw1K3sgXfrVuk6PsiUHymvVn-fU4GeMsd",
                "https://discord.com/api/webhooks/1379737983586140311/8MR61-_YJdNK79Z5sCtVFLJq1rxpOnzNIvrMu4XmGnW-MibkBukmlL_aF3Fk-hXZjz5K"
            ]
        },
        # SOL webhook configuration  
        "SOL": {
            "text_output": [
                "https://discord.com/api/webhooks/1379314747929001985/r0LJJsNE_VC2eKJ5339XaM7UJ1h9ivllXpzTcHVygPyl0PMrP8aHoScrYmcC51Bi8jTQ"
            ],
            "chart_output": [
                "https://discord.com/api/webhooks/1379738264654844025/9o2mOLQBp1VK8am1Lcl8inA9_PChXQuUdHnly3782GAAjbeoxRmKvKQiJvj9ehXC2zeW"
            ]
        },
        # Default webhook configuration (for currencies not specifically configured)
        "DEFAULT": {
            "text_output": [
                "https://discord.com/api/webhooks/1350837714601377792/Gdmxej07wvWgJXxQ3qSqV8o-7Oaw5xc1kHGDw1K3sgXfrVuk6PsiUHymvVn-fU4GeMsd"
            ],
            "chart_output": [
                "https://discord.com/api/webhooks/1350837714601377792/Gdmxej07wvWgJXxQ3qSqV8o-7Oaw5xc1kHGDw1K3sgXfrVuk6PsiUHymvVn-fU4GeMsd"
            ]
        }
    }
    
    # Send interval configuration (seconds)
    SEND_INTERVALS = {
        "text_output": 300,  # Text analysis sent every 5 minutes
        "chart_output": 600,  # Charts sent every 5 minutes
    }
    
    # Data warmup configuration
    DATA_WARMUP_CONFIG = {
        "startup_wait_time": 30,         # Wait 30 seconds after system startup (reduced from 60 seconds)
        "min_update_count": 10,         # At least 10 updates per currency per market (reduced from 20)
        "min_order_count": 2,          # At least 3 qualifying orders (reduced from 5)
        "enable_warmup_check": True,      # Temporarily disable warmup check to solve stuck issue
    }
    
    # Preset warmup modes (for quick switching)
    WARMUP_PRESETS = {
        "immediate_start": {
            "startup_wait_time": 0,
            "min_update_count": 0,
            "min_order_count": 0,
            "enable_warmup_check": False,
        },
        "fast_mode": {
            "startup_wait_time": 15,
            "min_update_count": 5,
            "min_order_count": 2,
            "enable_warmup_check": True,
        },
        "standard_mode": {
            "startup_wait_time": 30,
            "min_update_count": 10,
            "min_order_count": 3,
            "enable_warmup_check": True,
        },
        "stable_mode": {
            "startup_wait_time": 60,
            "min_update_count": 20,
            "min_order_count": 5,
            "enable_warmup_check": True,
        }
    }
    
    # Output options configuration
    OUTPUT_OPTIONS = {
        "enable_text_output": False,   # Whether to enable text analysis output
        "enable_chart_output": True,   # Whether to enable chart output
        "enable_console_output": True, # Whether to display information in console
        "save_charts_locally": False, # Whether to save chart files locally
    }
    
    # Chart configuration
    CHART_CONFIG = {
        "display_order_count": 10,      # Number of orders displayed on each side
        "chart_width": 1200,       # Chart width
        "chart_height": 800,        # Chart height
        "theme": "dark",         # Chart theme
        "format": "png",          # Chart format
        "send_delay": 3,          # Discord send interval delay (seconds) to avoid message loss
        "webhook_delay": 2,       # Delay between multiple webhooks of same currency (seconds)
    }
    
    # Analysis range configuration
    ANALYSIS_RANGES = [
        (0, 1),         # 0-1% price range
        (1, 2.5),       # 1-2.5% price range  
        (2.5, 5),       # 2.5-5% price range
        (5, 10),        # 5-10% price range
    ]
    
    @classmethod
    def get_min_quantity(cls, symbol: str, market_type: str = "spot") -> float:
        """
        Get corresponding minimum quantity threshold based on trading pair and market type
        
        Args:
            symbol: Trading pair symbol (e.g., 'BTCUSDT')
            market_type: Market type, either 'spot' or 'futures' (default: 'spot')
            
        Returns:
            float: Minimum quantity threshold for the specified symbol and market type
        """
        base_currency = symbol.replace("USDT", "").upper()
        currency_config = cls.MIN_QUANTITIES.get(base_currency, cls.MIN_QUANTITIES["DEFAULT"])
        
        # Ensure market_type is valid
        if market_type not in ["spot", "futures"]:
            market_type = "spot"
            
        return currency_config.get(market_type, currency_config["spot"])
    
    @classmethod
    def get_webhooks(cls, symbol: str, output_type: str) -> List[str]:
        """Get webhook URLs for specified currency and output type"""
        base_currency = symbol.replace("USDT", "").upper()
        webhooks = cls.DISCORD_WEBHOOKS.get(base_currency, cls.DISCORD_WEBHOOKS["DEFAULT"])
        return webhooks.get(output_type, [])
    
    @classmethod
    def is_output_enabled(cls, output_type: str) -> bool:
        """Check if specified output type is enabled"""
        if output_type == "text_output":
            return cls.OUTPUT_OPTIONS["enable_text_output"]
        elif output_type == "chart_output":
            return cls.OUTPUT_OPTIONS["enable_chart_output"]
        return False 
    
    @classmethod
    def set_warmup_preset(cls, preset_name: str):
        """Set warmup preset mode"""
        if preset_name in cls.WARMUP_PRESETS:
            cls.DATA_WARMUP_CONFIG.update(cls.WARMUP_PRESETS[preset_name])
            return True
        return False 