# 单只股票自动交易系统

基于Python函数式编程的单只股票自动交易系统，使用miniQMT的XtQuant API进行A股交易。

## 功能特性

- **数据获取**: 使用XtData API获取实时和历史行情数据
- **技术分析**: 多种技术指标计算（MA、RSI、MACD、布林带等）
- **交易策略**: 技术分析策略和动量策略
- **风险控制**: 止损止盈、仓位管理、最大回撤控制
- **自动交易**: 基于信号的自动买卖执行
- **回测系统**: 历史数据回测验证策略效果
- **数据存储**: MySQL数据库存储交易记录和行情数据

## 系统架构

```
├── config.py          # 配置文件
├── database.py        # 数据库管理
├── data_fetcher.py    # 数据获取模块
├── indicators.py      # 技术指标计算
├── strategy.py        # 交易策略
├── risk_control.py    # 风险控制
├── trader.py          # 交易执行
├── backtest.py        # 回测引擎
├── main.py            # 主程序
└── requirements.txt   # 依赖包
```

## 安装配置

### 1. 环境要求

- Python 3.6-3.12
- MySQL 5.7+
- miniQMT客户端

### 2. 安装依赖

```bash
pip install -r requirements.txt
```

### 3. 配置miniQMT

1. 下载并安装miniQMT客户端
2. 从miniQMT安装目录复制`xtquant`文件夹到项目目录
3. 启动miniQMT客户端并登录

### 4. 数据库配置

1. 创建MySQL数据库：
```sql
CREATE DATABASE stock_trading CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
```

2. 修改`config.py`中的数据库连接信息：
```python
DATABASE_CONFIG = {
    'host': 'localhost',
    'port': 3306,
    'user': 'your_username',
    'password': 'your_password',
    'database': 'stock_trading'
}
```

### 5. 交易配置

修改`config.py`中的交易参数：

```python
# 交易配置
TRADING_CONFIG = {
    'target_stock': '000001.SZ',  # 目标股票代码
    'account_id': 'your_account_id',  # 交易账户ID
    'position_ratio': 0.8,  # 仓位比例
    # ... 其他配置
}
```

## 使用方法

### 1. 初始化数据库

```python
from database import DatabaseManager

db = DatabaseManager()
db.init_tables()
```

### 2. 数据获取

```python
from data_fetcher import update_stock_data

# 更新股票数据
update_stock_data('000001.SZ', '20240101', '20241231')
```

### 3. 策略回测

```python
from backtest import run_backtest, print_backtest_summary

# 运行回测
result = run_backtest(
    stock_code='000001.SZ',
    start_date='20240101',
    end_date='20241231',
    initial_capital=100000
)

# 打印结果
print_backtest_summary(result)
```

### 4. 启动自动交易

```python
from main import AutoTradingSystem

# 创建交易系统
system = AutoTradingSystem('000001.SZ')

# 启动系统
system.start()
```

## 策略说明

### 技术分析策略

- **移动平均线**: 短期MA上穿长期MA产生买入信号
- **RSI**: 超卖区域(RSI<30)买入，超买区域(RSI>70)卖出
- **MACD**: MACD线上穿信号线买入，下穿卖出
- **布林带**: 价格触及下轨买入，触及上轨卖出
- **成交量**: 放量突破确认信号

### 动量策略

- **价格动量**: 基于价格变化率的趋势跟踪
- **成交量动量**: 结合成交量变化的动量分析

### 风险控制

- **止损**: 固定比例止损和ATR动态止损
- **止盈**: 固定比例止盈和移动止盈
- **仓位管理**: 固定金额、固定比例、Kelly公式、ATR仓位
- **最大回撤**: 实时监控并控制最大回撤
- **交易频率**: 限制日内交易次数

## 配置参数

### 交易参数

```python
TRADING_CONFIG = {
    'target_stock': '000001.SZ',      # 目标股票
    'position_ratio': 0.8,            # 基础仓位比例
    'min_trade_amount': 5000,         # 最小交易金额
    'max_trade_amount': 50000,        # 最大交易金额
    'stop_loss_pct': 0.05,           # 止损比例
    'take_profit_pct': 0.10,         # 止盈比例
}
```

### 策略参数

```python
STRATEGY_CONFIG = {
    'ma_short_period': 5,             # 短期均线周期
    'ma_long_period': 20,             # 长期均线周期
    'rsi_period': 14,                 # RSI周期
    'rsi_oversold': 30,               # RSI超卖线
    'rsi_overbought': 70,             # RSI超买线
    'volume_ma_period': 20,           # 成交量均线周期
}
```

### 风险参数

```python
RISK_CONFIG = {
    'max_daily_loss': 0.02,           # 最大日亏损比例
    'max_drawdown': 0.10,             # 最大回撤比例
    'max_single_position': 0.95,      # 最大单只股票仓位
    'max_daily_trades': 5,            # 最大日交易次数
}
```

## 监控和日志

系统使用loguru进行日志记录，日志文件保存在`logs/`目录下：

- `trading_{date}.log`: 交易日志
- `error_{date}.log`: 错误日志
- `risk_{date}.log`: 风控日志

## 注意事项

1. **实盘交易风险**: 本系统仅供学习研究，实盘交易请谨慎使用
2. **数据准确性**: 确保miniQMT客户端正常运行并有稳定的数据连接
3. **网络连接**: 保持网络连接稳定，避免交易中断
4. **资金安全**: 设置合理的风控参数，控制交易风险
5. **法规遵守**: 遵守相关法律法规和交易所规则

## 常见问题

### Q: 无法连接到miniQMT
A: 检查miniQMT客户端是否正常启动，确认session_id配置正确

### Q: 数据库连接失败
A: 检查MySQL服务是否启动，确认数据库配置信息正确

### Q: 策略信号不准确
A: 调整策略参数，增加数据样本进行回测验证

### Q: 交易执行失败
A: 检查账户资金是否充足，确认股票代码格式正确

## 开发计划

- [ ] 支持多只股票组合交易
- [ ] 增加机器学习策略
- [ ] 实时风险监控界面
- [ ] 策略参数自动优化
- [ ] 支持期货和期权交易

## 许可证

MIT License

## 免责声明

本软件仅供学习和研究使用，不构成投资建议。使用本软件进行实盘交易的所有风险由用户自行承担。开发者不对因使用本软件而产生的任何损失承担责任。