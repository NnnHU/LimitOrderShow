# -*- coding: utf-8 -*-
"""
快速预热测试
展示实际的数据预热等待时间和过程
"""

import time
from config import Config
from data_manager import data_manager

def test_quick_warmup():
    """快速预热测试"""
    print("=" * 60)
    print("📊 数据预热机制说明")
    print("=" * 60)
    
    print("当前预热配置:")
    print(f"  ⏰ 启动等待时间: {Config.DATA_WARMUP_CONFIG['启动等待时间']}秒")
    print(f"  🔄 最小更新次数: {Config.DATA_WARMUP_CONFIG['最小更新次数']}次/数据源")
    print(f"  📈 最小订单数量: {Config.DATA_WARMUP_CONFIG['最小订单数量']}条/边")
    print(f"  🎯 监控币种: {Config.SYMBOLS} ({len(Config.SYMBOLS)}个)")
    print(f"  📡 数据源总数: {len(Config.SYMBOLS) * 2} (每币种2个：现货+合约)")
    
    # 计算预期等待时间
    min_wait_time = Config.DATA_WARMUP_CONFIG['启动等待时间']
    
    print(f"\n⏳ 预热完成条件 (所有数据源都必须满足):")
    print(f"  1. 至少等待 {min_wait_time} 秒")
    print(f"  2. WebSocket至少收到 {Config.DATA_WARMUP_CONFIG['最小更新次数']} 次更新")
    print(f"  3. 符合阈值的订单至少 {Config.DATA_WARMUP_CONFIG['最小订单数量']} 条")
    
    print(f"\n💡 实际使用中的等待时间:")
    print(f"  - 最短等待: {min_wait_time} 秒 (如果WebSocket数据充足)")
    print(f"  - 典型等待: {min_wait_time + 10}-{min_wait_time + 30} 秒 (正常网络情况)")
    print(f"  - 最长等待: {min_wait_time + 60} 秒 (网络较慢或数据稀少)")
    
    print(f"\n🎛️ 如需调整预热时间，可修改 config.py 中的 DATA_WARMUP_CONFIG")
    print(f"🚫 如需立即启动（跳过预热），可设置 '启用预热检查': False")
    
    # 测试禁用预热的情况
    print(f"\n" + "=" * 60)
    print("测试禁用预热检查（立即启动模式）")
    print("=" * 60)
    
    # 临时禁用预热
    original_setting = Config.DATA_WARMUP_CONFIG["启用预热检查"]
    Config.DATA_WARMUP_CONFIG["启用预热检查"] = False
    
    start_time = time.time()
    data_manager.get_initial_snapshots()
    is_ready = data_manager.is_system_ready_for_output()
    elapsed = time.time() - start_time
    
    print(f"初始化用时: {elapsed:.2f}秒")
    print(f"系统立即就绪: {'✅ 是' if is_ready else '❌ 否'}")
    
    if is_ready:
        print("👍 禁用预热检查时，系统在完成初始化后立即可用")
    
    # 恢复设置
    Config.DATA_WARMUP_CONFIG["启用预热检查"] = original_setting
    
    print(f"\n" + "=" * 60)
    print("📝 使用建议")
    print("=" * 60)
    print("1. 🚀 快速测试: 禁用预热检查，立即发送")
    print("2. 📊 生产环境: 启用预热检查，确保数据质量")
    print("3. ⚡ 自定义配置: 根据网络状况调整预热参数")
    print("4. 🔍 实时监控: 观察控制台的预热完成提示")

if __name__ == "__main__":
    test_quick_warmup() 