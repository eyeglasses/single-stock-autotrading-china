# -*- coding: utf-8 -*-
"""
单股票自动交易系统主程序
整合数据获取、策略分析、风险控制、交易执行等功能
"""

import time
import schedule
from datetime import datetime, timedelta
from typing import Dict, Any, Optional
from loguru import logger
from functools import wraps

# 导入各功能模块
from config import (
    TRADING_CONFIG, RISK_CONFIG, STRATEGY_CONFIG, 
    LOG_CONFIG, DATA_CONFIG
)
from database import get_db_manager
from data_fetcher import (
    get_market_data, get_realtime_data, 
    update_stock_data, subscribe_realtime_data
)
from strategy import (
    get_trading_signal, analyze_stock_trend,
    SignalType, StrategyManager
)
from risk_control import (
    check_trading_risk, calculate_position_size,
    check_stop_loss_take_profit, is_trading_allowed
)
from trader import (
    buy_stock, sell_stock, get_account_asset,
    get_position, cancel_order, stock_trader
)

# 配置日志
import os
log_dir = LOG_CONFIG.get('log_dir', './logs')
os.makedirs(log_dir, exist_ok=True)

logger.add(
    os.path.join(log_dir, 'trading_{time:YYYY-MM-DD}.log'),
    rotation=LOG_CONFIG.get('rotation', '1 day'),
    retention=LOG_CONFIG.get('retention', '30 days'),
    level=LOG_CONFIG.get('level', 'INFO'),
    format=LOG_CONFIG.get('format', '{time:YYYY-MM-DD HH:mm:ss} | {level} | {name}:{function}:{line} | {message}')
)

def trading_session_only(func):
    """仅在交易时间执行的装饰器"""
    @wraps(func)
    def wrapper(*args, **kwargs):
        now = datetime.now()
        current_time = now.time()
        
        # A股交易时间：9:30-11:30, 13:00-15:00
        morning_start = datetime.strptime('09:30', '%H:%M').time()
        morning_end = datetime.strptime('11:30', '%H:%M').time()
        afternoon_start = datetime.strptime('13:00', '%H:%M').time()
        afternoon_end = datetime.strptime('15:00', '%H:%M').time()
        
        # 检查是否为工作日
        if now.weekday() >= 5:  # 周六、周日
            logger.info("非交易日，跳过执行")
            return None
        
        # 检查是否在交易时间
        in_morning = morning_start <= current_time <= morning_end
        in_afternoon = afternoon_start <= current_time <= afternoon_end
        
        if not (in_morning or in_afternoon):
            logger.info(f"非交易时间 {current_time}，跳过执行")
            return None
        
        return func(*args, **kwargs)
    return wrapper

class AutoTradingSystem:
    """自动交易系统主类"""
    
    def __init__(self, stock_code: str):
        self.stock_code = stock_code
        self.trading_config = TRADING_CONFIG
        self.risk_config = RISK_CONFIG
        self.strategy_config = STRATEGY_CONFIG
        
        # 系统状态
        self.is_running = False
        self.last_signal = None
        self.last_trade_time = None
        self.daily_trade_count = 0
        
        # 策略管理器
        self.strategy_manager = StrategyManager(stock_code)
        
        logger.info(f"自动交易系统初始化完成，目标股票: {stock_code}")
    
    def start(self):
        """启动自动交易系统"""
        try:
            logger.info("启动自动交易系统...")
            
            # 检查系统连接
            if not self._check_system_ready():
                logger.error("系统未就绪，无法启动")
                return False
            
            self.is_running = True
            
            # 设置定时任务
            self._setup_scheduled_tasks()
            
            # 初始化数据
            self._initialize_data()
            
            logger.info("自动交易系统启动成功")
            
            # 主循环
            self._run_main_loop()
            
        except Exception as e:
            logger.error(f"启动自动交易系统时出错: {e}")
            self.stop()
            return False
    
    def stop(self):
        """停止自动交易系统"""
        logger.info("停止自动交易系统...")
        self.is_running = False
        
        # 停止交易器
        if stock_trader:
            stock_trader.stop()
        
        logger.info("自动交易系统已停止")
    
    def check_system_ready(self) -> bool:
        """检查系统是否就绪（公有方法）"""
        return self._check_system_ready()
    
    def daily_initialization(self):
        """每日初始化（公共方法）"""
        return self._daily_initialization()
    
    def check_trading_signals(self):
        """检查交易信号（公共方法）"""
        return self._scheduled_signal_check()
    
    def risk_check(self):
        """风险检查（公共方法）"""
        return self._scheduled_risk_check()
    
    def daily_summary(self):
        """每日总结（公共方法）"""
        return self._daily_summary()
    
    def _check_system_ready(self) -> bool:
        """检查系统是否就绪"""
        try:
            # 检查数据库连接
            db_manager = get_db_manager()
            if not db_manager.test_connection():
                logger.error("数据库连接失败")
                return False
            logger.info("数据库连接正常")
            
            # 检查交易连接
            from trader import check_trader_connection, reconnect_trader, get_trader_status
            
            trader_status = get_trader_status()
            logger.info(f"交易器状态: {trader_status}")
            
            if not trader_status['is_connected']:
                logger.warning("交易连接未建立，尝试重新连接...")
                if reconnect_trader():
                    logger.info("交易连接重连成功")
                else:
                    logger.error("交易连接重连失败")
                    logger.error("请检查：")
                    logger.error("1. miniQMT是否已启动")
                    logger.error("2. config.py中的路径和账户配置是否正确")
                    logger.error("3. 网络连接是否正常")
                    return False
            
            # 验证交易连接
            if not check_trader_connection():
                logger.error("交易连接验证失败")
                return False
            logger.info("交易连接验证成功")
            
            # 检查账户资产
            asset = get_account_asset()
            if not asset:
                logger.error("无法获取账户资产")
                return False
            
            logger.info(f"账户总资产: {asset.get('total_asset', 0):.2f}")
            logger.info(f"可用资金: {asset.get('available_cash', 0):.2f}")
            
            return True
            
        except Exception as e:
            logger.error(f"系统就绪检查时出错: {e}")
            return False
    
    def _setup_scheduled_tasks(self):
        """设置定时任务"""
        # 每分钟检查一次交易信号（仅交易时间）
        schedule.every(1).minutes.do(self._scheduled_signal_check)
        
        # 每5分钟更新一次数据
        schedule.every(5).minutes.do(self._scheduled_data_update)
        
        # 每10分钟进行一次风险检查
        schedule.every(10).minutes.do(self._scheduled_risk_check)
        
        # 每30分钟检查止损止盈
        schedule.every(30).minutes.do(self._scheduled_stop_check)
        
        # 每日开盘前数据初始化
        schedule.every().day.at("09:00").do(self._daily_initialization)
        
        # 每日收盘后总结
        schedule.every().day.at("15:30").do(self._daily_summary)
        
        logger.info("定时任务设置完成")
    
    def _initialize_data(self):
        """初始化数据"""
        try:
            logger.info("初始化历史数据...")
            
            # 更新股票数据（获取最近60天的数据）
            success = update_stock_data(self.stock_code, 256)
            
            if success:
                logger.info("历史数据初始化完成")
            else:
                logger.warning("历史数据初始化失败")
            
            # 订阅实时数据
            subscribe_realtime_data(self.stock_code, None)
            
        except Exception as e:
            logger.error(f"初始化数据时出错: {e}")
    
    def _run_main_loop(self):
        """主循环"""
        logger.info("进入主循环...")
        
        while self.is_running:
            try:
                # 执行定时任务
                schedule.run_pending()
                
                # 短暂休眠
                time.sleep(1)
                
            except KeyboardInterrupt:
                logger.info("接收到停止信号")
                break
            except Exception as e:
                logger.error(f"主循环执行时出错: {e}")
                time.sleep(5)  # 出错后等待5秒
    
    @trading_session_only
    def _scheduled_signal_check(self):
        """定时信号检查"""
        try:
            logger.debug("执行定时信号检查...")
            
            # 检查是否允许交易
            if not is_trading_allowed(self.stock_code):
                logger.warning("风险控制阻止交易")
                return
            
            # 获取交易信号
            signal = self.strategy_manager.get_combined_signal()
            
            if not signal:
                logger.warning("无法获取交易信号")
                return
            
            signal_type = signal.get('signal_type')
            signal_strength = signal.get('signal_strength', 0)
            current_price = signal.get('price', 0)
            
            logger.info(f"交易信号: {signal_type}, 强度: {signal_strength:.2f}, 价格: {current_price:.2f}")
            
            # 执行交易决策
            self._execute_trading_decision(signal)
            
        except Exception as e:
            logger.error(f"定时信号检查时出错: {e}")
    
    def _scheduled_data_update(self):
        """定时数据更新"""
        try:
            logger.debug("执行定时数据更新...")
            
            # 更新最新数据（更新最近1天数据）
            update_stock_data(self.stock_code, 1)
            
        except Exception as e:
            logger.error(f"定时数据更新时出错: {e}")
    
    def _scheduled_risk_check(self):
        """定时风险检查"""
        try:
            logger.debug("执行定时风险检查...")
            
            risk_result = check_trading_risk(self.stock_code)
            
            if risk_result.get('overall_risk_level') in ['high', 'critical']:
                logger.warning(f"风险警告: {risk_result.get('risk_summary')}")
                
                # 如果风险过高，考虑减仓或停止交易
                if risk_result.get('required_action') == 'emergency_exit':
                    self._emergency_exit()
                elif risk_result.get('required_action') == 'reduce':
                    self._reduce_position()
            
        except Exception as e:
            logger.error(f"定时风险检查时出错: {e}")
    
    @trading_session_only
    def _scheduled_stop_check(self):
        """定时止损止盈检查"""
        try:
            logger.debug("执行定时止损止盈检查...")
            
            # 获取实时价格
            real_time_data = get_realtime_data(self.stock_code)
            if real_time_data is None or not isinstance(real_time_data, dict):
                logger.warning("无法获取实时价格")
                return
            
            current_price = real_time_data.get('price', 0)
            if current_price == 0:
                logger.warning("实时价格为零")
                return
            
            # 检查止损止盈条件
            stop_result = check_stop_loss_take_profit(self.stock_code, current_price)
            
            action = stop_result.get('action')
            if action in ['stop_loss', 'take_profit']:
                logger.info(f"触发{action}: {stop_result.get('reason')}")
                
                # 执行止损止盈
                volume = stop_result.get('volume', 0)
                if volume > 0:
                    order_id = sell_stock(self.stock_code, current_price, volume)
                    if order_id:
                        logger.info(f"{action}订单提交成功: {order_id}")
                    else:
                        logger.error(f"{action}订单提交失败")
            
        except Exception as e:
            logger.error(f"定时止损止盈检查时出错: {e}")
    
    def _daily_initialization(self):
        """每日初始化"""
        try:
            logger.info("执行每日初始化...")
            
            # 重置日交易计数
            self.daily_trade_count = 0
            
            # 更新历史数据（更新最近5天数据）
            update_stock_data(self.stock_code, 5)
            
            # 输出账户状态
            asset = get_account_asset()
            if asset:
                logger.info(f"开盘前账户状态 - 总资产: {asset.get('total_asset', 0):.2f}, 可用资金: {asset.get('available_cash', 0):.2f}")
            
            # 输出持仓状态
            position = get_position(self.stock_code)
            if position:
                logger.info(f"开盘前持仓 - 股数: {position.get('volume', 0)}, 市值: {position.get('market_value', 0):.2f}")
            
        except Exception as e:
            logger.error(f"每日初始化时出错: {e}")
    
    def _daily_summary(self):
        """每日总结"""
        try:
            logger.info("执行每日总结...")
            
            today = datetime.now().date()
            
            # 获取数据库管理器
            db_manager = get_db_manager()
            
            # 获取今日交易记录
            today_trades = db_manager.get_trade_records_by_date(today, self.stock_code)
            
            if today_trades:
                total_pnl = sum(trade.get('profit_loss', 0) for trade in today_trades)
                trade_count = len(today_trades)
                
                logger.info(f"今日交易总结 - 交易次数: {trade_count}, 总盈亏: {total_pnl:.2f}")
            else:
                logger.info("今日无交易记录")
            
            # 输出最终账户状态
            asset = get_account_asset()
            if asset:
                logger.info(f"收盘后账户状态 - 总资产: {asset.get('total_asset', 0):.2f}, 可用资金: {asset.get('available_cash', 0):.2f}")
            
        except Exception as e:
            logger.error(f"每日总结时出错: {e}")
    
    def _execute_trading_decision(self, signal: Dict[str, Any]):
        """执行交易决策
        
        Args:
            signal: 交易信号字典
        """
        try:
            signal_type = signal.get('signal_type')
            signal_strength = signal.get('signal_strength', 0)
            current_price = signal.get('price', 0)
            
            if signal_type in ['buy', 'strong_buy']:
                self._execute_buy_decision(signal_strength, current_price)
            elif signal_type in ['sell', 'strong_sell']:
                self._execute_sell_decision(signal_strength, current_price)
            else:
                logger.debug(f"持有信号，无需交易: {signal_type}")
            
        except Exception as e:
            logger.error(f"执行交易决策时出错: {e}")
    
    def _execute_buy_decision(self, signal_strength: float, current_price: float):
        """执行买入决策"""
        try:
            # 检查是否已有持仓
            position = get_position(self.stock_code)
            if position and position.get('volume', 0) > 0:
                logger.info("已有持仓，跳过买入")
                return
            
            # 计算仓位大小
            position_info = calculate_position_size(self.stock_code, signal_strength, current_price)
            
            if 'error' in position_info:
                logger.error(f"计算仓位失败: {position_info['error']}")
                return
            
            volume = position_info.get('volume', 0)
            if volume == 0:
                logger.warning("计算得到的交易量为0")
                return
            
            # 执行买入
            order_id = buy_stock(self.stock_code, current_price, volume)
            
            if order_id:
                logger.info(f"买入订单提交成功: {order_id}, 股票: {self.stock_code}, 价格: {current_price}, 数量: {volume}")
                self.daily_trade_count += 1
                self.last_trade_time = datetime.now()
            else:
                logger.error("买入订单提交失败")
            
        except Exception as e:
            logger.error(f"执行买入决策时出错: {e}")
    
    def _execute_sell_decision(self, signal_strength: float, current_price: float):
        """执行卖出决策"""
        try:
            # 检查持仓
            position = get_position(self.stock_code)
            if not position or position.get('volume', 0) == 0:
                logger.info("无持仓，跳过卖出")
                return
            
            volume = position.get('can_use_volume', position.get('volume', 0))
            if volume == 0:
                logger.warning("可用持仓为0")
                return
            
            # 根据信号强度决定卖出比例
            if signal_strength >= 0.8:  # 强卖出信号，全部卖出
                sell_volume = volume
            elif signal_strength >= 0.5:  # 中等信号，卖出一半
                sell_volume = volume // 2
            else:  # 弱信号，卖出1/3
                sell_volume = volume // 3
            
            sell_volume = max(100, sell_volume // 100 * 100)  # 确保是整手
            
            # 执行卖出
            order_id = sell_stock(self.stock_code, current_price, sell_volume)
            
            if order_id:
                logger.info(f"卖出订单提交成功: {order_id}, 股票: {self.stock_code}, 价格: {current_price}, 数量: {sell_volume}")
                self.daily_trade_count += 1
                self.last_trade_time = datetime.now()
            else:
                logger.error("卖出订单提交失败")
            
        except Exception as e:
            logger.error(f"执行卖出决策时出错: {e}")
    
    def _emergency_exit(self):
        """紧急退出"""
        try:
            logger.warning("执行紧急退出...")
            
            position = get_position(self.stock_code)
            if position and position.get('volume', 0) > 0:
                volume = position.get('can_use_volume', position.get('volume', 0))
                
                # 获取实时价格
                real_time_data = get_realtime_data(self.stock_code)
                current_price = real_time_data.get('price', 0) if real_time_data is not None and isinstance(real_time_data, dict) else 0
                
                if current_price > 0 and volume > 0:
                    order_id = sell_stock(self.stock_code, current_price, volume)
                    if order_id:
                        logger.warning(f"紧急退出订单提交: {order_id}")
                    else:
                        logger.error("紧急退出订单提交失败")
            
        except Exception as e:
            logger.error(f"紧急退出时出错: {e}")
    
    def _reduce_position(self):
        """减仓"""
        try:
            logger.info("执行减仓...")
            
            position = get_position(self.stock_code)
            if position and position.get('volume', 0) > 0:
                volume = position.get('can_use_volume', position.get('volume', 0))
                reduce_volume = volume // 3  # 减仓1/3
                reduce_volume = max(100, reduce_volume // 100 * 100)  # 确保是整手
                
                # 获取实时价格
                real_time_data = get_realtime_data(self.stock_code)
                current_price = real_time_data.get('price', 0) if real_time_data is not None and isinstance(real_time_data, dict) else 0
                
                if current_price > 0 and reduce_volume > 0:
                    order_id = sell_stock(self.stock_code, current_price, reduce_volume)
                    if order_id:
                        logger.info(f"减仓订单提交: {order_id}, 减仓数量: {reduce_volume}")
                    else:
                        logger.error("减仓订单提交失败")
            
        except Exception as e:
            logger.error(f"减仓时出错: {e}")

def main():
    """主函数"""
    try:
        # 目标股票代码
        target_stock = TRADING_CONFIG['target_stock']
        
        if not target_stock:
            logger.error("未配置目标股票，请在config.py中设置target_stock")
            return
        
        logger.info(f"启动单股票自动交易系统，目标股票: {target_stock}")
        
        # 创建并启动交易系统
        trading_system = AutoTradingSystem(target_stock)
        trading_system.start()
        
    except KeyboardInterrupt:
        logger.info("接收到停止信号，正在退出...")
    except Exception as e:
        logger.error(f"主程序执行时出错: {e}")
    finally:
        logger.info("程序结束")

if __name__ == "__main__":
    main()