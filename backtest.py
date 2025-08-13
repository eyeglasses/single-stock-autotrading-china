# -*- coding: utf-8 -*-
"""
回测模块
用于验证策略的历史表现
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, Any, List, Tuple, Optional
from dataclasses import dataclass
from loguru import logger

from data_fetcher import get_market_data
from strategy import StrategyManager, SignalType
from risk_control import PositionManager, StopLossManager
from config import TRADING_CONFIG, RISK_CONFIG, STRATEGY_CONFIG

@dataclass
class Trade:
    """交易记录"""
    timestamp: datetime
    stock_code: str
    action: str  # 'buy' or 'sell'
    price: float
    volume: int
    amount: float
    commission: float = 0.0
    reason: str = ""

@dataclass
class Position:
    """持仓记录"""
    stock_code: str
    volume: int
    avg_price: float
    market_value: float
    unrealized_pnl: float
    realized_pnl: float = 0.0

@dataclass
class BacktestResult:
    """回测结果"""
    start_date: datetime
    end_date: datetime
    initial_capital: float
    final_capital: float
    total_return: float
    annual_return: float
    max_drawdown: float
    sharpe_ratio: float
    win_rate: float
    profit_factor: float
    total_trades: int
    winning_trades: int
    losing_trades: int
    avg_win: float
    avg_loss: float
    trades: List[Trade]
    daily_returns: pd.Series
    equity_curve: pd.Series

class BacktestEngine:
    """回测引擎"""
    
    def __init__(self, 
                 stock_code: str,
                 initial_capital: float = 100000.0,
                 commission_rate: float = 0.0003):
        self.stock_code = stock_code
        self.initial_capital = initial_capital
        self.commission_rate = commission_rate
        
        # 交易配置
        self.trading_config = TRADING_CONFIG
        self.risk_config = RISK_CONFIG
        
        # 策略和风控
        self.strategy_manager = StrategyManager(stock_code)
        self.position_manager = PositionManager()
        self.stop_loss_manager = StopLossManager()
        
        # 回测状态
        self.current_capital = initial_capital
        self.current_position = None
        self.trades = []
        self.daily_equity = []
        self.daily_returns = []
        
    def run_backtest(self, 
                    start_date: str, 
                    end_date: str,
                    rebalance_freq: str = 'daily') -> BacktestResult:
        """运行回测
        
        Args:
            start_date: 开始日期 (YYYYMMDD)
            end_date: 结束日期 (YYYYMMDD)
            rebalance_freq: 重新平衡频率 ('daily', 'weekly', 'monthly')
            
        Returns:
            BacktestResult: 回测结果
        """
        try:
            logger.info(f"开始回测: {self.stock_code}, {start_date} - {end_date}")
            
            # 获取历史数据
            df = get_market_data(
                stock_code=self.stock_code,
                period='1d',
                count=-1  # 获取全部历史数据
            )
            
            if df is None or df.empty:
                raise ValueError("无法获取历史数据")
            
            # 重置状态
            self._reset_state()
            
            # 逐日回测
            for i in range(len(df)):
                current_date = df.index[i]
                current_data = df.iloc[:i+1]  # 截至当前日期的所有数据
                current_price = df.iloc[i]['close_price']
                
                # 跳过数据不足的情况
                if len(current_data) < 20:
                    self._update_daily_equity(current_date, current_price)
                    continue
                
                # 检查止损止盈
                if self.current_position:
                    stop_action = self._check_stop_conditions(current_price)
                    if stop_action:
                        self._execute_trade(current_date, current_price, stop_action)
                
                # 生成交易信号
                signal = self._generate_signal(current_data)
                
                if signal:
                    # 执行交易决策
                    self._execute_trading_logic(current_date, current_price, signal)
                
                # 更新每日权益
                self._update_daily_equity(current_date, current_price)
            
            # 计算回测结果
            result = self._calculate_results(start_date, end_date)
            
            logger.info(f"回测完成: 总收益率 {result.total_return:.2%}, 最大回撤 {result.max_drawdown:.2%}")
            
            return result
            
        except Exception as e:
            logger.error(f"回测执行时出错: {e}")
            raise
    
    def _reset_state(self):
        """重置回测状态"""
        self.current_capital = self.initial_capital
        self.current_position = None
        self.trades = []
        self.daily_equity = []
        self.daily_returns = []
    
    def _generate_signal(self, df: pd.DataFrame) -> Optional[Dict[str, Any]]:
        """生成交易信号
        
        Args:
            df: 历史数据
            
        Returns:
            Dict: 交易信号
        """
        try:
            # 使用策略管理器生成信号
            # 这里需要模拟策略管理器的行为
            signal_type, signal_strength, reason = self.strategy_manager.technical_strategy.analyze_trend(df)
            
            # 获取当前价格
            current_price = df.iloc[-1]['close_price']
            
            return {
                'signal_type': signal_type.value,
                'signal_strength': signal_strength,
                'reason': reason,
                'price': current_price
            }
            
        except Exception as e:
            logger.error(f"生成信号时出错: {e}")
            return None
    
    def _execute_trading_logic(self, date: datetime, price: float, signal: Dict[str, Any]):
        """执行交易逻辑
        
        Args:
            date: 交易日期
            price: 当前价格
            signal: 交易信号
        """
        signal_type = signal.get('signal_type')
        signal_strength = signal.get('signal_strength', 0)
        
        if signal_type in ['buy', 'strong_buy'] and not self.current_position:
            self._execute_buy(date, price, signal_strength, signal.get('reason', ''))
        elif signal_type in ['sell', 'strong_sell'] and self.current_position:
            self._execute_sell(date, price, signal_strength, signal.get('reason', ''))
    
    def _execute_buy(self, date: datetime, price: float, signal_strength: float, reason: str):
        """执行买入
        
        Args:
            date: 交易日期
            price: 买入价格
            signal_strength: 信号强度
            reason: 交易原因
        """
        try:
            # 计算仓位大小
            available_cash = self.current_capital
            
            # 简化的仓位计算
            base_ratio = self.trading_config['position_ratio']
            adjusted_ratio = base_ratio * signal_strength
            max_ratio = self.trading_config['max_single_position']
            position_ratio = min(adjusted_ratio, max_ratio)
            
            target_amount = available_cash * position_ratio
            volume = int(target_amount / price / 100) * 100  # 整手
            
            if volume < 100:  # 至少一手
                return
            
            actual_amount = volume * price
            commission = actual_amount * self.commission_rate
            total_cost = actual_amount + commission
            
            if total_cost > available_cash:
                return
            
            # 执行买入
            self.current_capital -= total_cost
            self.current_position = Position(
                stock_code=self.stock_code,
                volume=volume,
                avg_price=price,
                market_value=actual_amount,
                unrealized_pnl=0.0
            )
            
            # 记录交易
            # 确保 timestamp 是 datetime 对象
            if hasattr(date, 'to_pydatetime'):
                timestamp = date.to_pydatetime()
            elif isinstance(date, datetime):
                timestamp = date
            else:
                timestamp = datetime.now()
            
            trade = Trade(
                timestamp=timestamp,
                stock_code=self.stock_code,
                action='buy',
                price=price,
                volume=volume,
                amount=actual_amount,
                commission=commission,
                reason=reason
            )
            self.trades.append(trade)
            
            # 确保 date 是 datetime 对象
            if hasattr(date, 'strftime'):
                date_str = date.strftime('%Y-%m-%d')
            else:
                date_str = str(date)
            logger.debug(f"买入: {date_str}, 价格: {price:.2f}, 数量: {volume}, 金额: {actual_amount:.2f}")
            
        except Exception as e:
            logger.error(f"执行买入时出错: {e}")
    
    def _execute_sell(self, date: datetime, price: float, signal_strength: float, reason: str):
        """执行卖出
        
        Args:
            date: 交易日期
            price: 卖出价格
            signal_strength: 信号强度
            reason: 交易原因
        """
        try:
            if not self.current_position:
                return
            
            # 根据信号强度决定卖出比例
            if signal_strength >= 0.8:  # 强卖出信号，全部卖出
                sell_ratio = 1.0
            elif signal_strength >= 0.5:  # 中等信号，卖出一半
                sell_ratio = 0.5
            else:  # 弱信号，卖出1/3
                sell_ratio = 0.33
            
            sell_volume = int(self.current_position.volume * sell_ratio / 100) * 100
            
            if sell_volume < 100:
                return
            
            sell_amount = sell_volume * price
            commission = sell_amount * self.commission_rate
            net_amount = sell_amount - commission
            
            # 计算盈亏
            cost_basis = sell_volume * self.current_position.avg_price
            realized_pnl = net_amount - cost_basis
            
            # 更新资金和持仓
            self.current_capital += net_amount
            
            if sell_volume == self.current_position.volume:
                # 全部卖出
                self.current_position = None
            else:
                # 部分卖出
                self.current_position.volume -= sell_volume
                self.current_position.market_value = self.current_position.volume * price
            
            # 记录交易
            # 确保 timestamp 是 datetime 对象
            if hasattr(date, 'to_pydatetime'):
                timestamp = date.to_pydatetime()
            elif isinstance(date, datetime):
                timestamp = date
            else:
                timestamp = datetime.now()
            
            trade = Trade(
                timestamp=timestamp,
                stock_code=self.stock_code,
                action='sell',
                price=price,
                volume=sell_volume,
                amount=sell_amount,
                commission=commission,
                reason=reason
            )
            self.trades.append(trade)
            
            # 确保 date 是 datetime 对象
            if hasattr(date, 'strftime'):
                date_str = date.strftime('%Y-%m-%d')
            else:
                date_str = str(date)
            logger.debug(f"卖出: {date_str}, 价格: {price:.2f}, 数量: {sell_volume}, 盈亏: {realized_pnl:.2f}")
            
        except Exception as e:
            logger.error(f"执行卖出时出错: {e}")
    
    def _check_stop_conditions(self, current_price: float) -> Optional[str]:
        """检查止损止盈条件
        
        Args:
            current_price: 当前价格
            
        Returns:
            str: 止损止盈动作 ('stop_loss', 'take_profit', None)
        """
        if not self.current_position:
            return None
        
        entry_price = self.current_position.avg_price
        
        # 计算止损止盈价格
        stop_loss_price = self.stop_loss_manager.calculate_stop_loss_price(entry_price, 'buy')
        take_profit_price = self.stop_loss_manager.calculate_take_profit_price(entry_price, 'buy')
        
        if current_price <= stop_loss_price:
            return 'stop_loss'
        elif current_price >= take_profit_price:
            return 'take_profit'
        
        return None
    
    def _execute_trade(self, date: datetime, price: float, action: str):
        """执行止损止盈交易
        
        Args:
            date: 交易日期
            price: 交易价格
            action: 交易动作
        """
        if action in ['stop_loss', 'take_profit']:
            self._execute_sell(date, price, 1.0, action)
    
    def _update_daily_equity(self, date: datetime, price: float):
        """更新每日权益
        
        Args:
            date: 日期
            price: 当前价格
        """
        # 计算总权益
        cash = self.current_capital
        position_value = 0.0
        
        if self.current_position:
            position_value = self.current_position.volume * price
            self.current_position.market_value = position_value
            self.current_position.unrealized_pnl = position_value - (self.current_position.volume * self.current_position.avg_price)
        
        total_equity = cash + position_value
        
        # 记录每日权益
        self.daily_equity.append({
            'date': date,
            'equity': total_equity,
            'cash': cash,
            'position_value': position_value
        })
        
        # 计算日收益率
        if len(self.daily_equity) > 1:
            prev_equity = self.daily_equity[-2]['equity']
            daily_return = (total_equity - prev_equity) / prev_equity
            self.daily_returns.append(daily_return)
        else:
            self.daily_returns.append(0.0)
    
    def _calculate_results(self, start_date: str, end_date: str) -> BacktestResult:
        """计算回测结果
        
        Args:
            start_date: 开始日期
            end_date: 结束日期
            
        Returns:
            BacktestResult: 回测结果
        """
        if not self.daily_equity:
            raise ValueError("无权益数据")
        
        # 基本统计
        final_equity = self.daily_equity[-1]['equity']
        total_return = (final_equity - self.initial_capital) / self.initial_capital
        
        # 计算年化收益率
        start_dt = datetime.strptime(start_date, '%Y%m%d')
        end_dt = datetime.strptime(end_date, '%Y%m%d')
        days = (end_dt - start_dt).days
        years = days / 365.25
        annual_return = (1 + total_return) ** (1 / years) - 1 if years > 0 else 0
        
        # 权益曲线
        equity_series = pd.Series(
            [eq['equity'] for eq in self.daily_equity],
            index=[eq['date'] for eq in self.daily_equity]
        )
        
        # 日收益率序列
        returns_series = pd.Series(self.daily_returns[1:])  # 跳过第一个0值
        
        # 最大回撤
        max_drawdown = self._calculate_max_drawdown(equity_series)
        
        # 夏普比率
        sharpe_ratio = self._calculate_sharpe_ratio(returns_series)
        
        # 交易统计
        trade_stats = self._calculate_trade_statistics()
        
        return BacktestResult(
            start_date=start_dt,
            end_date=end_dt,
            initial_capital=self.initial_capital,
            final_capital=final_equity,
            total_return=total_return,
            annual_return=annual_return,
            max_drawdown=max_drawdown,
            sharpe_ratio=sharpe_ratio,
            win_rate=trade_stats['win_rate'],
            profit_factor=trade_stats['profit_factor'],
            total_trades=trade_stats['total_trades'],
            winning_trades=trade_stats['winning_trades'],
            losing_trades=trade_stats['losing_trades'],
            avg_win=trade_stats['avg_win'],
            avg_loss=trade_stats['avg_loss'],
            trades=self.trades,
            daily_returns=returns_series,
            equity_curve=equity_series
        )
    
    def _calculate_max_drawdown(self, equity_series: pd.Series) -> float:
        """计算最大回撤"""
        peak = equity_series.expanding().max()
        drawdown = (equity_series - peak) / peak
        return abs(drawdown.min())
    
    def _calculate_sharpe_ratio(self, returns_series: pd.Series, risk_free_rate: float = 0.03) -> float:
        """计算夏普比率"""
        if len(returns_series) == 0 or returns_series.std() == 0:
            return 0.0
        
        excess_returns = returns_series.mean() * 252 - risk_free_rate  # 年化
        volatility = returns_series.std() * np.sqrt(252)  # 年化波动率
        
        return excess_returns / volatility if volatility > 0 else 0.0
    
    def _calculate_trade_statistics(self) -> Dict[str, Any]:
        """计算交易统计"""
        if not self.trades:
            return {
                'total_trades': 0,
                'winning_trades': 0,
                'losing_trades': 0,
                'win_rate': 0.0,
                'avg_win': 0.0,
                'avg_loss': 0.0,
                'profit_factor': 0.0
            }
        
        # 配对买卖交易
        buy_trades = [t for t in self.trades if t.action == 'buy']
        sell_trades = [t for t in self.trades if t.action == 'sell']
        
        trade_pairs = []
        for buy_trade in buy_trades:
            # 找到对应的卖出交易
            matching_sells = [s for s in sell_trades if s.timestamp > buy_trade.timestamp]
            if matching_sells:
                sell_trade = matching_sells[0]  # 取第一个
                pnl = (sell_trade.price - buy_trade.price) * min(buy_trade.volume, sell_trade.volume) - buy_trade.commission - sell_trade.commission
                trade_pairs.append(pnl)
        
        if not trade_pairs:
            return {
                'total_trades': len(self.trades),
                'winning_trades': 0,
                'losing_trades': 0,
                'win_rate': 0.0,
                'avg_win': 0.0,
                'avg_loss': 0.0,
                'profit_factor': 0.0
            }
        
        winning_trades = [p for p in trade_pairs if p > 0]
        losing_trades = [p for p in trade_pairs if p < 0]
        
        total_trades = len(trade_pairs)
        win_count = len(winning_trades)
        loss_count = len(losing_trades)
        win_rate = win_count / total_trades if total_trades > 0 else 0
        
        avg_win = np.mean(winning_trades) if winning_trades else 0
        avg_loss = abs(np.mean(losing_trades)) if losing_trades else 0
        
        total_wins = sum(winning_trades) if winning_trades else 0
        total_losses = abs(sum(losing_trades)) if losing_trades else 0
        profit_factor = total_wins / total_losses if total_losses > 0 else float('inf')
        
        return {
            'total_trades': total_trades,
            'winning_trades': win_count,
            'losing_trades': loss_count,
            'win_rate': win_rate,
            'avg_win': avg_win,
            'avg_loss': avg_loss,
            'profit_factor': profit_factor
        }

def run_backtest(stock_code: str, 
                start_date: str, 
                end_date: str,
                initial_capital: float = 100000.0) -> BacktestResult:
    """运行回测的函数式接口
    
    Args:
        stock_code: 股票代码
        start_date: 开始日期 (YYYYMMDD)
        end_date: 结束日期 (YYYYMMDD)
        initial_capital: 初始资金
        
    Returns:
        BacktestResult: 回测结果
    """
    engine = BacktestEngine(stock_code, initial_capital)
    return engine.run_backtest(start_date, end_date)

def print_backtest_summary(result: BacktestResult):
    """打印回测摘要
    
    Args:
        result: 回测结果
    """
    print("\n" + "="*50)
    print("回测结果摘要")
    print("="*50)
    print(f"回测期间: {result.start_date.strftime('%Y-%m-%d')} 至 {result.end_date.strftime('%Y-%m-%d')}")
    print(f"初始资金: {result.initial_capital:,.2f}")
    print(f"最终资金: {result.final_capital:,.2f}")
    print(f"总收益率: {result.total_return:.2%}")
    print(f"年化收益率: {result.annual_return:.2%}")
    print(f"最大回撤: {result.max_drawdown:.2%}")
    print(f"夏普比率: {result.sharpe_ratio:.2f}")
    print(f"胜率: {result.win_rate:.2%}")
    print(f"盈亏比: {result.profit_factor:.2f}")
    print(f"总交易次数: {result.total_trades}")
    print(f"盈利交易: {result.winning_trades}")
    print(f"亏损交易: {result.losing_trades}")
    print(f"平均盈利: {result.avg_win:.2f}")
    print(f"平均亏损: {result.avg_loss:.2f}")
    print("="*50)

if __name__ == "__main__":
    # 示例用法
    stock_code = "000001.SZ"  # 平安银行
    start_date = "20230101"
    end_date = "20231231"
    
    try:
        result = run_backtest(stock_code, start_date, end_date)
        print_backtest_summary(result)
    except Exception as e:
        logger.error(f"回测失败: {e}")