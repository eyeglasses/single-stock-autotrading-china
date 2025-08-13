from flask import Flask, request, jsonify, render_template
import pandas as pd
from data_fetcher import get_market_data
from indicators import sma, macd, bollinger_bands
from visualize_stock import plot_stock_chart
import os
import base64
from datetime import datetime
from stock_filter import StockFilter

app = Flask(__name__)

@app.route('/stock_info', methods=['GET'])
def get_stock_info():
    stock_code = request.args.get('stock_code')
    if not stock_code:
        return jsonify({'error': 'Stock code is required'}), 400
    
    period = '1d'
    df_full = get_market_data(stock_code, period, 100)  # 获取数据用于计算指标和获取最新价
    if df_full is None or df_full.empty:
        return jsonify({'error': f'Unable to fetch data for {stock_code}'}), 404
    
    latest_data = df_full.iloc[-1]
    close = float(latest_data['close_price'])
    volume = int(latest_data['volume'])
    
    # 计算指标
    df_full['MA5'] = sma(df_full['close_price'], 5)
    df_full['MA20'] = sma(df_full['close_price'], 20)
    df_full['MA60'] = sma(df_full['close_price'], 60)
    macd_line, signal_line, hist = macd(df_full['close_price'])
    upper, middle, lower = bollinger_bands(df_full['close_price'])
    
    latest_ma5 = float(df_full['MA5'].iloc[-1])
    latest_ma20 = float(df_full['MA20'].iloc[-1])
    latest_ma60 = float(df_full['MA60'].iloc[-1])
    latest_macd = float(macd_line.iloc[-1])
    latest_boll_upper = float(upper.iloc[-1])
    latest_boll_middle = float(middle.iloc[-1])
    latest_boll_lower = float(lower.iloc[-1])
    
    # # 生成图表
    chart_path = f'{stock_code}_chart.png'
    plot_stock_chart(stock_code, period='1d', count=240, save_path=chart_path)
    chart_url = f'http://localhost:8000/{chart_path}'  # 假设有服务器提供文件
    
    # 生成图表并编码为base64
    chart_path = f'{stock_code}_chart.png'
    plot_stock_chart(stock_code, period='1d', count=240, save_path=chart_path)
    with open(chart_path, "rb") as image_file:
        encoded_string = base64.b64encode(image_file.read()).decode('utf-8')
    
    response = {
        'stock_code': stock_code,
        'latest_price': close,
        'volume': volume,
        'ma5': latest_ma5,
        'ma20': latest_ma20,
        'ma60': latest_ma60,
        'macd': latest_macd,
        'bollinger_upper': latest_boll_upper,
        'bollinger_middle': latest_boll_middle,
        'bollinger_lower': latest_boll_lower,
        'chart_url': chart_url
    }
    return jsonify(response)

@app.route('/stock_view', methods=['GET'])
def stock_view():
    stock_code = request.args.get('stock_code')
    if not stock_code:
        return 'Stock code is required', 400
    
    period = '1d'
    count = 1
    df = get_market_data(stock_code, period, count)
    if df is None or df.empty:
        return f'Unable to fetch data for {stock_code}', 404
    
    latest_data = df.iloc[-1]
    close = float(latest_data['close_price'])
    volume = int(latest_data['volume'])
    last_trade_date = latest_data['trade_date']  # 假设 trade_date 是字符串或可格式化
    
    df_full = get_market_data(stock_code, period, 100)
    df_full['MA5'] = sma(df_full['close_price'], 5)
    df_full['MA20'] = sma(df_full['close_price'], 20)
    df_full['MA60'] = sma(df_full['close_price'], 60)
    macd_line, signal_line, hist = macd(df_full['close_price'])
    upper, middle, lower = bollinger_bands(df_full['close_price'])
    
    latest_ma5 = float(df_full['MA5'].iloc[-1])
    latest_ma20 = float(df_full['MA20'].iloc[-1])
    latest_ma60 = float(df_full['MA60'].iloc[-1])
    latest_macd = float(macd_line.iloc[-1])
    latest_boll_upper = float(upper.iloc[-1])
    latest_boll_middle = float(middle.iloc[-1])
    latest_boll_lower = float(lower.iloc[-1])
    
    chart_path = f'{stock_code}_chart.png'
    plot_stock_chart(stock_code, period='1d', count=240, save_path=chart_path)
    
    with open(chart_path, 'rb') as img_file:
        chart_base64 = base64.b64encode(img_file.read()).decode('utf-8')
    
    current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    
    data = {
        'stock_code': stock_code,
        'latest_price': close,
        'volume': volume,
        'ma5': latest_ma5,
        'ma20': latest_ma20,
        'ma60': latest_ma60,
        'macd': latest_macd,
        'bollinger_upper': latest_boll_upper,
        'bollinger_middle': latest_boll_middle,
        'bollinger_lower': latest_boll_lower,
        'chart_base64': chart_base64,
        'last_trade_date': last_trade_date,
        'current_time': current_time
    }
    return render_template('index.html', data=data)

@app.route('/stock_filter.html', methods=['GET'])
def stock_filter():
    return render_template('stock_filter.html')

@app.route('/filter_stocks', methods=['POST'])
def filter_stocks():
    """
    处理前端筛选请求
    """
    try:
        filters = request.get_json()
        
        # 初始化筛选器
        filter = StockFilter()
        
        # 根据选择的股票类型加载数据
        stock_types = []
        
        # 支持两种格式：数组格式和对象格式
        if isinstance(filters['stock_types'], list):
            # 数组格式：["A股", "港股", "ETF"]
            stock_types = filters['stock_types']
        else:
            # 对象格式：{"a_share": true, "hk_stock": false, "etf": false}
            if filters['stock_types'].get('a_share'):
                stock_types.append('A股')
            if filters['stock_types'].get('hk_stock'):
                stock_types.append('港股')
            if filters['stock_types'].get('etf'):
                stock_types.append('ETF')
            
        filter.load_from_xtdata(stock_types)
        
        # 应用筛选条件
        result = filter.combined_filter(
            ma_params=filters.get('ma'),
            macd_params=filters.get('macd'),
            bollinger_params=filters.get('bollinger'),
            volume_params=filters.get('volume')
        )
        
        # 转换为前端需要的格式
        response_data = []
        for _, row in result.iterrows():
            response_data.append({
                'code': row['code'],
                'name': row['name'],
                'type': row['type'],
                'price': row['price'],
                'volume': row['volume']
            })
            
        return jsonify(response_data)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(port=5000, debug=True)