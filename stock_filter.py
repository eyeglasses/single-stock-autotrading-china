import pandas as pd
import numpy as np
from typing import List, Dict, Optional, Tuple
from datetime import datetime
import json
from flask import Flask, request, jsonify
import xtquant.xtdata as xtdata

class StockFilter:
    def __init__(self, data: pd.DataFrame = None):
        """
        初始化股票筛选器
        :param data: 可选，包含股票数据的DataFrame
        """
        self.data = data
        
    def load_from_xtdata(self, stock_types: List[str] = ['A股', '港股', 'ETF']) -> pd.DataFrame:
        """
        从xtdata加载股票数据
        :param stock_types: 股票类型列表
        :return: 包含股票数据的DataFrame
        """
        # 映射sector到stock_types (只包含xtdata支持的sector)
        sector_mapping = {
            '沪深A股': 'A股',
            '沪股通': 'A股'  # 沪股通也是A股的一部分
        }
        
        # 注意：xtdata当前不支持港股和ETF的sector查询
        # 如果需要港股和ETF数据，需要使用其他方法获取
        
        # 获取股票基本信息
        stock_info = []
        
        for sector, stock_type in sector_mapping.items():
            if stock_type not in stock_types:
                continue
                
            try:
                stocks = xtdata.get_stock_list_in_sector(sector)
                if not stocks:
                    print(f"获取{sector}股票列表为空")
                    continue
                    
                print(f"正在处理{sector}: {len(stocks)}只股票")
                
                # 限制处理数量以避免超时
                for i, stock_code in enumerate(stocks[:100]):  # 先处理前100只
                    try:
                        detail = xtdata.get_instrument_detail(stock_code)
                        if not detail:
                            continue
                            
                        # 获取价格和成交量数据
                        price_data = xtdata.get_market_data_ex(['close'], [stock_code], period='1d', count=1)
                        volume_data = xtdata.get_market_data_ex(['volume'], [stock_code], period='1d', count=1)
                        
                        if (price_data and stock_code in price_data and not price_data[stock_code].empty and
                            volume_data and stock_code in volume_data and not volume_data[stock_code].empty):
                            
                            price = price_data[stock_code]['close'].iloc[-1]
                            volume = volume_data[stock_code]['volume'].iloc[-1]
                            
                            stock_info.append({
                                'code': stock_code,
                                'name': detail.get('InstrumentName', ''),
                                'type': stock_type,
                                'price': float(price),
                                'volume': int(volume)
                            })
                            
                    except Exception as e:
                        # 跳过有问题的股票
                        continue
                        
            except Exception as e:
                print(f"获取{sector}股票列表失败: {e}")
        
        self.data = pd.DataFrame(stock_info)
        print(f"成功加载 {len(self.data)} 只股票数据")
        return self.data

    def calculate_ma(self, stock_code: str, days: int) -> Optional[float]:
        """
        计算指定股票的移动平均线(MA)
        :param stock_code: 股票代码
        :param days: MA天数
        :return: MA值或None
        """
        try:
            market_data = xtdata.get_market_data_ex(['close'], [stock_code], period='1d', count=days + 5)
            if not market_data or stock_code not in market_data:
                return None
            kline = market_data[stock_code]
            if kline.empty or len(kline) < days:
                return None
            return kline['close'].iloc[-days:].mean()
        except Exception as e:
            print(f"计算 {stock_code} MA-{days} 失败: {e}")
            return None

    def filter_by_ma(self, ma_days: int, condition: str, data: pd.DataFrame = None) -> pd.DataFrame:
        """
        根据移动平均线(MA)筛选股票
        :param ma_days: MA天数
        :param condition: 筛选条件 ('>=', '<=') - 比较当前价格与该股票的MA值
        :param data: 要筛选的数据，如果为None则使用self.data
        :return: 符合条件的股票DataFrame
        """
        source_data = data if data is not None else self.data
        if not source_data.empty:
            filtered_stocks = []
            for index, row in source_data.iterrows():
                stock_code = row['code']
                current_price = row['price']
                ma_value = self.calculate_ma(stock_code, ma_days)
                if ma_value is not None:
                    if condition == '>=' and current_price >= ma_value:
                        filtered_stocks.append(row)
                    elif condition == '<=' and current_price <= ma_value:
                        filtered_stocks.append(row)
            return pd.DataFrame(filtered_stocks)
        return pd.DataFrame()

    def calculate_macd(self, stock_code: str) -> Optional[pd.Series]:
        """
        计算指定股票的MACD指标 (DIF, DEA, MACD柱)
        :param stock_code: 股票代码
        :return: 包含MACD柱的Series或None
        """
        try:
            market_data = xtdata.get_market_data_ex(['close'], [stock_code], period='1d', count=100)
            if not market_data or stock_code not in market_data:
                return None
            kline = market_data[stock_code]
            if kline.empty or len(kline) < 34: # 至少需要34天数据 (26+9-1)
                return None
            
            close_prices = kline['close']
            
            ema_short = close_prices.ewm(span=12, adjust=False).mean()
            ema_long = close_prices.ewm(span=26, adjust=False).mean()
            
            dif = ema_short - ema_long
            dea = dif.ewm(span=9, adjust=False).mean()
            macd_hist = (dif - dea) * 2 # MACD柱
            
            return macd_hist
        except Exception as e:
            print(f"计算 {stock_code} MACD失败: {e}")
            return None

    def filter_by_macd(self, consecutive_days: int, direction: str, data: pd.DataFrame = None) -> pd.DataFrame:
        """
        根据MACD连续正/负天数筛选股票
        :param consecutive_days: 连续天数
        :param direction: 'positive' (正) 或 'negative' (负)
        :param data: 要筛选的数据，如果为None则使用self.data
        :return: 符合条件的股票DataFrame
        """
        source_data = data if data is not None else self.data
        if not source_data.empty:
            filtered_stocks = []
            for index, row in source_data.iterrows():
                stock_code = row['code']
                macd_hist = self.calculate_macd(stock_code)
                if macd_hist is not None and len(macd_hist) >= consecutive_days:
                    last_n_macd = macd_hist.iloc[-consecutive_days:]
                    if direction == 'positive' and all(last_n_macd > 0):
                        filtered_stocks.append(row)
                    elif direction == 'negative' and all(last_n_macd < 0):
                        filtered_stocks.append(row)
            return pd.DataFrame(filtered_stocks)
        return pd.DataFrame()

    def calculate_bollinger_bands(self, stock_code: str, window: int = 20, num_std_dev: int = 2) -> Optional[Tuple[float, float, float]]:
        """
        计算指定股票的布林带
        :param stock_code: 股票代码
        :param window: 窗口大小
        :param num_std_dev: 标准差倍数
        :return: (上轨, 中轨, 下轨) 或 None
        """
        try:
            market_data = xtdata.get_market_data_ex(['close'], [stock_code], period='1d', count=window + 5)
            if not market_data or stock_code not in market_data:
                return None
            kline = market_data[stock_code]
            if kline.empty or len(kline) < window:
                return None
            
            close_prices = kline['close']
            
            middle_band = close_prices.iloc[-window:].mean()
            std_dev = close_prices.iloc[-window:].std()
            
            upper_band = middle_band + (std_dev * num_std_dev)
            lower_band = middle_band - (std_dev * num_std_dev)
            
            return upper_band, middle_band, lower_band
        except Exception as e:
            print(f"计算 {stock_code} 布林带失败: {e}")
            return None

    def filter_by_bollinger(self, band: str, condition: str, window: int = 20, data: pd.DataFrame = None) -> pd.DataFrame:
        """
        根据布林带筛选股票
        :param band: 'upper' (上轨), 'middle' (中轨) 或 'lower' (下轨)
        :param condition: 筛选条件 ('>=', '<=')
        :param window: 布林带窗口大小
        :param data: 要筛选的数据，如果为None则使用self.data
        :return: 符合条件的股票DataFrame
        """
        source_data = data if data is not None else self.data
        if not source_data.empty:
            filtered_stocks = []
            for index, row in source_data.iterrows():
                stock_code = row['code']
                current_price = row['price']
                bollinger_bands = self.calculate_bollinger_bands(stock_code, window)
                
                if bollinger_bands:
                    upper_band, middle_band, lower_band = bollinger_bands
                    target_band_value = 0.0
                    if band == 'upper':
                        target_band_value = upper_band
                    elif band == 'middle':
                        target_band_value = middle_band
                    elif band == 'lower':
                        target_band_value = lower_band
                    
                    if condition == '>=' and current_price >= target_band_value:
                        filtered_stocks.append(row)
                    elif condition == '<=' and current_price <= target_band_value:
                        filtered_stocks.append(row)
            return pd.DataFrame(filtered_stocks)
        return pd.DataFrame()

    def combined_filter(self, ma_params: Optional[Dict] = None,
                        macd_params: Optional[Dict] = None,
                        bollinger_params: Optional[Dict] = None,
                        volume_params: Optional[Dict] = None) -> pd.DataFrame:
        """
        组合多种筛选条件
        :param ma_params: MA筛选参数，例如 {'ma_days': 20, 'condition': '>='} (比较股票价格与其自身MA值)
        :param macd_params: MACD筛选参数，例如 {'consecutive_days': 3, 'direction': 'positive'}
        :param bollinger_params: 布林带筛选参数，例如 {'band': 'upper', 'condition': '<=', 'window': 20} (比较股票价格与其布林带值)
        :param volume_params: 成交量筛选参数，例如 {'condition': '>=', 'value': 10000}
        :return: 符合所有条件的股票DataFrame
        """
        current_filtered_data = self.data.copy()

        if ma_params and ma_params.get('ma_days'):
            current_filtered_data = self.filter_by_ma(
                ma_days=ma_params['ma_days'],
                condition=ma_params['condition'],
                data=current_filtered_data
            )

        if macd_params and macd_params.get('consecutive_days'):
            current_filtered_data = self.filter_by_macd(
                consecutive_days=macd_params['consecutive_days'],
                direction=macd_params['direction'],
                data=current_filtered_data
            )

        if bollinger_params and bollinger_params.get('band'):
            current_filtered_data = self.filter_by_bollinger(
                band=bollinger_params['band'],
                condition=bollinger_params['condition'],
                window=bollinger_params.get('window', 20), # 默认窗口大小20
                data=current_filtered_data
            )
            
        if volume_params and volume_params.get('value') is not None:
            filtered_stocks = []
            for index, row in current_filtered_data.iterrows():
                current_volume = row['volume']
                if volume_params['condition'] == '>=' and current_volume >= volume_params['value']:
                    filtered_stocks.append(row)
                elif volume_params['condition'] == '<=' and current_volume <= volume_params['value']:
                    filtered_stocks.append(row)
            current_filtered_data = pd.DataFrame(filtered_stocks)

        return current_filtered_data


# Flask应用
app = Flask(__name__)

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
        if filters['stock_types']['a_share']:
            stock_types.append('A股')
        if filters['stock_types']['hk_stock']:
            stock_types.append('港股')
        if filters['stock_types']['etf']:
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

if __name__ == "__main__":
    app.run(debug=True)