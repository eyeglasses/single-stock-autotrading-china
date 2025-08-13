# -*- coding: utf-8 -*-
"""
优化版策略模块
减少指标计算量，提高性能
"""

import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, Tuple, List
from enum import Enum
from loguru import logger
from functools import wraps

from data_fetcher import get_market_data, get_realtime_data
from indicators import sma, ema, rsi  # 只导入核心指标
from strategy import SignalType, StrategyStatus, validate_data
from config import STRATEGY_CONFIG, TRADING_CONFIG

class OptimizedTechnicalStrategy:
    """优化版技术分析策略类"""
    
    def __init__(self, stock_code: str):
        self.stock_code = stock_code
        self.config = STRATEGY_CONFIG
        self.trading_config = TRADING_CONFIG
        self.status = StrategyStatus.ACTIVE
        self.last_signal = None
        self.last_signal_time = None

    @validate_data
    def analyze_trend_fast(self, df: pd.DataFrame) -> Tuple[SignalType, float, str]:
        """快速趋势分析策略（只计算核心指标）
        
        Args:
            df: 包含OHLCV数据的DataFrame
            
        Returns:
            Tuple[SignalType, float, str]: (信号类型, 信号强度, 信号描述)
        """
        try:
            # 只计算核心指标以提高性能
            df = self._calculate_core_indicators(df)
            
            latest = df.iloc[-1]
            prev = df.iloc[-2] if len(df) > 1 else latest
            
            signals = []
            signal_strength = 0.0
            reasons = []
            
            # 1. 移动平均线信号（权重50%）
            ma_signal, ma_strength, ma_reason = self._analyze_ma_signals_fast(df)
            signals.append(ma_signal)
            signal_strength += ma_strength * 0.5
            if ma_reason:
                reasons.append(ma_reason)
            
            # 2. RSI信号（权重30%）
            rsi_signal, rsi_strength, rsi_reason = self._analyze_rsi_signals_fast(latest, prev)
            signals.append(rsi_signal)
            signal_strength += rsi_strength * 0.3
            if rsi_reason:
                reasons.append(rsi_reason)
            
            # 3. 价格趋势信号（权重20%）
            trend_signal, trend_strength, trend_reason = self._analyze_price_trend(df)
            signals.append(trend_signal)
            signal_strength += trend_strength * 0.2
            if trend_reason:
                reasons.append(trend_reason)
            
            # 综合信号
            final_signal = self._combine_signals(signals, signal_strength)
            combined_reason = "; ".join(reasons) if reasons else "无明确信号"
            
            logger.info(f"{self.stock_code} 快速分析完成: {final_signal.value}, 强度: {signal_strength:.2f}")
            
            return final_signal, signal_strength, combined_reason
            
        except Exception as e:
            logger.error(f"快速趋势分析出错: {e}")
            return SignalType.HOLD, 0.0, f"分析错误: {str(e)}"
    
    def _calculate_core_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """只计算核心技术指标以提高性能"""
        # 创建副本以避免SettingWithCopyWarning
        df = df.copy()
        
        try:
            # 只计算最重要的指标
            # 移动平均线
            df.loc[:, 'sma_short'] = sma(df['close_price'], self.config['ma_short'])
            df.loc[:, 'sma_long'] = sma(df['close_price'], self.config['ma_long'])
            
            # RSI
            df.loc[:, 'rsi'] = rsi(df['close_price'], self.config['rsi_period'])
            
            # 价格变化
            df.loc[:, 'price_change'] = df['close_price'].pct_change()
            
            logger.info(f"核心指标计算完成，数据量: {len(df)}")
            
        except Exception as e:
            logger.error(f"计算核心指标时出错: {e}")
        
        return df
    
    def _analyze_ma_signals_fast(self, df: pd.DataFrame) -> Tuple[SignalType, float, str]:
        """快速分析移动平均线信号"""
        latest = df.iloc[-1]
        prev = df.iloc[-2] if len(df) > 1 else latest
        
        # 短期均线与长期均线的关系
        if pd.isna(latest['sma_short']) or pd.isna(latest['sma_long']):
            return SignalType.HOLD, 0.0, ""
        
        # 金叉死叉判断
        current_diff = latest['sma_short'] - latest['sma_long']
        prev_diff = prev['sma_short'] - prev['sma_long']
        
        # 价格与均线的关系
        price_above_short = latest['close_price'] > latest['sma_short']
        price_above_long = latest['close_price'] > latest['sma_long']
        
        if prev_diff <= 0 and current_diff > 0:  # 金叉
            return SignalType.BUY, 0.8, "短期均线金叉长期均线"
        elif prev_diff >= 0 and current_diff < 0:  # 死叉
            return SignalType.SELL, 0.8, "短期均线死叉长期均线"
        elif price_above_short and price_above_long and current_diff > 0:
            return SignalType.BUY, 0.5, "价格位于均线之上，趋势向上"
        elif not price_above_short and not price_above_long and current_diff < 0:
            return SignalType.SELL, 0.5, "价格位于均线之下，趋势向下"
        
        return SignalType.HOLD, 0.0, ""
    
    def _analyze_rsi_signals_fast(self, latest: pd.Series, prev: pd.Series) -> Tuple[SignalType, float, str]:
        """快速分析RSI信号"""
        if pd.isna(latest['rsi']):
            return SignalType.HOLD, 0.0, ""
        
        rsi = latest['rsi']
        rsi_oversold = self.config['rsi_oversold']
        rsi_overbought = self.config['rsi_overbought']
        
        if rsi <= rsi_oversold:
            return SignalType.BUY, 0.7, f"RSI超卖({rsi:.1f})"
        elif rsi >= rsi_overbought:
            return SignalType.SELL, 0.7, f"RSI超买({rsi:.1f})"
        elif rsi > rsi_oversold and prev['rsi'] <= rsi_oversold:
            return SignalType.BUY, 0.5, "RSI从超卖区域反弹"
        elif rsi < rsi_overbought and prev['rsi'] >= rsi_overbought:
            return SignalType.SELL, 0.5, "RSI从超买区域回落"
        
        return SignalType.HOLD, 0.0, ""
    
    def _analyze_price_trend(self, df: pd.DataFrame) -> Tuple[SignalType, float, str]:
        """分析价格趋势"""
        if len(df) < 5:
            return SignalType.HOLD, 0.0, ""
        
        # 计算最近5天的价格趋势
        recent_prices = df['close_price'].tail(5)
        price_changes = recent_prices.pct_change().dropna()
        
        if price_changes.empty:
            return SignalType.HOLD, 0.0, ""
        
        # 计算趋势强度
        positive_changes = (price_changes > 0).sum()
        negative_changes = (price_changes < 0).sum()
        
        avg_change = price_changes.mean()
        
        if positive_changes >= 3 and avg_change > 0.01:  # 连续上涨且涨幅超过1%
            return SignalType.BUY, 0.6, "价格呈上升趋势"
        elif negative_changes >= 3 and avg_change < -0.01:  # 连续下跌且跌幅超过1%
            return SignalType.SELL, 0.6, "价格呈下降趋势"
        elif abs(avg_change) < 0.005:  # 价格变化小于0.5%
            return SignalType.HOLD, 0.1, "价格横盘整理"
        
        return SignalType.HOLD, 0.0, ""
    
    def _combine_signals(self, signals: List[SignalType], signal_strength: float) -> SignalType:
        """综合多个信号"""
        buy_count = sum(1 for s in signals if s == SignalType.BUY)
        sell_count = sum(1 for s in signals if s == SignalType.SELL)
        
        # 强信号阈值
        strong_threshold = 0.6
        weak_threshold = 0.3
        
        if signal_strength >= strong_threshold:
            if buy_count > sell_count:
                return SignalType.STRONG_BUY
            elif sell_count > buy_count:
                return SignalType.STRONG_SELL
        elif signal_strength >= weak_threshold:
            if buy_count > sell_count:
                return SignalType.BUY
            elif sell_count > buy_count:
                return SignalType.SELL
        
        return SignalType.HOLD
    
    def generate_signal_fast(self) -> Dict[str, Any]:
        """快速生成交易信号
        
        Returns:
            Dict: 包含信号信息的字典
        """
        try:
            # 获取较少的历史数据以提高性能
            df = get_market_data(
                stock_code=self.stock_code,
                period='1d',
                count=30  # 只获取30天数据
            )
            
            if df is None or df.empty:
                logger.warning(f"无法获取{self.stock_code}的历史数据")
                return self._create_signal_dict(SignalType.HOLD, 0.0, "无数据")
            
            # 执行快速策略分析
            signal_type, signal_strength, reason = self.analyze_trend_fast(df)
            
            # 获取实时价格
            real_time_data = get_realtime_data(self.stock_code)
            current_price = real_time_data.get('price', df.iloc[-1]['close_price']) if real_time_data else df.iloc[-1]['close_price']
            
            # 创建信号字典
            signal_dict = self._create_signal_dict(signal_type, signal_strength, reason, current_price)
            
            # 更新最后信号
            self.last_signal = signal_type
            self.last_signal_time = datetime.now()
            
            return signal_dict
            
        except Exception as e:
            logger.error(f"生成交易信号时出错: {e}")
            return self._create_signal_dict(SignalType.HOLD, 0.0, f"错误: {str(e)}")
    
    def _create_signal_dict(self, signal_type: SignalType, strength: float, reason: str, price: float = 0.0) -> Dict[str, Any]:
        """创建信号字典"""
        return {
            'stock_code': self.stock_code,
            'signal_type': signal_type.value,
            'signal_strength': strength,
            'reason': reason,
            'price': price,
            'timestamp': datetime.now(),
            'strategy_name': 'optimized_technical_strategy'
        }

class OptimizedStrategyManager:
    """优化版策略管理器"""
    
    def __init__(self, stock_code: str):
        self.stock_code = stock_code
        self.technical_strategy = OptimizedTechnicalStrategy(stock_code)
    
    def get_fast_signal(self) -> Dict[str, Any]:
        """获取快速信号
        
        Returns:
            Dict: 快速信号信息
        """
        try:
            return self.technical_strategy.generate_signal_fast()
        except Exception as e:
            logger.error(f"获取快速信号时出错: {e}")
            return {
                'stock_code': self.stock_code,
                'signal_type': SignalType.HOLD.value,
                'signal_strength': 0.0,
                'reason': f"错误: {str(e)}",
                'price': 0.0,
                'timestamp': datetime.now(),
                'strategy_name': 'optimized_strategy'
            }

# 函数式接口
def create_optimized_strategy(stock_code: str) -> OptimizedTechnicalStrategy:
    """创建优化版技术分析策略实例"""
    return OptimizedTechnicalStrategy(stock_code)

def get_fast_trading_signal(stock_code: str) -> Dict[str, Any]:
    """获取快速交易信号的函数式接口
    
    Args:
        stock_code: 股票代码
    
    Returns:
        Dict: 交易信号信息
    """
    strategy = OptimizedStrategyManager(stock_code)
    return strategy.get_fast_signal()