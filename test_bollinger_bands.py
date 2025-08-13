#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import xtquant.xtdata as xtdata
import pandas as pd
from stock_filter import StockFilter

def test_bollinger_bands():
    """测试布林带计算和筛选逻辑"""
    
    # 初始化筛选器
    filter = StockFilter()
    filter.load_from_xtdata(['A股'])
    
    if filter.data.empty:
        print("没有加载到股票数据")
        return
    
    # 选择前5只股票进行测试
    test_stocks = filter.data.head(5)
    
    print("=== 布林带计算和筛选测试 ===")
    print(f"测试股票数量: {len(test_stocks)}")
    print()
    
    for index, row in test_stocks.iterrows():
        stock_code = row['code']
        stock_name = row['name']
        current_price = row['price']
        
        print(f"股票: {stock_code} ({stock_name})")
        print(f"当前价格: {current_price:.2f}")
        
        # 计算布林带
        bollinger_bands = filter.calculate_bollinger_bands(stock_code, window=20)
        
        if bollinger_bands:
            upper_band, middle_band, lower_band = bollinger_bands
            print(f"布林带 - 上轨: {upper_band:.2f}, 中轨: {middle_band:.2f}, 下轨: {lower_band:.2f}")
            
            # 测试各种条件
            conditions = [
                ('lower', '<=', '价格 <= 下轨'),
                ('lower', '>=', '价格 >= 下轨'),
                ('upper', '<=', '价格 <= 上轨'),
                ('upper', '>=', '价格 >= 上轨'),
                ('middle', '<=', '价格 <= 中轨'),
                ('middle', '>=', '价格 >= 中轨')
            ]
            
            for band, condition, description in conditions:
                if band == 'upper':
                    target_value = upper_band
                elif band == 'middle':
                    target_value = middle_band
                else:  # lower
                    target_value = lower_band
                
                if condition == '<=':
                    result = current_price <= target_value
                else:  # '>='
                    result = current_price >= target_value
                
                print(f"  {description}: {result} ({current_price:.2f} {condition} {target_value:.2f})")
        else:
            print("  布林带计算失败")
        
        print()
    
    # 测试筛选功能
    print("=== 筛选功能测试 ===")
    
    # 测试价格 <= 下轨的筛选
    print("\n1. 筛选价格 <= 下轨的股票:")
    result_lower_le = filter.filter_by_bollinger('lower', '<=', 20)
    print(f"符合条件的股票数量: {len(result_lower_le)}")
    
    if len(result_lower_le) > 0:
        print("前3只符合条件的股票:")
        for i, (_, row) in enumerate(result_lower_le.head(3).iterrows()):
            stock_code = row['code']
            stock_name = row['name']
            current_price = row['price']
            
            bollinger_bands = filter.calculate_bollinger_bands(stock_code, window=20)
            if bollinger_bands:
                _, _, lower_band = bollinger_bands
                print(f"  {i+1}. {stock_code} ({stock_name}) - 价格: {current_price:.2f}, 下轨: {lower_band:.2f}, 符合: {current_price <= lower_band}")
    
    # 测试价格 >= 上轨的筛选
    print("\n2. 筛选价格 >= 上轨的股票:")
    result_upper_ge = filter.filter_by_bollinger('upper', '>=', 20)
    print(f"符合条件的股票数量: {len(result_upper_ge)}")
    
    if len(result_upper_ge) > 0:
        print("前3只符合条件的股票:")
        for i, (_, row) in enumerate(result_upper_ge.head(3).iterrows()):
            stock_code = row['code']
            stock_name = row['name']
            current_price = row['price']
            
            bollinger_bands = filter.calculate_bollinger_bands(stock_code, window=20)
            if bollinger_bands:
                upper_band, _, _ = bollinger_bands
                print(f"  {i+1}. {stock_code} ({stock_name}) - 价格: {current_price:.2f}, 上轨: {upper_band:.2f}, 符合: {current_price >= upper_band}")

if __name__ == "__main__":
    test_bollinger_bands()