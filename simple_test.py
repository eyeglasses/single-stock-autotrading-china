#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
简单测试脚本
"""

try:
    print("开始测试...")
    
    # 测试数据获取
    from data_fetcher import get_market_data
    print("✓ data_fetcher导入成功")
    
    # 测试获取数据
    df = get_market_data('000001.SZ', period='1d', count=10)
    if df is not None and not df.empty:
        print(f"✓ 获取数据成功，数据量: {len(df)}")
        print(f"✓ 列名: {list(df.columns)}")
        
        # 检查是否有close_price列
        if 'close_price' in df.columns:
            print("✓ close_price列存在")
            print(f"✓ 最新价格: {df.iloc[-1]['close_price']:.2f}")
        else:
            print("✗ close_price列不存在")
            
    else:
        print("✗ 获取数据失败")
        
    print("\n测试完成")
    
except Exception as e:
    print(f"测试出错: {e}")
    import traceback
    traceback.print_exc()