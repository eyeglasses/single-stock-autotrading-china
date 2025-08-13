import pymysql
from loguru import logger
from config import DATABASE_CONFIG as DB_CONFIG

logger.add("logs/check_etf_db_{time}.log", rotation="1 day", level="INFO")

def check_etf_data():
    conn = None
    try:
        conn = pymysql.connect(
            host=DB_CONFIG['host'],
            user=DB_CONFIG['user'],
            password=DB_CONFIG['password'],
            database=DB_CONFIG['database'],
            charset=DB_CONFIG['charset']
        )
        cursor = conn.cursor()

        # 查询总行数
        cursor.execute("SELECT COUNT(*) FROM etf_data")
        total_rows = cursor.fetchone()[0]
        logger.info(f"etf_data 表中共有 {total_rows} 条数据。")

        # 查询前5条数据
        cursor.execute("SELECT * FROM etf_data LIMIT 5")
        records = cursor.fetchall()
        if records:
            logger.info("etf_data 表中前5条数据：")
            for row in records:
                logger.info(row)
        else:
            logger.info("etf_data 表中没有数据。")

    except pymysql.Error as e:
        logger.error(f"数据库操作失败: {e}")
    finally:
        if conn:
            conn.close()

if __name__ == '__main__':
    check_etf_data()