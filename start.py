# -*- coding: utf-8 -*-
"""
启动脚本
快速启动单只股票自动交易系统
"""

import sys
import os
from datetime import datetime
from loguru import logger

# 添加项目路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from main import AutoTradingSystem
from config import TRADING_CONFIG, LOG_CONFIG, MINIQMT_CONFIG
from database import DatabaseManager

def setup_logging():
    """设置日志"""
    # 创建日志目录
    os.makedirs(LOG_CONFIG['log_dir'], exist_ok=True)
    
    # 配置日志
    logger.remove()  # 移除默认处理器
    
    # 控制台日志
    logger.add(
        sys.stdout,
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
        level="INFO"
    )
    
    # 文件日志
    logger.add(
        f"{LOG_CONFIG['log_dir']}/trading_{datetime.now().strftime('%Y-%m-%d')}.log",
        rotation=LOG_CONFIG['rotation'],
        retention=LOG_CONFIG['retention'],
        level=LOG_CONFIG['level'],
        encoding='utf-8'
    )
    
    # 错误日志
    logger.add(
        "logs/error_{time:YYYY-MM-DD}.log",
        rotation="1 day",
        retention="30 days",
        level="ERROR",
        encoding='utf-8'
    )

def check_prerequisites():
    """检查前置条件"""
    print("检查系统前置条件...")
    
    # 检查xtquant模块
    try:
        import xtquant
        print("✓ xtquant模块已安装")
    except ImportError:
        print("✗ xtquant模块未找到")
        print("  请从miniQMT安装目录复制xtquant文件夹到项目目录")
        return False
    
    # 检查数据库连接
    try:
        db = DatabaseManager()
        result = db.execute_query("SELECT 1")
        if result:
            print("✓ 数据库连接正常")
        else:
            print("✗ 数据库连接失败")
            return False
    except Exception as e:
        print(f"✗ 数据库连接错误: {e}")
        print("  请检查config.py中的数据库配置")
        return False
    
    # 检查配置
    target_stock = TRADING_CONFIG.get('target_stock')
    if not target_stock:
        print("✗ 未配置目标股票")
        print("  请在config.py中设置target_stock")
        return False
    else:
        print(f"✓ 目标股票: {target_stock}")
    
    account_id = MINIQMT_CONFIG.get('account_id')
    if not account_id:
        print("✗ 未配置交易账户")
        print("  请在config.py的MINIQMT_CONFIG中设置account_id")
        return False
    else:
        print(f"✓ 交易账户: {account_id}")
    
    return True

def initialize_system():
    """初始化系统"""
    print("\n初始化系统...")
    
    try:
        # 检查数据库连接（数据库表在DatabaseManager初始化时已自动创建）
        db = DatabaseManager()
        result = db.execute_query("SELECT 1")
        if result is not None:
            print("✓ 数据库表初始化完成")
            return True
        else:
            print("✗ 数据库连接失败")
            return False
        
    except Exception as e:
        print(f"✗ 系统初始化失败: {e}")
        return False

def start_trading_system():
    """启动交易系统"""
    target_stock = TRADING_CONFIG['target_stock']
    
    print(f"\n启动自动交易系统...")
    print(f"目标股票: {target_stock}")
    print(f"启动时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    try:
        # 创建交易系统
        system = AutoTradingSystem(target_stock)
        
        # 检查系统就绪
        if not system.check_system_ready():
            print("✗ 系统就绪检查失败")
            return False
        
        print("✓ 系统就绪检查通过")
        
        # 启动系统
        print("\n正在启动交易系统...")
        print("按 Ctrl+C 停止系统")
        
        system.start()
        
    except KeyboardInterrupt:
        print("\n\n用户中断，正在停止系统...")
        logger.info("用户手动停止交易系统")
        
    except Exception as e:
        print(f"\n✗ 交易系统运行错误: {e}")
        logger.error(f"交易系统运行错误: {e}")
        return False
    
    return True

def show_banner():
    """显示启动横幅"""
    banner = """
╔══════════════════════════════════════════════════════════════╗
║                    单只股票自动交易系统                        ║
║                  Single Stock Auto Trading System            ║
║                                                              ║
║  基于miniQMT XtQuant API的Python函数式编程交易系统            ║
║                                                              ║
║  功能特性:                                                    ║
║  • 实时行情数据获取                                           ║
║  • 多种技术指标分析                                           ║
║  • 智能交易策略                                               ║
║  • 完善的风险控制                                             ║
║  • 自动化交易执行                                             ║
║  • 历史回测验证                                               ║
║                                                              ║
║  ⚠️  风险提示: 投资有风险，使用需谨慎                          ║
╚══════════════════════════════════════════════════════════════╝
"""
    print(banner)

def show_menu():
    """显示菜单"""
    menu = """
请选择操作:

1. 启动自动交易系统
2. 运行策略回测
3. 查看系统状态
4. 初始化数据库
5. 运行使用示例
6. 退出

请输入选项 (1-6): """
    
    return input(menu).strip()

def run_backtest_menu():
    """回测菜单"""
    from backtest import run_backtest, print_backtest_summary
    
    print("\n=== 策略回测 ===")
    
    stock_code = input(f"股票代码 (默认: {TRADING_CONFIG['target_stock']}): ").strip()
    if not stock_code:
        stock_code = TRADING_CONFIG['target_stock']
    
    start_date = input("开始日期 (YYYYMMDD, 默认: 20240101): ").strip()
    if not start_date:
        start_date = "20240101"
    
    end_date = input("结束日期 (YYYYMMDD, 默认: 20241231): ").strip()
    if not end_date:
        end_date = "20241231"
    
    initial_capital = input("初始资金 (默认: 100000): ").strip()
    if not initial_capital:
        initial_capital = 100000
    else:
        initial_capital = float(initial_capital)
    
    try:
        print(f"\n开始回测: {stock_code}, {start_date} - {end_date}")
        result = run_backtest(stock_code, start_date, end_date, initial_capital)
        print_backtest_summary(result)
        
    except Exception as e:
        print(f"回测失败: {e}")

def show_system_status():
    """显示系统状态"""
    print("\n=== 系统状态 ===")
    
    # 检查数据库
    try:
        db = DatabaseManager()
        result = db.execute_query("SELECT COUNT(*) as count FROM market_data")
        if result:
            print(f"✓ 数据库连接正常，行情数据: {result[0]['count']} 条")
    except Exception as e:
        print(f"✗ 数据库连接失败: {e}")
    
    # 检查配置
    print(f"✓ 目标股票: {TRADING_CONFIG['target_stock']}")
    print(f"✓ 交易账户: {MINIQMT_CONFIG['account_id']}")
    print(f"✓ 最大仓位比例: {TRADING_CONFIG['max_position_ratio']}")
    print(f"✓ 止损比例: {TRADING_CONFIG['stop_loss_ratio']}")
    print(f"✓ 止盈比例: {TRADING_CONFIG['take_profit_ratio']}")

def run_examples():
    """运行示例"""
    print("\n=== 运行使用示例 ===")
    
    try:
        from example import main as run_examples_main
        run_examples_main()
    except Exception as e:
        print(f"运行示例失败: {e}")

def main():
    """主函数"""
    # 设置日志
    setup_logging()
    
    # 显示横幅
    show_banner()
    
    # 检查前置条件
    if not check_prerequisites():
        print("\n请解决上述问题后重新启动")
        return
    
    # 主循环
    while True:
        try:
            choice = show_menu()
            
            if choice == '1':
                # 启动自动交易系统
                if initialize_system():
                    start_trading_system()
                
            elif choice == '2':
                # 运行策略回测
                run_backtest_menu()
                
            elif choice == '3':
                # 查看系统状态
                show_system_status()
                
            elif choice == '4':
                # 初始化数据库
                if initialize_system():
                    print("✓ 数据库初始化完成")
                
            elif choice == '5':
                # 运行使用示例
                run_examples()
                
            elif choice == '6':
                # 退出
                print("\n感谢使用，再见!")
                break
                
            else:
                print("\n无效选项，请重新选择")
            
            input("\n按回车键继续...")
            
        except KeyboardInterrupt:
            print("\n\n用户中断，退出程序")
            break
        except Exception as e:
            print(f"\n程序错误: {e}")
            logger.error(f"程序错误: {e}")

if __name__ == "__main__":
    main()