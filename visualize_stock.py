import pandas as pd
import mplfinance as mpf
from data_fetcher import get_market_data
from indicators import sma, macd, bollinger_bands
from typing import Optional

def plot_stock_chart(stock_code: str, period: str = '1d', count: int = 100, save_path: Optional[str] = None):
    """
    绘制股票蜡烛图，包括MA5/20/60、MACD、Bollinger Bands和成交量。
    
    参数:
        stock_code: 股票代码
        period: 数据周期 (默认'1d')
        count: 数据点数量 (默认100)
        save_path: 如果提供，则保存图表到文件
    """
    # 获取市场数据
    df = get_market_data(stock_code, period, count)
    if df is None or df.empty:
        print(f"无法获取 {stock_code} 的数据")
        return
    
    df['Date'] = pd.to_datetime(df['trade_date'])
    df = df.set_index('Date')
    df = df.rename(columns={
        'open_price': 'Open',
        'high_price': 'High',
        'low_price': 'Low',
        'close_price': 'Close',
        'volume': 'Volume'
    })
    # 计算指标
    df['MA5'] = sma(df['Close'], 5)
    df['MA20'] = sma(df['Close'], 20)
    df['MA60'] = sma(df['Close'], 60)
    df_macd, df_signal, df_hist = macd(df['Close'])
    upper, middle, lower = bollinger_bands(df['Close'])
    df['Upper'] = upper
    df['Middle'] = middle
    df['Lower'] = lower
    
    # 准备附加图
    add_plots = [
        mpf.make_addplot(df['MA5'], color='orange', panel=0),
        mpf.make_addplot(df['MA20'], color='blue', panel=0),
        mpf.make_addplot(df['MA60'], color='purple', panel=0),
        mpf.make_addplot(df['Upper'], color='gray', panel=0),
        mpf.make_addplot(df['Middle'], color='black', panel=0),
        mpf.make_addplot(df['Lower'], color='gray', panel=0),
        mpf.make_addplot(df_hist, type='bar', panel=1, color='dimgray', ylabel='MACD'),
        mpf.make_addplot(df_macd, panel=1, color='fuchsia'),
        mpf.make_addplot(df_signal, panel=1, color='b')
    ]
    
    # 绘制图表
    style = mpf.make_mpf_style(base_mpf_style='yahoo', rc={'font.size': 8})
    fig, axes = mpf.plot(
        df, type='candle', volume=True, addplot=add_plots, style=style,
        title=f'{stock_code} Stock Chart', ylabel='Price', returnfig=True
    )
    
    # 添加 Bollinger Bands 数值标注
    ax = axes[0]  # 主图轴
    latest_date = df.index[-1]
    upper_val = df['Upper'].iloc[-1]
    middle_val = df['Middle'].iloc[-1]
    lower_val = df['Lower'].iloc[-1]
    
    ax.text(-0.15, 0.95, f'Upper: {upper_val:.2f}', transform=ax.transAxes, va='top')
    ax.text(-0.15, 0.90, f'Middle: {middle_val:.2f}', transform=ax.transAxes, va='top')
    ax.text(-0.15, 0.85, f'Lower: {lower_val:.2f}', transform=ax.transAxes, va='top')
    
    if save_path:
        fig.savefig(save_path)
    else:
        mpf.show()

if __name__ == '__main__':
    # 示例使用
    plot_stock_chart('600820.SH', count=240, save_path='stock_chart.png')