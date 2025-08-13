# -*- coding: utf-8 -*-
"""
数据库管理模块
提供数据存储、查询等功能
"""

import mysql.connector
from mysql.connector import Error
import pandas as pd
from typing import Optional, List, Dict, Any, Tuple
from datetime import datetime, date
from loguru import logger
from config import DATABASE_CONFIG

class DatabaseManager:
    """数据库管理器"""
    
    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or DATABASE_CONFIG
        self.connection = None
        self._init_database()
    
    def _init_database(self) -> None:
        """初始化数据库连接和表结构"""
        try:
            # 设置连接超时
            config_with_timeout = self.config.copy()
            config_with_timeout.update({
                'connection_timeout': 5,
                'autocommit': True
            })
            
            self.connection = mysql.connector.connect(**config_with_timeout)
            if self.connection.is_connected():
                logger.info("数据库连接成功")
                self._create_tables()
        except Error as e:
            logger.error(f"数据库连接失败: {e}")
            self.connection = None
            raise
        except Exception as e:
            logger.error(f"数据库初始化异常: {e}")
            self.connection = None
            raise
    
    def _create_tables(self) -> None:
        """创建必要的数据表"""
        cursor = self.connection.cursor()
        
        # 行情数据表
        market_data_sql = """
        CREATE TABLE IF NOT EXISTS market_data (
            id BIGINT AUTO_INCREMENT PRIMARY KEY,
            stock_code VARCHAR(20) NOT NULL,
            trade_date DATE NOT NULL,
            open_price DECIMAL(10,3),
            high_price DECIMAL(10,3),
            low_price DECIMAL(10,3),
            close_price DECIMAL(10,3),
            volume BIGINT,
            amount DECIMAL(20,2),
            pre_close DECIMAL(10,3),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE KEY uk_stock_date (stock_code, trade_date),
            INDEX idx_stock_code (stock_code),
            INDEX idx_trade_date (trade_date)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
        """
        
        # 交易记录表
        trade_records_sql = """
        CREATE TABLE IF NOT EXISTS trade_records (
            id BIGINT AUTO_INCREMENT PRIMARY KEY,
            order_id VARCHAR(50) NOT NULL,
            stock_code VARCHAR(20) NOT NULL,
            trade_type ENUM('buy', 'sell') NOT NULL,
            price DECIMAL(10,3) NOT NULL,
            volume INT NOT NULL,
            amount DECIMAL(20,2) NOT NULL,
            commission DECIMAL(10,2) DEFAULT 0,
            trade_time DATETIME NOT NULL,
            status ENUM('pending', 'filled', 'cancelled', 'failed') DEFAULT 'pending',
            strategy_name VARCHAR(100),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE KEY uk_order_id (order_id),
            INDEX idx_stock_code (stock_code),
            INDEX idx_trade_time (trade_time)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
        """
        
        # 持仓记录表
        positions_sql = """
        CREATE TABLE IF NOT EXISTS positions (
            id BIGINT AUTO_INCREMENT PRIMARY KEY,
            stock_code VARCHAR(20) NOT NULL,
            volume INT NOT NULL,
            avg_cost DECIMAL(10,3) NOT NULL,
            market_value DECIMAL(20,2),
            profit_loss DECIMAL(20,2),
            profit_ratio DECIMAL(8,4),
            last_price DECIMAL(10,3),
            update_time DATETIME NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE KEY uk_stock_code (stock_code),
            INDEX idx_update_time (update_time)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
        """
        
        # 策略信号表
        strategy_signals_sql = """
        CREATE TABLE IF NOT EXISTS strategy_signals (
            id BIGINT AUTO_INCREMENT PRIMARY KEY,
            stock_code VARCHAR(20) NOT NULL,
            signal_type ENUM('buy', 'sell', 'hold') NOT NULL,
            signal_strength DECIMAL(5,2),
            price DECIMAL(10,3),
            volume_suggest INT,
            strategy_name VARCHAR(100) NOT NULL,
            signal_time DATETIME NOT NULL,
            executed BOOLEAN DEFAULT FALSE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            INDEX idx_stock_code (stock_code),
            INDEX idx_signal_time (signal_time),
            INDEX idx_strategy (strategy_name)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
        """
        
        # 风险控制记录表
        risk_control_sql = """
        CREATE TABLE IF NOT EXISTS risk_control (
            id BIGINT AUTO_INCREMENT PRIMARY KEY,
            stock_code VARCHAR(20),
            risk_type VARCHAR(50) NOT NULL,
            risk_level VARCHAR(20),
            description VARCHAR(500),
            action_taken VARCHAR(200),
            details TEXT,
            trigger_price DECIMAL(10,3),
            trigger_time DATETIME NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            INDEX idx_stock_code (stock_code),
            INDEX idx_trigger_time (trigger_time),
            INDEX idx_risk_type (risk_type)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
        """
        
        tables = [
            market_data_sql,
            trade_records_sql,
            positions_sql,
            strategy_signals_sql,
            risk_control_sql
        ]
        
        for sql in tables:
            try:
                cursor.execute(sql)
                logger.info("数据表创建成功")
            except Error as e:
                logger.error(f"创建数据表失败: {e}")
        
        cursor.close()
        self.connection.commit()
    
    def insert_market_data(self, data: Dict[str, Any]) -> bool:
        """插入行情数据"""
        sql = """
        INSERT INTO market_data 
        (stock_code, trade_date, open_price, high_price, low_price, close_price, volume, amount, pre_close)
        VALUES (%(stock_code)s, %(trade_date)s, %(open_price)s, %(high_price)s, %(low_price)s, 
                %(close_price)s, %(volume)s, %(amount)s, %(pre_close)s)
        ON DUPLICATE KEY UPDATE
        open_price=VALUES(open_price), high_price=VALUES(high_price), low_price=VALUES(low_price),
        close_price=VALUES(close_price), volume=VALUES(volume), amount=VALUES(amount), pre_close=VALUES(pre_close)
        """
        return self._execute_sql(sql, data)
    
    def insert_trade_record(self, data: Dict[str, Any]) -> bool:
        """插入交易记录"""
        sql = """
        INSERT INTO trade_records 
        (order_id, stock_code, trade_type, price, volume, amount, commission, trade_time, status, strategy_name)
        VALUES (%(order_id)s, %(stock_code)s, %(trade_type)s, %(price)s, %(volume)s, 
                %(amount)s, %(commission)s, %(trade_time)s, %(status)s, %(strategy_name)s)
        ON DUPLICATE KEY UPDATE
        status=VALUES(status), commission=VALUES(commission)
        """
        return self._execute_sql(sql, data)
    
    def update_position(self, data: Dict[str, Any]) -> bool:
        """更新持仓记录"""
        sql = """
        INSERT INTO positions 
        (stock_code, volume, avg_cost, market_value, profit_loss, profit_ratio, last_price, update_time)
        VALUES (%(stock_code)s, %(volume)s, %(avg_cost)s, %(market_value)s, 
                %(profit_loss)s, %(profit_ratio)s, %(last_price)s, %(update_time)s)
        ON DUPLICATE KEY UPDATE
        volume=VALUES(volume), avg_cost=VALUES(avg_cost), market_value=VALUES(market_value),
        profit_loss=VALUES(profit_loss), profit_ratio=VALUES(profit_ratio), 
        last_price=VALUES(last_price), update_time=VALUES(update_time)
        """
        return self._execute_sql(sql, data)
    
    def insert_strategy_signal(self, data: Dict[str, Any]) -> bool:
        """插入策略信号"""
        sql = """
        INSERT INTO strategy_signals 
        (stock_code, signal_type, signal_strength, price, volume_suggest, strategy_name, signal_time)
        VALUES (%(stock_code)s, %(signal_type)s, %(signal_strength)s, %(price)s, 
                %(volume_suggest)s, %(strategy_name)s, %(signal_time)s)
        """
        return self._execute_sql(sql, data)
    
    def get_market_data(self, stock_code: str, start_date: date = None, end_date: date = None, limit: int = None) -> pd.DataFrame:
        """获取行情数据"""
        sql = "SELECT * FROM market_data WHERE stock_code = %s"
        params = [stock_code]
        
        if start_date:
            sql += " AND trade_date >= %s"
            params.append(start_date)
        
        if end_date:
            sql += " AND trade_date <= %s"
            params.append(end_date)
        
        sql += " ORDER BY trade_date DESC"
        
        if limit:
            sql += f" LIMIT {limit}"
        
        return self._query_to_dataframe(sql, params)
    
    def get_trade_records(self, stock_code: str = None, start_time: datetime = None, end_time: datetime = None) -> pd.DataFrame:
        """获取交易记录"""
        sql = "SELECT * FROM trade_records WHERE 1=1"
        params = []
        
        if stock_code:
            sql += " AND stock_code = %s"
            params.append(stock_code)
        
        if start_time:
            sql += " AND trade_time >= %s"
            params.append(start_time)
        
        if end_time:
            sql += " AND trade_time <= %s"
            params.append(end_time)
        
        sql += " ORDER BY trade_time DESC"
        
        return self._query_to_dataframe(sql, params)
    
    def get_current_position(self, stock_code: str) -> Optional[Dict[str, Any]]:
        """获取当前持仓"""
        sql = "SELECT * FROM positions WHERE stock_code = %s"
        result = self._query_one(sql, [stock_code])
        return result
    
    def get_strategy_signals(self, stock_code: str, executed: bool = False, limit: int = 10) -> pd.DataFrame:
        """获取策略信号"""
        sql = "SELECT * FROM strategy_signals WHERE stock_code = %s AND executed = %s ORDER BY signal_time DESC LIMIT %s"
        return self._query_to_dataframe(sql, [stock_code, executed, limit])
    
    def _execute_sql(self, sql: str, params: Dict[str, Any] = None) -> bool:
        """执行SQL语句"""
        try:
            cursor = self.connection.cursor()
            cursor.execute(sql, params)
            self.connection.commit()
            cursor.close()
            return True
        except Error as e:
            logger.error(f"SQL执行失败: {e}")
            self.connection.rollback()
            return False
    
    def _query_to_dataframe(self, sql: str, params: List = None) -> pd.DataFrame:
        """查询结果转换为DataFrame"""
        try:
            return pd.read_sql(sql, self.connection, params=params)
        except Error as e:
            logger.error(f"查询失败: {e}")
            return pd.DataFrame()
    
    def _query_one(self, sql: str, params: List = None) -> Optional[Dict[str, Any]]:
        """查询单条记录"""
        try:
            cursor = self.connection.cursor(dictionary=True)
            cursor.execute(sql, params)
            result = cursor.fetchone()
            cursor.close()
            return result
        except Error as e:
            logger.error(f"查询失败: {e}")
            return None
    
    def execute_query(self, sql: str, params: List = None) -> Optional[List[Dict[str, Any]]]:
        """执行查询语句"""
        try:
            cursor = self.connection.cursor(dictionary=True)
            cursor.execute(sql, params)
            result = cursor.fetchall()
            cursor.close()
            return result
        except Error as e:
            logger.error(f"查询失败: {e}")
            return None
    
    def test_connection(self) -> bool:
        """测试数据库连接"""
        try:
            if self.connection and self.connection.is_connected():
                # 执行一个简单的查询来测试连接
                cursor = self.connection.cursor()
                cursor.execute("SELECT 1")
                cursor.fetchone()
                cursor.close()
                return True
            else:
                return False
        except Error as e:
            logger.error(f"数据库连接测试失败: {e}")
            return False
    
    def init_tables(self) -> bool:
        """初始化数据表（公共方法）"""
        try:
            self._create_tables()
            return True
        except Exception as e:
            logger.error(f"初始化数据表失败: {e}")
            return False
    
    def get_trade_records_by_date(self, trade_date: date, stock_code: str = None) -> List[Dict[str, Any]]:
        """根据日期获取交易记录"""
        sql = "SELECT * FROM trade_records WHERE DATE(trade_time) = %s"
        params = [trade_date]
        
        if stock_code:
            sql += " AND stock_code = %s"
            params.append(stock_code)
        
        sql += " ORDER BY trade_time DESC"
        
        return self.execute_query(sql, params) or []
    
    def get_trade_records_by_period(self, start_date: date, end_date: date, stock_code: str = None) -> List[Dict[str, Any]]:
        """根据时间段获取交易记录"""
        sql = "SELECT * FROM trade_records WHERE DATE(trade_time) BETWEEN %s AND %s"
        params = [start_date, end_date]
        
        if stock_code:
            sql += " AND stock_code = %s"
            params.append(stock_code)
        
        sql += " ORDER BY trade_time DESC"
        
        return self.execute_query(sql, params) or []
    
    def insert_risk_control_log(self, data: Dict[str, Any]) -> bool:
        """插入风险控制记录"""
        sql = """
        INSERT INTO risk_control 
        (stock_code, risk_type, risk_level, description, action_taken, details, trigger_price, trigger_time)
        VALUES (%(stock_code)s, %(risk_type)s, %(risk_level)s, %(description)s, %(action_taken)s, %(details)s, %(trigger_price)s, %(trigger_time)s)
        """
        
        # 转换数据格式
        risk_data = {
            'stock_code': data.get('stock_code', ''),
            'risk_type': data.get('risk_type', 'unknown')[:50],  # 限制长度
            'risk_level': data.get('risk_level', 'low')[:20],
            'description': data.get('description', '')[:500],
            'action_taken': data.get('action', '')[:200],
            'details': data.get('details', '')[:1000],  # TEXT字段，但仍然限制长度
            'trigger_price': data.get('trigger_price'),
            'trigger_time': data.get('timestamp', datetime.now())
        }
        
        return self._execute_sql(sql, risk_data)
    
    def close(self) -> None:
        """关闭数据库连接"""
        if self.connection and self.connection.is_connected():
            self.connection.close()
            logger.info("数据库连接已关闭")

# 全局数据库实例（延迟初始化）
db_manager = None

def get_db_manager():
    """获取数据库管理器实例（延迟初始化）"""
    global db_manager
    if db_manager is None:
        try:
            db_manager = DatabaseManager()
        except Exception as e:
            logger.error(f"数据库初始化失败: {e}")
            # 返回一个模拟的数据库管理器，避免程序崩溃
            db_manager = MockDatabaseManager()
    return db_manager

class MockDatabaseManager:
    """模拟数据库管理器，用于数据库连接失败时的降级处理"""
    
    def insert_strategy_signal(self, data):
        logger.warning("数据库未连接，跳过信号保存")
        return False
    
    def insert_trade_record(self, data):
        logger.warning("数据库未连接，跳过交易记录保存")
        return False
    
    def update_position(self, data):
        logger.warning("数据库未连接，跳过持仓更新")
        return False
    
    def insert_risk_control_log(self, data):
        logger.warning("数据库未连接，跳过风险控制日志")
        return False
    
    def get_market_data(self, *args, **kwargs):
        logger.warning("数据库未连接，返回空数据")
        return pd.DataFrame()
    
    def get_trade_records(self, *args, **kwargs):
        logger.warning("数据库未连接，返回空数据")
        return pd.DataFrame()
    
    def get_current_position(self, *args, **kwargs):
        logger.warning("数据库未连接，返回空持仓")
        return None
    
    def get_strategy_signals(self, *args, **kwargs):
        logger.warning("数据库未连接，返回空信号")
        return pd.DataFrame()
    
    def test_connection(self):
        return False
    
    def close(self):
        pass

# 使用延迟初始化，不在模块级别直接初始化
# db_manager将通过get_db_manager()函数获取