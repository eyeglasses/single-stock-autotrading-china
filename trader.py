# -*- coding: utf-8 -*-
"""
交易执行模块
使用miniQMT的xttrader API进行实际的买卖操作
"""

import time
from datetime import datetime
from typing import Optional, Dict, Any, List
from enum import Enum
from loguru import logger
from functools import wraps

try:
    from xtquant.xttrader import XtQuantTrader, XtQuantTraderCallback
    from xtquant.xttype import StockAccount
    from xtquant import xtconstant
except ImportError:
    logger.warning("xtquant未安装，请从QMT安装目录复制xtquant库")
    XtQuantTrader = None
    XtQuantTraderCallback = None
    StockAccount = None
    xtconstant = None

# from database import db_manager  # 延迟导入以避免卡住
from config import MINIQMT_CONFIG, TRADING_CONFIG

class OrderStatus(Enum):
    """订单状态枚举"""
    PENDING = "pending"
    FILLED = "filled"
    CANCELLED = "cancelled"
    FAILED = "failed"

class TradeType(Enum):
    """交易类型枚举"""
    BUY = "buy"
    SELL = "sell"

def ensure_trader_connected(func):
    """确保交易连接的装饰器"""
    @wraps(func)
    def wrapper(self, *args, **kwargs):
        if not self.is_connected:
            logger.warning("交易连接未建立，尝试重新连接...")
            if not self.reconnect():
                logger.error("交易连接重连失败")
                return None
        
        # 双重检查连接状态
        if not self.check_connection():
            logger.error("交易连接验证失败")
            return None
            
        return func(self, *args, **kwargs)
    return wrapper

class TradingCallback(XtQuantTraderCallback):
    """交易回调类"""
    
    def __init__(self, trader_instance):
        super().__init__()
        self.trader = trader_instance
    
    def on_disconnected(self):
        """连接断开回调"""
        logger.warning("交易连接断开")
        self.trader.is_connected = False
    
    def on_stock_order(self, order):
        """委托回报推送"""
        logger.info(f"委托回报: {order.stock_code}, 状态: {order.order_status}, 系统编号: {order.order_sysid}")
        
        # 更新订单状态到数据库
        order_data = {
            'order_id': order.order_id,
            'stock_code': order.stock_code,
            'trade_type': 'buy' if order.order_type == xtconstant.STOCK_BUY else 'sell',
            'price': order.price,
            'volume': order.order_volume,
            'amount': order.price * order.order_volume,
            'trade_time': datetime.now(),
            'status': self._convert_order_status(order.order_status),
            'strategy_name': 'single_stock_strategy'
        }
        
        from database import db_manager
        db_manager.insert_trade_record(order_data)
    
    def on_stock_trade(self, trade):
        """成交变动推送"""
        logger.info(f"成交回报: {trade.stock_code}, 成交量: {trade.traded_volume}, 成交价: {trade.traded_price}")
        
        # 更新成交记录
        trade_data = {
            'order_id': trade.order_id,
            'stock_code': trade.stock_code,
            'trade_type': 'buy' if trade.order_type == xtconstant.STOCK_BUY else 'sell',
            'price': trade.traded_price,
            'volume': trade.traded_volume,
            'amount': trade.traded_price * trade.traded_volume,
            'commission': getattr(trade, 'commission', 0),
            'trade_time': datetime.now(),
            'status': 'filled',
            'strategy_name': 'single_stock_strategy'
        }
        
        from database import db_manager
        db_manager.insert_trade_record(trade_data)
    
    def on_order_error(self, order_error):
        """委托失败推送"""
        logger.error(f"委托失败: {order_error.order_id}, 错误: {order_error.error_msg}")
    
    def on_cancel_error(self, cancel_error):
        """撤单失败推送"""
        logger.error(f"撤单失败: {cancel_error.order_id}, 错误: {cancel_error.error_msg}")
    
    def on_order_stock_async_response(self, response):
        """异步下单回报推送"""
        logger.info(f"异步下单回报: {response.order_id}, 结果: {response.order_result}")
    
    def _convert_order_status(self, status):
        """转换订单状态"""
        status_mapping = {
            xtconstant.ORDER_UNREPORTED: OrderStatus.PENDING.value,
            xtconstant.ORDER_WAIT_REPORTING: OrderStatus.PENDING.value,
            xtconstant.ORDER_REPORTED: OrderStatus.PENDING.value,
            xtconstant.ORDER_REPORTED_CANCEL: OrderStatus.CANCELLED.value,
            xtconstant.ORDER_PARTSUCC_CANCEL: OrderStatus.CANCELLED.value,
            xtconstant.ORDER_PART_CANCEL: OrderStatus.CANCELLED.value,
            xtconstant.ORDER_CANCELED: OrderStatus.CANCELLED.value,
            xtconstant.ORDER_PART_SUCC: OrderStatus.FILLED.value,
            xtconstant.ORDER_SUCCEEDED: OrderStatus.FILLED.value,
            xtconstant.ORDER_JUNK: OrderStatus.FAILED.value,
            xtconstant.ORDER_UNKNOWN: OrderStatus.FAILED.value
        }
        return status_mapping.get(status, OrderStatus.PENDING.value)

class StockTrader:
    """股票交易器"""
    
    def __init__(self):
        self.config = MINIQMT_CONFIG
        self.trading_config = TRADING_CONFIG
        self.xt_trader = None
        self.account = None
        self.is_connected = False
        self.callback = None
        self._init_trader()
    
    def _init_trader(self):
        """初始化交易器"""
        if XtQuantTrader is None:
            logger.error("xtquant不可用，无法初始化交易器")
            logger.error("请确保已安装miniQMT并正确配置xtquant库")
            return
        
        try:
            # 检查miniQMT路径
            import os
            if not os.path.exists(self.config['path']):
                logger.error(f"miniQMT路径不存在: {self.config['path']}")
                logger.error("请在config.py中配置正确的miniQMT安装路径")
                return
            
            logger.info(f"初始化交易器，路径: {self.config['path']}, 会话ID: {self.config['session_id']}")
            
            # 创建交易实例
            self.xt_trader = XtQuantTrader(self.config['path'], self.config['session_id'])
            
            # 创建回调实例
            self.callback = TradingCallback(self)
            self.xt_trader.register_callback(self.callback)
            
            # 启动交易
            start_result = self.xt_trader.start()
            logger.info(f"交易器启动结果: {start_result}")
            
            # 创建账户对象
            if self.config['account_id']:
                self.account = StockAccount(self.config['account_id'])
                logger.info(f"创建账户对象: {self.config['account_id']}")
                
                # 连接账户
                connect_result = self.xt_trader.connect()
                logger.info(f"连接结果: {connect_result}")
                
                if connect_result == 0:
                    self.is_connected = True
                    logger.info("交易连接建立成功")
                    
                    # 验证连接状态
                    try:
                        asset = self.xt_trader.query_stock_asset(self.account)
                        if asset:
                            logger.info(f"账户资产验证成功: 总资产={asset.total_asset}")
                        else:
                            logger.warning("无法获取账户资产，连接可能有问题")
                    except Exception as e:
                        logger.warning(f"验证账户连接时出错: {e}")
                        
                else:
                    logger.error(f"交易连接失败，错误码: {connect_result}")
                    logger.error("可能的原因：")
                    logger.error("1. miniQMT未启动")
                    logger.error("2. 账户ID配置错误")
                    logger.error("3. 网络连接问题")
                    logger.error("4. 账户权限问题")
            else:
                logger.warning("未配置账户ID，请在config.py中设置")
                
        except Exception as e:
            logger.error(f"初始化交易器失败: {e}")
            import traceback
            logger.error(f"详细错误信息: {traceback.format_exc()}")
    
    def check_connection(self) -> bool:
        """检查交易连接状态"""
        if not self.is_connected or not self.xt_trader or not self.account:
            return False
        
        try:
            # 尝试获取账户资产来验证连接
            asset = self.xt_trader.query_stock_asset(self.account)
            return asset is not None
        except Exception as e:
            logger.error(f"检查连接状态时出错: {e}")
            self.is_connected = False
            return False
    
    def reconnect(self) -> bool:
        """重新连接交易器"""
        logger.info("尝试重新连接交易器...")
        self.is_connected = False
        
        try:
            if self.xt_trader and self.account:
                connect_result = self.xt_trader.connect()
                if connect_result == 0:
                    self.is_connected = True
                    logger.info("重新连接成功")
                    return True
                else:
                    logger.error(f"重新连接失败，错误码: {connect_result}")
            else:
                logger.error("交易器或账户对象未初始化")
                self._init_trader()
                return self.is_connected
        except Exception as e:
            logger.error(f"重新连接时出错: {e}")
        
        return False
    
    @ensure_trader_connected
    def buy_stock(self, stock_code: str, price: float, volume: int, order_type: int = None) -> Optional[str]:
        """买入股票
        
        Args:
            stock_code: 股票代码
            price: 买入价格
            volume: 买入数量（股）
            order_type: 订单类型
        
        Returns:
            str: 订单ID，失败返回None
        """
        if not self.account:
            logger.error("账户未配置")
            return None
        
        # 默认使用限价单
        if order_type is None:
            order_type = xtconstant.STOCK_BUY
        
        try:
            # 检查资金是否充足
            asset = self.get_account_asset()
            if asset:
                required_amount = price * volume * 1.001  # 加上手续费余量
                if asset.get('cash', 0) < required_amount:
                    logger.warning(f"资金不足，需要: {required_amount}, 可用: {asset.get('cash', 0)}")
                    return None
            
            # 下单
            order_id = self.xt_trader.order_stock(self.account, stock_code, order_type, volume, price)
            
            if order_id > 0:
                logger.info(f"买入订单提交成功: {stock_code}, 价格: {price}, 数量: {volume}, 订单ID: {order_id}")
                
                # 记录到数据库
                order_data = {
                    'order_id': str(order_id),
                    'stock_code': stock_code,
                    'trade_type': TradeType.BUY.value,
                    'price': price,
                    'volume': volume,
                    'amount': price * volume,
                    'trade_time': datetime.now(),
                    'status': OrderStatus.PENDING.value,
                    'strategy_name': 'single_stock_strategy'
                }
                from database import db_manager
                db_manager.insert_trade_record(order_data)
                
                return str(order_id)
            else:
                logger.error(f"买入订单提交失败: {stock_code}, 错误码: {order_id}")
                return None
                
        except Exception as e:
            logger.error(f"买入股票时出错: {e}")
            return None
    
    @ensure_trader_connected
    def sell_stock(self, stock_code: str, price: float, volume: int, order_type: int = None) -> Optional[str]:
        """卖出股票
        
        Args:
            stock_code: 股票代码
            price: 卖出价格
            volume: 卖出数量（股）
            order_type: 订单类型
        
        Returns:
            str: 订单ID，失败返回None
        """
        if not self.account:
            logger.error("账户未配置")
            return None
        
        # 默认使用限价单
        if order_type is None:
            order_type = xtconstant.STOCK_SELL
        
        try:
            # 检查持仓是否充足
            position = self.get_position(stock_code)
            if position and position.get('volume', 0) < volume:
                logger.warning(f"持仓不足，需要: {volume}, 可用: {position.get('volume', 0)}")
                return None
            
            # 下单
            order_id = self.xt_trader.order_stock(self.account, stock_code, order_type, volume, price)
            
            if order_id > 0:
                logger.info(f"卖出订单提交成功: {stock_code}, 价格: {price}, 数量: {volume}, 订单ID: {order_id}")
                
                # 记录到数据库
                order_data = {
                    'order_id': str(order_id),
                    'stock_code': stock_code,
                    'trade_type': TradeType.SELL.value,
                    'price': price,
                    'volume': volume,
                    'amount': price * volume,
                    'trade_time': datetime.now(),
                    'status': OrderStatus.PENDING.value,
                    'strategy_name': 'single_stock_strategy'
                }
                from database import db_manager
                db_manager.insert_trade_record(order_data)
                
                return str(order_id)
            else:
                logger.error(f"卖出订单提交失败: {stock_code}, 错误码: {order_id}")
                return None
                
        except Exception as e:
            logger.error(f"卖出股票时出错: {e}")
            return None
    
    @ensure_trader_connected
    def cancel_order(self, order_id: str) -> bool:
        """撤销订单
        
        Args:
            order_id: 订单ID
        
        Returns:
            bool: 撤销是否成功
        """
        try:
            result = self.xt_trader.cancel_order_stock(self.account, int(order_id))
            if result == 0:
                logger.info(f"撤单成功: {order_id}")
                return True
            else:
                logger.error(f"撤单失败: {order_id}, 错误码: {result}")
                return False
        except Exception as e:
            logger.error(f"撤单时出错: {e}")
            return False
    
    @ensure_trader_connected
    def get_account_asset(self) -> Optional[Dict[str, Any]]:
        """获取账户资产
        
        Returns:
            Dict: 账户资产信息
        """
        try:
            asset = self.xt_trader.query_stock_asset(self.account)
            if asset:
                return {
                    'total_asset': asset.total_asset,
                    'cash': asset.cash,
                    'market_value': asset.market_value,
                    'frozen_cash': asset.frozen_cash,
                    'available_cash': asset.cash - asset.frozen_cash
                }
            return None
        except Exception as e:
            logger.error(f"获取账户资产时出错: {e}")
            return None
    
    @ensure_trader_connected
    def get_position(self, stock_code: str) -> Optional[Dict[str, Any]]:
        """获取持仓信息
        
        Args:
            stock_code: 股票代码
        
        Returns:
            Dict: 持仓信息
        """
        try:
            positions = self.xt_trader.query_stock_positions(self.account)
            if positions:
                for pos in positions:
                    if pos.stock_code == stock_code:
                        return {
                            'stock_code': pos.stock_code,
                            'volume': pos.volume,
                            'can_use_volume': pos.can_use_volume,
                            'avg_price': getattr(pos, 'avg_price', getattr(pos, 'open_price', 0)),
                            'market_value': pos.market_value,
                            'profit_loss': getattr(pos, 'profit_loss', 0),
                            'profit_ratio': getattr(pos, 'profit_ratio', 0)
                        }
            return None
        except Exception as e:
            logger.error(f"获取持仓信息时出错: {e}")
            return None
    
    @ensure_trader_connected
    def get_orders(self, stock_code: str = None) -> List[Dict[str, Any]]:
        """获取订单列表
        
        Args:
            stock_code: 股票代码，None表示获取所有订单
        
        Returns:
            List[Dict]: 订单列表
        """
        try:
            orders = self.xt_trader.query_stock_orders(self.account)
            result = []
            
            if orders:
                for order in orders:
                    if stock_code is None or order.stock_code == stock_code:
                        result.append({
                            'order_id': order.order_id,
                            'stock_code': order.stock_code,
                            'order_type': order.order_type,
                            'price': order.price,
                            'volume': order.order_volume,
                            'traded_volume': order.traded_volume,
                            'status': order.order_status,
                            'order_time': getattr(order, 'order_time', None)
                        })
            
            return result
        except Exception as e:
            logger.error(f"获取订单列表时出错: {e}")
            return []
    
    def stop(self):
        """停止交易器"""
        if self.xt_trader:
            try:
                self.xt_trader.stop()
                self.is_connected = False
                logger.info("交易器已停止")
            except Exception as e:
                logger.error(f"停止交易器时出错: {e}")

# 创建全局交易器实例
stock_trader = StockTrader()

# 函数式接口
def buy_stock(stock_code: str, price: float, volume: int) -> Optional[str]:
    """买入股票的函数式接口"""
    return stock_trader.buy_stock(stock_code, price, volume)

def sell_stock(stock_code: str, price: float, volume: int) -> Optional[str]:
    """卖出股票的函数式接口"""
    return stock_trader.sell_stock(stock_code, price, volume)

def get_account_asset() -> Optional[Dict[str, Any]]:
    """获取账户资产的函数式接口"""
    return stock_trader.get_account_asset()

def get_position(stock_code: str) -> Optional[Dict[str, Any]]:
    """获取持仓的函数式接口"""
    return stock_trader.get_position(stock_code)

def cancel_order(order_id: str) -> bool:
    """撤销订单的函数式接口"""
    return stock_trader.cancel_order(order_id)

def get_orders(stock_code: str = None) -> List[Dict[str, Any]]:
    """获取订单列表的函数式接口"""
    return stock_trader.get_orders(stock_code)

def check_trader_connection() -> bool:
    """检查交易连接状态的函数式接口"""
    return stock_trader.check_connection()

def reconnect_trader() -> bool:
    """重新连接交易器的函数式接口"""
    return stock_trader.reconnect()

def get_trader_status() -> Dict[str, Any]:
    """获取交易器状态的函数式接口"""
    return {
        'is_connected': stock_trader.is_connected,
        'has_trader': stock_trader.xt_trader is not None,
        'has_account': stock_trader.account is not None,
        'connection_verified': stock_trader.check_connection() if stock_trader.is_connected else False
    }