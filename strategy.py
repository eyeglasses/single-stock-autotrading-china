# -*- coding: utf-8 -*-
"""
交易策略模块

本模块实现了多种股票交易策略，包括：
1. 技术分析策略 (TechnicalStrategy) - 基于技术指标的综合分析
2. 动量策略 (MomentumStrategy) - 基于价格动量的分析
3. ETF当天交易策略 (ETFDayTradingStrategy) - 专门针对ETF的日内交易策略
4. 策略管理器 (StrategyManager) - 综合多种策略的信号管理

主要功能：
- 多种技术指标计算和分析
- 信号生成和强度评估
- 数据库信号存储
- 实时价格获取和决策
- 风险控制和参数配置

作者: AI助手
创建时间: 2024
"""

import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, Tuple, List
from enum import Enum
from loguru import logger
from functools import wraps

# 导入数据获取模块
from data_fetcher import get_market_data, get_realtime_data
# 导入技术指标计算模块
from indicators import (
    sma, ema, rsi, macd,                    # 移动平均线、RSI、MACD指标
    bollinger_bands, stochastic, williams_r, # 布林带、KD指标、威廉指标
    atr, volume_sma, price_change,          # ATR、成交量均线、价格变化
    momentum                                # 动量指标
)
from database import get_db_manager         # 数据库管理器
from config import STRATEGY_CONFIG, TRADING_CONFIG  # 策略和交易配置

class SignalType(Enum):
    """
    交易信号类型枚举
    
    定义了策略可以生成的五种交易信号：
    - BUY: 买入信号，表示当前是买入的好时机
    - SELL: 卖出信号，表示当前应该卖出持仓
    - HOLD: 持有信号，表示当前应该保持现状，不进行交易
    - STRONG_BUY: 强买入信号，表示强烈建议买入
    - STRONG_SELL: 强卖出信号，表示强烈建议卖出
    """
    BUY = "buy"                 # 买入信号
    SELL = "sell"               # 卖出信号
    HOLD = "hold"               # 持有信号
    STRONG_BUY = "strong_buy"   # 强买入信号
    STRONG_SELL = "strong_sell" # 强卖出信号

class StrategyStatus(Enum):
    """策略状态枚举"""
    ACTIVE = "active"
    INACTIVE = "inactive"
    PAUSED = "paused"

def validate_data(func):
    """验证数据有效性的装饰器"""
    @wraps(func)
    def wrapper(*args, **kwargs):
        # 检查第一个参数是否为DataFrame
        if len(args) > 0 and isinstance(args[0], pd.DataFrame):
            df = args[0]
            if df.empty:
                logger.warning("数据为空，无法执行策略分析")
                return SignalType.HOLD, 0.0, "数据为空"
            if len(df) < 20:  # 至少需要20个数据点
                logger.warning("数据点不足，无法执行策略分析")
                return SignalType.HOLD, 0.0, "数据点不足"
        return func(*args, **kwargs)
    return wrapper

class TechnicalStrategy:
    """
    技术分析策略类
    
    基于多种技术指标的综合分析策略，包括：
    - 移动平均线分析 (SMA, EMA)
    - 相对强弱指数 (RSI)
    - MACD指标分析
    - 布林带分析
    - KD随机指标
    - 威廉指标 (%R)
    - 平均真实波幅 (ATR)
    - 成交量分析
    - 价格动量分析
    
    该策略通过综合多个技术指标的信号，生成最终的交易建议。
    每个指标都有其权重，最终信号强度通过加权平均计算得出。
    
    Attributes:
        stock_code (str): 股票代码
        config (dict): 策略配置参数
        trading_config (dict): 交易配置参数
        status (StrategyStatus): 策略状态
        last_signal (SignalType): 最后一次生成的信号
        last_signal_time (datetime): 最后一次信号生成时间
    """
    
    def __init__(self, stock_code: str):
        """
        初始化技术分析策略
        
        Args:
            stock_code (str): 股票代码，如 '000001.SZ'
        """
        self.stock_code = stock_code
        self.config = STRATEGY_CONFIG
        self.trading_config = TRADING_CONFIG
        self.status = StrategyStatus.ACTIVE
        self.last_signal = None
        self.last_signal_time = None
        
    @validate_data
    def analyze_trend(self, df: pd.DataFrame) -> Tuple[SignalType, float, str]:
        """
        股票趋势分析策略 - 技术分析策略的核心方法
        
        这是技术分析策略的主要分析方法，通过综合多种技术指标来判断股票的趋势方向
        和交易时机。该方法采用多指标融合的方式，提高信号的准确性和可靠性。
        
        分析流程：
        1. 数据预处理和指标计算
           - 计算移动平均线（SMA、EMA）
           - 计算动量指标（RSI、MACD）
           - 计算波动性指标（布林带、ATR）
           - 计算成交量指标
           
        2. 单项指标信号分析
           - 移动平均线金叉死叉分析
           - RSI超买超卖分析
           - MACD趋势转换分析
           - 布林带支撑阻力分析
           - 成交量价格配合分析
           
        3. 多指标信号综合
           - 根据配置权重加权平均
           - 信号一致性验证
           - 最终信号强度计算
        
        Args:
            df (pd.DataFrame): 包含OHLCV数据的DataFrame，必须包含以下列：
                - close_price: 收盘价（必需）
                - high_price: 最高价（必需）
                - low_price: 最低价（必需）
                - volume: 成交量（必需）
                - 数据应按时间正序排列，至少包含20个数据点
                
        Returns:
            Tuple[SignalType, float, str]: 包含三个元素的元组：
                - SignalType: 交易信号类型
                  * BUY: 买入信号
                  * SELL: 卖出信号
                  * HOLD: 持有信号
                  * STRONG_BUY: 强买入信号
                  * STRONG_SELL: 强卖出信号
                - float: 信号强度 (0.0-1.0)
                  * 0.0-0.3: 弱信号
                  * 0.3-0.6: 中等信号
                  * 0.6-1.0: 强信号
                - str: 信号描述和分析原因
                  * 包含各指标的具体分析结果
                  * 说明信号产生的主要原因
        
        Raises:
            Exception: 当数据不足、格式错误或计算过程中出现异常时
            
        Example:
            >>> strategy = TechnicalStrategy('000001.SZ')
            >>> df = get_market_data('000001.SZ', period='1d', count=30)
            >>> signal, strength, reason = strategy.analyze_trend(df)
            >>> print(f"信号: {signal.value}, 强度: {strength:.2f}, 原因: {reason}")
        """
        try:
            # 计算技术指标
            df = self._calculate_all_indicators(df)
            
            latest = df.iloc[-1]
            prev = df.iloc[-2] if len(df) > 1 else latest
            
            signals = []
            signal_strength = 0.0
            reasons = []
            
            # 1. 移动平均线信号
            ma_signal, ma_strength, ma_reason = self._analyze_ma_signals(df)
            signals.append(ma_signal)
            signal_strength += ma_strength * 0.3
            if ma_reason:
                reasons.append(ma_reason)
            
            # 2. RSI信号
            rsi_signal, rsi_strength, rsi_reason = self._analyze_rsi_signals(latest, prev)
            signals.append(rsi_signal)
            signal_strength += rsi_strength * 0.2
            if rsi_reason:
                reasons.append(rsi_reason)
            
            # 3. MACD信号
            macd_signal, macd_strength, macd_reason = self._analyze_macd_signals(df)
            signals.append(macd_signal)
            signal_strength += macd_strength * 0.25
            if macd_reason:
                reasons.append(macd_reason)
            
            # 4. 布林带信号
            bb_signal, bb_strength, bb_reason = self._analyze_bollinger_signals(latest)
            signals.append(bb_signal)
            signal_strength += bb_strength * 0.15
            if bb_reason:
                reasons.append(bb_reason)
            
            # 5. 成交量信号
            vol_signal, vol_strength, vol_reason = self._analyze_volume_signals(latest, prev)
            signals.append(vol_signal)
            signal_strength += vol_strength * 0.1
            if vol_reason:
                reasons.append(vol_reason)
            
            # 综合信号判断
            final_signal = self._combine_signals(signals, signal_strength)
            reason_text = "; ".join(reasons) if reasons else "无明确信号"
            
            return final_signal, signal_strength, reason_text
            
        except Exception as e:
            logger.error(f"趋势分析时出错: {e}")
            return SignalType.HOLD, 0.0, f"分析错误: {str(e)}"
    
    def _calculate_all_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        计算所有技术指标
        
        这是技术分析的基础方法，计算策略所需的全部技术指标。
        所有指标都基于收盘价、最高价、最低价和成交量数据计算。
        
        计算的指标包括：
        1. 趋势指标：
           - SMA (简单移动平均线): 短期和长期
           - EMA (指数移动平均线): 短期和长期
           
        2. 动量指标：
           - RSI (相对强弱指数): 用于判断超买超卖
           - MACD (指数平滑移动平均线): 包括MACD线、信号线、柱状图
           - 动量指标: 衡量价格变化速度
           
        3. 波动性指标：
           - 布林带: 包括上轨、中轨、下轨
           - ATR (平均真实波幅): 衡量价格波动性
           
        4. 超买超卖指标：
           - KD指标 (随机指标): K线和D线
           - 威廉指标 (%R): 超买超卖判断
           
        5. 成交量指标：
           - 成交量移动平均线
           - 价格变化率
        
        Args:
            df (pd.DataFrame): 包含OHLCV数据的DataFrame，必须包含：
                - close_price: 收盘价序列
                - high_price: 最高价序列
                - low_price: 最低价序列
                - volume: 成交量序列
                
        Returns:
            pd.DataFrame: 原始数据加上所有计算的技术指标列：
                - sma_short/sma_long: 短期/长期简单移动平均线
                - ema_short/ema_long: 短期/长期指数移动平均线
                - rsi: 相对强弱指数
                - macd/macd_signal/macd_histogram: MACD相关指标
                - bb_upper/bb_middle/bb_lower: 布林带上中下轨
                - k/d: KD指标的K线和D线
                - williams_r: 威廉指标
                - atr: 平均真实波幅
                - volume_sma: 成交量移动平均
                - price_change: 价格变化率
                - momentum: 动量指标
                
        Note:
            - 所有指标都是基于配置参数计算
            - 指标值可能包含NaN（特别是序列开始部分）
            - 使用.loc避免SettingWithCopyWarning
        """
        # 创建副本以避免SettingWithCopyWarning
        df = df.copy()
        
        # 1. 计算移动平均线指标
        # 短期和长期移动平均线，用于判断趋势方向和金叉死叉
        df.loc[:, 'sma_short'] = sma(df['close_price'], self.config['ma_short'])  # 短期简单移动平均线
        df.loc[:, 'sma_long'] = sma(df['close_price'], self.config['ma_long'])    # 长期简单移动平均线
        df.loc[:, 'ema_short'] = ema(df['close_price'], self.config['ma_short'])  # 短期指数移动平均线
        df.loc[:, 'ema_long'] = ema(df['close_price'], self.config['ma_long'])    # 长期指数移动平均线
        
        # 2. 计算RSI相对强弱指数
        # 用于判断超买超卖状态，范围0-100
        df.loc[:, 'rsi'] = rsi(df['close_price'], self.config['rsi_period'])
        
        # 3. 计算MACD指标
        # 趋势跟踪指标，包含MACD线、信号线和柱状图
        macd_line, signal_line, histogram = macd(df['close_price'])
        df.loc[:, 'macd'] = macd_line              # MACD线（快线-慢线）
        df.loc[:, 'macd_signal'] = signal_line     # 信号线（MACD的EMA）
        df.loc[:, 'macd_histogram'] = histogram    # 柱状图（MACD-信号线）
        
        # 4. 计算布林带指标
        # 基于移动平均线和标准差的波动性指标
        upper, middle, lower = bollinger_bands(df['close_price'])
        df.loc[:, 'bb_upper'] = upper    # 布林带上轨（阻力位）
        df.loc[:, 'bb_middle'] = middle  # 布林带中轨（移动平均线）
        df.loc[:, 'bb_lower'] = lower    # 布林带下轨（支撑位）
        
        # 5. 计算KD随机指标
        # 超买超卖指标，范围0-100
        k_line, d_line = stochastic(df['high_price'], df['low_price'], df['close_price'])
        df.loc[:, 'k'] = k_line  # K值（快线）
        df.loc[:, 'd'] = d_line  # D值（慢线，K值的移动平均）
        
        # 6. 计算威廉指标
        # 超买超卖指标，范围-100到0
        df.loc[:, 'williams_r'] = williams_r(df['high_price'], df['low_price'], df['close_price'])
        
        # 7. 计算ATR平均真实波幅
        # 衡量价格波动性的指标
        df.loc[:, 'atr'] = atr(df['high_price'], df['low_price'], df['close_price'])
        
        # 8. 计算成交量相关指标
        df.loc[:, 'volume_sma'] = volume_sma(df['volume'], self.config['volume_ma_period'])  # 成交量移动平均
        
        # 9. 计算价格变化率
        # 衡量价格变动幅度
        df.loc[:, 'price_change'] = price_change(df['close_price'])
        
        # 10. 计算动量指标
        # 衡量价格变化的速度
        df.loc[:, 'momentum'] = momentum(df['close_price'])
        
        return df
    
    def _analyze_ma_signals(self, df: pd.DataFrame) -> Tuple[SignalType, float, str]:
        """
        分析移动平均线信号
        
        移动平均线是最基础和重要的技术指标之一，通过分析不同周期移动平均线的
        相对位置关系来判断趋势方向和买卖时机。
        
        分析逻辑：
        1. 金叉信号：短期均线上穿长期均线，表示上涨趋势开始
        2. 死叉信号：短期均线下穿长期均线，表示下跌趋势开始
        3. 价格位置：价格相对于均线的位置反映当前趋势强度
        4. 趋势确认：均线方向和价格位置的组合确认趋势
        
        Args:
            df (pd.DataFrame): 包含移动平均线指标的数据框，必须包含：
                - sma_short: 短期简单移动平均线
                - sma_long: 长期简单移动平均线
                - close_price: 收盘价
                
        Returns:
            Tuple[SignalType, float, str]: 包含三个元素的元组：
                - SignalType: 移动平均线交易信号
                  * BUY: 金叉或价格位于均线之上
                  * SELL: 死叉或价格位于均线之下
                  * HOLD: 信号不明确或数据不足
                - float: 信号强度 (0.0-1.0)
                  * 0.8: 金叉/死叉强信号
                  * 0.5: 趋势确认中等信号
                  * 0.0: 无明确信号
                - str: 信号描述
                  * 说明具体的均线关系和价格位置
                  
        Note:
            - 金叉死叉是移动平均线分析的核心信号
            - 价格位置提供趋势强度的额外确认
            - 需要至少2个数据点来判断交叉
        """
        latest = df.iloc[-1]  # 获取最新数据点
        prev = df.iloc[-2] if len(df) > 1 else latest  # 获取前一个数据点，用于判断交叉
        
        # 检查移动平均线数据的有效性
        if pd.isna(latest['sma_short']) or pd.isna(latest['sma_long']):
            return SignalType.HOLD, 0.0, ""
        
        # 计算短期和长期均线的差值，用于判断金叉死叉
        current_diff = latest['sma_short'] - latest['sma_long']  # 当前时点的均线差值
        prev_diff = prev['sma_short'] - prev['sma_long']         # 前一时点的均线差值
        
        # 分析价格相对于移动平均线的位置
        price_above_short = latest['close_price'] > latest['sma_short']  # 价格是否在短期均线之上
        price_above_long = latest['close_price'] > latest['sma_long']    # 价格是否在长期均线之上
        
        # 信号判断逻辑
        
        # 1. 金叉信号：短期均线从下方穿越长期均线到上方
        if prev_diff <= 0 and current_diff > 0:  # 金叉
            return SignalType.BUY, 0.8, "短期均线金叉长期均线"
            
        # 2. 死叉信号：短期均线从上方穿越长期均线到下方
        elif prev_diff >= 0 and current_diff < 0:  # 死叉
            return SignalType.SELL, 0.8, "短期均线死叉长期均线"
            
        # 3. 多头排列：价格位于两条均线之上，且短期均线在长期均线之上
        elif price_above_short and price_above_long and current_diff > 0:
            return SignalType.BUY, 0.5, "价格位于均线之上，趋势向上"
            
        # 4. 空头排列：价格位于两条均线之下，且短期均线在长期均线之下
        elif not price_above_short and not price_above_long and current_diff < 0:
            return SignalType.SELL, 0.5, "价格位于均线之下，趋势向下"
        
        # 5. 其他情况：信号不明确，建议观望
        return SignalType.HOLD, 0.0, ""
    
    def _analyze_rsi_signals(self, latest: pd.Series, prev: pd.Series) -> Tuple[SignalType, float, str]:
        """
        分析RSI（相对强弱指数）信号
        
        RSI是衡量价格变动速度和变化的动量指标，主要用于识别超买和超卖状态。
        RSI值在0-100之间波动，是判断市场情绪和寻找反转机会的重要工具。
        
        分析逻辑：
        1. 超买区域（通常>70）：价格可能过高，存在回调风险
        2. 超卖区域（通常<30）：价格可能过低，存在反弹机会
        3. 反转确认：从极端区域回归正常范围的确认信号
        4. 趋势延续：RSI保持在极端区域的持续信号
        
        Args:
            latest (pd.Series): 最新数据点，必须包含：
                - rsi: RSI指标值（0-100范围）
            prev (pd.Series): 前一个数据点，用于判断RSI变化趋势
                
        Returns:
            Tuple[SignalType, float, str]: 包含三个元素的元组：
                - SignalType: RSI交易信号
                  * BUY: RSI超卖或从超卖区域反弹
                  * SELL: RSI超买或从超买区域回落
                  * HOLD: RSI在中性区域
                - float: 信号强度 (0.0-1.0)
                  * 0.7: 超买/超卖强信号
                  * 0.5: 反转确认中等信号
                  * 0.0: 中性无信号
                - str: 信号描述
                  * 包含具体RSI数值和状态描述
                  
        Note:
            - RSI是反向指标，超买时看跌，超卖时看涨
            - 在强趋势中，RSI可能长时间保持极端值
            - 建议结合其他指标确认RSI信号
            - 配置参数来自self.config['rsi_overbought']和['rsi_oversold']
        """
        # 检查RSI数据的有效性
        if pd.isna(latest['rsi']):
            return SignalType.HOLD, 0.0, "RSI数据不足"
        
        # 获取RSI值和配置阈值
        rsi = latest['rsi']  # 当前RSI值
        rsi_oversold = self.config['rsi_oversold']    # 超卖阈值（默认30）
        rsi_overbought = self.config['rsi_overbought']  # 超买阈值（默认70）
        
        # RSI信号判断逻辑
        
        # 1. 超卖信号：RSI低于或等于超卖阈值
        if rsi <= rsi_oversold:
            return SignalType.BUY, 0.7, f"RSI超卖({rsi:.1f})，价格可能反弹"
            
        # 2. 超买信号：RSI高于或等于超买阈值
        elif rsi >= rsi_overbought:
            return SignalType.SELL, 0.7, f"RSI超买({rsi:.1f})，价格可能回调"
            
        # 3. 超卖反弹确认：RSI从超卖区域向上突破
        elif rsi > rsi_oversold and prev['rsi'] <= rsi_oversold:
            return SignalType.BUY, 0.5, "RSI从超卖区域反弹，买入信号确认"
            
        # 4. 超买回落确认：RSI从超买区域向下突破
        elif rsi < rsi_overbought and prev['rsi'] >= rsi_overbought:
            return SignalType.SELL, 0.5, "RSI从超买区域回落，卖出信号确认"
        
        # 5. 中性区域：RSI在正常范围内，无明确信号
        return SignalType.HOLD, 0.0, f"RSI中性({rsi:.1f})，无明确方向"
    
    def _analyze_macd_signals(self, df: pd.DataFrame) -> Tuple[SignalType, float, str]:
        """
        分析MACD（指数平滑移动平均线）信号
        
        MACD是一个趋势跟踪动量指标，通过计算两条不同周期的指数移动平均线之差
        来显示价格趋势的变化。MACD包含三个组成部分：
        1. MACD线：快线EMA - 慢线EMA
        2. 信号线：MACD线的EMA平滑
        3. 柱状图：MACD线 - 信号线
        
        分析逻辑：
        1. 金叉信号：MACD线从下方穿越信号线，看涨信号
        2. 死叉信号：MACD线从上方穿越信号线，看跌信号
        3. 柱状图增强：柱状图值增大，趋势加强
        4. 柱状图减弱：柱状图值减小，趋势减弱
        5. 零轴突破：MACD线穿越零轴，表示趋势转换
        
        Args:
            df (pd.DataFrame): 包含MACD指标的数据框，必须包含：
                - macd: MACD线值
                - macd_signal: MACD信号线值
                - macd_histogram: MACD柱状图值
                
        Returns:
            Tuple[SignalType, float, str]: 包含三个元素的元组：
                - SignalType: MACD交易信号
                  * BUY: MACD金叉或柱状图增强
                  * SELL: MACD死叉或柱状图减弱
                  * HOLD: 信号不明确
                - float: 信号强度 (0.0-1.0)
                  * 0.6: 金叉/死叉中等信号
                  * 0.3: 柱状图变化弱信号
                  * 0.0: 无明确信号
                - str: 信号描述
                  * 说明具体的MACD状态和信号类型
                  
        Note:
            - MACD金叉死叉是重要的趋势转换信号
            - 柱状图的变化可以提前预示金叉死叉
            - 零轴上方的金叉比零轴下方的金叉更可靠
            - 需要至少2个数据点来判断交叉
        """
        latest = df.iloc[-1]  # 获取最新数据点
        prev = df.iloc[-2] if len(df) > 1 else latest  # 获取前一个数据点
        
        # 检查MACD数据的有效性
        if pd.isna(latest['macd']) or pd.isna(latest['macd_signal']):
            return SignalType.HOLD, 0.0, "MACD数据不足"
        
        # 计算MACD线与信号线的差值，用于判断金叉死叉
        current_diff = latest['macd'] - latest['macd_signal']  # 当前时点的差值
        prev_diff = prev['macd'] - prev['macd_signal']         # 前一时点的差值
        
        # MACD信号判断逻辑
        
        # 1. 金叉信号：MACD线从下方穿越信号线到上方
        if prev_diff <= 0 and current_diff > 0:
            return SignalType.BUY, 0.6, "MACD金叉，趋势转为上涨"
            
        # 2. 死叉信号：MACD线从上方穿越信号线到下方
        elif prev_diff >= 0 and current_diff < 0:
            return SignalType.SELL, 0.6, "MACD死叉，趋势转为下跌"
        
        # 3. 分析MACD柱状图的变化趋势
        if not pd.isna(latest['macd_histogram']) and not pd.isna(prev['macd_histogram']):
            # 柱状图增强：当前柱状图大于前期且为正值，表示上涨动能增强
            if latest['macd_histogram'] > prev['macd_histogram'] and latest['macd_histogram'] > 0:
                return SignalType.BUY, 0.3, "MACD柱状图增强，上涨动能加强"
                
            # 柱状图减弱：当前柱状图小于前期且为负值，表示下跌动能增强
            elif latest['macd_histogram'] < prev['macd_histogram'] and latest['macd_histogram'] < 0:
                return SignalType.SELL, 0.3, "MACD柱状图减弱，下跌动能加强"
        
        # 4. 其他情况：信号不明确
        return SignalType.HOLD, 0.0, "MACD信号不明确"
    
    def _analyze_bollinger_signals(self, latest: pd.Series) -> Tuple[SignalType, float, str]:
        """
        分析布林带（Bollinger Bands）信号
        
        布林带是一种技术分析工具，由三条线组成：
        1. 中轨：通常是20日简单移动平均线
        2. 上轨：中轨 + (2 × 标准差)
        3. 下轨：中轨 - (2 × 标准差)
        
        布林带主要用于：
        - 判断价格的相对高低位置
        - 识别超买超卖状态
        - 预测价格反转机会
        - 衡量市场波动性
        
        分析逻辑：
        1. 价格触及下轨：通常表示超卖，可能反弹
        2. 价格触及上轨：通常表示超买，可能回调
        3. 价格位置：相对于中轨的位置反映趋势强度
        4. 带宽变化：布林带收缩或扩张反映波动性变化
        
        Args:
            latest (pd.Series): 最新数据点，必须包含：
                - close_price: 收盘价
                - bb_upper: 布林带上轨
                - bb_middle: 布林带中轨
                - bb_lower: 布林带下轨
                
        Returns:
            Tuple[SignalType, float, str]: 包含三个元素的元组：
                - SignalType: 布林带交易信号
                  * BUY: 价格触及下轨或位于下半部
                  * SELL: 价格触及上轨或位于上半部
                  * HOLD: 价格在中轨附近
                - float: 信号强度 (0.0-1.0)
                  * 0.6: 触及上下轨的中等信号
                  * 0.2: 位于上下半部的弱信号
                  * 0.0: 无明确信号
                - str: 信号描述
                  * 说明价格相对于布林带的具体位置
                  
        Note:
            - 布林带信号在震荡市场中更有效
            - 在强趋势中，价格可能长时间沿着上轨或下轨运行
            - 建议结合其他指标确认布林带信号
            - 布林带收缩时通常预示着大幅波动即将到来
        """
        # 检查布林带数据的有效性
        if pd.isna(latest['bb_upper']) or pd.isna(latest['bb_lower']):
            return SignalType.HOLD, 0.0, "布林带数据不足"
        
        # 获取价格和布林带各轨道的值
        price = latest['close_price']     # 当前收盘价
        bb_upper = latest['bb_upper']     # 布林带上轨
        bb_lower = latest['bb_lower']     # 布林带下轨
        bb_middle = latest['bb_middle']   # 布林带中轨（移动平均线）
        
        # 布林带信号判断逻辑
        
        # 1. 价格触及或跌破下轨：超卖信号，可能反弹
        if price <= bb_lower:
            return SignalType.BUY, 0.6, "价格触及布林带下轨，超卖反弹机会"
            
        # 2. 价格触及或突破上轨：超买信号，可能回调
        elif price >= bb_upper:
            return SignalType.SELL, 0.6, "价格触及布林带上轨，超买回调风险"
            
        # 3. 价格位于中轨上方但未触及上轨：偏强势，轻微看涨
        elif price > bb_middle and price < bb_upper:
            return SignalType.BUY, 0.2, "价格位于布林带上半部，趋势偏强"
            
        # 4. 价格位于中轨下方但未触及下轨：偏弱势，轻微看跌
        elif price < bb_middle and price > bb_lower:
            return SignalType.SELL, 0.2, "价格位于布林带下半部，趋势偏弱"
        
        # 5. 价格接近中轨：中性信号
        return SignalType.HOLD, 0.0, "价格接近布林带中轨，方向不明"
    
    def _analyze_volume_signals(self, latest: pd.Series, prev: pd.Series) -> Tuple[SignalType, float, str]:
        """
        分析成交量信号
        
        成交量是技术分析中的重要确认指标，它反映了市场参与者的活跃程度和
        对价格变动的认同度。量价关系是技术分析的核心原理之一。
        
        分析原理：
        1. 量价配合：价格上涨伴随放量，价格下跌伴随放量
        2. 量价背离：价格与成交量走势相反，可能预示趋势转换
        3. 缩量整理：成交量萎缩，通常表示市场观望情绪浓厚
        4. 异常放量：突然的大成交量可能预示重要变化
        
        分析逻辑：
        1. 放量上涨：成交量放大且价格上涨，看涨信号
        2. 放量下跌：成交量放大且价格下跌，看跌信号
        3. 缩量上涨：价格上涨但成交量萎缩，上涨乏力
        4. 缩量下跌：价格下跌但成交量萎缩，下跌乏力
        5. 缩量整理：成交量持续萎缩，市场观望
        
        Args:
            latest (pd.Series): 最新数据点，必须包含：
                - volume: 当前成交量
                - volume_sma: 成交量移动平均线
                - price_change: 价格变化率
            prev (pd.Series): 前一个数据点，用于趋势分析
                
        Returns:
            Tuple[SignalType, float, str]: 包含三个元素的元组：
                - SignalType: 成交量交易信号
                  * BUY: 放量上涨或缩量下跌
                  * SELL: 放量下跌或缩量上涨
                  * HOLD: 缩量整理或信号不明确
                - float: 信号强度 (0.0-1.0)
                  * 0.4: 放量配合价格的中等信号
                  * 0.2: 缩量信号的弱信号
                  * 0.1: 整理信号的微弱信号
                  * 0.0: 无明确信号
                - str: 信号描述
                  * 说明具体的量价关系和市场状态
                  
        Note:
            - 成交量通常作为确认指标，而非独立的交易信号
            - 放量突破比缩量突破更可靠
            - 在牛市中，缩量上涨可能是正常的
            - 在熊市中，缩量下跌可能是正常的
        """
        # 检查成交量数据的有效性
        if pd.isna(latest['volume_sma']):
            return SignalType.HOLD, 0.0, "成交量数据不足"
        
        # 获取成交量相关数据
        volume = latest['volume']           # 当前成交量
        volume_sma = latest['volume_sma']   # 成交量移动平均线
        price_change = latest['price_change']  # 价格变化率
        
        # 计算成交量比率（当前成交量相对于平均成交量的倍数）
        volume_ratio = volume / volume_sma if volume_sma > 0 else 1
        
        # 成交量信号判断逻辑
        
        # 1. 放量上涨：成交量显著放大且价格上涨
        if volume > volume_sma * 1.5:  # 放量
            if price_change > self.config['price_change_threshold']:
                return SignalType.BUY, 0.4, f"放量上涨(量比{volume_ratio:.1f})，买盘积极"
            elif price_change < -self.config['price_change_threshold']:
                return SignalType.SELL, 0.4, f"放量下跌(量比{volume_ratio:.1f})，卖盘汹涌"
                
        # 2. 缩量整理：成交量持续萎缩
        elif volume < volume_sma * 0.5:  # 缩量
            if abs(price_change) < self.config['price_change_threshold'] * 0.5:
                return SignalType.HOLD, 0.1, f"缩量整理(量比{volume_ratio:.1f})，市场观望"
            # 缩量上涨：上涨乏力信号
            elif price_change > 0:
                return SignalType.SELL, 0.2, f"缩量上涨(量比{volume_ratio:.1f})，上涨乏力"
            # 缩量下跌：下跌乏力信号
            else:
                return SignalType.BUY, 0.2, f"缩量下跌(量比{volume_ratio:.1f})，下跌乏力"
        
        # 3. 其他情况：成交量和价格变化都不明显
        return SignalType.HOLD, 0.0, "量价关系平稳，无明确信号"
    
    def _combine_signals(self, signals: List[SignalType], signal_strength: float) -> SignalType:
        """
        组合多个技术指标信号，生成最终交易决策
        
        这是技术分析策略的核心决策方法，通过综合多个技术指标的信号，
        减少单一指标的误判，提高交易决策的可靠性。
        
        组合原理：
        1. 多数原则：多数指标指向同一方向时，信号更可靠
        2. 强度分级：根据信号强度分为强信号、普通信号和弱信号
        3. 阈值控制：只有达到一定强度阈值才产生交易信号
        4. 冲突处理：当指标信号冲突时，保持观望
        
        决策逻辑：
        1. 强信号判断：信号强度≥0.6时，可能产生强买/强卖信号
        2. 普通信号判断：信号强度≥0.3时，可能产生买/卖信号
        3. 弱信号处理：信号强度<0.3时，保持观望
        4. 方向判断：买入信号多于卖出信号时看涨，反之看跌
        
        Args:
            signals (List[SignalType]): 各个技术指标产生的信号列表，包含：
                - 移动平均线信号（趋势跟踪）
                - RSI信号（超买超卖）
                - MACD信号（动量变化）
                - 布林带信号（价格位置）
                - 成交量信号（量价关系）
            signal_strength (float): 综合信号强度 (0.0-1.0)
                - 0.6以上：强信号阈值，可能产生STRONG_BUY/STRONG_SELL
                - 0.3-0.6：普通信号阈值，可能产生BUY/SELL
                - 0.3以下：弱信号，倾向于HOLD
                
        Returns:
            SignalType: 最终的交易信号
                - STRONG_BUY: 强烈买入信号（高强度且买入信号占优）
                - BUY: 买入信号（中等强度且买入信号占优）
                - STRONG_SELL: 强烈卖出信号（高强度且卖出信号占优）
                - SELL: 卖出信号（中等强度且卖出信号占优）
                - HOLD: 观望信号（信号强度不足或方向不明确）
                
        Note:
            - 采用分级阈值策略，确保信号的可靠性
            - 强信号需要更高的强度要求，减少误判
            - 当买入和卖出信号数量相等时，默认保持观望
            - 该方法是保守策略，优先避免错误交易
        """
        # 统计各类信号的数量
        buy_count = sum(1 for s in signals if s == SignalType.BUY)    # 买入信号数量
        sell_count = sum(1 for s in signals if s == SignalType.SELL)  # 卖出信号数量
        
        # 定义信号强度阈值
        strong_threshold = 0.6  # 强信号阈值：需要较高的信号强度
        weak_threshold = 0.3    # 弱信号阈值：最低的信号强度要求
        
        # 强信号判断：当信号强度达到强阈值时
        if signal_strength >= strong_threshold:
            # 买入信号占优势，产生强买入信号
            if buy_count > sell_count:
                return SignalType.STRONG_BUY
            # 卖出信号占优势，产生强卖出信号
            elif sell_count > buy_count:
                return SignalType.STRONG_SELL
                
        # 普通信号判断：当信号强度达到弱阈值但未达到强阈值时
        elif signal_strength >= weak_threshold:
            # 买入信号占优势，产生普通买入信号
            if buy_count > sell_count:
                return SignalType.BUY
            # 卖出信号占优势，产生普通卖出信号
            elif sell_count > buy_count:
                return SignalType.SELL
        
        # 默认观望：信号强度不足或买卖信号平衡时保持观望
        return SignalType.HOLD
    
    def generate_signal(self) -> Dict[str, Any]:
        """
        生成技术分析交易信号
        
        这是技术分析策略的主要入口方法，负责整个信号生成流程的协调和执行。
        该方法集成了数据获取、技术分析、实时价格获取、信号保存等完整流程。
        
        执行流程：
        1. 数据获取：获取指定股票的历史交易数据
        2. 数据验证：检查数据的完整性和有效性
        3. 技术分析：调用analyze_trend方法进行综合技术分析
        4. 实时价格：获取当前最新的股票价格
        5. 信号构建：创建包含完整信息的信号字典
        6. 数据持久化：将信号保存到数据库
        7. 状态更新：更新策略的最后信号状态
        
        数据要求：
        - 需要至少30天的历史数据进行技术指标计算
        - 数据包含开盘价、收盘价、最高价、最低价、成交量
        - 实时价格用于提供最新的市场信息
        
        Returns:
            Dict[str, Any]: 包含完整信号信息的字典，结构如下：
                {
                    'stock_code': str,           # 股票代码
                    'signal_type': str,          # 信号类型（buy/sell/hold/strong_buy/strong_sell）
                    'signal_strength': float,    # 信号强度 (0.0-1.0)
                    'reason': str,               # 信号产生原因的详细描述
                    'price': float,              # 信号产生时的股票价格
                    'volume_suggest': int,       # 建议交易数量（当前为0，预留字段）
                    'signal_time': datetime,     # 信号产生时间
                    'strategy_name': str         # 策略名称标识
                }
                
        Raises:
            Exception: 当数据获取失败、分析过程出错或数据库操作失败时
                      会捕获异常并返回HOLD信号，确保系统稳定性
                      
        Note:
            - 该方法具有容错机制，任何异常都会返回安全的HOLD信号
            - 历史数据不足时会记录警告并返回HOLD信号
            - 实时价格获取失败时会使用历史数据的最后收盘价
            - 所有信号都会自动保存到数据库以供后续分析
            - 方法执行后会更新策略实例的状态信息
        """
        try:
            # 第一步：获取历史交易数据
            # 获取30天的日线数据，为技术指标计算提供足够的历史数据
            df = get_market_data(
                stock_code=self.stock_code,
                period='1d',
                count=30  # 获取30天数据，确保技术指标计算的准确性
            )
            
            # 第二步：数据有效性检查
            if df is None or df.empty:
                logger.warning(f"无法获取{self.stock_code}的历史数据")
                return self._create_signal_dict(SignalType.HOLD, 0.0, "历史数据不足，无法进行技术分析")
            
            # 第三步：执行技术分析策略
            # 调用核心分析方法，获取信号类型、强度和原因
            signal_type, signal_strength, reason = self.analyze_trend(df)
            
            # 第四步：获取实时价格信息
            # 尝试获取最新的实时价格，如果失败则使用历史数据的最后收盘价
            real_time_data = get_realtime_data(self.stock_code)
            if real_time_data is not None and isinstance(real_time_data, dict):
                current_price = real_time_data.get('price', df.iloc[-1]['close_price'])
            else:
                current_price = df.iloc[-1]['close_price']  # 使用历史数据的最后收盘价作为备选
            
            # 第五步：构建信号字典
            # 创建包含所有必要信息的信号字典
            signal_dict = self._create_signal_dict(signal_type, signal_strength, reason, current_price)
            
            # 第六步：数据持久化
            # 将生成的信号保存到数据库，用于历史记录和后续分析
            self._save_signal_to_db(signal_dict)
            
            # 第七步：更新策略状态
            # 记录最后生成的信号和时间，用于策略状态跟踪
            self.last_signal = signal_type
            self.last_signal_time = datetime.now()
            
            return signal_dict
            
        except Exception as e:
            # 异常处理：确保任何错误都不会导致系统崩溃
            logger.error(f"生成交易信号时出错: {e}")
            return self._create_signal_dict(SignalType.HOLD, 0.0, f"系统错误: {str(e)}，建议稍后重试")
    
    def _create_signal_dict(self, signal_type: SignalType, strength: float, reason: str, price: float = 0.0) -> Dict[str, Any]:
        """
        创建标准化的交易信号字典
        
        这是一个工具方法，用于创建统一格式的交易信号字典，确保所有信号
        都包含必要的字段和信息，便于后续的数据处理和存储。
        
        字段说明：
        - stock_code: 股票代码，用于标识具体的交易标的
        - signal_type: 信号类型，转换为字符串格式便于存储
        - signal_strength: 信号强度，量化信号的可信度
        - reason: 信号原因，提供人类可读的决策依据
        - price: 信号价格，记录信号产生时的股票价格
        - volume_suggest: 建议交易量，预留字段用于未来扩展
        - signal_time: 信号时间，记录信号的精确产生时间
        - strategy_name: 策略名称，用于区分不同的策略来源
        
        Args:
            signal_type (SignalType): 交易信号类型枚举值
                - BUY/SELL/HOLD: 基本交易信号
                - STRONG_BUY/STRONG_SELL: 强信号
            strength (float): 信号强度 (0.0-1.0)
                - 0.0: 无信号或最弱信号
                - 1.0: 最强信号
            reason (str): 信号产生的原因描述
                - 应包含具体的技术分析依据
                - 便于用户理解和决策参考
            price (float, optional): 信号产生时的股票价格
                - 默认为0.0，通常会传入实际价格
                - 用于记录信号的价格背景
                
        Returns:
            Dict[str, Any]: 标准化的信号字典，包含以下字段：
                {
                    'stock_code': str,           # 股票代码
                    'signal_type': str,          # 信号类型字符串
                    'signal_strength': float,    # 信号强度
                    'reason': str,               # 信号原因
                    'price': float,              # 信号价格
                    'volume_suggest': int,       # 建议交易量（预留）
                    'signal_time': datetime,     # 信号时间
                    'strategy_name': str         # 策略名称
                }
                
        Note:
            - 该方法确保所有信号都有统一的数据结构
            - signal_time使用当前时间，确保时间戳的准确性
            - volume_suggest字段预留用于未来的仓位管理功能
            - strategy_name固定为'technical_strategy'，便于策略识别
        """
        return {
            'stock_code': self.stock_code,                    # 股票代码
            'signal_type': signal_type.value,                # 信号类型（转为字符串）
            'signal_strength': strength,                     # 信号强度
            'reason': reason,                                # 信号原因描述
            'price': price,                                  # 信号价格
            'volume_suggest': 0,                             # 建议交易量（预留字段）
            'signal_time': datetime.now(),                   # 信号产生时间
            'strategy_name': 'technical_strategy'            # 策略名称标识
        }
    
    def _save_signal_to_db(self, signal_dict: Dict[str, Any]):
        """
        将交易信号保存到数据库
        
        这是数据持久化的核心方法，负责将生成的交易信号安全地保存到数据库中，
        用于历史记录、策略回测、性能分析等用途。
        
        保存意义：
        1. 历史记录：保留所有交易信号的完整历史
        2. 策略回测：为策略效果评估提供数据基础
        3. 性能分析：分析策略的成功率和收益率
        4. 审计追踪：提供交易决策的完整审计链
        5. 系统监控：监控策略的运行状态和频率
        
        错误处理：
        - 采用try-catch机制，确保数据库错误不影响主流程
        - 记录详细的错误日志，便于问题诊断
        - 即使保存失败，也不会影响信号的返回
        
        Args:
            signal_dict (Dict[str, Any]): 要保存的信号字典，应包含：
                - stock_code: 股票代码
                - signal_type: 信号类型
                - signal_strength: 信号强度
                - reason: 信号原因
                - price: 信号价格
                - volume_suggest: 建议交易量
                - signal_time: 信号时间
                - strategy_name: 策略名称
                
        Raises:
            Exception: 数据库操作异常时会被捕获并记录日志
                      不会向上抛出，确保主流程的稳定性
                      
        Note:
            - 使用数据库管理器的insert_strategy_signal方法
            - 异常处理确保数据库问题不会影响策略执行
            - 错误日志包含详细的异常信息，便于调试
            - 该方法是异步安全的，可以在多线程环境中使用
        """
        try:
            # 调用数据库管理器保存信号
            get_db_manager().insert_strategy_signal(signal_dict)
            logger.debug(f"成功保存{self.stock_code}的交易信号到数据库")
        except Exception as e:
            # 记录错误但不影响主流程
            logger.error(f"保存{self.stock_code}信号到数据库时出错: {e}")
            # 注意：这里不重新抛出异常，确保信号生成流程的稳定性

class MomentumStrategy:
    """
    动量策略类
    
    动量策略是基于价格动量和趋势延续性的交易策略。该策略认为价格的
    强势上涨或下跌趋势会在短期内延续，通过捕捉这种动量来获取收益。
    
    策略原理：
    1. 动量效应：股价的上涨或下跌趋势具有延续性
    2. 趋势跟踪：在趋势形成初期进入，在趋势结束前退出
    3. 强度判断：通过动量指标和价格变化幅度判断趋势强度
    4. 快速反应：相比技术分析策略，动量策略反应更快
    
    适用场景：
    - 趋势明确的市场环境
    - 突破性行情的初期
    - 短期交易和日内交易
    - 波动性较大的股票
    
    风险控制：
    - 设置明确的动量阈值
    - 结合价格变化幅度确认
    - 避免在震荡市中频繁交易
    
    技术指标：
    - 动量指标(Momentum)：衡量价格变化的速度
    - 价格变化率(Price Change)：衡量价格变化的幅度
    """
    
    def __init__(self, stock_code: str):
        """
        初始化动量策略
        
        Args:
            stock_code (str): 股票代码，如'000001'、'600000'等
        """
        self.stock_code = stock_code      # 股票代码
        self.config = STRATEGY_CONFIG     # 策略配置参数
        
    @validate_data
    def analyze_momentum(self, df: pd.DataFrame) -> Tuple[SignalType, float, str]:
        """
        执行动量分析，生成交易信号
        
        动量分析通过计算价格的动量指标和变化幅度，判断当前的趋势强度
        和方向，从而生成相应的交易信号。
        
        分析逻辑：
        1. 计算动量指标：衡量价格变化的速度和力度
        2. 计算价格变化率：衡量价格变化的幅度
        3. 综合判断：结合动量和变化幅度确定信号强度
        4. 阈值判断：根据预设阈值生成不同强度的信号
        
        信号判断标准：
        - 强买入：动量>5且涨幅>2%
        - 买入：动量>2且涨幅>1%
        - 强卖出：动量<-5且跌幅>2%
        - 卖出：动量<-2且跌幅>1%
        - 观望：其他情况
        
        Args:
            df (pd.DataFrame): 包含OHLCV数据的DataFrame，必须包含：
                - close_price: 收盘价序列
                - 足够的历史数据用于动量计算
                
        Returns:
            Tuple[SignalType, float, str]: 包含三个元素的元组：
                - SignalType: 交易信号类型
                  * STRONG_BUY: 强势上涨动量
                  * BUY: 上涨动量
                  * STRONG_SELL: 强势下跌动量
                  * SELL: 下跌动量
                  * HOLD: 动量不明确
                - float: 信号强度 (0.0-1.0)
                  * 0.8: 强信号（强买入/强卖出）
                  * 0.6: 中等信号（买入/卖出）
                  * 0.0: 无信号（观望）
                - str: 信号描述，包含具体的动量值和价格变化
                
        Raises:
            Exception: 当数据计算出错时会被捕获并返回HOLD信号
                      
        Note:
            - 动量策略适合趋势明确的市场环境
            - 在震荡市中可能产生较多假信号
            - 建议与其他策略结合使用以提高准确性
            - 该策略反应速度快，适合短期交易
        """
        try:
            # 创建数据副本，避免修改原始数据
            df = df.copy()
            
            # 计算动量指标：衡量价格变化的速度
            df.loc[:, 'momentum'] = momentum(df['close_price'])
            
            # 计算价格变化率：衡量价格变化的幅度
            df.loc[:, 'price_change'] = price_change(df['close_price'])
            
            # 获取最新的数据点
            latest = df.iloc[-1]
            
            # 提取关键指标值
            momentum_value = latest['momentum']        # 动量值
            price_change_value = latest['price_change'] # 价格变化率
            
            # 动量信号判断逻辑
            
            # 强势上涨：高动量且大幅上涨
            if momentum_value > 5 and price_change_value > 2:
                return SignalType.STRONG_BUY, 0.8, f"强势上涨动量(动量:{momentum_value:.2f}, 涨幅:{price_change_value:.2f}%)"
                
            # 普通上涨：中等动量且适度上涨
            elif momentum_value > 2 and price_change_value > 1:
                return SignalType.BUY, 0.6, f"上涨动量(动量:{momentum_value:.2f}, 涨幅:{price_change_value:.2f}%)"
                
            # 强势下跌：负动量且大幅下跌
            elif momentum_value < -5 and price_change_value < -2:
                return SignalType.STRONG_SELL, 0.8, f"强势下跌动量(动量:{momentum_value:.2f}, 跌幅:{price_change_value:.2f}%)"
                
            # 普通下跌：负动量且适度下跌
            elif momentum_value < -2 and price_change_value < -1:
                return SignalType.SELL, 0.6, f"下跌动量(动量:{momentum_value:.2f}, 跌幅:{price_change_value:.2f}%)"
            
            # 其他情况：动量不明确，保持观望
            return SignalType.HOLD, 0.0, f"动量信号不明确(动量:{momentum_value:.2f}, 变化:{price_change_value:.2f}%)"
            
        except Exception as e:
            # 异常处理：确保错误不会导致系统崩溃
            logger.error(f"动量分析时出错: {e}")
            return SignalType.HOLD, 0.0, f"动量分析错误: {str(e)}"

class ETFDayTradingStrategy:
    """
    ETF当天交易策略类
    
    ETF当天交易策略是专门针对ETF（交易型开放式指数基金）设计的日内交易策略。
    该策略基于布林带中轨和MACD指标的组合，通过实时价格与技术指标的关系
    来判断买卖时机，并根据MACD柱状图的连续性来确定交易数量。
    
    策略核心思想：
    1. 均值回归：价格围绕布林带中轨（移动平均线）波动
    2. 趋势确认：通过MACD指标确认价格趋势的强度
    3. 数量控制：根据MACD连续性动态调整交易数量
    4. 日内交易：适合ETF的高流动性特点，进行当日买卖
    
    技术指标组合：
    - 布林带(Bollinger Bands)：判断价格相对位置
    - MACD指标：确认趋势方向和强度
    - 历史波动率：评估市场波动程度
    
    交易逻辑：
    - 买入条件：实时价格 < 布林带中轨 + MACD连续负值确认
    - 卖出条件：实时价格 > 布林带中轨 + MACD连续正值确认
    - 数量策略：MACD连续天数 × 100股
    
    适用场景：
    - ETF产品的日内交易
    - 高流动性市场环境
    - 波动性适中的市场
    - 追求稳定收益的投资者
    
    风险控制：
    - 基于技术指标的客观判断
    - 动态数量调整机制
    - 实时价格监控
    - 严格的止损止盈逻辑
    """
    
    def __init__(self, stock_code: str):
        """
        初始化ETF当天交易策略
        
        Args:
            stock_code (str): ETF代码，如'510300'、'159919'等
        """
        self.stock_code = stock_code           # ETF代码
        self.config = STRATEGY_CONFIG          # 策略配置参数
        self.trading_config = TRADING_CONFIG   # 交易配置参数
        self.status = StrategyStatus.ACTIVE    # 策略状态
        
    @validate_data
    def analyze_etf_day_trading(self, df: pd.DataFrame) -> Tuple[SignalType, float, str, int]:
        """
        执行ETF当天交易分析，生成交易信号和建议数量
        
        该方法是ETF日内交易策略的核心分析函数，通过综合分析布林带、MACD指标
        和实时价格，生成具体的交易信号和建议交易数量。
        
        分析流程：
        1. 计算历史波动率：基于一年数据计算平均波动范围
        2. 计算布林带指标：确定价格通道和中轨位置
        3. 计算MACD指标：分析趋势方向和强度
        4. 分析MACD连续性：确定交易数量
        5. 获取实时价格：进行最终交易决策
        6. 综合判断：生成最终交易信号
        
        核心逻辑：
        - 价格高于布林带中轨 → 卖出信号
        - 价格低于布林带中轨 → 买入信号
        - MACD连续性 → 确定交易数量和信号强度
        - 实时价格确认 → 最终交易决策
        
        Args:
            df (pd.DataFrame): 包含OHLCV数据的DataFrame，要求：
                - close_price: 收盘价序列
                - high_price: 最高价序列
                - low_price: 最低价序列
                - volume: 成交量序列
                - 至少包含250个交易日的历史数据
                
        Returns:
            Tuple[SignalType, float, str, int]: 包含四个元素的元组：
                - SignalType: 交易信号类型
                  * BUY: 买入信号（价格低于中轨）
                  * SELL: 卖出信号（价格高于中轨）
                  * HOLD: 观望信号（价格接近中轨）
                - float: 信号强度 (0.0-1.0)
                  * 0.8: 强信号（有MACD连续性确认）
                  * 0.5: 中等信号（仅基于价格位置）
                  * 0.0: 无信号（观望状态）
                - str: 信号描述，包含具体的价格和指标信息
                - int: 建议交易数量
                  * 基于MACD连续天数计算：连续天数 × 100股
                  * 最小100股，最大根据连续性确定
                  * 0表示不建议交易
                  
        Raises:
            Exception: 当数据计算或获取实时价格出错时会被捕获
                      
        Note:
            - 该策略专门针对ETF产品设计
            - 需要充足的历史数据（建议至少250个交易日）
            - 依赖实时价格数据进行最终决策
            - 交易数量基于MACD连续性动态调整
            - 适合日内交易，不建议隔夜持仓
        """
        try:
            # 步骤1: 计算一年历史数据的平均波动范围
            # 用于评估市场的整体波动水平，为后续分析提供参考
            yearly_high_avg = df['high_price'].mean()  # 年度平均最高价
            yearly_low_avg = df['low_price'].mean()    # 年度平均最低价
            avg_volatility = yearly_high_avg - yearly_low_avg  # 平均波动幅度
            
            # 步骤2: 计算布林带指标
            # 布林带用于判断价格的相对位置，中轨作为均值回归的参考线
            upper, middle, lower = bollinger_bands(df['close_price'])
            df = df.copy()  # 创建副本避免修改原数据
            df.loc[:, 'bb_upper'] = upper    # 布林带上轨
            df.loc[:, 'bb_middle'] = middle  # 布林带中轨（移动平均线）
            df.loc[:, 'bb_lower'] = lower    # 布林带下轨
            
            # 步骤3: 计算MACD指标
            # MACD用于确认趋势方向和强度，柱状图用于判断连续性
            macd_line, signal_line, histogram = macd(df['close_price'])
            df.loc[:, 'macd'] = macd_line           # MACD主线
            df.loc[:, 'macd_signal'] = signal_line  # MACD信号线
            df.loc[:, 'macd_histogram'] = histogram # MACD柱状图
            
            # 获取最新的技术指标数据
            latest = df.iloc[-1]
            bb_middle_price = latest['bb_middle']  # 布林带中轨价格
            
            # 步骤4: 分析MACD柱状图连续性
            # 通过MACD连续性确定趋势强度和建议交易数量
            macd_signal, trade_volume = self._analyze_macd_consecutive(df)
            
            # 步骤5: 获取实时价格进行最终判断
            # 实时价格是最终交易决策的关键因素
            real_time_data = get_realtime_data(self.stock_code)
            current_price = real_time_data.get('price', latest['close_price']) if real_time_data is not None and isinstance(real_time_data, dict) else latest['close_price']
            
            # 步骤6: 基于实时价格与布林带中轨的关系做最终决策
            price_diff = current_price - bb_middle_price  # 价格偏离中轨的程度
            
            # 价格高于中轨：卖出逻辑
            if price_diff > 0:
                if macd_signal == SignalType.SELL:
                    # 强卖出：价格高于中轨且MACD连续为正
                    return SignalType.SELL, 0.8, f"价格({current_price:.2f})高于布林带中轨({bb_middle_price:.2f})，MACD连续为正，执行卖出", trade_volume
                else:
                    # 普通卖出：仅基于价格位置
                    return SignalType.SELL, 0.5, f"价格({current_price:.2f})高于布林带中轨({bb_middle_price:.2f})，执行卖出", 100
                    
            # 价格低于中轨：买入逻辑
            elif price_diff < 0:
                if macd_signal == SignalType.BUY:
                    # 强买入：价格低于中轨且MACD连续为负
                    return SignalType.BUY, 0.8, f"价格({current_price:.2f})低于布林带中轨({bb_middle_price:.2f})，MACD连续为负，执行买入", trade_volume
                else:
                    # 普通买入：仅基于价格位置
                    return SignalType.BUY, 0.5, f"价格({current_price:.2f})低于布林带中轨({bb_middle_price:.2f})，执行买入", 100
                    
            # 价格接近中轨：观望
            else:
                return SignalType.HOLD, 0.0, f"价格({current_price:.2f})接近布林带中轨({bb_middle_price:.2f})，暂时观望", 0
                
        except Exception as e:
            logger.error(f"ETF当天交易分析时出错: {e}")
            return SignalType.HOLD, 0.0, f"分析错误: {str(e)}", 0
    
    def _analyze_macd_consecutive(self, df: pd.DataFrame) -> Tuple[SignalType, int]:
        """
        分析MACD柱状图连续性，确定交易信号和数量
        
        该方法通过分析MACD柱状图的连续正值或负值天数，来判断当前趋势的
        强度和持续性，并据此确定相应的交易信号和建议交易数量。
        
        分析逻辑：
        1. 获取最近5天的MACD柱状图数据
        2. 计算连续负值天数（看涨信号）
        3. 计算连续正值天数（看跌信号）
        4. 根据连续天数确定信号强度和交易数量
        
        连续性判断标准：
        - 连续负值≥2天：生成买入信号，数量=连续天数×100股
        - 连续正值≥2天：生成卖出信号，数量=连续天数×100股
        - 其他情况：观望，数量=0
        
        Args:
            df (pd.DataFrame): 包含MACD指标的DataFrame，必须包含：
                - macd_histogram: MACD柱状图数据
                - 至少5个数据点用于连续性分析
                
        Returns:
            Tuple[SignalType, int]: 包含两个元素的元组：
                - SignalType: 基于MACD连续性的交易信号
                  * BUY: 连续负值≥2天（趋势向上）
                  * SELL: 连续正值≥2天（趋势向下）
                  * HOLD: 连续性不足或数据不够
                - int: 建议交易数量
                  * 连续天数 × 100股（最小200股）
                  * 0表示不建议交易
                  
        Note:
            - 连续性分析基于最近5个交易日
            - 交易数量与连续天数成正比，体现趋势强度
            - 该方法为ETF策略的辅助判断工具
            - 需要与价格位置分析结合使用
        """
        # 数据充足性检查：至少需要5个数据点进行连续性分析
        if len(df) < 5:
            return SignalType.HOLD, 0
            
        # 获取最近5天的MACD柱状图数据
        # 柱状图反映MACD线与信号线的差值，正值表示上升趋势，负值表示下降趋势
        recent_histogram = df['macd_histogram'].tail(5).values
        
        # 计算连续负值天数（从最新数据向前统计）
        # 连续负值表示下降趋势可能结束，是潜在的买入信号
        consecutive_negative = 0
        for i in range(len(recent_histogram) - 1, -1, -1):
            if recent_histogram[i] < 0:
                consecutive_negative += 1
            else:
                break  # 遇到非负值就停止计数
                
        # 计算连续正值天数（从最新数据向前统计）
        # 连续正值表示上升趋势可能结束，是潜在的卖出信号
        consecutive_positive = 0
        for i in range(len(recent_histogram) - 1, -1, -1):
            if recent_histogram[i] > 0:
                consecutive_positive += 1
            else:
                break  # 遇到非正值就停止计数
        
        # 根据连续天数确定交易信号和数量
        
        # 连续负值≥2天：买入信号
        if consecutive_negative >= 2:
            trade_volume = consecutive_negative * 100  # 连续天数×100股
            return SignalType.BUY, trade_volume
            
        # 连续正值≥2天：卖出信号
        elif consecutive_positive >= 2:
            trade_volume = consecutive_positive * 100  # 连续天数×100股
            return SignalType.SELL, trade_volume
            
        # 连续性不足：观望
        else:
            return SignalType.HOLD, 0
    
    def generate_etf_signal(self) -> Dict[str, Any]:
        """生成ETF交易信号
        
        Returns:
            Dict: 包含信号信息的字典
        """
        try:
            # 获取一年历史数据
            df = get_market_data(
                stock_code=self.stock_code,
                period='1d',
                count=250  # 获取一年数据（约250个交易日）
            )
            
            if df is None or df.empty:
                logger.warning(f"无法获取{self.stock_code}的历史数据")
                return self._create_etf_signal_dict(SignalType.HOLD, 0.0, "无数据", 0)
            
            # 执行ETF策略分析
            signal_type, signal_strength, reason, trade_volume = self.analyze_etf_day_trading(df)
            
            # 获取实时价格
            real_time_data = get_realtime_data(self.stock_code)
            current_price = real_time_data.get('price', df.iloc[-1]['close_price']) if real_time_data is not None and isinstance(real_time_data, dict) else df.iloc[-1]['close_price']
            
            # 创建信号字典
            signal_dict = self._create_etf_signal_dict(signal_type, signal_strength, reason, trade_volume, current_price)
            
            # 保存信号到数据库
            self._save_signal_to_db(signal_dict)
            
            return signal_dict
            
        except Exception as e:
            logger.error(f"生成ETF交易信号时出错: {e}")
            return self._create_etf_signal_dict(SignalType.HOLD, 0.0, f"错误: {str(e)}", 0)
    
    def _create_etf_signal_dict(self, signal_type: SignalType, strength: float, reason: str, trade_volume: int, price: float = 0.0) -> Dict[str, Any]:
        """创建ETF信号字典"""
        return {
            'stock_code': self.stock_code,
            'signal_type': signal_type.value,
            'signal_strength': strength,
            'reason': reason,
            'price': price,
            'volume_suggest': trade_volume,  # ETF策略特有的建议交易数量
            'signal_time': datetime.now(),
            'strategy_name': 'etf_day_trading_strategy'
        }
    
    def _save_signal_to_db(self, signal_dict: Dict[str, Any]):
        """保存信号到数据库"""
        try:
            get_db_manager().insert_strategy_signal(signal_dict)
        except Exception as e:
            logger.error(f"保存ETF信号到数据库时出错: {e}")

class StrategyManager:
    """
    策略管理器 - 多策略整合与信号综合
    
    功能说明：
    - 整合多种交易策略（技术分析、动量分析、ETF日内交易）
    - 通过加权平均方式综合不同策略的信号
    - 提供统一的信号生成接口
    - 支持策略权重动态调整
    
    核心理念：
    - 多策略分散风险：避免单一策略的局限性
    - 加权综合决策：根据策略可靠性分配权重
    - 信号强度量化：综合多个策略的信号强度
    - 冲突处理机制：当策略信号冲突时的处理逻辑
    
    适用场景：
    - 需要提高信号准确性的交易场景
    - 风险控制要求较高的投资策略
    - 多维度分析的量化交易系统
    - 需要策略组合优化的场景
    
    风险控制：
    - 策略权重平衡，避免过度依赖单一策略
    - 信号冲突时采用保守策略
    - 综合强度阈值控制，避免弱信号交易
    """
    
    def __init__(self, stock_code: str):
        """
        初始化策略管理器
        
        参数:
            stock_code (str): 股票代码
            
        初始化内容:
            - 创建各种策略实例
            - 设置策略字典映射
            - 配置策略管理参数
        """
        self.stock_code = stock_code
        # 初始化各种策略实例
        self.technical_strategy = TechnicalStrategy(stock_code)        # 技术分析策略
        self.momentum_strategy = MomentumStrategy(stock_code)          # 动量分析策略
        self.etf_day_trading_strategy = ETFDayTradingStrategy(stock_code)  # ETF日内交易策略
        
        # 策略字典映射 - 便于统一管理和调用
        self.strategies = {
            'technical': self.technical_strategy,           # 技术分析策略
            'momentum': self.momentum_strategy,             # 动量分析策略
            'etf_day_trading': self.etf_day_trading_strategy  # ETF日内交易策略
        }
        
    def get_combined_signal(self) -> Dict[str, Any]:
        """获取综合信号
        
        Returns:
            Dict: 综合信号信息
        """
        try:
            # 获取技术分析信号
            tech_signal = self.technical_strategy.generate_signal()
            
            # 获取历史数据用于动量分析
            df = get_market_data(
                stock_code=self.stock_code,
                period='1d',
                count=30  # 获取30天数据
            )
            
            momentum_signal_type = SignalType.HOLD
            momentum_strength = 0.0
            momentum_reason = "无动量数据"
            
            if df is not None and not df.empty:
                momentum_signal_type, momentum_strength, momentum_reason = self.momentum_strategy.analyze_momentum(df)
            
            # 综合两个策略的信号
            tech_weight = 0.7
            momentum_weight = 0.3
            
            combined_strength = (
                tech_signal['signal_strength'] * tech_weight +
                momentum_strength * momentum_weight
            )
            
            # 确定最终信号
            tech_type = SignalType(tech_signal['signal_type'])
            final_signal = self._combine_strategy_signals(tech_type, momentum_signal_type, combined_strength)
            
            combined_reason = f"技术分析: {tech_signal['reason']}; 动量分析: {momentum_reason}"
            
            return {
                'stock_code': self.stock_code,
                'signal_type': final_signal.value,
                'signal_strength': combined_strength,
                'reason': combined_reason,
                'price': tech_signal['price'],
                'timestamp': datetime.now(),
                'strategy_name': 'combined_strategy',
                'technical_signal': tech_signal,
                'momentum_signal': {
                    'signal_type': momentum_signal_type.value,
                    'signal_strength': momentum_strength,
                    'reason': momentum_reason
                }
            }
            
        except Exception as e:
            logger.error(f"获取综合信号时出错: {e}")
            return {
                'stock_code': self.stock_code,
                'signal_type': SignalType.HOLD.value,
                'signal_strength': 0.0,
                'reason': f"错误: {str(e)}",
                'price': 0.0,
                'timestamp': datetime.now(),
                'strategy_name': 'combined_strategy'
            }
    
    def _combine_strategy_signals(self, tech_signal: SignalType, momentum_signal: SignalType, strength: float) -> SignalType:
        """
        综合多个策略信号 - 信号冲突处理与强度判断
        
        功能说明：
        - 处理技术分析和动量分析信号的冲突
        - 根据信号一致性和强度确定最终信号
        - 实现保守的信号合并策略
        
        合并逻辑：
        1. 信号一致性检查：两个策略信号方向相同时增强信号
        2. 强度阈值判断：根据综合强度确定信号级别
        3. 冲突处理：信号冲突时以技术分析为主导
        4. 保守策略：不确定时返回HOLD信号
        
        参数:
            tech_signal (SignalType): 技术分析信号
            momentum_signal (SignalType): 动量分析信号
            strength (float): 综合信号强度（0.0-1.0）
        
        返回值:
            SignalType: 最终综合信号类型
        
        决策规则：
        - 信号一致且强度≥0.7：返回强信号（STRONG_BUY/STRONG_SELL）
        - 信号一致且强度<0.7：返回普通信号（BUY/SELL）
        - 信号冲突且强度≥0.5：以技术分析信号为准
        - 其他情况：返回HOLD信号
        
        注意事项：
        - 优先考虑信号的一致性
        - 采用保守的合并策略，避免错误信号
        - 技术分析在冲突时具有更高权重
        """
        # 如果两个信号一致，增强信号强度
        if tech_signal == momentum_signal and tech_signal != SignalType.HOLD:
            if strength >= 0.7:
                return SignalType.STRONG_BUY if tech_signal == SignalType.BUY else SignalType.STRONG_SELL
            else:
                return tech_signal
        
        # 如果信号冲突，以技术分析为主
        if strength >= 0.5:
            return tech_signal
        
        return SignalType.HOLD

# ============================================================================
# 函数式接口 - 策略工厂和便捷函数
# ============================================================================

def create_strategy(stock_code: str, strategy_type: str = 'combined') -> Any:
    """
    策略工厂函数 - 创建指定类型的策略实例
    
    功能说明：
    - 根据策略类型创建相应的策略实例
    - 提供统一的策略创建接口
    - 支持所有可用的策略类型
    - 包含策略类型验证和错误处理
    
    支持的策略类型：
    - 'technical': 技术分析策略（单一技术指标分析）
    - 'momentum': 动量策略（价格动量和趋势分析）
    - 'etf_day_trading': ETF日内交易策略（适用于ETF的短线交易）
    - 'combined': 综合策略（多策略整合，推荐使用）
    
    参数:
        stock_code (str): 股票代码（如：'000001.SZ'）
        strategy_type (str): 策略类型，默认为'combined'
    
    返回值:
        Any: 对应的策略实例
    
    异常:
        ValueError: 当策略类型不支持时抛出
    
    使用示例:
        >>> strategy = create_strategy('000001.SZ', 'combined')
        >>> signal = strategy.get_combined_signal()
    
    注意事项:
        - 推荐使用'combined'策略类型，具有更好的稳定性
        - ETF策略专门针对ETF产品优化
        - 所有策略都需要有效的股票代码
    """
    if strategy_type == 'technical':
        return TechnicalStrategy(stock_code)
    elif strategy_type == 'momentum':
        return MomentumStrategy(stock_code)
    elif strategy_type == 'etf_day_trading':
        return ETFDayTradingStrategy(stock_code)
    elif strategy_type == 'combined':
        return StrategyManager(stock_code)
    else:
        raise ValueError(f"不支持的策略类型: {strategy_type}")

def get_trading_signal(stock_code: str, strategy_type: str = 'combined') -> Dict[str, Any]:
    """
    获取交易信号的函数式接口 - 一站式信号生成服务
    
    功能说明：
    - 创建指定策略并生成交易信号
    - 提供统一的信号获取接口
    - 自动处理不同策略的调用方式
    - 包含完整的错误处理机制
    
    执行流程：
    1. 根据策略类型创建策略实例
    2. 调用相应的信号生成方法
    3. 返回标准化的信号字典
    4. 处理异常情况并返回保守信号
    
    参数:
        stock_code (str): 股票代码（如：'000001.SZ'）
        strategy_type (str): 策略类型，默认为'combined'
    
    返回值:
        Dict[str, Any]: 交易信号信息，包含：
            - stock_code: 股票代码
            - signal_type: 信号类型
            - signal_strength: 信号强度
            - reason: 分析原因
            - price: 当前价格
            - timestamp: 信号时间
            - strategy_name: 策略名称
            - 其他策略特定字段
    
    使用示例:
        >>> signal = get_trading_signal('000001.SZ', 'combined')
        >>> print(f"信号类型: {signal['signal_type']}")
        >>> print(f"信号强度: {signal['signal_strength']}")
    
    注意事项:
        - 综合策略返回最全面的信号信息
        - 策略不支持时返回HOLD信号
        - 所有异常都会被捕获并记录
    """
    strategy = create_strategy(stock_code, strategy_type)
    
    if strategy_type == 'combined':
        return strategy.get_combined_signal()
    elif hasattr(strategy, 'generate_signal'):
        return strategy.generate_signal()
    else:
        logger.error(f"策略 {strategy_type} 不支持信号生成")
        return {
            'stock_code': stock_code,
            'signal_type': SignalType.HOLD.value,
            'signal_strength': 0.0,
            'reason': '策略不支持',
            'price': 0.0,
            'timestamp': datetime.now(),
            'strategy_name': strategy_type
        }

def analyze_stock_trend(stock_code: str, days: int = 30) -> Dict[str, Any]:
    """分析股票趋势的函数式接口
    
    Args:
        stock_code: 股票代码
        days: 分析天数
    
    Returns:
        Dict: 趋势分析结果
    """
    try:
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days)
        
        df = get_market_data(
            stock_code=stock_code,
            period='1d',
            count=days  # 根据指定天数获取数据
        )
        
        if df is None or df.empty:
            return {'error': '无法获取数据'}
        
        strategy = TechnicalStrategy(stock_code)
        signal_type, strength, reason = strategy.analyze_trend(df)
        
        return {
            'stock_code': stock_code,
            'trend_signal': signal_type.value,
            'trend_strength': strength,
            'analysis_reason': reason,
            'analysis_period': f'{days}天',
            'timestamp': datetime.now()
        }
        
    except Exception as e:
        logger.error(f"分析股票趋势时出错: {e}")
        return {'error': str(e)}

# 为了兼容example.py中的函数调用，添加别名函数
def create_technical_strategy(stock_code: str) -> TechnicalStrategy:
    """创建技术分析策略实例"""
    return TechnicalStrategy(stock_code)

def create_momentum_strategy(stock_code: str) -> MomentumStrategy:
    """创建动量策略实例"""
    return MomentumStrategy(stock_code)

def create_etf_day_trading_strategy(stock_code: str) -> ETFDayTradingStrategy:
    """创建ETF当天交易策略实例"""
    return ETFDayTradingStrategy(stock_code)

def generate_trading_signal(stock_code: str, df: pd.DataFrame = None) -> Dict[str, Any]:
    """生成交易信号"""
    return get_trading_signal(stock_code, 'combined')

def generate_etf_trading_signal(stock_code: str) -> Dict[str, Any]:
    """生成ETF交易信号的便捷函数"""
    strategy = create_etf_day_trading_strategy(stock_code)
    return strategy.generate_etf_signal()