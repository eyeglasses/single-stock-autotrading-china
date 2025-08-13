#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sys
sys.path.append('.')

from stock_filter import StockFilter
import xtquant.xtdata as xtdata

# 连接数据源
try:
    xtdata.connect()
except AttributeError:
    # 如果connect方法不存在，尝试其他连接方式或跳过
    pass

# 初始化筛选器
filter_obj = StockFilter()

# 加载A股数据
print("正在加载A股数据...")
filter_obj.load_from_xtdata(['A股'])
print(f"加载了 {len(filter_obj.data)} 只股票")

# 测试组合筛选：MA5 >= 当前价格 AND 当前价格 <= 布林带下轨
print("\n=== 测试组合筛选 ===")
print("条件1: 当前价格 >= MA5")
print("条件2: 当前价格 <= 布林带下轨")

result = filter_obj.combined_filter(
    ma_params={'ma_days': 5, 'condition': '>='},
    bollinger_params={'band': 'lower', 'condition': '<=', 'window': 20}
)

print(f"\n符合组合条件的股票数量: {len(result)}")

if len(result) > 0:
    print("\n前5只符合条件的股票:")
    for i, (index, row) in enumerate(result.head(5).iterrows()):
        stock_code = row['code']
        current_price = row['price']
        
        # 计算MA5
        ma5 = filter_obj.calculate_ma(stock_code, 5)
        
        # 计算布林带
        bollinger_bands = filter_obj.calculate_bollinger_bands(stock_code, 20)
        
        if ma5 and bollinger_bands:
            upper_band, middle_band, lower_band = bollinger_bands
            print(f"  {i+1}. {stock_code} ({row['name']})")
            print(f"     当前价格: {current_price:.2f}")
            print(f"     MA5: {ma5:.2f}, 价格>=MA5: {current_price >= ma5}")
            print(f"     布林带下轨: {lower_band:.2f}, 价格<=下轨: {current_price <= lower_band}")
            print()

# 测试单独的布林带筛选
print("\n=== 测试单独布林带筛选 ===")
print("条件: 当前价格 <= 布林带下轨")

bollinger_only = filter_obj.filter_by_bollinger(
    band='lower', 
    condition='<=', 
    window=20
)

print(f"\n符合布林带条件的股票数量: {len(bollinger_only)}")

if len(bollinger_only) > 0:
    print("\n前3只符合条件的股票:")
    for i, (index, row) in enumerate(bollinger_only.head(3).iterrows()):
        stock_code = row['code']
        current_price = row['price']
        
        bollinger_bands = filter_obj.calculate_bollinger_bands(stock_code, 20)
        if bollinger_bands:
            upper_band, middle_band, lower_band = bollinger_bands
            print(f"  {i+1}. {stock_code} ({row['name']})")
            print(f"     当前价格: {current_price:.2f}")
            print(f"     布林带下轨: {lower_band:.2f}")
            print(f"     价格<=下轨: {current_price <= lower_band}")
            print()

print("测试完成！")