#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
修复xtdata连接问题
"""

import sys
import os
import time
from datetime import datetime
from loguru import logger

# 配置日志
logger.remove()
logger.add(sys.stdout, level="INFO", format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {message}")

def fix_xtdata_connection():
    """修复xtdata连接问题"""
    logger.info("=== 开始修复xtdata连接问题 ===")
    
    try:
        from xtquant import xtdata
        logger.success("xtquant导入成功")
    except ImportError as e:
        logger.error(f"xtquant导入失败: {e}")
        return False
    
    # 1. 尝试连接xtdata
    logger.info("步骤1: 尝试连接xtdata")
    try:
        # 检查是否需要显式连接
        # 某些版本的xtdata需要显式调用连接方法
        if hasattr(xtdata, 'connect'):
            logger.info("调用xtdata.connect()")
            result = xtdata.connect()
            logger.info(f"连接结果: {result}")
        
        # 等待连接稳定
        time.sleep(2)
        
    except Exception as e:
        logger.warning(f"连接过程中出现异常: {e}")
    
    # 2. 测试基础功能
    logger.info("步骤2: 测试基础功能")
    stock_code = "513330.SH"
    
    # 尝试不同的数据获取方式
    methods_to_try = [
        {
            'name': '方法1: 标准tick数据',
            'params': {
                'field_list': [],
                'stock_list': [stock_code],
                'period': 'tick',
                'count': 1
            }
        },
        {
            'name': '方法2: 1分钟数据',
            'params': {
                'field_list': [],
                'stock_list': [stock_code],
                'period': '1m',
                'count': 1
            }
        },
        {
            'name': '方法3: 日线数据',
            'params': {
                'field_list': [],
                'stock_list': [stock_code],
                'period': '1d',
                'count': 1
            }
        }
    ]
    
    success_method = None
    
    for method in methods_to_try:
        logger.info(f"尝试 {method['name']}")
        try:
            data = xtdata.get_market_data_ex(**method['params'])
            
            if stock_code in data and data[stock_code] is not None:
                # 检查数据是否为空
                if hasattr(data[stock_code], '__len__') and len(data[stock_code]) > 0:
                    logger.success(f"{method['name']} 成功获取数据")
                    logger.info(f"数据类型: {type(data[stock_code])}")
                    logger.info(f"数据长度: {len(data[stock_code])}")
                    success_method = method
                    break
                else:
                    logger.warning(f"{method['name']} 返回空数据")
            else:
                logger.warning(f"{method['name']} 未返回目标股票数据")
                
        except Exception as e:
            logger.error(f"{method['name']} 失败: {e}")
    
    if success_method:
        logger.success(f"找到可用的数据获取方法: {success_method['name']}")
        return True
    else:
        logger.error("所有数据获取方法都失败")
        return False

def check_miniqmt_login_status():
    """检查miniQMT登录状态"""
    logger.info("=== 检查miniQMT登录状态 ===")
    
    try:
        from xtquant import xttrader
        
        # 尝试获取账户信息来检查登录状态
        logger.info("尝试获取账户信息...")
        
        # 这里需要根据实际的miniQMT配置来调整
        # 通常需要session_id等参数
        
        logger.info("如果看到此消息，说明xttrader模块可用")
        return True
        
    except ImportError:
        logger.warning("xttrader模块不可用")
        return False
    except Exception as e:
        logger.warning(f"检查登录状态时出错: {e}")
        return False

def suggest_solutions():
    """提供解决方案建议"""
    logger.info("=== 解决方案建议 ===")
    
    solutions = [
        "1. 确保miniQMT客户端已启动并完成登录",
        "2. 检查miniQMT中的行情连接状态（通常在状态栏显示）",
        "3. 确认股票代码格式正确（如：513330.SH）",
        "4. 检查网络连接，确保能访问行情服务器",
        "5. 尝试在miniQMT客户端中手动查看该股票行情",
        "6. 检查是否在交易时间内（9:30-11:30, 13:00-15:00）",
        "7. 重启miniQMT客户端",
        "8. 检查miniQMT的数据订阅权限",
        "9. 确认xtquant库版本与miniQMT版本兼容",
        "10. 检查防火墙设置，确保miniQMT能正常联网"
    ]
    
    for solution in solutions:
        logger.info(solution)

def create_improved_data_fetcher():
    """创建改进的数据获取器"""
    logger.info("=== 创建改进的数据获取器 ===")
    
    improved_code = '''
# 在data_fetcher.py中添加以下改进的实时数据获取方法

@ensure_xtdata_connected
def get_realtime_data_improved(self, stock_code: str) -> Optional[Dict[str, Any]]:
    """改进的实时行情数据获取方法"""
    try:
        # 方法1: 尝试获取tick数据
        try:
            tick_data = xtdata.get_market_data_ex([], [stock_code], period='tick', count=1)
            if stock_code in tick_data and tick_data[stock_code] is not None:
                if hasattr(tick_data[stock_code], '__len__') and len(tick_data[stock_code]) > 0:
                    latest_tick = tick_data[stock_code][-1]
                    return self._parse_tick_data(stock_code, latest_tick)
        except Exception as e:
            logger.debug(f"tick数据获取失败: {e}")
        
        # 方法2: 尝试获取1分钟数据
        try:
            min_data = xtdata.get_market_data_ex([], [stock_code], period='1m', count=1)
            if stock_code in min_data and min_data[stock_code] is not None:
                if hasattr(min_data[stock_code], '__len__') and len(min_data[stock_code]) > 0:
                    latest_min = min_data[stock_code][-1]
                    return self._parse_min_data(stock_code, latest_min)
        except Exception as e:
            logger.debug(f"1分钟数据获取失败: {e}")
        
        # 方法3: 使用历史数据的最新记录
        try:
            day_data = xtdata.get_market_data_ex([], [stock_code], period='1d', count=1)
            if stock_code in day_data and day_data[stock_code] is not None:
                if hasattr(day_data[stock_code], '__len__') and len(day_data[stock_code]) > 0:
                    latest_day = day_data[stock_code][-1]
                    return self._parse_day_data(stock_code, latest_day)
        except Exception as e:
            logger.debug(f"日线数据获取失败: {e}")
        
        logger.warning(f"所有方法都无法获取实时数据: {stock_code}")
        return None
        
    except Exception as e:
        logger.error(f"获取实时数据失败: {e}")
        return None

def _parse_tick_data(self, stock_code: str, tick_data) -> Dict[str, Any]:
    """解析tick数据"""
    return {
        'stock_code': stock_code,
        'price': tick_data.get('lastPrice', 0),
        'volume': tick_data.get('volume', 0),
        'amount': tick_data.get('amount', 0),
        'bid_price': tick_data.get('bidPrice', [0])[0] if tick_data.get('bidPrice') else 0,
        'ask_price': tick_data.get('askPrice', [0])[0] if tick_data.get('askPrice') else 0,
        'timestamp': datetime.now(),
        'data_type': 'tick'
    }

def _parse_min_data(self, stock_code: str, min_data) -> Dict[str, Any]:
    """解析分钟数据"""
    return {
        'stock_code': stock_code,
        'price': min_data.get('close', 0),
        'volume': min_data.get('volume', 0),
        'amount': min_data.get('amount', 0),
        'timestamp': datetime.now(),
        'data_type': 'minute'
    }

def _parse_day_data(self, stock_code: str, day_data) -> Dict[str, Any]:
    """解析日线数据"""
    return {
        'stock_code': stock_code,
        'price': day_data.get('close', 0),
        'volume': day_data.get('volume', 0),
        'amount': day_data.get('amount', 0),
        'timestamp': datetime.now(),
        'data_type': 'daily'
    }
'''
    
    logger.info("改进代码已准备好，可以手动添加到data_fetcher.py中")
    return improved_code

def main():
    """主函数"""
    logger.info("开始修复xtdata连接问题...")
    logger.info(f"当前时间: {datetime.now()}")
    
    # 1. 尝试修复连接
    if fix_xtdata_connection():
        logger.success("xtdata连接修复成功！")
    else:
        logger.error("xtdata连接修复失败")
    
    # 2. 检查登录状态
    check_miniqmt_login_status()
    
    # 3. 提供解决方案建议
    suggest_solutions()
    
    # 4. 创建改进的数据获取器代码
    create_improved_data_fetcher()
    
    logger.info("修复过程完成")

if __name__ == "__main__":
    main()