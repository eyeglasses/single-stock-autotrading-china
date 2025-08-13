#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import xtquant.xtdata as xtdata

def test_sectors():
    """测试不同sector的股票数量"""
    
    sectors = ['沪深A股', '港股', '港股通', 'ETF', '基金', '沪股通', '深股通']
    
    print("测试各个sector的股票数量:")
    for sector in sectors:
        try:
            stocks = xtdata.get_stock_list_in_sector(sector)
            if stocks:
                print(f"{sector}: {len(stocks)}只股票")
                # 显示前5只股票作为示例
                print(f"  示例: {stocks[:5]}")
            else:
                print(f"{sector}: 0只股票或不支持")
        except Exception as e:
            print(f"{sector}: 错误 - {e}")
        print()

if __name__ == "__main__":
    test_sectors()