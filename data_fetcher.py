# -*- coding: utf-8 -*-
"""
数据获取模块
使用miniQMT的xtdata API获取行情数据
"""

import pandas as pd
import numpy as np
from datetime import datetime, date, timedelta
from typing import Optional, List, Dict, Any, Callable
from loguru import logger
from functools import wraps

try:
    from xtquant import xtdata
except ImportError:
    logger.warning("xtquant未安装，请从QMT安装目录复制xtquant库")
    xtdata = None

from config import DATA_CONFIG

def ensure_xtdata_connected(func: Callable) -> Callable:
    """确保xtdata连接的装饰器"""
    @wraps(func)
    def wrapper(*args, **kwargs):
        if xtdata is None:
            logger.error("xtdata未可用")
            return None
        return func(*args, **kwargs)
    return wrapper

class DataFetcher:
    """数据获取器"""
    
    def __init__(self):
        self.config = DATA_CONFIG
        self.is_connected = False
        self._init_connection()
    
    def _init_connection(self) -> None:
        """初始化xtdata连接"""
        if xtdata is None:
            logger.error("xtdata不可用，无法初始化连接")
            return
        
        try:
            # 这里可以添加xtdata的连接初始化代码
            # 具体连接方式需要根据实际环境配置
            self.is_connected = True
            logger.info("xtdata连接初始化成功")
        except Exception as e:
            logger.error(f"xtdata连接初始化失败: {e}")
    
    @ensure_xtdata_connected
    def download_history_data(self, stock_code: str, period: str = '1d', start_date: str = None) -> bool:
        """下载历史数据
        
        Args:
            stock_code: 股票代码，如 '000001.SZ'
            period: 周期，如 '1d', '1m', '5m' 等
            start_date: 开始日期，格式 'YYYY-MM-DD'
        
        Returns:
            bool: 下载是否成功
        """
        try:
            # 下载历史数据
            xtdata.download_history_data(stock_code, period=period)
            logger.info(f"历史数据下载成功: {stock_code}, period: {period}")
            return True
        except Exception as e:
            logger.error(f"历史数据下载失败: {e}")
            return False
    
    @ensure_xtdata_connected
    def get_market_data(self, stock_code: str, period: str = '1d', count: int = -1) -> Optional[pd.DataFrame]:
        """获取行情数据
        
        Args:
            stock_code: 股票代码
            period: 周期
            count: 获取数量，-1表示全部
        
        Returns:
            pd.DataFrame: 行情数据
        """
        try:
            # 首先尝试更新历史数据
            self.download_history_data(stock_code, period=period)
            
            # 获取行情数据
            data = xtdata.get_market_data_ex([], [stock_code], period=period, count=count)
            
            if stock_code in data:
                df = pd.DataFrame(data[stock_code])
                if not df.empty:
                    # 调试：打印原始数据结构
                    logger.debug(f"原始数据列名: {df.columns.tolist()}")
                    logger.debug(f"原始数据索引: {df.index[:5].tolist()}")
                    
                    # 重命名列名以符合数据库字段
                    column_mapping = {
                        'open': 'open_price',
                        'high': 'high_price', 
                        'low': 'low_price',
                        'close': 'close_price',
                        'volume': 'volume',
                        'amount': 'amount'
                    }
                    
                    df = df.rename(columns=column_mapping)
                    
                    # 处理时间：从索引中获取时间信息
                    try:
                        # 将索引转换为日期
                        df['trade_date'] = pd.to_datetime(df.index, format='%Y%m%d').date
                        logger.debug(f"时间转换成功，前几个日期: {df['trade_date'].head().tolist()}")
                    except Exception as e:
                        logger.error(f"时间转换失败: {e}")
                        return None
                    
                    # 添加股票代码
                    df['stock_code'] = stock_code
                    
                    # 计算前收盘价
                    df['pre_close'] = df['close_price'].shift(1)
                    
                    logger.info(f"获取行情数据成功: {stock_code}, 数据量: {len(df)}")
                    return df
            
            logger.warning(f"未获取到行情数据: {stock_code}")
            return None
            
        except Exception as e:
            logger.error(f"获取行情数据失败: {e}")
            return None
    
    @ensure_xtdata_connected
    def get_realtime_data(self, stock_code: str) -> Optional[Dict[str, Any]]:
        """获取实时行情数据（带降级策略）
        
        Args:
            stock_code: 股票代码
        
        Returns:
            Dict: 实时行情数据
        """
        # 方法1: 尝试获取tick数据
        try:
            tick_data = xtdata.get_market_data_ex([], [stock_code], period='tick', count=1)
            
            if stock_code in tick_data and tick_data[stock_code] is not None:
                data = tick_data[stock_code]
                # 检查是否为DataFrame且不为空
                if hasattr(data, 'empty') and not data.empty:
                    # 获取最后一行数据
                    latest_tick = data.iloc[-1]
                    
                    realtime_data = {
                        'stock_code': stock_code,
                        'price': latest_tick.get('lastPrice', 0),
                        'volume': latest_tick.get('volume', 0),
                        'amount': latest_tick.get('amount', 0),
                        'bid_price': latest_tick.get('bidPrice1', 0) if 'bidPrice1' in latest_tick else 0,
                        'ask_price': latest_tick.get('askPrice1', 0) if 'askPrice1' in latest_tick else 0,
                        'bid_volume': latest_tick.get('bidVol1', 0) if 'bidVol1' in latest_tick else 0,
                        'ask_volume': latest_tick.get('askVol1', 0) if 'askVol1' in latest_tick else 0,
                        'timestamp': datetime.now(),
                        'data_type': 'tick'
                    }
                    
                    logger.debug(f"获取tick实时数据成功: {stock_code}")
                    return realtime_data
        except Exception as e:
            logger.debug(f"tick数据获取失败: {e}")
        
        # 方法2: 降级到1分钟数据
        try:
            min_data = xtdata.get_market_data_ex([], [stock_code], period='1m', count=1)
            
            if stock_code in min_data and min_data[stock_code] is not None:
                data = min_data[stock_code]
                # 检查是否为DataFrame且不为空
                if hasattr(data, 'empty') and not data.empty:
                    # 获取最后一行数据
                    latest_min = data.iloc[-1]
                    
                    realtime_data = {
                        'stock_code': stock_code,
                        'price': latest_min.get('close', 0),
                        'volume': latest_min.get('volume', 0),
                        'amount': latest_min.get('amount', 0),
                        'bid_price': 0,  # 分钟数据通常没有买卖盘信息
                        'ask_price': 0,
                        'bid_volume': 0,
                        'ask_volume': 0,
                        'timestamp': datetime.now(),
                        'data_type': 'minute'
                    }
                    
                    logger.debug(f"获取分钟实时数据成功: {stock_code}")
                    return realtime_data
        except Exception as e:
            logger.debug(f"分钟数据获取失败: {e}")
        
        # 方法3: 最后降级到日线数据
        try:
            day_data = xtdata.get_market_data_ex([], [stock_code], period='1d', count=1)
            
            if stock_code in day_data and day_data[stock_code] is not None:
                data = day_data[stock_code]
                # 检查是否为DataFrame且不为空
                if hasattr(data, 'empty') and not data.empty:
                    # 获取最后一行数据
                    latest_day = data.iloc[-1]
                    
                    realtime_data = {
                        'stock_code': stock_code,
                        'price': latest_day.get('close', 0),
                        'volume': latest_day.get('volume', 0),
                        'amount': latest_day.get('amount', 0),
                        'bid_price': 0,
                        'ask_price': 0,
                        'bid_volume': 0,
                        'ask_volume': 0,
                        'timestamp': datetime.now(),
                        'data_type': 'daily'
                    }
                    
                    logger.warning(f"使用日线数据作为实时数据: {stock_code}")
                    return realtime_data
        except Exception as e:
            logger.debug(f"日线数据获取失败: {e}")
        
        logger.error(f"所有方法都无法获取实时数据: {stock_code}")
        return None
    
    @ensure_xtdata_connected
    def subscribe_realtime_data(self, stock_code: str, callback: Callable) -> bool:
        """订阅实时数据
        
        Args:
            stock_code: 股票代码
            callback: 回调函数
        
        Returns:
            bool: 订阅是否成功
        """
        try:
            # 订阅实时行情
            xtdata.subscribe_quote(stock_code, period='tick', count=-1, callback=callback)
            logger.info(f"订阅实时数据成功: {stock_code}")
            return True
        except Exception as e:
            logger.error(f"订阅实时数据失败: {e}")
            return False
    
    def save_market_data_to_db(self, df: pd.DataFrame) -> bool:
        """保存行情数据到数据库
        
        Args:
            df: 行情数据DataFrame
        
        Returns:
            bool: 保存是否成功
        """
        if df is None or df.empty:
            return False
        
        # 处理NaN值
        df = df.fillna(0)
        
        success_count = 0
        for _, row in df.iterrows():
            data = {
                'stock_code': row.get('stock_code'),
                'trade_date': row.get('trade_date'),
                'open_price': float(row.get('open_price', 0)),
                'high_price': float(row.get('high_price', 0)),
                'low_price': float(row.get('low_price', 0)),
                'close_price': float(row.get('close_price', 0)),
                'volume': int(row.get('volume', 0)),
                'amount': float(row.get('amount', 0)),
                'pre_close': float(row.get('pre_close', 0)) if pd.notna(row.get('pre_close')) else None
            }
            
            # 延迟导入数据库管理器
            from database import db_manager
            if db_manager.insert_market_data(data):
                success_count += 1
        
        logger.info(f"保存行情数据到数据库: 成功 {success_count}/{len(df)} 条")
        return success_count > 0
    
    def update_stock_data(self, stock_code: str, days: int = None) -> bool:
        """更新股票数据
        
        Args:
            stock_code: 股票代码
            days: 更新天数，None表示使用配置的默认值
        
        Returns:
            bool: 更新是否成功
        """
        days = days or self.config['history_days']
        
        # 下载历史数据
        if not self.download_history_data(stock_code):
            return False
        
        # 获取行情数据
        df = self.get_market_data(stock_code, count=days)
        if df is None:
            return False
        
        # 保存到数据库
        return self.save_market_data_to_db(df)
    
    def get_stock_basic_info(self, stock_code: str) -> Optional[Dict[str, Any]]:
        """获取股票基本信息
        
        Args:
            stock_code: 股票代码
        
        Returns:
            Dict: 股票基本信息
        """
        try:
            if xtdata is None:
                return None
            
            # 获取合约基础信息
            info = xtdata.get_instrument_detail(stock_code)
            if info:
                return {
                    'stock_code': stock_code,
                    'stock_name': info.get('InstrumentName', ''),
                    'exchange': info.get('ExchangeID', ''),
                    'lot_size': info.get('VolumeMultiple', 100),
                    'price_tick': info.get('PriceTick', 0.01),
                    'list_date': info.get('OpenDate', ''),
                    'delist_date': info.get('ExpireDate', '')
                }
            
            return None
            
        except Exception as e:
            logger.error(f"获取股票基本信息失败: {e}")
            return None

# 创建全局数据获取器实例
data_fetcher = DataFetcher()

# 函数式接口
def get_market_data(stock_code: str, period: str = '1d', count: int = -1) -> Optional[pd.DataFrame]:
    """获取行情数据的函数式接口"""
    return data_fetcher.get_market_data(stock_code, period, count)

def get_realtime_data(stock_code: str) -> Optional[Dict[str, Any]]:
    """获取实时数据的函数式接口"""
    return data_fetcher.get_realtime_data(stock_code)

def update_stock_data(stock_code: str, days: int = None) -> bool:
    """更新股票数据的函数式接口"""
    return data_fetcher.update_stock_data(stock_code, days)

def subscribe_realtime_data(stock_code: str, callback: Callable) -> bool:
    """订阅实时数据的函数式接口"""
    return data_fetcher.subscribe_realtime_data(stock_code, callback)

def get_stock_info(stock_code: str) -> Optional[Dict[str, Any]]:
    """获取股票基本信息的函数式接口"""
    return data_fetcher.get_stock_basic_info(stock_code)