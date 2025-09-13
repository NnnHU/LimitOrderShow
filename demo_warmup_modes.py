# -*- coding: utf-8 -*-
"""
预热模式演示
展示不同预热模式的配置和预期等待时间
"""

from config import Config

def demo_warmup_modes():
    """演示不同的预热模式"""
    print("=" * 70)
    print("🚀 币安深度监控系统 - 预热模式选择")
    print("=" * 70)
    
    print("📋 可用的预热模式:")
    print()
    
    for mode_name, settings in Config.WARMUP_PRESETS.items():
        print(f"🔸 {mode_name}:")
        print(f"   ⏰ 等待时间: {settings['启动等待时间']}秒")
        print(f"   🔄 更新次数: {settings['最小更新次数']}次")
        print(f"   📊 订单数量: {settings['最小订单数量']}条")
        print(f"   ✅ 启用检查: {'是' if settings['启用预热检查'] else '否'}")
        
        # 计算预期等待时间
        if not settings['启用预热检查']:
            wait_time = "立即可用 (约3-5秒初始化)"
        else:
            min_time = settings['启动等待时间']
            typical_time = min_time + 15
            wait_time = f"{min_time}-{typical_time}秒"
        
        print(f"   ⏳ 预期等待: {wait_time}")
        print()
    
    print("=" * 70)
    print("💡 使用说明:")
    print()
    print("方法1: 直接修改 config.py")
    print("   在 DATA_WARMUP_CONFIG 中手动设置参数")
    print()
    print("方法2: 使用预设模式")
    print("   在主程序启动前调用:")
    print("   Config.set_warmup_preset('快速模式')")
    print()
    print("方法3: 在主程序中临时调整")
    print("   Config.DATA_WARMUP_CONFIG['启用预热检查'] = False")
    print()
    
    print("=" * 70)
    print("🎯 推荐使用场景:")
    print()
    print("🚀 立即启动 - 测试和开发阶段")
    print("   优势: 无等待，立即发送")
    print("   风险: 可能发送空数据图表")
    print()
    print("⚡ 快速模式 - 日常监控")
    print("   优势: 等待时间短，数据基本稳定")
    print("   适用: 网络良好的生产环境")
    print()
    print("📊 标准模式 - 当前默认设置")
    print("   优势: 平衡了等待时间和数据质量")
    print("   适用: 大多数使用场景")
    print()
    print("🛡️ 稳定模式 - 高可靠性要求")
    print("   优势: 数据最稳定，极少空数据")
    print("   适用: 关键业务监控")
    print()

def interactive_mode_selection():
    """交互式模式选择"""
    print("=" * 50)
    print("🎛️ 交互式预热模式设置")
    print("=" * 50)
    
    modes = list(Config.WARMUP_PRESETS.keys())
    
    print("请选择预热模式:")
    for i, mode in enumerate(modes, 1):
        settings = Config.WARMUP_PRESETS[mode]
        if not settings['启用预热检查']:
            wait_info = "立即启动"
        else:
            wait_info = f"等待{settings['启动等待时间']}秒+"
        print(f"  {i}. {mode} ({wait_info})")
    
    try:
        choice = input(f"\n请输入选择 (1-{len(modes)}, 或按回车使用当前设置): ").strip()
        
        if choice == "":
            print("使用当前设置")
        elif choice.isdigit() and 1 <= int(choice) <= len(modes):
            selected_mode = modes[int(choice) - 1]
            success = Config.set_warmup_preset(selected_mode)
            
            if success:
                print(f"✅ 已切换到: {selected_mode}")
                print(f"当前配置: {Config.DATA_WARMUP_CONFIG}")
            else:
                print("❌ 设置失败")
        else:
            print("❌ 无效选择，使用当前设置")
            
    except KeyboardInterrupt:
        print("\n操作取消")

if __name__ == "__main__":
    demo_warmup_modes()
    print()
    interactive_mode_selection() 