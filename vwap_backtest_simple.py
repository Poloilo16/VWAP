import pandas as pd
import numpy as np
from datetime import datetime, time
import warnings
warnings.filterwarnings('ignore')

class SimplifiedVWAPStrategy:
    def __init__(self, initial_capital=100000, commission_per_share=0.0005):
        self.initial_capital = initial_capital
        self.commission_per_share = commission_per_share
        self.trades = []
        
    def load_and_prepare_data(self, symbol):
        """Load data and prepare for backtesting"""
        filename = f'{symbol}_60day_1min_data.csv'
        print(f"Loading {filename}...")
        
        df = pd.read_csv(filename)
        df['Datetime'] = pd.to_datetime(df['Datetime'])
        
        # Filter for regular trading hours (9:30 AM - 4:00 PM ET)
        df['Time'] = df['Datetime'].dt.time
        market_open = time(9, 30)
        market_close = time(16, 0)
        df = df[(df['Time'] >= market_open) & (df['Time'] <= market_close)].copy()
        
        # Add date column
        df['Date'] = df['Datetime'].dt.date
        
        # Calculate typical price and price-volume for VWAP
        df['TypicalPrice'] = (df['High'] + df['Low'] + df['Close']) / 3
        df['PriceVolume'] = df['TypicalPrice'] * df['Volume']
        
        print(f"Loaded {len(df)} rows for {symbol}")
        print(f"Date range: {df['Date'].min()} to {df['Date'].max()}")
        print(f"Trading days: {df['Date'].nunique()}")
        
        return df.sort_values('Datetime').reset_index(drop=True)
    
    def calculate_intraday_vwap(self, daily_data):
        """Calculate VWAP for intraday data"""
        daily_data = daily_data.copy()
        daily_data['CumPriceVolume'] = daily_data['PriceVolume'].cumsum()
        daily_data['CumVolume'] = daily_data['Volume'].cumsum()
        daily_data['VWAP'] = daily_data['CumPriceVolume'] / daily_data['CumVolume']
        return daily_data
    
    def backtest_symbol(self, symbol):
        """Run backtest for a single symbol"""
        print(f"\n{'='*50}")
        print(f"BACKTESTING {symbol}")
        print(f"{'='*50}")
        
        # Load data
        df = self.load_and_prepare_data(symbol)
        
        current_capital = self.initial_capital
        symbol_trades = []
        
        # Process each trading day
        trading_days = sorted(df['Date'].unique())
        print(f"Processing {len(trading_days)} trading days...")
        
        for i, date in enumerate(trading_days):
            if i % 10 == 0:  # Progress indicator
                print(f"Processing day {i+1}/{len(trading_days)} ({date})")
            
            daily_data = df[df['Date'] == date].copy()
            if len(daily_data) < 2:
                continue
                
            # Calculate intraday VWAP
            daily_data = self.calculate_intraday_vwap(daily_data)
            
            # Find 9:31 AM entry signal
            entry_candidates = daily_data[daily_data['Time'] == time(9, 31)]
            if len(entry_candidates) == 0:
                continue
                
            entry_row = entry_candidates.iloc[0]
            entry_price = entry_row['Close']
            entry_vwap = entry_row['VWAP']
            
            # Determine signal
            if entry_price > entry_vwap:
                signal = 'long'
            elif entry_price < entry_vwap:
                signal = 'short'
            else:
                continue  # No signal
            
            # Calculate position size (100% of capital)
            shares = int(current_capital / entry_price)
            if shares <= 0:
                continue
                
            commission_entry = shares * self.commission_per_share
            
            # Look for exit signal
            subsequent_data = daily_data[daily_data['Datetime'] > entry_row['Datetime']]
            exit_price = None
            exit_time = None
            exit_reason = None
            
            for _, row in subsequent_data.iterrows():
                current_close = row['Close']
                current_vwap = row['VWAP']
                
                # Check stop loss
                if signal == 'long' and current_close < current_vwap:
                    exit_price = current_close
                    exit_time = row['Datetime']
                    exit_reason = 'Stop Loss (Close < VWAP)'
                    break
                elif signal == 'short' and current_close > current_vwap:
                    exit_price = current_close
                    exit_time = row['Datetime']
                    exit_reason = 'Stop Loss (Close > VWAP)'
                    break
            
            # If no stop loss, exit at market close
            if exit_price is None:
                last_row = daily_data.iloc[-1]
                exit_price = last_row['Close']
                exit_time = last_row['Datetime']
                exit_reason = 'Market Close'
            
            # Calculate P&L
            commission_exit = shares * self.commission_per_share
            total_commission = commission_entry + commission_exit
            
            if signal == 'long':
                gross_pnl = (exit_price - entry_price) * shares
            else:  # short
                gross_pnl = (entry_price - exit_price) * shares
            
            net_pnl = gross_pnl - total_commission
            current_capital += net_pnl
            
            # Record trade
            trade = {
                'symbol': symbol,
                'date': date,
                'signal': signal,
                'shares': shares,
                'entry_price': entry_price,
                'exit_price': exit_price,
                'entry_vwap': entry_vwap,
                'gross_pnl': gross_pnl,
                'commission': total_commission,
                'net_pnl': net_pnl,
                'exit_reason': exit_reason,
                'capital_after': current_capital
            }
            
            symbol_trades.append(trade)
            self.trades.append(trade)
        
        return {
            'symbol': symbol,
            'trades': symbol_trades,
            'final_capital': current_capital,
            'total_return': (current_capital - self.initial_capital) / self.initial_capital * 100
        }
    
    def calculate_metrics(self, symbol_trades):
        """Calculate basic performance metrics"""
        if not symbol_trades:
            return {}
        
        df_trades = pd.DataFrame(symbol_trades)
        total_trades = len(df_trades)
        winning_trades = len(df_trades[df_trades['net_pnl'] > 0])
        win_rate = winning_trades / total_trades * 100 if total_trades > 0 else 0
        
        total_pnl = df_trades['net_pnl'].sum()
        avg_trade = df_trades['net_pnl'].mean()
        max_winner = df_trades['net_pnl'].max()
        max_loser = df_trades['net_pnl'].min()
        
        return {
            'total_trades': total_trades,
            'win_rate': win_rate,
            'total_pnl': total_pnl,
            'avg_trade': avg_trade,
            'max_winner': max_winner,
            'max_loser': max_loser
        }
    
    def print_summary(self, results):
        """Print summary results"""
        symbol = results['symbol']
        trades = results['trades']
        metrics = self.calculate_metrics(trades)
        
        print(f"\n{symbol} RESULTS:")
        print(f"Initial Capital: ${self.initial_capital:,.2f}")
        print(f"Final Capital: ${results['final_capital']:,.2f}")
        print(f"Total Return: {results['total_return']:.2f}%")
        print(f"Total Trades: {metrics.get('total_trades', 0)}")
        print(f"Win Rate: {metrics.get('win_rate', 0):.1f}%")
        print(f"Average Trade: ${metrics.get('avg_trade', 0):.2f}")
        print(f"Best Trade: ${metrics.get('max_winner', 0):.2f}")
        print(f"Worst Trade: ${metrics.get('max_loser', 0):.2f}")
        
        # Show last few trades
        if trades:
            print(f"\nLast 5 trades:")
            for trade in trades[-5:]:
                print(f"  {trade['date']}: {trade['signal'].upper()} | "
                      f"${trade['entry_price']:.2f} -> ${trade['exit_price']:.2f} | "
                      f"P&L: ${trade['net_pnl']:.2f}")

def main():
    print("Simplified VWAP Strategy Backtest")
    print("=================================")
    
    strategy = SimplifiedVWAPStrategy(initial_capital=100000, commission_per_share=0.0005)
    
    # Backtest both symbols
    symbols = ['QQQ', 'TQQQ']
    all_results = {}
    
    for symbol in symbols:
        results = strategy.backtest_symbol(symbol)
        all_results[symbol] = results
        strategy.print_summary(results)
    
    # Combined summary
    print(f"\n{'='*60}")
    print("COMBINED STRATEGY SUMMARY")
    print(f"{'='*60}")
    
    total_trades = sum(len(results['trades']) for results in all_results.values())
    combined_return = 0
    
    for symbol, results in all_results.items():
        combined_return += results['total_return']
    
    print(f"Total Trades Across All Symbols: {total_trades}")
    print(f"Combined Return: {combined_return:.2f}%")
    
    # Export trades to CSV
    if strategy.trades:
        trades_df = pd.DataFrame(strategy.trades)
        trades_df.to_csv('vwap_strategy_trades.csv', index=False)
        print(f"\nTrade log exported to 'vwap_strategy_trades.csv'")
    
    print("\nBacktest complete!")

if __name__ == "__main__":
    main()