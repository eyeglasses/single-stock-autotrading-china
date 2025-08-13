#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
详细调试xtdata数据获取问题
"""

import sys
import time
from datetime import datetime
from loguru import logger

# 配置日志
logger.remove()
logger.add(sys.stdout, level="DEBUG", format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {message}")

def debug_xtdata_raw_calls():
    """直接调试xtdata原始调用"""
    logger.info("=== 直接调试xtdata原始调用 ===")
    
    try:
        from xtquant import xtdata
        logger.success("xtquant导入成功")
    except ImportError as e:
        logger.error(f"xtquant导入失败: {e}")
        return False
    
    stock_code = "513330.SH"
    
    # 测试各种参数组合
    test_cases = [
        {
            'name': 'tick数据 - 空字段列表',
            'params': {
                'field_list': [],
                'stock_list': [stock_code],
                'period': 'tick',
                'count': 1
            }
        },
        {
            'name': 'tick数据 - 指定字段',
            'params': {
                'field_list': ['time', 'lastPrice', 'volume'],
                'stock_list': [stock_code],
                'period': 'tick',
                'count': 1
            }
        },
        {
            'name': '1分钟数据',
            'params': {
                'field_list': [],
                'stock_list': [stock_code],
                'period': '1m',
                'count': 1
            }
        },
        {
            'name': '5分钟数据',
            'params': {
                'field_list': [],
                'stock_list': [stock_code],
                'period': '5m',
                'count': 1
            }
        },
        {
            'name': '日线数据',
            'params': {
                'field_list': [],
                'stock_list': [stock_code],
                'period': '1d',
                'count': 1
            }
        },
        {
            'name': '日线数据 - 多条',
            'params': {
                'field_list': [],
                'stock_list': [stock_code],
                'period': '1d',
                'count': 5
            }
        }
    ]
    
    for test_case in test_cases:
        logger.info(f"\n--- 测试: {test_case['name']} ---")
        
        try:
            logger.debug(f"调用参数: {test_case['params']}")
            
            # 调用xtdata.get_market_data_ex
            result = xtdata.get_market_data_ex(**test_case['params'])
            
            logger.debug(f"返回结果类型: {type(result)}")
            logger.debug(f"返回结果: {result}")
            
            if isinstance(result, dict):
                logger.info(f"返回字典，键: {list(result.keys())}")
                
                if stock_code in result:
                    data = result[stock_code]
                    logger.info(f"股票数据类型: {type(data)}")
                    
                    if data is not None:
                        if hasattr(data, '__len__'):
                            logger.info(f"数据长度: {len(data)}")
                            
                            if len(data) > 0:
                                logger.success(f"✓ {test_case['name']} - 成功获取数据")
                                logger.info(f"第一条数据: {data[0] if hasattr(data, '__getitem__') else 'N/A'}")
                                if len(data) > 1:
                                    logger.info(f"最后一条数据: {data[-1]}")
                            else:
                                logger.warning(f"⚠ {test_case['name']} - 数据为空")
                        else:
                            logger.info(f"数据内容: {data}")
                            logger.success(f"✓ {test_case['name']} - 获取到数据")
                    else:
                        logger.warning(f"⚠ {test_case['name']} - 数据为None")
                else:
                    logger.warning(f"⚠ {test_case['name']} - 结果中没有目标股票")
            else:
                logger.warning(f"⚠ {test_case['name']} - 返回结果不是字典")
                
        except Exception as e:
            logger.error(f"✗ {test_case['name']} - 异常: {e}")
            logger.error(f"异常类型: {type(e).__name__}")
            import traceback
            logger.error(f"异常详情: {traceback.format_exc()}")
        
        time.sleep(0.5)  # 避免请求过于频繁
    
    return True

def test_different_stock_codes():
    """测试不同的股票代码格式"""
    logger.info("\n=== 测试不同的股票代码格式 ===")
    
    try:
        from xtquant import xtdata
    except ImportError:
        logger.error("xtquant不可用")
        return False
    
    # 测试不同的股票代码
    test_stocks = [
        "513330.SH",   # 原始目标
        "000001.SZ",   # 深圳股票
        "600000.SH",   # 上海股票
        "159919.SZ",   # ETF
        "513330",      # 不带后缀
        "SH513330",    # 前缀格式
    ]
    
    for stock_code in test_stocks:
        logger.info(f"\n--- 测试股票代码: {stock_code} ---")
        
        try:
            # 使用最简单的日线数据测试
            result = xtdata.get_market_data_ex(
                field_list=[],
                stock_list=[stock_code],
                period='1d',
                count=1
            )
            
            if isinstance(result, dict) and stock_code in result:
                data = result[stock_code]
                if data is not None and hasattr(data, '__len__') and len(data) > 0:
                    logger.success(f"✓ {stock_code} - 成功")
                else:
                    logger.warning(f"⚠ {stock_code} - 无数据")
            else:
                logger.warning(f"⚠ {stock_code} - 无结果")
                
        except Exception as e:
            logger.error(f"✗ {stock_code} - 错误: {e}")
    
    return True

def check_xtdata_connection_status():
    """检查xtdata连接状态"""
    logger.info("\n=== 检查xtdata连接状态 ===")
    
    try:
        from xtquant import xtdata
        
        # 检查xtdata的各种属性和方法
        logger.info(f"xtdata模块: {xtdata}")
        logger.info(f"xtdata属性: {dir(xtdata)}")
        
        # 检查是否有连接相关的方法
        connection_methods = ['connect', 'is_connected', 'get_connect_status']
        for method in connection_methods:
            if hasattr(xtdata, method):
                logger.info(f"发现方法: {method}")
                try:
                    result = getattr(xtdata, method)()
                    logger.info(f"{method}() 返回: {result}")
                except Exception as e:
                    logger.warning(f"{method}() 调用失败: {e}")
        
        # 尝试获取一些基础信息
        info_methods = ['get_stock_list_in_sector', 'get_trading_dates']
        for method in info_methods:
            if hasattr(xtdata, method):
                logger.info(f"尝试调用: {method}")
                try:
                    if method == 'get_trading_dates':
                        result = getattr(xtdata, method)('SSE', '20250801', '20250804')
                    else:
                        result = getattr(xtdata, method)()
                    logger.info(f"{method} 成功，结果类型: {type(result)}")
                except Exception as e:
                    logger.warning(f"{method} 失败: {e}")
        
        return True
        
    except Exception as e:
        logger.error(f"检查xtdata连接状态失败: {e}")
        return False

def main():
    """主函数"""
    logger.info("开始详细调试xtdata数据获取问题...")
    logger.info(f"当前时间: {datetime.now()}")
    
    # 1. 检查xtdata连接状态
    check_xtdata_connection_status()
    
    # 2. 测试不同股票代码
    test_different_stock_codes()
    
    # 3. 详细测试各种数据获取方法
    debug_xtdata_raw_calls()
    
    logger.info("\n=== 调试完成 ===")
    logger.info("请根据上述结果分析问题原因")

if __name__ == "__main__":
    main()