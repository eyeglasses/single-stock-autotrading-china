import pandas as pd
import numpy as np
from typing import List, Dict, Optional, Tuple
from datetime import datetime
import json
import xtquant.xtdata as xtdata

def debug_stock_filter():
    """
    调试股票筛选功能
    """
    print("开始调试股票筛选功能...")
    
    # 1. 测试获取股票列表
    print("\n1. 测试获取股票列表:")
    all_stocks = []
    for sector in ['沪深A股', '港股', 'ETF']:
        try:
            stocks = xtdata.get_stock_list_in_sector(sector)
            if stocks:
                print(f"{sector}: 获取到 {len(stocks)} 只股票")
                all_stocks.extend(stocks[:5])  # 只取前5只用于测试
            else:
                print(f"{sector}: 未获取到股票")
        except Exception as e:
            print(f"获取{sector}股票列表失败: {e}")
    
    print(f"\n总共获取到 {len(all_stocks)} 只股票用于测试")
    if not all_stocks:
        print("错误：未获取到任何股票数据！")
        return
    
    # 2. 测试获取股票详细信息
    print("\n2. 测试获取股票详细信息:")
    stock_info = []
    for i, stock_code in enumerate(all_stocks[:3]):  # 只测试前3只
        print(f"\n处理股票 {i+1}/{min(3, len(all_stocks))}: {stock_code}")
        try:
            detail = xtdata.get_instrument_detail(stock_code)
            if detail:
                print(f"  - 名称: {detail.get('InstrumentName', 'N/A')}")
                print(f"  - 类型: {detail.get('InstrumentType', 'N/A')}")
                
                # 获取价格数据
                try:
                    # 使用get_market_data_ex获取数据
                    market_data = xtdata.get_market_data_ex(
                        field_list=['close', 'volume'], 
                        stock_list=[stock_code], 
                        period='1d', 
                        count=1
                    )
                    print(f"  - 市场数据类型: {type(market_data)}")
                    print(f"  - 市场数据内容: {market_data}")
                    
                    if market_data and stock_code in market_data:
                        stock_df = market_data[stock_code]
                        
                        if not stock_df.empty and 'close' in stock_df.columns and 'volume' in stock_df.columns:
                            price = stock_df['close'].iloc[-1]
                            volume = stock_df['volume'].iloc[-1]
                            
                            print(f"  - 价格: {price}")
                            print(f"  - 成交量: {volume}")
                            
                            stock_info.append({
                                'code': stock_code,
                                'name': detail.get('InstrumentName', ''),
                                'type': detail.get('InstrumentType', ''),
                                'price': price,
                                'volume': volume
                            })
                        else:
                            print(f"  - DataFrame为空或缺少字段")
                    else:
                        print(f"  - 无法获取价格数据，股票代码不在返回数据中")
                except Exception as e:
                    print(f"  - 获取价格数据失败: {e}")
                    import traceback
                    traceback.print_exc()
            else:
                print(f"  - 无法获取股票详细信息")
        except Exception as e:
            print(f"  - 处理失败: {e}")
    
    print(f"\n成功处理 {len(stock_info)} 只股票")
    
    if not stock_info:
        print("错误：未能获取到任何有效的股票信息！")
        return
    
    # 3. 测试MA计算
    print("\n3. 测试MA计算:")
    test_stock = stock_info[0]
    stock_code = test_stock['code']
    print(f"测试股票: {stock_code} ({test_stock['name']})")
    
    try:
        market_data = xtdata.get_market_data_ex(['close'], [stock_code], period='1d', count=25)
        if market_data and stock_code in market_data:
            kline = market_data[stock_code]
            if not kline.empty and 'close' in kline.columns:
                print(f"  - 获取到 {len(kline)} 天的K线数据")
                ma5 = kline['close'].iloc[-5:].mean()
                ma10 = kline['close'].iloc[-10:].mean()
                ma20 = kline['close'].iloc[-20:].mean()
                current_price = test_stock['price']
                
                print(f"  - 当前价格: {current_price:.2f}")
                print(f"  - MA5: {ma5:.2f}")
                print(f"  - MA10: {ma10:.2f}")
                print(f"  - MA20: {ma20:.2f}")
                
                print(f"  - 价格 >= MA5: {current_price >= ma5}")
                print(f"  - 价格 >= MA10: {current_price >= ma10}")
                print(f"  - 价格 >= MA20: {current_price >= ma20}")
            else:
                print(f"  - K线数据为空或缺少close字段")
        else:
            print(f"  - 无法获取K线数据")
    except Exception as e:
        print(f"  - MA计算失败: {e}")
        import traceback
        traceback.print_exc()
    
    # 4. 测试筛选逻辑
    print("\n4. 测试筛选逻辑:")
    df = pd.DataFrame(stock_info)
    print(f"原始数据: {len(df)} 只股票")
    
    # 测试MA筛选
    print("\n测试MA筛选 (MA5, 价格 >= MA):")
    filtered_count = 0
    for _, row in df.iterrows():
        stock_code = row['code']
        current_price = row['price']
        try:
            market_data = xtdata.get_market_data_ex(['close'], [stock_code], period='1d', count=10)
            if market_data and stock_code in market_data:
                kline = market_data[stock_code]
                if not kline.empty and 'close' in kline.columns and len(kline) >= 5:
                    ma5 = kline['close'].iloc[-5:].mean()
                    if current_price >= ma5:
                        filtered_count += 1
                        print(f"  - {stock_code}: 价格{current_price:.2f} >= MA5({ma5:.2f}) ✓")
                    else:
                        print(f"  - {stock_code}: 价格{current_price:.2f} < MA5({ma5:.2f}) ✗")
                else:
                    print(f"  - {stock_code}: K线数据不足或缺少字段")
            else:
                print(f"  - {stock_code}: 无法获取市场数据")
        except Exception as e:
            print(f"  - {stock_code}: 计算失败 {e}")
            import traceback
            traceback.print_exc()
    
    print(f"\nMA筛选结果: {filtered_count}/{len(df)} 只股票符合条件")
    
    print("\n调试完成！")

if __name__ == "__main__":
    debug_stock_filter()