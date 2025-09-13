# -*- coding: utf-8 -*-
"""
快速修复预热卡住问题
"""

from config import Config

def quick_fix_options():
    """显示快速修复选项"""
    print("=" * 60)
    print("🚨 系统预热卡住 - 快速解决方案")
    print("=" * 60)
    
    print("根据您的情况，有以下几种解决方案：")
    print()
    
    print("1. 🚀 立即启动（推荐）")
    print("   - 跳过预热检查，立即开始发送")
    print("   - 适合：想要快速开始监控")
    print()
    
    print("2. ⚡ 快速模式")
    print("   - 降低预热要求到15秒")
    print("   - 适合：希望有数据检查但等待时间短")
    print()
    
    print("3. 🔧 调整当前预热参数")
    print("   - 手动降低预热要求")
    print("   - 适合：想要自定义设置")
    print()
    
    print("4. 🔄 重启程序")
    print("   - 可能是WebSocket连接问题")
    print("   - 适合：网络连接不稳定")

def apply_instant_start():
    """应用立即启动模式"""
    print("\n🚀 正在应用立即启动模式...")
    Config.DATA_WARMUP_CONFIG['启用预热检查'] = False
    print("✅ 已禁用预热检查")
    print("💡 系统将在初始化完成后立即开始发送")
    return True

def apply_fast_mode():
    """应用快速模式"""
    print("\n⚡ 正在应用快速模式...")
    success = Config.set_warmup_preset('快速模式')
    if success:
        print("✅ 已切换到快速模式")
        print(f"💡 新的预热配置: {Config.DATA_WARMUP_CONFIG}")
        return True
    else:
        print("❌ 快速模式应用失败")
        return False

def apply_custom_settings():
    """应用自定义设置"""
    print("\n🔧 正在应用宽松的预热设置...")
    Config.DATA_WARMUP_CONFIG.update({
        '启动等待时间': 15,
        '最小更新次数': 3,
        '最小订单数量': 1,
        '启用预热检查': True
    })
    print("✅ 已应用宽松设置")
    print("💡 新的要求: 15秒 + 3次更新 + 1条订单")
    return True

def interactive_fix():
    """交互式修复"""
    quick_fix_options()
    
    try:
        choice = input("\n请选择解决方案 (1-4): ").strip()
        
        if choice == "1":
            return apply_instant_start()
        elif choice == "2":
            return apply_fast_mode()
        elif choice == "3":
            return apply_custom_settings()
        elif choice == "4":
            print("\n🔄 请手动重启主程序")
            print("   Ctrl+C 停止当前程序，然后重新运行 python main.py")
            return False
        else:
            print("❌ 无效选择")
            return False
            
    except KeyboardInterrupt:
        print("\n操作取消")
        return False

# 非交互式快速修复（推荐给卡住的用户）
def emergency_fix():
    """紧急修复 - 直接应用最宽松的设置"""
    print("🚨 紧急修复模式 - 应用最宽松设置")
    print()
    
    print("正在应用以下设置:")
    print("- 启用预热检查: False (立即启动)")
    print("- 备用设置: 等待5秒 + 1次更新 + 1条订单")
    
    # 主要方案：直接禁用预热
    Config.DATA_WARMUP_CONFIG['启用预热检查'] = False
    
    # 备用方案：设置极宽松的要求
    Config.DATA_WARMUP_CONFIG.update({
        '启动等待时间': 5,
        '最小更新次数': 1,
        '最小订单数量': 1
    })
    
    print("✅ 紧急修复已应用")
    print("💡 系统现在应该可以立即启动或很快完成预热")

if __name__ == "__main__":
    # 如果用户直接运行这个脚本，说明遇到了问题
    print("检测到您可能遇到了预热卡住问题")
    print("正在应用紧急修复...")
    emergency_fix()
    print("\n现在请重新运行主程序: python main.py") 