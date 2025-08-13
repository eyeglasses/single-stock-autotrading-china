# -*- coding: utf-8 -*-
"""
技术指标计算模块
提供各种技术分析指标的计算功能
"""

import pandas as pd
import numpy as np
from typing import Tuple, Optional, Union
from functools import wraps
from loguru import logger

def validate_data(func):
    """验证数据有效性的装饰器"""
    @wraps(func)
    def wrapper(data, *args, **kwargs):
        if data is None or len(data) == 0:
            logger.warning(f"数据为空，无法计算指标: {func.__name__}")
            return None
        return func(data, *args, **kwargs)
    return wrapper

@validate_data
def sma(data: pd.Series, period: int) -> pd.Series:
    """简单移动平均线
    
    Args:
        data: 价格序列
        period: 周期
    
    Returns:
        pd.Series: SMA值
    """
    return data.rolling(window=period).mean()

@validate_data
def ema(data: pd.Series, period: int) -> pd.Series:
    """指数移动平均线
    
    Args:
        data: 价格序列
        period: 周期
    
    Returns:
        pd.Series: EMA值
    """
    return data.ewm(span=period).mean()

@validate_data
def rsi(data: pd.Series, period: int = 14) -> pd.Series:
    """相对强弱指标
    
    Args:
        data: 价格序列
        period: 周期，默认14
    
    Returns:
        pd.Series: RSI值
    """
    delta = data.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    
    rs = gain / loss
    rsi_values = 100 - (100 / (1 + rs))
    
    return rsi_values

@validate_data
def macd(data: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9) -> Tuple[pd.Series, pd.Series, pd.Series]:
    """MACD指标
    
    Args:
        data: 价格序列
        fast: 快线周期，默认12
        slow: 慢线周期，默认26
        signal: 信号线周期，默认9
    
    Returns:
        Tuple[pd.Series, pd.Series, pd.Series]: (MACD线, 信号线, 柱状图)
    """
    ema_fast = ema(data, fast)
    ema_slow = ema(data, slow)
    
    macd_line = ema_fast - ema_slow
    signal_line = ema(macd_line, signal)
    histogram = macd_line - signal_line
    
    return macd_line, signal_line, histogram

@validate_data
def bollinger_bands(data: pd.Series, period: int = 20, std_dev: float = 2) -> Tuple[pd.Series, pd.Series, pd.Series]:
    """布林带
    
    Args:
        data: 价格序列
        period: 周期，默认20
        std_dev: 标准差倍数，默认2
    
    Returns:
        Tuple[pd.Series, pd.Series, pd.Series]: (上轨, 中轨, 下轨)
    """
    middle = sma(data, period)
    std = data.rolling(window=period).std()
    
    upper = middle + (std * std_dev)
    lower = middle - (std * std_dev)
    
    return upper, middle, lower

@validate_data
def stochastic(high: pd.Series, low: pd.Series, close: pd.Series, k_period: int = 14, d_period: int = 3) -> Tuple[pd.Series, pd.Series]:
    """随机指标KD
    
    Args:
        high: 最高价序列
        low: 最低价序列
        close: 收盘价序列
        k_period: K值周期，默认14
        d_period: D值周期，默认3
    
    Returns:
        Tuple[pd.Series, pd.Series]: (K值, D值)
    """
    lowest_low = low.rolling(window=k_period).min()
    highest_high = high.rolling(window=k_period).max()
    
    k_percent = 100 * ((close - lowest_low) / (highest_high - lowest_low))
    d_percent = k_percent.rolling(window=d_period).mean()
    
    return k_percent, d_percent

@validate_data
def williams_r(high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14) -> pd.Series:
    """威廉指标
    
    Args:
        high: 最高价序列
        low: 最低价序列
        close: 收盘价序列
        period: 周期，默认14
    
    Returns:
        pd.Series: Williams %R值
    """
    highest_high = high.rolling(window=period).max()
    lowest_low = low.rolling(window=period).min()
    
    wr = -100 * ((highest_high - close) / (highest_high - lowest_low))
    
    return wr

@validate_data
def atr(high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14) -> pd.Series:
    """平均真实波幅
    
    Args:
        high: 最高价序列
        low: 最低价序列
        close: 收盘价序列
        period: 周期，默认14
    
    Returns:
        pd.Series: ATR值
    """
    prev_close = close.shift(1)
    
    tr1 = high - low
    tr2 = abs(high - prev_close)
    tr3 = abs(low - prev_close)
    
    true_range = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    atr_values = true_range.rolling(window=period).mean()
    
    return atr_values

@validate_data
def volume_sma(volume: pd.Series, period: int = 10) -> pd.Series:
    """成交量移动平均
    
    Args:
        volume: 成交量序列
        period: 周期，默认10
    
    Returns:
        pd.Series: 成交量移动平均值
    """
    return volume.rolling(window=period).mean()

@validate_data
def price_change(data: pd.Series, period: int = 1) -> pd.Series:
    """价格变化率
    
    Args:
        data: 价格序列
        period: 周期，默认1
    
    Returns:
        pd.Series: 价格变化率
    """
    return data.pct_change(periods=period)

@validate_data
def momentum(data: pd.Series, period: int = 10) -> pd.Series:
    """动量指标
    
    Args:
        data: 价格序列
        period: 周期，默认10
    
    Returns:
        pd.Series: 动量值
    """
    return data - data.shift(period)

def calculate_all_indicators(df: pd.DataFrame, config: dict = None) -> pd.DataFrame:
    """计算所有技术指标
    
    Args:
        df: 包含OHLCV数据的DataFrame
        config: 指标参数配置
    
    Returns:
        pd.DataFrame: 包含所有指标的DataFrame
    """
    if df is None or df.empty:
        logger.warning("数据为空，无法计算指标")
        return df
    
    # 默认配置
    default_config = {
        'ma_short': 5,
        'ma_long': 20,
        'rsi_period': 14,
        'macd_fast': 12,
        'macd_slow': 26,
        'macd_signal': 9,
        'bb_period': 20,
        'bb_std': 2,
        'volume_ma_period': 10,
        'atr_period': 14
    }
    
    if config:
        default_config.update(config)
    
    result_df = df.copy()
    
    try:
        # 移动平均线
        result_df['ma_short'] = sma(df['close_price'], default_config['ma_short'])
        result_df['ma_long'] = sma(df['close_price'], default_config['ma_long'])
        
        # RSI
        result_df['rsi'] = rsi(df['close_price'], default_config['rsi_period'])
        
        # MACD
        macd_line, signal_line, histogram = macd(
            df['close_price'], 
            default_config['macd_fast'], 
            default_config['macd_slow'], 
            default_config['macd_signal']
        )
        result_df['macd'] = macd_line
        result_df['macd_signal'] = signal_line
        result_df['macd_histogram'] = histogram
        
        # 布林带
        bb_upper, bb_middle, bb_lower = bollinger_bands(
            df['close_price'], 
            default_config['bb_period'], 
            default_config['bb_std']
        )
        result_df['bb_upper'] = bb_upper
        result_df['bb_middle'] = bb_middle
        result_df['bb_lower'] = bb_lower
        
        # KD指标
        k_percent, d_percent = stochastic(df['high_price'], df['low_price'], df['close_price'])
        result_df['k_percent'] = k_percent
        result_df['d_percent'] = d_percent
        
        # Williams %R
        result_df['williams_r'] = williams_r(df['high_price'], df['low_price'], df['close_price'])
        
        # ATR
        result_df['atr'] = atr(df['high_price'], df['low_price'], df['close_price'], default_config['atr_period'])
        
        # 成交量指标
        result_df['volume_ma'] = volume_sma(df['volume'], default_config['volume_ma_period'])
        result_df['volume_ratio'] = df['volume'] / result_df['volume_ma']
        
        # 价格变化
        result_df['price_change'] = price_change(df['close_price'])
        result_df['price_change_pct'] = result_df['price_change'] / df['close_price'].shift(1) * 100
        
        # 动量指标
        result_df['momentum'] = momentum(df['close_price'])
        
        # 趋势判断
        result_df['trend'] = np.where(result_df['ma_short'] > result_df['ma_long'], 1, -1)
        
        # 超买超卖判断
        result_df['overbought'] = result_df['rsi'] > 70
        result_df['oversold'] = result_df['rsi'] < 30
        
        # 布林带位置
        result_df['bb_position'] = (df['close_price'] - bb_lower) / (bb_upper - bb_lower)
        
        logger.info(f"技术指标计算完成，数据量: {len(result_df)}")
        
    except Exception as e:
        logger.error(f"计算技术指标时出错: {e}")
    
    return result_df

def get_signal_strength(df: pd.DataFrame, index: int = -1) -> dict:
    """获取信号强度
    
    Args:
        df: 包含技术指标的DataFrame
        index: 数据索引，默认-1（最新数据）
    
    Returns:
        dict: 信号强度字典
    """
    if df is None or df.empty or abs(index) > len(df):
        return {}
    
    row = df.iloc[index]
    signals = {}
    
    try:
        # 趋势信号
        signals['trend'] = row.get('trend', 0)
        
        # RSI信号
        rsi_val = row.get('rsi', 50)
        if rsi_val > 70:
            signals['rsi_signal'] = -1  # 超买
        elif rsi_val < 30:
            signals['rsi_signal'] = 1   # 超卖
        else:
            signals['rsi_signal'] = 0   # 中性
        
        # MACD信号
        macd_val = row.get('macd', 0)
        macd_signal_val = row.get('macd_signal', 0)
        if macd_val > macd_signal_val:
            signals['macd_signal'] = 1  # 金叉
        else:
            signals['macd_signal'] = -1 # 死叉
        
        # 布林带信号
        bb_pos = row.get('bb_position', 0.5)
        if bb_pos > 0.8:
            signals['bb_signal'] = -1   # 接近上轨
        elif bb_pos < 0.2:
            signals['bb_signal'] = 1    # 接近下轨
        else:
            signals['bb_signal'] = 0    # 中性
        
        # 成交量信号
        vol_ratio = row.get('volume_ratio', 1)
        if vol_ratio > 1.5:
            signals['volume_signal'] = 1  # 放量
        elif vol_ratio < 0.5:
            signals['volume_signal'] = -1 # 缩量
        else:
            signals['volume_signal'] = 0  # 正常
        
        # 综合信号强度
        signal_sum = sum([v for v in signals.values() if isinstance(v, (int, float))])
        signals['total_strength'] = signal_sum / len([v for v in signals.values() if isinstance(v, (int, float))])
        
    except Exception as e:
        logger.error(f"计算信号强度时出错: {e}")
    
    return signals

# 函数式接口
def get_ma_signal(short_ma: float, long_ma: float) -> int:
    """获取均线信号"""
    if short_ma > long_ma:
        return 1  # 买入信号
    elif short_ma < long_ma:
        return -1 # 卖出信号
    else:
        return 0  # 中性

def get_rsi_signal(rsi_value: float, oversold: float = 30, overbought: float = 70) -> int:
    """获取RSI信号"""
    if rsi_value < oversold:
        return 1  # 超卖，买入信号
    elif rsi_value > overbought:
        return -1 # 超买，卖出信号
    else:
        return 0  # 中性

def get_macd_signal(macd: float, signal: float) -> int:
    """获取MACD信号"""
    if macd > signal:
        return 1  # 金叉，买入信号
    else:
        return -1 # 死叉，卖出信号