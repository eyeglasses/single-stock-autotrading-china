# -*- coding: utf-8 -*-
"""
使用示例
演示如何使用单只股票自动交易系统
"""

import sys
import os
from datetime import datetime, timedelta
from loguru import logger

# 添加项目路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# 导入数据库管理模块
# DatabaseManager: 提供MySQL数据库连接、表初始化、数据插入和查询功能
from database import DatabaseManager

# 导入数据获取模块
# 该模块使用miniQMT的XtData API获取股票行情数据
from data_fetcher import (
    update_stock_data,    # 更新股票历史数据到数据库
    get_market_data,      # 获取股票历史行情数据(日线、分钟线等)
    get_realtime_data,   # 获取股票实时行情数据
    get_stock_info        # 获取股票基本信息(名称、代码等)
)

# 导入交易策略模块
# 该模块实现技术分析和动量策略，生成买卖信号
from strategy import (
    create_technical_strategy,  # 创建技术分析策略实例(MA、RSI、MACD、布林带等)
    create_momentum_strategy,   # 创建动量策略实例(价格动量、成交量动量)
    generate_trading_signal,    # 生成综合交易信号(结合多种策略)
    analyze_stock_trend         # 分析股票趋势(上涨、下跌、震荡)
)

# 导入风险控制模块
# 该模块提供仓位管理、止损止盈、风险限制等功能
from risk_control import (
    check_risk_limits,              # 检查风险限制(日亏损、最大回撤、交易频率等)
    calculate_position_size_legacy,        # 计算仓位大小(固定金额、百分比、Kelly公式、ATR等)
    check_stop_loss_take_profit_with_entry     # 检查止损止盈条件
)

# 导入交易执行模块
# 该模块使用miniQMT的XtTrader API执行实际的买卖操作
from trader import (
    buy_stock,          # 执行买入股票操作
    sell_stock,         # 执行卖出股票操作
    get_account_asset,  # 查询账户资产信息(总资产、可用资金等)
    get_position,       # 查询当前持仓信息
    get_orders          # 查询订单信息(历史订单、当日订单等)
)

# 导入回测模块
# 该模块提供策略历史回测功能，验证策略效果
from backtest import run_backtest, print_backtest_summary  # 运行回测和打印回测结果摘要

# 导入主程序模块
# AutoTradingSystem: 自动交易系统主类，整合所有功能模块
from main import AutoTradingSystem

# 导入配置模块
# TRADING_CONFIG: 交易相关配置参数(目标股票、仓位比例、止损止盈等)
from config import TRADING_CONFIG

def example_1_database_setup():
    """示例1: 数据库初始化"""
    print("\n=== 示例1: 数据库初始化 ===")
    
    try:
        # 创建数据库管理器
        db = DatabaseManager()
        
        # 初始化数据表
        db.init_tables()
        print("✓ 数据库表初始化成功")
        
        # 测试连接
        result = db.execute_query("SELECT 1 as test")
        if result:
            print("✓ 数据库连接测试成功")
        
    except Exception as e:
        print(f"✗ 数据库初始化失败: {e}")

def example_2_data_fetching():
    """示例2: 数据获取"""
    print("\n=== 示例2: 数据获取 ===")
    
    stock_code = "513330.SH"  # 恒生互联网
    
    try:
        # 获取股票基本信息
        stock_info = get_stock_info(stock_code)
        if stock_info:
            print(f"✓ 股票信息: {stock_info}")
        
        # 获取历史数据
        end_date = datetime.now().strftime('%Y%m%d')
        start_date = (datetime.now() - timedelta(days=30)).strftime('%Y%m%d')
        
        df = get_market_data(
            stock_code=stock_code,
            period='1d',
            count=30  # 获取30天数据
        )
        
        if df is not None and not df.empty:
            print(f"✓ 获取历史数据成功: {len(df)} 条记录")
            print(f"  最新价格: {df.iloc[-1]['close_price']:.2f}")
            print(f"  日期范围: {df.index[0]} 至 {df.index[-1]}")
        
        # 获取实时数据
        real_time_data = get_realtime_data(stock_code)
        if real_time_data is not None and isinstance(real_time_data, dict):
            print(f"✓ 实时数据: 价格 {real_time_data.get('price', 'N/A')}")
        
        # 更新数据到数据库
        update_stock_data(stock_code, 30)  # 更新30天数据
        print("✓ 数据已更新到数据库")
        
    except Exception as e:
        print(f"✗ 数据获取失败: {e}")

def example_3_strategy_analysis():
    """示例3: 策略分析"""
    print("\n=== 示例3: 策略分析 ===")
    
    stock_code = "513330.SH"
    
    try:
        # 获取历史数据
        df = get_market_data(
            stock_code=stock_code,
            period='1d',
            count=60  # 获取60天数据
        )
        
        if df is None or df.empty:
            print("✗ 无法获取数据")
            return
        
        # 创建技术分析策略
        tech_strategy = create_technical_strategy(stock_code)
        signal_type, strength, reason = tech_strategy.analyze_trend(df)
        print(f"✓ 技术分析信号: {signal_type.value}, 强度: {strength:.2f}, 原因: {reason}")
        
        # 创建动量策略
        momentum_strategy = create_momentum_strategy(stock_code)
        momentum_signal, momentum_strength, momentum_reason = momentum_strategy.analyze_momentum(df)
        print(f"✓ 动量分析信号: {momentum_signal.value}, 强度: {momentum_strength:.2f}, 原因: {momentum_reason}")
        
        # 生成综合交易信号
        trading_signal = generate_trading_signal(stock_code, df)
        if trading_signal:
            print(f"✓ 综合交易信号: {trading_signal}")
        
        # 分析股票趋势
        trend_analysis = analyze_stock_trend(stock_code, 30)  # 分析30天趋势
        print(f"✓ 趋势分析: {trend_analysis}")
        
    except Exception as e:
        print(f"✗ 策略分析失败: {e}")

def example_4_risk_control():
    """示例4: 风险控制"""
    print("\n=== 示例4: 风险控制 ===")
    
    stock_code = "513330.SH"
    
    try:
        # 检查风险限制
        risk_check = check_risk_limits(stock_code)
        print(f"✓ 风险检查结果: {risk_check}")
        
        # 计算仓位大小
        current_price = 12.50  # 假设当前价格
        available_cash = 50000  # 假设可用资金
        
        position_size = calculate_position_size_legacy(
            stock_code=stock_code,
            current_price=current_price,
            available_cash=available_cash,
            size_type='percentage'
        )
        print(f"✓ 建议仓位大小: {position_size} 股")
        
        # 检查止损止盈
        entry_price = 12.00  # 假设入场价格
        stop_check = check_stop_loss_take_profit_with_entry(
            stock_code=stock_code,
            entry_price=entry_price,
            current_price=current_price,
            trade_type='buy'
        )
        print(f"✓ 止损止盈检查: {stop_check}")
        
    except Exception as e:
        print(f"✗ 风险控制失败: {e}")

def example_5_trading_operations():
    """示例5: 交易操作 (模拟)"""
    print("\n=== 示例5: 交易操作 (模拟) ===")
    
    stock_code = "513330.SH"
    
    try:
        # 注意: 这些是模拟操作，实际交易需要确保miniQMT客户端正常运行
        
        # 查询账户资产
        print("查询账户资产...")
        # assets = get_account_assets()
        # print(f"✓ 账户资产: {assets}")
        
        # 查询持仓
        print("查询持仓...")
        # positions = get_positions()
        # print(f"✓ 当前持仓: {positions}")
        
        # 查询订单
        print("查询订单...")
        # orders = get_orders()
        # print(f"✓ 订单列表: {orders}")
        
        # 模拟买入操作
        print("模拟买入操作...")
        # order_id = buy_stock(
        #     stock_code=stock_code,
        #     volume=1000,
        #     price=12.50,
        #     order_type='limit'
        # )
        # print(f"✓ 买入订单ID: {order_id}")
        
        print("✓ 交易操作示例完成 (模拟)")
        
    except Exception as e:
        print(f"✗ 交易操作失败: {e}")

def example_6_backtest():
    """示例6: 策略回测"""
    print("\n=== 示例6: 策略回测 ===")
    
    stock_code = "513330.SH"
    
    try:
        # 设置回测参数
        start_date = "20240101"
        end_date = "20240630"
        initial_capital = 10000
        
        print(f"开始回测: {stock_code}, {start_date} - {end_date}")
        
        # 运行回测
        result = run_backtest(
            stock_code=stock_code,
            start_date=start_date,
            end_date=end_date,
            initial_capital=initial_capital
        )
        
        # 打印回测结果
        print_backtest_summary(result)
        
        # 详细分析
        print(f"\n详细分析:")
        print(f"交易次数: {len(result.trades)}")
        if result.trades:
            print(f"首次交易: {result.trades[0].timestamp}")
            print(f"最后交易: {result.trades[-1].timestamp}")
        
    except Exception as e:
        print(f"✗ 回测失败: {e}")

def example_7_auto_trading_system():
    """示例7: 自动交易系统"""
    print("\n=== 示例7: 自动交易系统 ===")
    
    stock_code = TRADING_CONFIG['target_stock']
    
    try:
        # 创建自动交易系统
        system = AutoTradingSystem(stock_code)
        
        # 检查系统就绪状态
        if system.check_system_ready():
            print("✓ 系统就绪检查通过")
        else:
            print("✗ 系统就绪检查失败")
            return
        
        # 初始化日常任务
        system.daily_initialization()
        print("✓ 日常初始化完成")
        
        # 执行一次信号检查
        system.check_trading_signals()
        print("✓ 交易信号检查完成")
        
        # 执行风险检查
        system.risk_check()
        print("✓ 风险检查完成")
        
        # 生成日报
        system.daily_summary()
        print("✓ 日报生成完成")
        
        print("\n注意: 要启动完整的自动交易系统，请运行 system.start()")
        print("这将启动定时任务，持续监控和交易")
        
    except Exception as e:
        print(f"✗ 自动交易系统示例失败: {e}")

def main():
    """主函数 - 运行所有示例"""
    print("单只股票自动交易系统 - 使用示例")
    print("=" * 50)
    
    # 配置日志
    logger.add(
        "logs/example_{time:YYYY-MM-DD}.log",
        rotation="1 day",
        retention="30 days",
        level="INFO"
    )
    
    try:
        # 运行所有示例
        example_1_database_setup()
        example_2_data_fetching()
        example_3_strategy_analysis()
        example_4_risk_control()
        example_5_trading_operations()
        example_6_backtest()
        example_7_auto_trading_system()
        
        print("\n" + "=" * 50)
        print("所有示例运行完成!")
        print("\n下一步:")
        print("1. 检查配置文件 config.py")
        print("2. 确保miniQMT客户端正常运行")
        print("3. 运行回测验证策略效果")
        print("4. 小资金实盘测试")
        print("5. 正式启动自动交易系统")
        
    except Exception as e:
        logger.error(f"示例运行失败: {e}")
        print(f"\n✗ 示例运行失败: {e}")

if __name__ == "__main__":
    main()