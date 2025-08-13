#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
简单测试股票数据加载
"""

import sys
sys.path.append('.')

import xtquant.xtdata as xtdata
import pandas as pd

def test_load():
    print("开始测试股票数据加载...")
    
    # 1. 测试获取股票列表
    print("\n1. 测试获取股票列表:")
    try:
        stocks = xtdata.get_stock_list_in_sector('沪深A股')
        print(f"获取到 {len(stocks)} 只A股")
        test_stocks = stocks[:3]  # 取前3只测试
        print(f"测试股票: {test_stocks}")
    except Exception as e:
        print(f"获取股票列表失败: {e}")
        return
    
    # 2. 测试获取股票详细信息
    print("\n2. 测试获取股票详细信息:")
    valid_stocks = []
    for stock_code in test_stocks:
        try:
            detail = xtdata.get_instrument_detail(stock_code)
            if detail:
                print(f"  {stock_code}: {detail.get('InstrumentName', 'N/A')} - {detail.get('InstrumentType', 'N/A')}")
                valid_stocks.append(stock_code)
            else:
                print(f"  {stock_code}: 无法获取详细信息")
        except Exception as e:
            print(f"  {stock_code}: 获取详细信息失败 - {e}")
    
    # 3. 测试获取市场数据
    print("\n3. 测试获取市场数据:")
    stock_info = []
    for stock_code in valid_stocks:
        try:
            # 获取基本信息
            detail = xtdata.get_instrument_detail(stock_code)
            
            # 获取价格数据
            price_data = xtdata.get_market_data_ex(['close'], [stock_code], period='1d', count=1)
            volume_data = xtdata.get_market_data_ex(['volume'], [stock_code], period='1d', count=1)
            
            if price_data and stock_code in price_data and not price_data[stock_code].empty:
                price = price_data[stock_code]['close'].iloc[-1]
                volume = volume_data[stock_code]['volume'].iloc[-1] if volume_data and stock_code in volume_data else 0
                
                stock_info.append({
                    'code': stock_code,
                    'name': detail.get('InstrumentName', ''),
                    'type': detail.get('InstrumentType', ''),
                    'price': price,
                    'volume': volume
                })
                
                print(f"  {stock_code}: 价格={price:.2f}, 成交量={volume}")
            else:
                print(f"  {stock_code}: 无法获取价格数据")
                
        except Exception as e:
            print(f"  {stock_code}: 获取市场数据失败 - {e}")
            import traceback
            traceback.print_exc()
    
    # 4. 创建DataFrame
    print("\n4. 创建DataFrame:")
    if stock_info:
        df = pd.DataFrame(stock_info)
        print(f"成功创建包含 {len(df)} 只股票的DataFrame")
        print(df)
        return df
    else:
        print("❌ 没有有效的股票数据")
        return None

if __name__ == "__main__":
    test_load()