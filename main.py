from polygon import RESTClient
import pandas as pd
from datetime import datetime, timedelta
import os
import time

# Polygon.io API configuration
# Get your free API key from: https://polygon.io/dashboard
# Free tier: 5 calls/minute, 2 years of historical data
API_KEY = 'UO6ppH2aLza24EdNFcXQEoP56gO6AGJM'  # Replace with your actual API key

# Initialize Polygon client
client = RESTClient(api_key=API_KEY)

# Define parameters
symbols = ['QQQ', 'TQQQ']  # QQQ and TQQQ ETFs

# Calculate date range for 60+ days
end_date = datetime.now().date()
start_date = end_date - timedelta(days=70)  # 70 days to ensure 60+ trading days

print(f"Downloading 60+ days of 1-minute data for {symbols}")
print(f"Date range: {start_date} to {end_date}")
print(f"Using Polygon.io API (Free tier: 5 calls/minute, 2 years historical data)")

# Create data directory if it doesn't exist
os.makedirs('data', exist_ok=True)

def download_polygon_data(symbol, start_date, end_date, max_retries=3):
    """
    Download 1-minute data from Polygon.io with retry logic
    """
    retry_count = 0
    while retry_count < max_retries:
        try:
            print(f"  Fetching data (attempt {retry_count + 1}/{max_retries})...")
            
            # Get aggregates (OHLCV) data
            # Polygon.io aggregates endpoint for minute bars
            aggs = client.get_aggs(
                ticker=symbol,
                multiplier=1,
                timespan="minute",
                from_=start_date,
                to=end_date,
                adjusted=True,
                sort="asc",
                limit=50000  # Max results per request
            )
            
            if aggs and len(aggs) > 0:
                # Convert to DataFrame
                data_list = []
                for agg in aggs:
                    data_list.append({
                        'Datetime': pd.to_datetime(agg.timestamp, unit='ms'),
                        'Open': agg.open,
                        'High': agg.high,
                        'Low': agg.low,
                        'Close': agg.close,
                        'Volume': agg.volume
                    })
                
                df = pd.DataFrame(data_list)
                df['Symbol'] = symbol
                
                # Reorder columns
                df = df[['Datetime', 'Symbol', 'Open', 'High', 'Low', 'Close', 'Volume']]
                
                print(f"    ✓ Successfully downloaded {len(df)} bars")
                return df
            else:
                print(f"    ✗ No data returned for {symbol}")
                return pd.DataFrame()
                
        except Exception as e:
            retry_count += 1
            error_msg = str(e)
            
            if "API key" in error_msg or "authentication" in error_msg.lower():
                print(f"    ✗ Authentication error: {error_msg}")
                print(f"    Please get a free API key from: https://polygon.io/dashboard")
                return pd.DataFrame()
            elif "rate limit" in error_msg.lower() or "429" in error_msg:
                print(f"    Rate limit hit, waiting 15 seconds before retry...")
                time.sleep(15)
            else:
                print(f"    Error (attempt {retry_count}): {error_msg}")
                if retry_count < max_retries:
                    print(f"    Retrying in 5 seconds...")
                    time.sleep(5)
    
    print(f"    ✗ Failed to download data after {max_retries} attempts")
    return pd.DataFrame()

# Download data for each symbol
for symbol_idx, symbol in enumerate(symbols):
    print(f"\nDownloading data for {symbol}...")
    
    try:
        # Download real data from Polygon.io
        data = download_polygon_data(symbol, start_date, end_date)
        
        if not data.empty:
            # Ensure datetime is properly formatted
            data['Datetime'] = pd.to_datetime(data['Datetime'])
            data = data.sort_values('Datetime').reset_index(drop=True)
            
            # Remove duplicates
            data = data.drop_duplicates(subset=['Datetime', 'Symbol']).reset_index(drop=True)
            
            # Filter to trading hours and recent dates
            # Keep data from last 60+ days
            cutoff_date = datetime.now() - timedelta(days=65)
            data = data[data['Datetime'] >= cutoff_date].reset_index(drop=True)
            
            if not data.empty:
                # Save to CSV
                filename = f'{symbol}_60day_1min_data.csv'
                data.to_csv(filename, index=False)
                
                print(f"✓ Downloaded {len(data)} bars for {symbol}")
                print(f"✓ Saved to {filename}")
                print(f"Data preview for {symbol}:")
                print(data.head())
                print(f"Data shape: {data.shape}")
                
                # Show data summary
                date_range = f"{data['Datetime'].min()} to {data['Datetime'].max()}"
                print(f"Date range in data: {date_range}")
                print(f"Total trading volume: {data['Volume'].sum():,.0f}")
                
                # Calculate actual days covered
                unique_dates = data['Datetime'].dt.date.nunique()
                total_days = (data['Datetime'].max() - data['Datetime'].min()).days
                print(f"Unique trading days covered: {unique_dates} (over {total_days} calendar days)")
            else:
                print(f"✗ No recent data available for {symbol} after filtering")
        else:
            print(f"✗ No data available for {symbol}")
            
    except Exception as e:
        print(f"✗ Error downloading data for {symbol}: {str(e)}")
    
    # Add delay between symbols to respect API rate limits (5 calls/minute)
    if symbol_idx < len(symbols) - 1:
        print(f"Waiting 15 seconds to respect rate limits (5 calls/minute)...")
        time.sleep(15)

print(f"\nDownload complete!")

# Show summary of downloaded files
print("\nSummary of downloaded files:")
for symbol in symbols:
    filename = f'{symbol}_60day_1min_data.csv'
    if os.path.exists(filename):
        df = pd.read_csv(filename)
        if not df.empty:
            df['Datetime'] = pd.to_datetime(df['Datetime'])
            unique_days = df['Datetime'].dt.date.nunique()
            total_days = (df['Datetime'].max() - df['Datetime'].min()).days
            date_range = f"{df['Datetime'].min().date()} to {df['Datetime'].max().date()}"
            print(f"  {filename}: {len(df)} rows, {unique_days} trading days over {total_days} calendar days ({date_range})")
        else:
            print(f"  {filename}: Empty file")
    else:
        print(f"  {filename}: File not found")

