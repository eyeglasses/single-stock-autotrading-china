# MySQL股票价格数据查询指南

本指南介绍如何查看和查询MySQL数据库中存储的股票价格数据。

## 📊 数据库表结构

### 1. market_data 表（行情数据）
```sql
CREATE TABLE market_data (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    stock_code VARCHAR(20) NOT NULL,        -- 股票代码（如：000001.SZ）
    trade_date DATE NOT NULL,               -- 交易日期
    open_price DECIMAL(10,3),               -- 开盘价
    high_price DECIMAL(10,3),               -- 最高价
    low_price DECIMAL(10,3),                -- 最低价
    close_price DECIMAL(10,3),              -- 收盘价
    volume BIGINT,                          -- 成交量
    amount DECIMAL(20,2),                   -- 成交额
    pre_close DECIMAL(10,3),                -- 前收盘价
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uk_stock_date (stock_code, trade_date)
);
```

### 2. trade_records 表（交易记录）
```sql
CREATE TABLE trade_records (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    order_id VARCHAR(50) NOT NULL,
    stock_code VARCHAR(20) NOT NULL,
    trade_type ENUM('buy', 'sell') NOT NULL,
    price DECIMAL(10,3) NOT NULL,
    volume INT NOT NULL,
    amount DECIMAL(20,2) NOT NULL,
    commission DECIMAL(10,2) DEFAULT 0,
    trade_time DATETIME NOT NULL,
    status ENUM('pending', 'filled', 'cancelled', 'failed') DEFAULT 'pending'
);
```

## 🔍 常用SQL查询

### 1. 查看所有股票列表
```sql
SELECT DISTINCT stock_code 
FROM market_data 
ORDER BY stock_code;
```

### 2. 查看特定股票的最新价格
```sql
SELECT 
    stock_code,
    trade_date,
    open_price,
    high_price,
    low_price,
    close_price,
    volume
FROM market_data 
WHERE stock_code = '000001.SZ'
ORDER BY trade_date DESC 
LIMIT 10;
```

### 3. 查看所有股票的汇总信息
```sql
SELECT 
    stock_code,
    COUNT(*) as record_count,
    MIN(trade_date) as earliest_date,
    MAX(trade_date) as latest_date,
    AVG(close_price) as avg_price,
    MAX(close_price) as max_price,
    MIN(close_price) as min_price
FROM market_data 
GROUP BY stock_code 
ORDER BY latest_date DESC;
```

### 4. 查看最近N天的数据
```sql
SELECT *
FROM market_data 
WHERE trade_date >= DATE_SUB(CURDATE(), INTERVAL 30 DAY)
ORDER BY trade_date DESC, stock_code;
```

### 5. 按价格范围搜索股票
```sql
SELECT DISTINCT
    stock_code,
    trade_date,
    close_price,
    volume
FROM market_data 
WHERE close_price BETWEEN 10.0 AND 50.0
AND trade_date >= DATE_SUB(CURDATE(), INTERVAL 7 DAY)
ORDER BY trade_date DESC, close_price DESC;
```

### 6. 查看交易记录
```sql
SELECT 
    stock_code,
    trade_type,
    price,
    volume,
    amount,
    trade_time
FROM trade_records 
WHERE stock_code = '000001.SZ'
ORDER BY trade_time DESC
LIMIT 20;
```

## 🐍 Python代码查询

### 1. 使用数据库管理器查询
```python
from database import get_db_manager
from datetime import date, timedelta

# 获取数据库管理器
db_manager = get_db_manager()

# 查询特定股票的行情数据
stock_code = '000001.SZ'
end_date = date.today()
start_date = end_date - timedelta(days=30)

df = db_manager.get_market_data(
    stock_code=stock_code,
    start_date=start_date,
    end_date=end_date,
    limit=30
)

print(f"股票 {stock_code} 最近30天数据:")
print(df.head())
```

### 2. 直接执行SQL查询
```python
from database import get_db_manager

db_manager = get_db_manager()

# 执行自定义SQL查询
sql = """
SELECT 
    stock_code,
    COUNT(*) as record_count,
    MAX(trade_date) as latest_date,
    AVG(close_price) as avg_price
FROM market_data 
GROUP BY stock_code
"""

results = db_manager.execute_query(sql)
for row in results:
    print(f"股票: {row['stock_code']}, 记录数: {row['record_count']}, 最新日期: {row['latest_date']}, 平均价格: {row['avg_price']:.3f}")
```

### 3. 查询并导出数据
```python
import pandas as pd
from database import get_db_manager

db_manager = get_db_manager()

# 获取数据
df = db_manager.get_market_data('000001.SZ')

# 导出到CSV
df.to_csv('stock_data.csv', index=False, encoding='utf-8-sig')
print(f"已导出 {len(df)} 条记录到 stock_data.csv")
```

## 📈 数据分析示例

### 1. 价格趋势分析
```python
import matplotlib.pyplot as plt
from database import get_db_manager

db_manager = get_db_manager()
df = db_manager.get_market_data('000001.SZ', limit=100)

# 绘制价格趋势图
plt.figure(figsize=(12, 6))
plt.plot(df['trade_date'], df['close_price'], label='收盘价')
plt.plot(df['trade_date'], df['open_price'], label='开盘价', alpha=0.7)
plt.title('股票价格趋势')
plt.xlabel('日期')
plt.ylabel('价格')
plt.legend()
plt.xticks(rotation=45)
plt.tight_layout()
plt.show()
```

### 2. 成交量分析
```python
# 分析成交量与价格关系
df['price_change'] = df['close_price'].pct_change()
df['volume_ma'] = df['volume'].rolling(window=5).mean()

print("成交量与价格变化相关性:")
print(df[['price_change', 'volume']].corr())
```

## 🛠️ 实用工具函数

### 1. 快速查看股票信息
```python
def quick_stock_info(stock_code):
    """快速查看股票基本信息"""
    db_manager = get_db_manager()
    
    # 获取最新数据
    df = db_manager.get_market_data(stock_code, limit=1)
    if df.empty:
        print(f"未找到股票 {stock_code} 的数据")
        return
    
    latest = df.iloc[0]
    print(f"股票代码: {stock_code}")
    print(f"最新日期: {latest['trade_date']}")
    print(f"收盘价: {latest['close_price']:.3f}")
    print(f"成交量: {latest['volume']:,}")
    print(f"成交额: {latest['amount']:,.2f}")

# 使用示例
quick_stock_info('000001.SZ')
```

### 2. 批量查询多只股票
```python
def batch_stock_query(stock_codes, days=10):
    """批量查询多只股票数据"""
    db_manager = get_db_manager()
    results = {}
    
    for code in stock_codes:
        df = db_manager.get_market_data(code, limit=days)
        if not df.empty:
            results[code] = {
                'latest_price': df.iloc[0]['close_price'],
                'records': len(df),
                'avg_price': df['close_price'].mean()
            }
    
    return results

# 使用示例
stocks = ['000001.SZ', '000002.SZ', '513330.SH']
results = batch_stock_query(stocks)
for code, info in results.items():
    print(f"{code}: 最新价格 {info['latest_price']:.3f}, 平均价格 {info['avg_price']:.3f}")
```

## 🔧 故障排除

### 1. 数据库连接问题
```python
from database import get_db_manager

db_manager = get_db_manager()
if db_manager.test_connection():
    print("✅ 数据库连接正常")
else:
    print("❌ 数据库连接失败，请检查配置")
```

### 2. 检查数据完整性
```sql
-- 检查是否有重复数据
SELECT stock_code, trade_date, COUNT(*) as cnt
FROM market_data 
GROUP BY stock_code, trade_date 
HAVING cnt > 1;

-- 检查数据日期范围
SELECT 
    MIN(trade_date) as earliest,
    MAX(trade_date) as latest,
    COUNT(DISTINCT stock_code) as stock_count,
    COUNT(*) as total_records
FROM market_data;
```

## 📝 使用建议

1. **定期备份数据**: 重要的股票数据应该定期备份
2. **索引优化**: 确保在 `stock_code` 和 `trade_date` 上有适当的索引
3. **数据清理**: 定期检查和清理异常数据
4. **性能监控**: 对于大量数据查询，注意监控查询性能
5. **数据验证**: 在插入新数据时进行数据验证

## 🎯 快速开始

1. 运行 `view_stock_data.py` 脚本查看现有数据
2. 使用上述SQL查询语句直接在MySQL客户端中执行
3. 在Python代码中导入 `database` 模块进行编程查询
4. 根据需要修改查询条件和参数

---

💡 **提示**: 如果数据库中还没有股票数据，请先运行数据获取程序来下载和存储股票行情数据。