import pandas as pd
import numpy as np
from datetime import datetime, time
import warnings
warnings.filterwarnings('ignore')

class EnhancedVWAPStrategy:
    def __init__(self, initial_capital=100000, commission_per_share=0.0005):
        """
        Enhanced VWAP Strategy with improved stop losses and filters
        
        Key Improvements:
        1. Trend filter using 20-period moving average
        2. VWAP buffer to reduce whipsaws (0.1% buffer)
        3. Confirmation candles before entry
        4. Trailing stop loss mechanism
        5. Time-based stops (maximum hold time)
        6. Volume filter for entry
        7. Volatility-based position sizing
        """
        self.initial_capital = initial_capital
        self.commission_per_share = commission_per_share
        self.trades = []
        
        # Enhanced strategy parameters
        self.vwap_buffer = 0.001  # 0.1% buffer around VWAP
        self.confirmation_candles = 2  # Wait for 2 candles confirmation
        self.max_hold_minutes = 120  # Maximum 2 hours hold time
        self.trend_ma_period = 20  # 20-minute moving average for trend
        self.volume_threshold = 1.2  # Volume must be 20% above average
        self.trailing_stop_pct = 0.005  # 0.5% trailing stop
        self.max_daily_trades = 3  # Maximum 3 trades per day
        
    def load_and_prepare_data(self, symbol):
        """Load data and add enhanced indicators"""
        filename = f'{symbol}_60day_1min_data.csv'
        print(f"Loading {filename}...")
        
        df = pd.read_csv(filename)
        df['Datetime'] = pd.to_datetime(df['Datetime'])
        
        # Filter for regular trading hours (9:30 AM - 4:00 PM ET)
        df['Time'] = df['Datetime'].dt.time
        start_time = time(9, 30)
        end_time = time(16, 0)
        df = df[(df['Time'] >= start_time) & (df['Time'] <= end_time)].copy()
        
        print(f"Data after filtering: {len(df)} rows")
        return df
    
    def calculate_enhanced_indicators(self, df):
        """Calculate VWAP and additional indicators for enhanced strategy"""
        df = df.copy()
        df['Date'] = df['Datetime'].dt.date
        
        # Calculate VWAP by day
        df['Typical_Price'] = (df['High'] + df['Low'] + df['Close']) / 3
        df['Volume_Price'] = df['Typical_Price'] * df['Volume']
        
        # Calculate VWAP, trend MA, and volume indicators by day
        daily_calculations = []
        
        for date in df['Date'].unique():
            day_data = df[df['Date'] == date].copy()
            
            # VWAP calculation
            day_data['Cumulative_Volume'] = day_data['Volume'].cumsum()
            day_data['Cumulative_Volume_Price'] = day_data['Volume_Price'].cumsum()
            day_data['VWAP'] = day_data['Cumulative_Volume_Price'] / day_data['Cumulative_Volume']
            
            # Trend filter: 20-period moving average
            day_data['Trend_MA'] = day_data['Close'].rolling(window=self.trend_ma_period, min_periods=1).mean()
            
            # Volume filter: rolling average volume
            day_data['Avg_Volume'] = day_data['Volume'].rolling(window=20, min_periods=1).mean()
            day_data['Volume_Ratio'] = day_data['Volume'] / day_data['Avg_Volume']
            
            # Volatility measure (for position sizing)
            day_data['Returns'] = day_data['Close'].pct_change()
            day_data['Volatility'] = day_data['Returns'].rolling(window=20, min_periods=1).std()
            
            daily_calculations.append(day_data)
        
        df_enhanced = pd.concat(daily_calculations, ignore_index=True)
        return df_enhanced
    
    def check_entry_conditions(self, df, current_idx, direction):
        """Enhanced entry conditions with multiple filters"""
        current_row = df.iloc[current_idx]
        current_time = current_row['Datetime'].time()
        
        # Only check for entries after 9:31 AM (need at least 2 minutes of data)
        if current_time < time(9, 32):
            return False
        
        # Get previous candles for confirmation
        if current_idx < self.confirmation_candles:
            return False
        
        prev_candles = df.iloc[current_idx-self.confirmation_candles:current_idx]
        current_candle = current_row
        
        # Basic VWAP condition with buffer
        vwap = current_candle['VWAP']
        close_price = current_candle['Close']
        
        # Trend filter: only trade in direction of trend
        trend_ma = current_candle['Trend_MA']
        is_uptrend = close_price > trend_ma
        
        # Volume filter: require above-average volume
        volume_ok = current_candle['Volume_Ratio'] >= self.volume_threshold
        
        # VWAP buffer to reduce whipsaws
        if direction == 'long':
            vwap_condition = close_price > vwap * (1 + self.vwap_buffer)
            trend_condition = is_uptrend
            # Confirmation: previous candles should also support the direction
            confirmation = all(candle['Close'] > candle['VWAP'] for _, candle in prev_candles.iterrows())
        else:  # short
            vwap_condition = close_price < vwap * (1 - self.vwap_buffer)
            trend_condition = not is_uptrend
            confirmation = all(candle['Close'] < candle['VWAP'] for _, candle in prev_candles.iterrows())
        
        return vwap_condition and trend_condition and volume_ok and confirmation
    
    def calculate_position_size(self, current_price, volatility, capital):
        """Calculate position size based on volatility"""
        # Base position size on inverse volatility
        # Higher volatility = smaller position size
        base_size = capital / current_price
        
        # Adjust for volatility (cap between 50% and 100% of available capital)
        volatility_adj = max(0.5, min(1.0, 1.0 - (volatility * 100)))
        adjusted_size = int(base_size * volatility_adj)
        
        return max(1, adjusted_size)  # At least 1 share
    
    def check_exit_conditions(self, df, entry_idx, current_idx, direction, entry_price, highest_price, lowest_price):
        """Enhanced exit conditions with multiple stop types"""
        current_row = df.iloc[current_idx]
        current_price = current_row['Close']
        current_vwap = current_row['VWAP']
        
        # Time-based exit: maximum hold time
        time_diff = (current_row['Datetime'] - df.iloc[entry_idx]['Datetime']).total_seconds() / 60
        if time_diff >= self.max_hold_minutes:
            return True, "Time Stop"
        
        # Market close exit
        if current_row['Datetime'].time() >= time(15, 59):
            return True, "Market Close"
        
        # Enhanced VWAP stop with buffer (less sensitive)
        if direction == 'long':
            # Trailing stop
            trailing_stop_price = highest_price * (1 - self.trailing_stop_pct)
            if current_price <= trailing_stop_price:
                return True, "Trailing Stop"
            
            # VWAP stop with buffer
            if current_price < current_vwap * (1 - self.vwap_buffer):
                return True, "VWAP Stop"
            
        else:  # short
            # Trailing stop
            trailing_stop_price = lowest_price * (1 + self.trailing_stop_pct)
            if current_price >= trailing_stop_price:
                return True, "Trailing Stop"
            
            # VWAP stop with buffer  
            if current_price > current_vwap * (1 + self.vwap_buffer):
                return True, "VWAP Stop"
        
        return False, ""
    
    def backtest(self, symbol):
        """Run enhanced backtest with improved logic"""
        df = self.load_and_prepare_data(symbol)
        df = self.calculate_enhanced_indicators(df)
        
        capital = self.initial_capital
        position = None
        daily_trades = {}  # Track trades per day
        
        print(f"\n=== Enhanced VWAP Strategy Backtest for {symbol} ===")
        print(f"Initial Capital: ${capital:,.2f}")
        print(f"Strategy improvements:")
        print(f"  - VWAP buffer: {self.vwap_buffer*100:.1f}%")
        print(f"  - Confirmation candles: {self.confirmation_candles}")
        print(f"  - Trailing stop: {self.trailing_stop_pct*100:.1f}%")
        print(f"  - Max hold time: {self.max_hold_minutes} minutes")
        print(f"  - Trend filter: {self.trend_ma_period}-period MA")
        print(f"  - Volume threshold: {self.volume_threshold:.1f}x average")
        print(f"  - Max daily trades: {self.max_daily_trades}")
        
        for i in range(len(df)):
            current_row = df.iloc[i]
            current_date = current_row['Date']
            current_time = current_row['Datetime'].time()
            
            # Initialize daily trade counter
            if current_date not in daily_trades:
                daily_trades[current_date] = 0
            
            # Check for exit if in position
            if position is not None:
                # Update highest/lowest for trailing stops
                if position['direction'] == 'long':
                    position['highest_price'] = max(position['highest_price'], current_row['High'])
                else:
                    position['lowest_price'] = min(position['lowest_price'], current_row['Low'])
                
                should_exit, exit_reason = self.check_exit_conditions(
                    df, position['entry_idx'], i, position['direction'], 
                    position['entry_price'], position['highest_price'], position['lowest_price']
                )
                
                if should_exit:
                    # Exit position
                    exit_price = current_row['Close']
                    shares = position['shares']
                    commission = shares * self.commission_per_share * 2  # Entry + exit
                    
                    if position['direction'] == 'long':
                        pnl = (exit_price - position['entry_price']) * shares - commission
                    else:
                        pnl = (position['entry_price'] - exit_price) * shares - commission
                    
                    capital += pnl
                    
                    # Log trade
                    trade = {
                        'Symbol': symbol,
                        'Entry_Time': position['entry_time'],
                        'Exit_Time': current_row['Datetime'],
                        'Direction': position['direction'],
                        'Entry_Price': position['entry_price'],
                        'Exit_Price': exit_price,
                        'Entry_VWAP': position['entry_vwap'],
                        'Exit_VWAP': current_row['VWAP'],
                        'Shares': shares,
                        'PnL': pnl,
                        'Exit_Reason': exit_reason,
                        'Hold_Time_Minutes': (current_row['Datetime'] - position['entry_time']).total_seconds() / 60,
                        'Capital_After': capital
                    }
                    self.trades.append(trade)
                    position = None
            
            # Check for entry if not in position and haven't exceeded daily limit
            if position is None and daily_trades[current_date] < self.max_daily_trades:
                # Only consider entries in a specific time window (9:32 AM - 2:00 PM)
                if time(9, 32) <= current_time <= time(14, 0):
                    # Check for long entry
                    if self.check_entry_conditions(df, i, 'long'):
                        shares = self.calculate_position_size(
                            current_row['Close'], current_row['Volatility'], capital
                        )
                        
                        position = {
                            'direction': 'long',
                            'entry_idx': i,
                            'entry_time': current_row['Datetime'],
                            'entry_price': current_row['Close'],
                            'entry_vwap': current_row['VWAP'],
                            'shares': shares,
                            'highest_price': current_row['High'],
                            'lowest_price': current_row['Low']
                        }
                        daily_trades[current_date] += 1
                    
                    # Check for short entry (if not already long)
                    elif self.check_entry_conditions(df, i, 'short'):
                        shares = self.calculate_position_size(
                            current_row['Close'], current_row['Volatility'], capital
                        )
                        
                        position = {
                            'direction': 'short',
                            'entry_idx': i,
                            'entry_time': current_row['Datetime'],
                            'entry_price': current_row['Close'],
                            'entry_vwap': current_row['VWAP'],
                            'shares': shares,
                            'highest_price': current_row['High'],
                            'lowest_price': current_row['Low']
                        }
                        daily_trades[current_date] += 1
        
        # Close any remaining position at the end
        if position is not None:
            final_row = df.iloc[-1]
            exit_price = final_row['Close']
            shares = position['shares']
            commission = shares * self.commission_per_share * 2
            
            if position['direction'] == 'long':
                pnl = (exit_price - position['entry_price']) * shares - commission
            else:
                pnl = (position['entry_price'] - exit_price) * shares - commission
            
            capital += pnl
            
            trade = {
                'Symbol': symbol,
                'Entry_Time': position['entry_time'],
                'Exit_Time': final_row['Datetime'],
                'Direction': position['direction'],
                'Entry_Price': position['entry_price'],
                'Exit_Price': exit_price,
                'Entry_VWAP': position['entry_vwap'],
                'Exit_VWAP': final_row['VWAP'],
                'Shares': shares,
                'PnL': pnl,
                'Exit_Reason': 'End of Data',
                'Hold_Time_Minutes': (final_row['Datetime'] - position['entry_time']).total_seconds() / 60,
                'Capital_After': capital
            }
            self.trades.append(trade)
        
        return capital
    
    def analyze_results(self, symbols):
        """Analyze and display enhanced strategy results"""
        if not self.trades:
            print("No trades executed!")
            return
        
        trades_df = pd.DataFrame(self.trades)
        
        print(f"\n=== Enhanced VWAP Strategy Results ===")
        print(f"Total Trades: {len(trades_df)}")
        print(f"Initial Capital: ${self.initial_capital:,.2f}")
        print(f"Final Capital: ${trades_df['Capital_After'].iloc[-1]:,.2f}")
        
        total_return = (trades_df['Capital_After'].iloc[-1] - self.initial_capital) / self.initial_capital * 100
        print(f"Total Return: {total_return:.2f}%")
        
        # Win rate and trade statistics
        winning_trades = trades_df[trades_df['PnL'] > 0]
        win_rate = len(winning_trades) / len(trades_df) * 100
        
        print(f"\nTrade Statistics:")
        print(f"Win Rate: {win_rate:.1f}%")
        print(f"Average Trade: ${trades_df['PnL'].mean():.2f}")
        print(f"Best Trade: ${trades_df['PnL'].max():.2f}")
        print(f"Worst Trade: ${trades_df['PnL'].min():.2f}")
        print(f"Average Hold Time: {trades_df['Hold_Time_Minutes'].mean():.1f} minutes")
        
        # Exit reason analysis
        print(f"\nExit Reason Breakdown:")
        exit_reasons = trades_df['Exit_Reason'].value_counts()
        for reason, count in exit_reasons.items():
            print(f"  {reason}: {count} ({count/len(trades_df)*100:.1f}%)")
        
        # Performance by symbol
        print(f"\nPerformance by Symbol:")
        for symbol in symbols:
            symbol_trades = trades_df[trades_df['Symbol'] == symbol]
            if len(symbol_trades) > 0:
                symbol_pnl = symbol_trades['PnL'].sum()
                symbol_win_rate = len(symbol_trades[symbol_trades['PnL'] > 0]) / len(symbol_trades) * 100
                print(f"  {symbol}: {len(symbol_trades)} trades, ${symbol_pnl:.2f} PnL, {symbol_win_rate:.1f}% win rate")
        
        # Save detailed results
        trades_df.to_csv('enhanced_vwap_trades.csv', index=False)
        print(f"\nDetailed trades saved to: enhanced_vwap_trades.csv")
        
        return trades_df

def main():
    """Run the enhanced VWAP strategy backtest"""
    strategy = EnhancedVWAPStrategy(initial_capital=100000)
    symbols = ['QQQ', 'TQQQ']
    
    print("=== Enhanced VWAP Strategy Backtest ===")
    print("Improvements over original strategy:")
    print("✓ Trend filter using 20-period moving average")
    print("✓ VWAP buffer (0.1%) to reduce whipsaws") 
    print("✓ Confirmation candles before entry")
    print("✓ Trailing stop loss (0.5%)")
    print("✓ Time-based maximum hold (2 hours)")
    print("✓ Volume filter (1.2x average volume)")
    print("✓ Volatility-based position sizing")
    print("✓ Maximum daily trades limit (3)")
    print("✓ Limited entry window (9:32 AM - 2:00 PM)")
    
    for symbol in symbols:
        try:
            final_capital = strategy.backtest(symbol)
            print(f"{symbol} backtest completed. Final capital: ${final_capital:,.2f}")
        except Exception as e:
            print(f"Error backtesting {symbol}: {e}")
    
    # Analyze combined results
    strategy.analyze_results(symbols)

if __name__ == "__main__":
    main()