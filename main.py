from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.requests import StockBarsRequest
from alpaca.data.timeframe import TimeFrame
import pandas as pd
from datetime import datetime, timedelta

# 1. Your API credentials
API_KEY = 'CKAW4GB96I5VH0PCXVS5'
SECRET_KEY = 'P1cWSJqJGuXoyQyVzlbdsaFdxVRssIlIacHT13fI'

client = StockHistoricalDataClient(API_KEY, SECRET_KEY)

# 2. Define parameters
symbol = 'AAPL'
start_date = datetime.now() - timedelta(days=5)  # 5 days ago (max for 1Min data)
end_date = datetime.now()

# 3. Create request
request_params = StockBarsRequest(
    symbol_or_symbols=symbol,
    start=start_date,
    end=end_date,
    timeframe=TimeFrame.MINUTE
)

# 4. Fetch and display data
bars = client.get_stock_bars(request_params).df

# Optional: if multiple symbols, it's multi-indexed
if isinstance(bars.index, pd.MultiIndex):
    bars = bars.reset_index()

print(bars.head())