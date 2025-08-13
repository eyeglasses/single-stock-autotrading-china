# -*- coding: utf-8 -*-
"""
简单的MySQL股票数据查询演示
直接使用mysql.connector进行查询
"""

import mysql.connector
from mysql.connector import Error
import pandas as pd
from datetime import datetime, date, timedelta
from config import DATABASE_CONFIG

def connect_database():
    """连接数据库"""
    try:
        connection = mysql.connector.connect(**DATABASE_CONFIG)
        if connection.is_connected():
            print("✅ 数据库连接成功")
            return connection
    except Error as e:
        print(f"❌ 数据库连接失败: {e}")
        return None

def show_tables(connection):
    """显示所有表"""
    print("\n=== 数据库表列表 ===")
    try:
        cursor = connection.cursor()
        cursor.execute("SHOW TABLES")
        tables = cursor.fetchall()
        
        if tables:
            print("📊 找到以下数据表:")
            for table in tables:
                print(f"  - {table[0]}")
        else:
            print("❌ 没有找到数据表")
        
        cursor.close()
        return [table[0] for table in tables]
    except Error as e:
        print(f"❌ 查询表失败: {e}")
        return []

def show_market_data_summary(connection):
    """显示行情数据汇总"""
    print("\n=== 行情数据汇总 ===")
    try:
        cursor = connection.cursor(dictionary=True)
        
        # 检查market_data表是否存在
        cursor.execute("SHOW TABLES LIKE 'market_data'")
        if not cursor.fetchone():
            print("❌ market_data表不存在")
            cursor.close()
            return
        
        # 查询汇总信息
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
        LIMIT 10
        """
        
        cursor.execute(sql)
        results = cursor.fetchall()
        
        if results:
            print(f"📈 找到 {len(results)} 只股票的数据:")
            print(f"{'股票代码':<12} {'记录数':<8} {'最早日期':<12} {'最新日期':<12} {'平均价格':<10} {'最高价格':<10} {'最低价格':<10}")
            print("-" * 80)
            
            for row in results:
                print(f"{row['stock_code']:<12} {row['record_count']:<8} {str(row['earliest_date']):<12} {str(row['latest_date']):<12} {row['avg_price']:<10.3f} {row['max_price']:<10.3f} {row['min_price']:<10.3f}")
        else:
            print("❌ market_data表中没有数据")
        
        cursor.close()
        
    except Error as e:
        print(f"❌ 查询行情数据失败: {e}")

def show_recent_data(connection, limit=10):
    """显示最近的数据"""
    print(f"\n=== 最近 {limit} 条行情数据 ===")
    try:
        cursor = connection.cursor(dictionary=True)
        
        sql = """
        SELECT 
            stock_code,
            trade_date,
            open_price,
            high_price,
            low_price,
            close_price,
            volume
        FROM market_data 
        ORDER BY trade_date DESC, stock_code 
        LIMIT %s
        """
        
        cursor.execute(sql, (limit,))
        results = cursor.fetchall()
        
        if results:
            print(f"📊 最近 {len(results)} 条记录:")
            print(f"{'股票代码':<12} {'交易日期':<12} {'开盘价':<8} {'最高价':<8} {'最低价':<8} {'收盘价':<8} {'成交量':<12}")
            print("-" * 80)
            
            for row in results:
                print(f"{row['stock_code']:<12} {str(row['trade_date']):<12} {row['open_price']:<8.3f} {row['high_price']:<8.3f} {row['low_price']:<8.3f} {row['close_price']:<8.3f} {row['volume']:<12}")
        else:
            print("❌ 没有找到数据")
        
        cursor.close()
        
    except Error as e:
        print(f"❌ 查询最近数据失败: {e}")

def show_stock_data(connection, stock_code, days=10):
    """显示特定股票的数据"""
    print(f"\n=== 股票 {stock_code} 最近 {days} 天数据 ===")
    try:
        cursor = connection.cursor(dictionary=True)
        
        sql = """
        SELECT 
            trade_date,
            open_price,
            high_price,
            low_price,
            close_price,
            volume,
            amount
        FROM market_data 
        WHERE stock_code = %s
        ORDER BY trade_date DESC 
        LIMIT %s
        """
        
        cursor.execute(sql, (stock_code, days))
        results = cursor.fetchall()
        
        if results:
            print(f"📈 找到 {len(results)} 条记录:")
            print(f"{'交易日期':<12} {'开盘价':<8} {'最高价':<8} {'最低价':<8} {'收盘价':<8} {'成交量':<12} {'成交额':<15}")
            print("-" * 85)
            
            for row in results:
                volume_str = f"{row['volume']:,}" if row['volume'] else "0"
                amount_str = f"{row['amount']:,.2f}" if row['amount'] else "0.00"
                print(f"{str(row['trade_date']):<12} {row['open_price']:<8.3f} {row['high_price']:<8.3f} {row['low_price']:<8.3f} {row['close_price']:<8.3f} {volume_str:<12} {amount_str:<15}")
            
            # 显示统计信息
            latest_price = results[0]['close_price']
            max_price = max(row['close_price'] for row in results)
            min_price = min(row['close_price'] for row in results)
            avg_price = sum(row['close_price'] for row in results) / len(results)
            
            print(f"\n📊 统计信息:")
            print(f"最新价格: {latest_price:.3f}")
            print(f"期间最高: {max_price:.3f}")
            print(f"期间最低: {min_price:.3f}")
            print(f"平均价格: {avg_price:.3f}")
            
        else:
            print(f"❌ 没有找到股票 {stock_code} 的数据")
        
        cursor.close()
        
    except Error as e:
        print(f"❌ 查询股票数据失败: {e}")

def show_trade_records(connection, limit=10):
    """显示交易记录"""
    print(f"\n=== 最近 {limit} 条交易记录 ===")
    try:
        cursor = connection.cursor(dictionary=True)
        
        # 检查trade_records表是否存在
        cursor.execute("SHOW TABLES LIKE 'trade_records'")
        if not cursor.fetchone():
            print("❌ trade_records表不存在")
            cursor.close()
            return
        
        sql = """
        SELECT 
            stock_code,
            trade_type,
            price,
            volume,
            amount,
            trade_time,
            status
        FROM trade_records 
        ORDER BY trade_time DESC 
        LIMIT %s
        """
        
        cursor.execute(sql, (limit,))
        results = cursor.fetchall()
        
        if results:
            print(f"💰 找到 {len(results)} 条交易记录:")
            print(f"{'股票代码':<12} {'类型':<6} {'价格':<8} {'数量':<8} {'金额':<12} {'时间':<20} {'状态':<10}")
            print("-" * 85)
            
            for row in results:
                trade_type_cn = "买入" if row['trade_type'] == 'buy' else "卖出"
                print(f"{row['stock_code']:<12} {trade_type_cn:<6} {row['price']:<8.3f} {row['volume']:<8} {row['amount']:<12.2f} {str(row['trade_time']):<20} {row['status']:<10}")
        else:
            print("❌ 没有找到交易记录")
        
        cursor.close()
        
    except Error as e:
        print(f"❌ 查询交易记录失败: {e}")

def interactive_query(connection):
    """交互式查询"""
    print("\n=== 交互式查询 ===")
    print("请输入SQL查询语句（输入 'quit' 退出）:")
    
    while True:
        try:
            sql = input("SQL> ").strip()
            
            if sql.lower() in ['quit', 'exit', 'q']:
                break
            
            if not sql:
                continue
            
            cursor = connection.cursor(dictionary=True)
            cursor.execute(sql)
            
            if sql.upper().startswith('SELECT'):
                results = cursor.fetchall()
                if results:
                    print(f"\n✅ 查询结果 ({len(results)} 条记录):")
                    # 显示列名
                    if results:
                        columns = list(results[0].keys())
                        print(" | ".join(f"{col:<15}" for col in columns))
                        print("-" * (len(columns) * 17))
                        
                        # 显示数据（最多显示20行）
                        for i, row in enumerate(results[:20]):
                            print(" | ".join(f"{str(row[col]):<15}" for col in columns))
                        
                        if len(results) > 20:
                            print(f"... 还有 {len(results) - 20} 条记录未显示")
                else:
                    print("❌ 查询结果为空")
            else:
                connection.commit()
                print(f"✅ SQL执行成功，影响行数: {cursor.rowcount}")
            
            cursor.close()
            
        except Error as e:
            print(f"❌ SQL执行失败: {e}")
        except KeyboardInterrupt:
            print("\n👋 退出交互式查询")
            break
        except Exception as e:
            print(f"❌ 发生错误: {e}")

def main():
    """主函数"""
    print("📈 MySQL股票数据查询演示")
    print("=" * 50)
    
    # 连接数据库
    connection = connect_database()
    if not connection:
        print("❌ 无法连接数据库，程序退出")
        return
    
    try:
        # 1. 显示所有表
        tables = show_tables(connection)
        
        # 2. 如果有market_data表，显示汇总信息
        if 'market_data' in tables:
            show_market_data_summary(connection)
            show_recent_data(connection, 5)
            
            # 尝试查询一些常见的股票代码
            test_stocks = ['000001.SZ', '000002.SZ', '513330.SH', '600000.SH']
            for stock_code in test_stocks:
                # 先检查是否有这个股票的数据
                cursor = connection.cursor()
                cursor.execute("SELECT COUNT(*) FROM market_data WHERE stock_code = %s", (stock_code,))
                count = cursor.fetchone()[0]
                cursor.close()
                
                if count > 0:
                    show_stock_data(connection, stock_code, 5)
                    break
        
        # 3. 如果有trade_records表，显示交易记录
        if 'trade_records' in tables:
            show_trade_records(connection, 5)
        
        # 4. 交互式查询
        print("\n" + "=" * 50)
        print("🎯 常用查询示例:")
        print("1. SELECT * FROM market_data LIMIT 5;")
        print("2. SELECT DISTINCT stock_code FROM market_data;")
        print("3. SELECT * FROM market_data WHERE stock_code = '000001.SZ' ORDER BY trade_date DESC LIMIT 10;")
        print("4. SELECT stock_code, AVG(close_price) as avg_price FROM market_data GROUP BY stock_code;")
        
        choice = input("\n是否进入交互式查询模式？(y/n): ").strip().lower()
        if choice in ['y', 'yes']:
            interactive_query(connection)
        
    finally:
        connection.close()
        print("\n👋 数据库连接已关闭")

if __name__ == "__main__":
    main()