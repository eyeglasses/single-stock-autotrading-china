import requests
from bs4 import BeautifulSoup
import pymysql
import schedule
import time
from datetime import datetime
from loguru import logger

# 配置日志
logger.add("logs/etf_collector_{time}.log", rotation="1 day", level="INFO")

from config import DATABASE_CONFIG as DB_CONFIG

def get_etf_data_from_web(page=1):
    """从东方财富网获取ETF数据"""
    url = "https://datacenter.eastmoney.com/stock/fundselector/api/data/get?"
    params = {
        'type': 'RPTA_APP_FUNDSELECT',
        'sty': 'ETF_TYPE_CODE,SECUCODE,SECURITY_CODE,CHANGE_RATE_1W,CHANGE_RATE_1M,CHANGE_RATE_3M,YTD_CHANGE_RATE,DEC_TOTALSHARE,DEC_NAV,SECURITY_NAME_ABBR,DERIVE_INDEX_CODE,INDEX_CODE,INDEX_NAME,NEW_PRICE,CHANGE_RATE,CHANGE,VOLUME,DEAL_AMOUNT,PREMIUM_DISCOUNT_RATIO,QUANTITY_RELATIVE_RATIO,HIGH_PRICE,LOW_PRICE,STOCK_ID,PRE_CLOSE_PRICE',
        'extraCols': '',
        'source': 'FUND_SELECTOR',
        'client': 'APP',
        'sr': '-1,-1,1',
        'st': 'CHANGE_RATE,CHANGE,SECURITY_CODE',
        'filter': '(ETF_TYPE_CODE="ALL")',
        'p': page, # 页码
        'ps': 2000, # 每页数量，尽量大一些以减少请求次数
        'isIndexFilter': '1'
    }
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }
    try:
        response = requests.get(url, params=params, headers=headers, timeout=10)
        response.raise_for_status()  # 检查HTTP请求是否成功
        data_json = response.json()
        
        etf_list = []
        total_count = 0
        if data_json and 'result' in data_json:
            if 'data' in data_json['result']:
                for item in data_json['result']['data']:
                    etf_list.append({
                        'code': item.get('SECURITY_CODE'),
                        'name': item.get('SECURITY_NAME_ABBR'),
                        'market': 'SH' if item.get('SECURITY_CODE', '').startswith(('5', '6')) else 'SZ', # 简单判断市场
                        'price': item.get('NEW_PRICE'),
                        'change_percent': item.get('CHANGE_RATE'),
                        'volume': item.get('VOLUME'),
                        'amount': item.get('DEAL_AMOUNT')
                    })
            if 'pages' in data_json['result'] and 'total' in data_json['result']['pages']:
                total_count = data_json['result']['pages']['total']
        logger.info(f"成功从API获取第{page}页ETF数据，数量: {len(etf_list)}，总条数: {total_count}")
        return etf_list, total_count
    except requests.exceptions.RequestException as e:
        logger.error(f"请求API失败: {e}")
        return []
    except Exception as e:
        logger.error(f"解析API数据失败: {e}")
        return []

def save_etf_data_to_mysql(etf_data):
    """将ETF数据保存到MySQL数据库"""
    if not etf_data:
        logger.info("没有ETF数据可保存。")
        return

    conn = None
    try:
        conn = pymysql.connect(**DB_CONFIG)
        cursor = conn.cursor()
        
        # 创建表（如果不存在）
        create_table_sql = """
        CREATE TABLE IF NOT EXISTS etf_data (
            code VARCHAR(20) PRIMARY KEY,
            name VARCHAR(255),
            market VARCHAR(10),
            price DECIMAL(10, 4),
            change_percent DECIMAL(10, 4),
            volume BIGINT,
            amount DECIMAL(20, 4),
            update_time DATETIME
        );
        """
        cursor.execute(create_table_sql)
        conn.commit()
        logger.info("确保etf_data表存在。")

        # 插入或更新数据
        insert_sql = """
        INSERT INTO etf_data (code, name, market, price, change_percent, volume, amount, update_time)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        ON DUPLICATE KEY UPDATE
        name=VALUES(name), market=VALUES(market), price=VALUES(price), 
        change_percent=VALUES(change_percent), volume=VALUES(volume), amount=VALUES(amount), 
        update_time=VALUES(update_time);
        """
        
        for item in etf_data:
            try:
                cursor.execute(insert_sql, (
                    item.get('code'),
                    item.get('name'),
                    item.get('market'),
                    item.get('price'),
                    item.get('change_percent'),
                    item.get('volume'),
                    item.get('amount'),
                    datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                ))
            except Exception as e:
                logger.error(f"插入/更新数据失败: {item['code']} - {e}")
        
        conn.commit()
        logger.info(f"成功保存 {len(etf_data)} 条ETF数据到MySQL。")
    except pymysql.Error as e:
        logger.error(f"数据库操作失败: {e}")
        if conn:
            conn.rollback()
    finally:
        if conn:
            conn.close()

def job():
    """定时任务执行的函数"""
    logger.info(f"开始执行ETF数据抓取和存储任务，当前时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    all_etf_data = []
    # 东方财富网的ETF数据是分页的，需要模拟翻页
    # 第一次请求获取总数据量和第一页数据
    first_page_data, total_count = get_etf_data_from_web(page=1)
    if not first_page_data:
        logger.warning("未能获取第一页ETF数据，无法继续。")
        return
    all_etf_data.extend(first_page_data)

    # 计算总页数
    ps = 500 # 每页数量
    total_pages = (total_count + ps - 1) // ps
    logger.info(f"总ETF数据条数: {total_count}，总页数: {total_pages}")

    # 从第二页开始遍历所有页
    for page in range(2, total_pages + 1):
        page_data, _ = get_etf_data_from_web(page=page)
        if page_data:
            all_etf_data.extend(page_data)
        else:
            logger.warning(f"获取第{page}页数据失败，可能数据不完整。")
            break
    
    if all_etf_data:
        save_etf_data_to_mysql(all_etf_data)
    else:
        logger.warning("未能获取到任何ETF数据，跳过保存。")
    logger.info("ETF数据抓取和存储任务完成。")

if __name__ == '__main__':
    logger.info("ETF数据收集器启动。")
    # 每天下午15:30执行
    job() # 立即执行一次，用于测试
    schedule.every().day.at("15:30").do(job)

    while True:
        schedule.run_pending()
        time.sleep(1) # 每秒检查一次任务