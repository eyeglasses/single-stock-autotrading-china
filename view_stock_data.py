# -*- coding: utf-8 -*-
"""
查看MySQL数据库中存储的股票价格数据
演示多种查询方法
"""

import sys
import os
from datetime import datetime, date, timedelta
import pandas as pd
from loguru import logger

# 添加项目路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# 导入数据库管理模块
from database import get_db_manager
from config import DATABASE_CONFIG

# 配置日志
logger.add(
    "logs/view_data_{time:YYYY-MM-DD}.log",
    rotation="1 day",
    retention="30 days",
    level="INFO"
)

def view_market_data_by_stock(stock_code: str, days: int = 30):
    """
    查看指定股票的行情数据
    
    Args:
        stock_code: 股票代码，如 '000001.SZ'
        days: 查看最近多少天的数据
    """
    print(f"\n=== 查看股票 {stock_code} 最近 {days} 天的行情数据 ===")
    
    try:
        db_manager = get_db_manager()
        
        # 计算开始日期
        end_date = date.today()
        start_date = end_date - timedelta(days=days)
        
        # 获取行情数据
        df = db_manager.get_market_data(
            stock_code=stock_code,
            start_date=start_date,
            end_date=end_date,
            limit=days
        )
        
        if df.empty:
            print(f"❌ 未找到股票 {stock_code} 的数据")
            return
        
        print(f"✅ 找到 {len(df)} 条记录")
        print("\n📊 数据预览:")
        print(df.head(10).to_string(index=False))
        
        # 显示统计信息
        if 'close_price' in df.columns:
            latest_price = df.iloc[0]['close_price'] if len(df) > 0 else 0
            max_price = df['close_price'].max()
            min_price = df['close_price'].min()
            avg_price = df['close_price'].mean()
            
            print(f"\n📈 价格统计:")
            print(f"最新价格: {latest_price:.3f}")
            print(f"最高价格: {max_price:.3f}")
            print(f"最低价格: {min_price:.3f}")
            print(f"平均价格: {avg_price:.3f}")
        
        return df
        
    except Exception as e:
        logger.error(f"查询股票数据失败: {e}")
        print(f"❌ 查询失败: {e}")
        return None

def view_all_stocks_summary():
    """
    查看数据库中所有股票的汇总信息
    """
    print("\n=== 数据库中所有股票汇总 ===")
    
    try:
        db_manager = get_db_manager()
        
        # 直接执行SQL查询
        sql = """
        SELECT 
            stock_code,
            COUNT(*) as record_count,
            MIN(trade_date) as earliest_date,
            MAX(trade_date) as latest_date,
            AVG(close_price) as avg_price,
            MAX(close_price) as max_price,
            MIN(close_price) as min_price
        FROM market_data 
        GROUP BY stock_code 
        ORDER BY latest_date DESC
        """
        
        results = db_manager.execute_query(sql)
        
        if not results:
            print("❌ 数据库中没有股票数据")
            return
        
        print(f"✅ 找到 {len(results)} 只股票的数据")
        print("\n📊 股票汇总:")
        
        # 格式化输出
        print(f"{'股票代码':<12} {'记录数':<8} {'最早日期':<12} {'最新日期':<12} {'平均价格':<10} {'最高价格':<10} {'最低价格':<10}")
        print("-" * 80)
        
        for row in results:
            print(f"{row['stock_code']:<12} {row['record_count']:<8} {row['earliest_date']:<12} {row['latest_date']:<12} {row['avg_price']:<10.3f} {row['max_price']:<10.3f} {row['min_price']:<10.3f}")
        
        return results
        
    except Exception as e:
        logger.error(f"查询汇总数据失败: {e}")
        print(f"❌ 查询失败: {e}")
        return None

def view_recent_data(limit: int = 50):
    """
    查看最近的股票数据
    
    Args:
        limit: 显示记录数量
    """
    print(f"\n=== 最近 {limit} 条股票数据 ===")
    
    try:
        db_manager = get_db_manager()
        
        sql = """
        SELECT 
            stock_code,
            trade_date,
            open_price,
            high_price,
            low_price,
            close_price,
            volume,
            amount
        FROM market_data 
        ORDER BY trade_date DESC, stock_code 
        LIMIT %s
        """
        
        results = db_manager.execute_query(sql, [limit])
        
        if not results:
            print("❌ 没有找到数据")
            return
        
        print(f"✅ 找到 {len(results)} 条记录")
        print("\n📊 最近数据:")
        
        # 转换为DataFrame便于显示
        df = pd.DataFrame(results)
        print(df.to_string(index=False))
        
        return results
        
    except Exception as e:
        logger.error(f"查询最近数据失败: {e}")
        print(f"❌ 查询失败: {e}")
        return None

def search_by_price_range(min_price: float, max_price: float, days: int = 7):
    """
    按价格范围搜索股票
    
    Args:
        min_price: 最低价格
        max_price: 最高价格
        days: 搜索最近多少天
    """
    print(f"\n=== 搜索价格在 {min_price}-{max_price} 范围内的股票（最近{days}天） ===")
    
    try:
        db_manager = get_db_manager()
        
        # 计算日期范围
        end_date = date.today()
        start_date = end_date - timedelta(days=days)
        
        sql = """
        SELECT DISTINCT
            stock_code,
            trade_date,
            close_price,
            volume
        FROM market_data 
        WHERE close_price BETWEEN %s AND %s
        AND trade_date BETWEEN %s AND %s
        ORDER BY trade_date DESC, close_price DESC
        """
        
        results = db_manager.execute_query(sql, [min_price, max_price, start_date, end_date])
        
        if not results:
            print(f"❌ 没有找到价格在 {min_price}-{max_price} 范围内的股票")
            return
        
        print(f"✅ 找到 {len(results)} 条记录")
        print("\n📊 搜索结果:")
        
        df = pd.DataFrame(results)
        print(df.to_string(index=False))
        
        return results
        
    except Exception as e:
        logger.error(f"按价格搜索失败: {e}")
        print(f"❌ 搜索失败: {e}")
        return None

def export_to_csv(stock_code: str, filename: str = None):
    """
    导出股票数据到CSV文件
    
    Args:
        stock_code: 股票代码
        filename: 文件名，如果不指定则自动生成
    """
    if not filename:
        filename = f"stock_data_{stock_code.replace('.', '_')}_{date.today().strftime('%Y%m%d')}.csv"
    
    print(f"\n=== 导出股票 {stock_code} 数据到 {filename} ===")
    
    try:
        db_manager = get_db_manager()
        
        # 获取所有数据
        df = db_manager.get_market_data(stock_code=stock_code)
        
        if df.empty:
            print(f"❌ 股票 {stock_code} 没有数据可导出")
            return False
        
        # 导出到CSV
        df.to_csv(filename, index=False, encoding='utf-8-sig')
        print(f"✅ 成功导出 {len(df)} 条记录到 {filename}")
        
        return True
        
    except Exception as e:
        logger.error(f"导出数据失败: {e}")
        print(f"❌ 导出失败: {e}")
        return False

def main():
    """
    主函数 - 演示各种查询方法
    """
    print("📈 MySQL股票价格数据查看工具")
    print("=" * 50)
    
    try:
        # 1. 查看数据库连接
        db_manager = get_db_manager()
        if not db_manager.test_connection():
            print("❌ 数据库连接失败，请检查配置")
            return
        
        print("✅ 数据库连接成功")
        
        # 2. 查看所有股票汇总
        view_all_stocks_summary()
        
        # 3. 查看最近数据
        view_recent_data(20)
        
        # 4. 查看特定股票数据（如果有的话）
        # 这里使用一个示例股票代码，实际使用时请替换为真实的股票代码
        stock_codes = ['000001.SZ', '000002.SZ', '513330.SH']  # 示例股票代码
        
        for stock_code in stock_codes:
            result = view_market_data_by_stock(stock_code, 10)
            if result is not None and not result.empty:
                break
        
        # 5. 按价格范围搜索
        search_by_price_range(0.5, 2.0, 30)
        
        print("\n" + "=" * 50)
        print("🎯 使用说明:")
        print("1. view_market_data_by_stock('股票代码', 天数) - 查看特定股票数据")
        print("2. view_all_stocks_summary() - 查看所有股票汇总")
        print("3. view_recent_data(条数) - 查看最近数据")
        print("4. search_by_price_range(最低价, 最高价, 天数) - 按价格搜索")
        print("5. export_to_csv('股票代码', '文件名') - 导出数据")
        print("\n💡 提示: 可以直接调用这些函数来查询特定数据")
        
    except Exception as e:
        logger.error(f"程序运行失败: {e}")
        print(f"❌ 程序运行失败: {e}")

if __name__ == "__main__":
    main()