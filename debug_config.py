#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
调试配置问题
"""

print("=== 调试配置问题 ===")

try:
    print("1. 导入config模块...")
    from config import TRADING_CONFIG, RISK_CONFIG
    print(f"✓ 配置导入成功")
    print(f"TRADING_CONFIG: {TRADING_CONFIG}")
    
    print("\n2. 测试关键配置项...")
    position_ratio = TRADING_CONFIG['position_ratio']
    max_single_position = TRADING_CONFIG['max_single_position']
    print(f"✓ position_ratio = {position_ratio}")
    print(f"✓ max_single_position = {max_single_position}")
    
    print("\n3. 模拟backtest.py中的逻辑...")
    # 模拟BacktestEngine.__init__
    trading_config = TRADING_CONFIG
    risk_config = RISK_CONFIG
    print(f"✓ 配置赋值成功")
    
    # 模拟_execute_buy中的逻辑
    base_ratio = trading_config['position_ratio']
    signal_strength = 0.8
    adjusted_ratio = base_ratio * signal_strength
    max_ratio = trading_config['max_single_position']
    position_ratio = min(adjusted_ratio, max_ratio)
    print(f"✓ 仓位计算成功: position_ratio = {position_ratio}")
    
    print("\n=== 所有测试通过 ===")
    
except Exception as e:
    print(f"✗ 错误: {e}")
    import traceback
    traceback.print_exc()