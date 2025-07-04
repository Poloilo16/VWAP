# Stock Data Downloader - QQQ & TQQQ 1-Minute Data

This project downloads 1-minute historical stock data for QQQ and TQQQ ETFs using Yahoo Finance.

## Features

- Downloads 1-minute intraday data for QQQ (Invesco QQQ Trust) and TQQQ (ProShares UltraPro QQQ)
- Uses Yahoo Finance API via `yfinance` library (no API credentials required)
- Saves data to CSV files for further analysis
- Includes data validation and error handling
- Provides data summaries and statistics

## Files

- `main.py` - Main script to download 1-minute data
- `requirements.txt` - Python dependencies
- `data/` - Directory containing downloaded CSV files
  - `QQQ_1min_data.csv` - QQQ 1-minute data
  - `TQQQ_1min_data.csv` - TQQQ 1-minute data

## Installation

1. Create a virtual environment:
```bash
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

## Usage

Run the script to download the latest 1-minute data:
```bash
python3 main.py
```

## Data Format

The CSV files contain the following columns:
- `Datetime` - Timestamp (with timezone)
- `Symbol` - Stock symbol (QQQ or TQQQ)
- `Open` - Opening price
- `High` - Highest price
- `Low` - Lowest price
- `Close` - Closing price
- `Volume` - Trading volume

## Notes

- Yahoo Finance typically provides 1-minute data for the last 7 days
- Data includes pre-market and after-hours trading sessions
- Times are in Eastern Time (ET) with timezone information
- The script handles market holidays and weekends automatically

## Data Summary

Recent download results:
- **QQQ**: 1,373 1-minute bars with total volume of 152.7M shares
- **TQQQ**: 1,373 1-minute bars with total volume of 214.2M shares
- **Date range**: June 30 - July 3, 2025 (market hours)

## Use Cases

This data can be used for:
- VWAP (Volume Weighted Average Price) calculations
- Intraday trading analysis
- High-frequency trading research
- Market microstructure studies
- Algorithmic trading strategy development