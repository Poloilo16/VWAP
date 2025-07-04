import yfinance as yf
import pandas as pd
from datetime import datetime, timedelta
import os

# Define parameters
symbols = ['QQQ', 'TQQQ']  # QQQ and TQQQ ETFs
# Note: yfinance 1-minute data is typically available for the last 7 days
start_date = datetime.now() - timedelta(days=7)  # 7 days ago
end_date = datetime.now()

print(f"Downloading 1-minute data for {symbols}")
print(f"Date range: {start_date.strftime('%Y-%m-%d %H:%M:%S')} to {end_date.strftime('%Y-%m-%d %H:%M:%S')}")

# Create data directory if it doesn't exist
os.makedirs('data', exist_ok=True)

# Download data for each symbol
for symbol in symbols:
    print(f"\nDownloading data for {symbol}...")
    
    try:
        # Create ticker object
        ticker = yf.Ticker(symbol)
        
        # Download 1-minute data
        data = ticker.history(
            start=start_date,
            end=end_date,
            interval='1m'
        )
        
        if not data.empty:
            # Reset index to make Datetime a column
            data = data.reset_index()
            
            # Add symbol column
            data['Symbol'] = symbol
            
            # Reorder columns for better readability
            columns_order = ['Datetime', 'Symbol', 'Open', 'High', 'Low', 'Close', 'Volume']
            data = data[columns_order]
            
            # Save to CSV
            filename = f'data/{symbol}_1min_data.csv'
            data.to_csv(filename, index=False)
            
            print(f"✓ Downloaded {len(data)} bars for {symbol}")
            print(f"✓ Saved to {filename}")
            print(f"Data preview for {symbol}:")
            print(data.head())
            print(f"Data shape: {data.shape}")
            
            # Show data summary
            print(f"Date range in data: {data['Datetime'].min()} to {data['Datetime'].max()}")
            print(f"Total trading volume: {data['Volume'].sum():,.0f}")
            
        else:
            print(f"✗ No data available for {symbol} in the specified date range")
            
    except Exception as e:
        print(f"✗ Error downloading data for {symbol}: {str(e)}")

print(f"\nDownload complete! Data saved in 'data/' directory.")

# Show summary of downloaded files
print("\nSummary of downloaded files:")
if os.path.exists('data'):
    for file in os.listdir('data'):
        if file.endswith('.csv'):
            filepath = os.path.join('data', file)
            df = pd.read_csv(filepath)
            print(f"  {file}: {len(df)} rows")
else:
    print("  No data directory found.")