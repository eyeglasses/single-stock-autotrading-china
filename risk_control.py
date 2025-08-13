# -*- coding: utf-8 -*-
"""
风险控制模块
实现仓位管理、止损止盈、最大回撤控制等风险管理功能
"""

import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, Tuple, List
from enum import Enum
from loguru import logger
from functools import wraps

# from database import db_manager  # 延迟导入以避免卡住
from config import RISK_CONFIG, TRADING_CONFIG
from trader import get_account_asset, get_position

class RiskLevel(Enum):
    """风险等级枚举"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"

class RiskAction(Enum):
    """风险控制动作枚举"""
    ALLOW = "allow"
    REDUCE = "reduce"
    STOP = "stop"
    EMERGENCY_EXIT = "emergency_exit"

class PositionSizeType(Enum):
    """仓位大小类型枚举"""
    FIXED_AMOUNT = "fixed_amount"
    PERCENTAGE = "percentage"
    KELLY = "kelly"
    ATR_BASED = "atr_based"

def log_risk_event(func):
    """记录风险事件的装饰器"""
    @wraps(func)
    def wrapper(*args, **kwargs):
        result = func(*args, **kwargs)
        
        # 如果返回结果包含风险信息，记录到数据库
        if isinstance(result, dict) and 'risk_level' in result:
            try:
                # 映射函数名到简短的风险类型
                risk_type_map = {
                    'check_daily_loss_limit': 'daily_loss',
                    'check_drawdown_limit': 'drawdown',
                    'check_position_limit': 'position',
                    'check_trade_frequency': 'frequency',
                    'comprehensive_risk_check': 'comprehensive'
                }
                
                risk_data = {
                    'timestamp': datetime.now(),
                    'risk_type': risk_type_map.get(func.__name__, func.__name__[:50]),  # 限制长度
                    'risk_level': result['risk_level'],
                    'description': result.get('description', '')[:200],  # 限制描述长度
                    'action': result.get('action', ''),
                    'stock_code': result.get('stock_code', ''),
                    'details': str(result)[:500]  # 限制详情长度
                }
                from database import db_manager
                db_manager.insert_risk_control_log(risk_data)
            except Exception as e:
                logger.error(f"记录风险事件时出错: {e}")
        
        return result
    return wrapper

class PositionManager:
    """仓位管理器"""
    
    def __init__(self):
        self.config = RISK_CONFIG
        self.trading_config = TRADING_CONFIG
        
    def reset(self):
        """重置仓位管理器状态"""
        # 仓位管理器通常不需要重置状态，因为它是无状态的
        # 这个方法主要是为了兼容回测引擎的调用
        pass
        
    def calculate_position_size(self, 
                              stock_code: str, 
                              signal_strength: float, 
                              current_price: float,
                              method: PositionSizeType = PositionSizeType.PERCENTAGE) -> Dict[str, Any]:
        """计算仓位大小
        
        Args:
            stock_code: 股票代码
            signal_strength: 信号强度 (0-1)
            current_price: 当前价格
            method: 仓位计算方法
            
        Returns:
            Dict: 包含仓位信息的字典
        """
        try:
            # 获取账户资产
            asset = get_account_asset()
            if not asset:
                return {'error': '无法获取账户资产'}
            
            available_cash = asset.get('available_cash', 0)
            total_asset = asset.get('total_asset', 0)
            
            if method == PositionSizeType.FIXED_AMOUNT:
                return self._calculate_fixed_amount_position(stock_code, current_price, available_cash)
            elif method == PositionSizeType.PERCENTAGE:
                return self._calculate_percentage_position(stock_code, signal_strength, current_price, total_asset)
            elif method == PositionSizeType.KELLY:
                return self._calculate_kelly_position(stock_code, signal_strength, current_price, available_cash)
            elif method == PositionSizeType.ATR_BASED:
                return self._calculate_atr_position(stock_code, current_price, available_cash)
            else:
                return {'error': f'不支持的仓位计算方法: {method}'}
                
        except Exception as e:
            logger.error(f"计算仓位大小时出错: {e}")
            return {'error': str(e)}
    
    def _calculate_fixed_amount_position(self, stock_code: str, price: float, available_cash: float) -> Dict[str, Any]:
        """固定金额仓位计算"""
        target_amount = self.trading_config['trade_amount']
        
        if available_cash < target_amount:
            target_amount = available_cash * 0.95  # 留5%余量
        
        volume = int(target_amount / price / 100) * 100  # 整手
        actual_amount = volume * price
        
        return {
            'method': 'fixed_amount',
            'target_amount': target_amount,
            'actual_amount': actual_amount,
            'volume': volume,
            'price': price,
            'position_ratio': actual_amount / available_cash if available_cash > 0 else 0
        }
    
    def _calculate_percentage_position(self, stock_code: str, signal_strength: float, price: float, total_asset: float) -> Dict[str, Any]:
        """百分比仓位计算"""
        base_ratio = self.trading_config['position_ratio']
        
        # 根据信号强度调整仓位比例
        adjusted_ratio = base_ratio * signal_strength
        
        # 限制最大仓位
        max_ratio = self.trading_config['max_single_position']
        adjusted_ratio = min(adjusted_ratio, max_ratio)
        
        target_amount = total_asset * adjusted_ratio
        volume = int(target_amount / price / 100) * 100  # 整手
        actual_amount = volume * price
        
        return {
            'method': 'percentage',
            'signal_strength': signal_strength,
            'base_ratio': base_ratio,
            'adjusted_ratio': adjusted_ratio,
            'target_amount': target_amount,
            'actual_amount': actual_amount,
            'volume': volume,
            'price': price,
            'position_ratio': adjusted_ratio
        }
    
    def _calculate_kelly_position(self, stock_code: str, signal_strength: float, price: float, available_cash: float) -> Dict[str, Any]:
        """凯利公式仓位计算"""
        # 简化的凯利公式：f = (bp - q) / b
        # 其中 b = 赔率, p = 胜率, q = 败率
        
        # 基于历史数据估算胜率和赔率
        win_rate = 0.55 + signal_strength * 0.15  # 基础胜率55%，根据信号强度调整
        avg_win = 0.03  # 平均盈利3%
        avg_loss = 0.02  # 平均亏损2%
        
        odds = avg_win / avg_loss
        kelly_ratio = (odds * win_rate - (1 - win_rate)) / odds
        
        # 限制凯利比例
        kelly_ratio = max(0, min(kelly_ratio, self.trading_config['max_single_position']))
        
        target_amount = available_cash * kelly_ratio
        volume = int(target_amount / price / 100) * 100
        actual_amount = volume * price
        
        return {
            'method': 'kelly',
            'win_rate': win_rate,
            'odds': odds,
            'kelly_ratio': kelly_ratio,
            'target_amount': target_amount,
            'actual_amount': actual_amount,
            'volume': volume,
            'price': price,
            'position_ratio': kelly_ratio
        }
    
    def _calculate_atr_position(self, stock_code: str, price: float, available_cash: float) -> Dict[str, Any]:
        """基于ATR的仓位计算"""
        # 这里需要获取ATR数据，简化处理
        atr_ratio = 0.02  # 假设ATR为价格的2%
        risk_per_share = price * atr_ratio
        
        # 风险金额为可用资金的1%
        risk_amount = available_cash * 0.01
        volume = int(risk_amount / risk_per_share / 100) * 100
        actual_amount = volume * price
        
        return {
            'method': 'atr_based',
            'atr_ratio': atr_ratio,
            'risk_per_share': risk_per_share,
            'risk_amount': risk_amount,
            'target_amount': actual_amount,
            'actual_amount': actual_amount,
            'volume': volume,
            'price': price,
            'position_ratio': actual_amount / available_cash if available_cash > 0 else 0
        }

class RiskController:
    """风险控制器"""
    
    def __init__(self):
        self.config = RISK_CONFIG
        self.trading_config = TRADING_CONFIG
        self.position_manager = PositionManager()
        
    @log_risk_event
    def check_daily_loss_limit(self, stock_code: str = None) -> Dict[str, Any]:
        """检查日亏损限制
        
        Args:
            stock_code: 股票代码，None表示检查整体
            
        Returns:
            Dict: 风险检查结果
        """
        try:
            today = datetime.now().date()
            
            # 获取今日交易记录
            from database import db_manager
            today_trades = db_manager.get_trade_records_by_date(today, stock_code)
            
            if not today_trades:
                return {
                    'risk_level': RiskLevel.LOW.value,
                    'action': RiskAction.ALLOW.value,
                    'description': '今日无交易记录',
                    'stock_code': stock_code or 'ALL'
                }
            
            # 计算今日盈亏
            total_pnl = sum(trade.get('profit_loss', 0) for trade in today_trades)
            
            # 获取账户总资产
            asset = get_account_asset()
            total_asset = asset.get('total_asset', 0) if asset else 0
            
            if total_asset == 0:
                return {
                    'risk_level': RiskLevel.CRITICAL.value,
                    'action': RiskAction.STOP.value,
                    'description': '无法获取账户资产',
                    'stock_code': stock_code or 'ALL'
                }
            
            # 计算亏损比例
            loss_ratio = abs(total_pnl) / total_asset if total_pnl < 0 else 0
            max_daily_loss = self.config['max_daily_loss']
            
            if loss_ratio >= max_daily_loss:
                return {
                    'risk_level': RiskLevel.CRITICAL.value,
                    'action': RiskAction.STOP.value,
                    'description': f'日亏损超限: {loss_ratio:.2%} >= {max_daily_loss:.2%}',
                    'loss_amount': total_pnl,
                    'loss_ratio': loss_ratio,
                    'stock_code': stock_code or 'ALL'
                }
            elif loss_ratio >= max_daily_loss * 0.8:
                return {
                    'risk_level': RiskLevel.HIGH.value,
                    'action': RiskAction.REDUCE.value,
                    'description': f'日亏损接近限制: {loss_ratio:.2%}',
                    'loss_amount': total_pnl,
                    'loss_ratio': loss_ratio,
                    'stock_code': stock_code or 'ALL'
                }
            elif loss_ratio >= max_daily_loss * 0.5:
                return {
                    'risk_level': RiskLevel.MEDIUM.value,
                    'action': RiskAction.ALLOW.value,
                    'description': f'日亏损在可控范围: {loss_ratio:.2%}',
                    'loss_amount': total_pnl,
                    'loss_ratio': loss_ratio,
                    'stock_code': stock_code or 'ALL'
                }
            else:
                return {
                    'risk_level': RiskLevel.LOW.value,
                    'action': RiskAction.ALLOW.value,
                    'description': f'日盈亏正常: {total_pnl:.2f}',
                    'pnl_amount': total_pnl,
                    'stock_code': stock_code or 'ALL'
                }
                
        except Exception as e:
            logger.error(f"检查日亏损限制时出错: {e}")
            return {
                'risk_level': RiskLevel.CRITICAL.value,
                'action': RiskAction.STOP.value,
                'description': f'风险检查错误: {str(e)}',
                'stock_code': stock_code or 'ALL'
            }
    
    @log_risk_event
    def check_drawdown_limit(self, stock_code: str = None) -> Dict[str, Any]:
        """检查最大回撤限制
        
        Args:
            stock_code: 股票代码
            
        Returns:
            Dict: 风险检查结果
        """
        try:
            # 获取最近30天的交易记录
            end_date = datetime.now().date()
            start_date = end_date - timedelta(days=30)
            
            from database import db_manager
            trades = db_manager.get_trade_records_by_period(start_date, end_date, stock_code)
            
            if not trades:
                return {
                    'risk_level': RiskLevel.LOW.value,
                    'action': RiskAction.ALLOW.value,
                    'description': '无历史交易记录',
                    'stock_code': stock_code or 'ALL'
                }
            
            # 计算累计盈亏曲线
            cumulative_pnl = []
            running_total = 0
            
            for trade in sorted(trades, key=lambda x: x.get('trade_time', datetime.now())):
                running_total += trade.get('profit_loss', 0)
                cumulative_pnl.append(running_total)
            
            if not cumulative_pnl:
                return {
                    'risk_level': RiskLevel.LOW.value,
                    'action': RiskAction.ALLOW.value,
                    'description': '无有效盈亏数据',
                    'stock_code': stock_code or 'ALL'
                }
            
            # 计算最大回撤
            peak = cumulative_pnl[0]
            max_drawdown = 0
            
            for pnl in cumulative_pnl:
                if pnl > peak:
                    peak = pnl
                drawdown = (peak - pnl) / abs(peak) if peak != 0 else 0
                max_drawdown = max(max_drawdown, drawdown)
            
            max_allowed_drawdown = self.config['max_drawdown']
            
            if max_drawdown >= max_allowed_drawdown:
                return {
                    'risk_level': RiskLevel.CRITICAL.value,
                    'action': RiskAction.EMERGENCY_EXIT.value,
                    'description': f'最大回撤超限: {max_drawdown:.2%} >= {max_allowed_drawdown:.2%}',
                    'max_drawdown': max_drawdown,
                    'peak_value': peak,
                    'current_value': cumulative_pnl[-1],
                    'stock_code': stock_code or 'ALL'
                }
            elif max_drawdown >= max_allowed_drawdown * 0.8:
                return {
                    'risk_level': RiskLevel.HIGH.value,
                    'action': RiskAction.REDUCE.value,
                    'description': f'回撤接近限制: {max_drawdown:.2%}',
                    'max_drawdown': max_drawdown,
                    'stock_code': stock_code or 'ALL'
                }
            else:
                return {
                    'risk_level': RiskLevel.LOW.value,
                    'action': RiskAction.ALLOW.value,
                    'description': f'回撤在可控范围: {max_drawdown:.2%}',
                    'max_drawdown': max_drawdown,
                    'stock_code': stock_code or 'ALL'
                }
                
        except Exception as e:
            logger.error(f"检查回撤限制时出错: {e}")
            return {
                'risk_level': RiskLevel.CRITICAL.value,
                'action': RiskAction.STOP.value,
                'description': f'回撤检查错误: {str(e)}',
                'stock_code': stock_code or 'ALL'
            }
    
    @log_risk_event
    def check_position_limit(self, stock_code: str) -> Dict[str, Any]:
        """检查仓位限制
        
        Args:
            stock_code: 股票代码
            
        Returns:
            Dict: 风险检查结果
        """
        try:
            # 获取当前持仓
            position = get_position(stock_code)
            asset = get_account_asset()
            
            if not asset:
                return {
                    'risk_level': RiskLevel.CRITICAL.value,
                    'action': RiskAction.STOP.value,
                    'description': '无法获取账户资产',
                    'stock_code': stock_code
                }
            
            total_asset = asset.get('total_asset', 0)
            
            if not position or total_asset == 0:
                return {
                    'risk_level': RiskLevel.LOW.value,
                    'action': RiskAction.ALLOW.value,
                    'description': '无持仓或资产为零',
                    'stock_code': stock_code
                }
            
            # 计算仓位比例
            position_value = position.get('market_value', 0)
            position_ratio = position_value / total_asset
            
            max_single_position = self.trading_config['max_single_position']
            
            if position_ratio >= max_single_position:
                return {
                    'risk_level': RiskLevel.HIGH.value,
                    'action': RiskAction.REDUCE.value,
                    'description': f'单股仓位超限: {position_ratio:.2%} >= {max_single_position:.2%}',
                    'position_ratio': position_ratio,
                    'position_value': position_value,
                    'stock_code': stock_code
                }
            elif position_ratio >= max_single_position * 0.9:
                return {
                    'risk_level': RiskLevel.MEDIUM.value,
                    'action': RiskAction.ALLOW.value,
                    'description': f'仓位接近限制: {position_ratio:.2%}',
                    'position_ratio': position_ratio,
                    'stock_code': stock_code
                }
            else:
                return {
                    'risk_level': RiskLevel.LOW.value,
                    'action': RiskAction.ALLOW.value,
                    'description': f'仓位正常: {position_ratio:.2%}',
                    'position_ratio': position_ratio,
                    'stock_code': stock_code
                }
                
        except Exception as e:
            logger.error(f"检查仓位限制时出错: {e}")
            return {
                'risk_level': RiskLevel.CRITICAL.value,
                'action': RiskAction.STOP.value,
                'description': f'仓位检查错误: {str(e)}',
                'stock_code': stock_code
            }
    
    @log_risk_event
    def check_trade_frequency(self, stock_code: str) -> Dict[str, Any]:
        """检查交易频率限制
        
        Args:
            stock_code: 股票代码
            
        Returns:
            Dict: 风险检查结果
        """
        try:
            today = datetime.now().date()
            
            # 获取今日交易次数
            from database import db_manager
            today_trades = db_manager.get_trade_records_by_date(today, stock_code)
            trade_count = len(today_trades) if today_trades else 0
            
            max_daily_trades = self.config['trade_frequency_limit']
            
            if trade_count >= max_daily_trades:
                return {
                    'risk_level': RiskLevel.HIGH.value,
                    'action': RiskAction.STOP.value,
                    'description': f'日交易次数超限: {trade_count} >= {max_daily_trades}',
                    'trade_count': trade_count,
                    'stock_code': stock_code
                }
            elif trade_count >= max_daily_trades * 0.8:
                return {
                    'risk_level': RiskLevel.MEDIUM.value,
                    'action': RiskAction.ALLOW.value,
                    'description': f'交易频率较高: {trade_count}/{max_daily_trades}',
                    'trade_count': trade_count,
                    'stock_code': stock_code
                }
            else:
                return {
                    'risk_level': RiskLevel.LOW.value,
                    'action': RiskAction.ALLOW.value,
                    'description': f'交易频率正常: {trade_count}/{max_daily_trades}',
                    'trade_count': trade_count,
                    'stock_code': stock_code
                }
                
        except Exception as e:
            logger.error(f"检查交易频率时出错: {e}")
            return {
                'risk_level': RiskLevel.CRITICAL.value,
                'action': RiskAction.STOP.value,
                'description': f'频率检查错误: {str(e)}',
                'stock_code': stock_code
            }
    
    def comprehensive_risk_check(self, stock_code: str) -> Dict[str, Any]:
        """综合风险检查
        
        Args:
            stock_code: 股票代码
            
        Returns:
            Dict: 综合风险检查结果
        """
        try:
            checks = {
                'daily_loss': self.check_daily_loss_limit(stock_code),
                'drawdown': self.check_drawdown_limit(stock_code),
                'position': self.check_position_limit(stock_code),
                'frequency': self.check_trade_frequency(stock_code)
            }
            
            # 确定最高风险等级
            risk_levels = [check['risk_level'] for check in checks.values()]
            actions = [check['action'] for check in checks.values()]
            
            # 风险等级优先级
            level_priority = {
                RiskLevel.CRITICAL.value: 4,
                RiskLevel.HIGH.value: 3,
                RiskLevel.MEDIUM.value: 2,
                RiskLevel.LOW.value: 1
            }
            
            highest_risk = max(risk_levels, key=lambda x: level_priority.get(x, 0))
            
            # 动作优先级
            action_priority = {
                RiskAction.EMERGENCY_EXIT.value: 4,
                RiskAction.STOP.value: 3,
                RiskAction.REDUCE.value: 2,
                RiskAction.ALLOW.value: 1
            }
            
            required_action = max(actions, key=lambda x: action_priority.get(x, 0))
            
            # 收集所有风险描述
            descriptions = [check['description'] for check in checks.values() if check['description']]
            
            return {
                'stock_code': stock_code,
                'overall_risk_level': highest_risk,
                'required_action': required_action,
                'risk_summary': '; '.join(descriptions),
                'detailed_checks': checks,
                'timestamp': datetime.now(),
                'can_trade': required_action in [RiskAction.ALLOW.value, RiskAction.REDUCE.value]
            }
            
        except Exception as e:
            logger.error(f"综合风险检查时出错: {e}")
            return {
                'stock_code': stock_code,
                'overall_risk_level': RiskLevel.CRITICAL.value,
                'required_action': RiskAction.STOP.value,
                'risk_summary': f'风险检查错误: {str(e)}',
                'timestamp': datetime.now(),
                'can_trade': False
            }

class StopLossManager:
    """止损止盈管理器"""
    
    def __init__(self):
        self.config = TRADING_CONFIG
        
    def reset(self):
        """重置止损止盈管理器状态"""
        # 止损止盈管理器通常不需要重置状态，因为它是无状态的
        # 这个方法主要是为了兼容回测引擎的调用
        pass
        
    def calculate_stop_loss_price(self, entry_price: float, trade_type: str) -> float:
        """计算止损价格
        
        Args:
            entry_price: 入场价格
            trade_type: 交易类型 ('buy' 或 'sell')
            
        Returns:
            float: 止损价格
        """
        stop_loss_ratio = self.config['stop_loss_ratio']
        
        if trade_type.lower() == 'buy':
            return entry_price * (1 - stop_loss_ratio)
        else:  # sell
            return entry_price * (1 + stop_loss_ratio)
    
    def calculate_take_profit_price(self, entry_price: float, trade_type: str) -> float:
        """计算止盈价格
        
        Args:
            entry_price: 入场价格
            trade_type: 交易类型 ('buy' 或 'sell')
            
        Returns:
            float: 止盈价格
        """
        take_profit_ratio = self.config['take_profit_ratio']
        
        if trade_type.lower() == 'buy':
            return entry_price * (1 + take_profit_ratio)
        else:  # sell
            return entry_price * (1 - take_profit_ratio)
    
    def check_stop_conditions(self, stock_code: str, current_price: float) -> Dict[str, Any]:
        """检查止损止盈条件
        
        Args:
            stock_code: 股票代码
            current_price: 当前价格
            
        Returns:
            Dict: 止损止盈检查结果
        """
        try:
            # 获取当前持仓
            position = get_position(stock_code)
            
            if not position:
                return {
                    'action': 'none',
                    'reason': '无持仓',
                    'stock_code': stock_code
                }
            
            avg_price = position.get('avg_price', 0)
            volume = position.get('volume', 0)
            
            if avg_price == 0 or volume == 0:
                return {
                    'action': 'none',
                    'reason': '持仓数据异常',
                    'stock_code': stock_code
                }
            
            # 计算止损止盈价格
            stop_loss_price = self.calculate_stop_loss_price(avg_price, 'buy')
            take_profit_price = self.calculate_take_profit_price(avg_price, 'buy')
            
            # 计算当前盈亏比例
            pnl_ratio = (current_price - avg_price) / avg_price
            
            if current_price <= stop_loss_price:
                return {
                    'action': 'stop_loss',
                    'reason': f'触发止损: 当前价{current_price:.2f} <= 止损价{stop_loss_price:.2f}',
                    'current_price': current_price,
                    'stop_price': stop_loss_price,
                    'entry_price': avg_price,
                    'pnl_ratio': pnl_ratio,
                    'volume': volume,
                    'stock_code': stock_code
                }
            elif current_price >= take_profit_price:
                return {
                    'action': 'take_profit',
                    'reason': f'触发止盈: 当前价{current_price:.2f} >= 止盈价{take_profit_price:.2f}',
                    'current_price': current_price,
                    'take_profit_price': take_profit_price,
                    'entry_price': avg_price,
                    'pnl_ratio': pnl_ratio,
                    'volume': volume,
                    'stock_code': stock_code
                }
            else:
                return {
                    'action': 'hold',
                    'reason': f'价格在止损止盈区间内: {stop_loss_price:.2f} < {current_price:.2f} < {take_profit_price:.2f}',
                    'current_price': current_price,
                    'stop_loss_price': stop_loss_price,
                    'take_profit_price': take_profit_price,
                    'entry_price': avg_price,
                    'pnl_ratio': pnl_ratio,
                    'stock_code': stock_code
                }
                
        except Exception as e:
            logger.error(f"检查止损止盈条件时出错: {e}")
            return {
                'action': 'error',
                'reason': f'检查错误: {str(e)}',
                'stock_code': stock_code
            }

# 创建全局实例
risk_controller = RiskController()
position_manager = PositionManager()
stop_loss_manager = StopLossManager()

# 函数式接口
def check_trading_risk(stock_code: str) -> Dict[str, Any]:
    """检查交易风险的函数式接口"""
    return risk_controller.comprehensive_risk_check(stock_code)

def calculate_position_size(stock_code: str, signal_strength: float, current_price: float) -> Dict[str, Any]:
    """计算仓位大小的函数式接口"""
    return position_manager.calculate_position_size(stock_code, signal_strength, current_price)

def check_stop_loss_take_profit(stock_code: str, current_price: float) -> Dict[str, Any]:
    """检查止损止盈的函数式接口"""
    return stop_loss_manager.check_stop_conditions(stock_code, current_price)

def is_trading_allowed(stock_code: str) -> bool:
    """检查是否允许交易的函数式接口"""
    risk_result = check_trading_risk(stock_code)
    return risk_result.get('can_trade', False)

def get_risk_summary(stock_code: str) -> str:
    """获取风险摘要的函数式接口"""
    risk_result = check_trading_risk(stock_code)
    return risk_result.get('risk_summary', '无风险信息')

# 为了兼容example.py中的函数调用，添加别名函数
def check_risk_limits(stock_code: str) -> Dict[str, Any]:
    """检查风险限制（别名函数）"""
    return check_trading_risk(stock_code)

def calculate_position_size_legacy(stock_code: str, current_price: float, available_cash: float, size_type: str = 'percentage') -> int:
    """计算仓位大小（兼容旧版本的别名函数）"""
    method_map = {
        'fixed_amount': PositionSizeType.FIXED_AMOUNT,
        'percentage': PositionSizeType.PERCENTAGE,
        'kelly': PositionSizeType.KELLY,
        'atr_based': PositionSizeType.ATR_BASED
    }
    
    method = method_map.get(size_type, PositionSizeType.PERCENTAGE)
    result = position_manager.calculate_position_size(stock_code, 0.5, current_price, method)
    return result.get('volume', 0)

def check_stop_loss_take_profit_with_entry(stock_code: str, entry_price: float, current_price: float, trade_type: str) -> Dict[str, Any]:
    """检查止损止盈（带入场价格的别名函数）"""
    return stop_loss_manager.check_stop_conditions(stock_code, current_price)