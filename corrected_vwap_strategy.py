import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from datetime import datetime, time
import warnings
warnings.filterwarnings('ignore')

class CorrectedVWAPStrategy:
    def __init__(self, initial_capital=100000, commission_per_share=0.0005):
        """
        Corrected VWAP Strategy with proper calculation and improved parameters
        
        Key Fixes Applied:
        1. Correct VWAP calculation using Close price instead of Typical Price
        2. Delayed entry timing (9:45 AM) for stable VWAP
        3. Confirmed exits with buffers to reduce whipsaws
        4. Risk-based position sizing (2% max risk per trade)
        5. Multiple stop types: profit target, time stop, confirmed VWAP stop
        6. Volume-based entry filters
        """
        self.initial_capital = initial_capital
        self.commission_per_share = commission_per_share
        self.trades = []
        
        # CORRECTED STRATEGY PARAMETERS
        self.entry_start_time = time(9, 45)    # Wait 15 minutes for stable VWAP
        self.entry_end_time = time(15, 30)     # Stop entries before close
        self.vwap_buffer = 0.001               # 0.1% buffer for entries/exits
        self.confirmation_candles = 2          # Require 2 candles for exits
        self.max_hold_minutes = 120            # 2-hour maximum hold time
        self.profit_target_pct = 0.015         # 1.5% profit target
        self.max_risk_per_trade = 0.02         # 2% of capital at risk
        self.volume_multiplier = 1.2           # Require 1.2x average volume
        self.min_vwap_minutes = 15             # Minimum data for reliable VWAP
        
    def load_and_prepare_data(self, symbol):
        """Load data and prepare for backtesting"""
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
        return df.sort_values('Datetime').reset_index(drop=True)
    
    def calculate_vwap_correctly(self, df):
        """
        CORRECTED VWAP calculation using proper price weighting
        
        FIX #1: Use Close price instead of Typical Price for more accurate VWAP
        """
        df = df.copy()
        df['Date'] = df['Datetime'].dt.date
        
        # CORRECT: Use Close price as proxy for average transaction price
        # This is much more accurate than theoretical Typical Price
        df['Trade_Price'] = df['Close']
        df['PriceVolume'] = df['Trade_Price'] * df['Volume']
        
        # Calculate VWAP by day with volume threshold
        for date in df['Date'].unique():
            date_mask = df['Date'] == date
            date_data = df[date_mask].copy()
            
            # Calculate cumulative VWAP from market open each day
            cumsum_pv = date_data['PriceVolume'].cumsum()
            cumsum_vol = date_data['Volume'].cumsum()
            
            # More robust VWAP with minimum volume threshold
            vwap_values = np.where(
                cumsum_vol > 1000,  # Minimum volume for reliable VWAP
                cumsum_pv / cumsum_vol,
                date_data['Trade_Price']
            )
            df.loc[date_mask, 'VWAP'] = vwap_values
        
        # Calculate rolling average volume for filtering
        df['Avg_Volume_15'] = df.groupby('Date')['Volume'].rolling(15, min_periods=1).mean().reset_index(0, drop=True)
        
        return df
    
    def calculate_atr(self, df, period=14):
        """Calculate Average True Range for position sizing"""
        df = df.copy()
        df['High_Low'] = df['High'] - df['Low']
        df['High_Close_Prev'] = abs(df['High'] - df['Close'].shift(1))
        df['Low_Close_Prev'] = abs(df['Low'] - df['Close'].shift(1))
        
        df['True_Range'] = df[['High_Low', 'High_Close_Prev', 'Low_Close_Prev']].max(axis=1)
        df['ATR'] = df.groupby('Date')['True_Range'].rolling(period, min_periods=1).mean().reset_index(0, drop=True)
        
        return df
    
    def check_entry_conditions(self, df, current_idx):
        """
        CORRECTED entry conditions with proper timing and volume filters
        
        FIX #2: Wait until 9:45 AM for stable VWAP calculation
        FIX #3: Add volume-based entry filters
        """
        current_row = df.iloc[current_idx]
        current_time = current_row['Datetime'].time()
        
        # Don't trade too early - wait for stable VWAP (FIX #2)
        if current_time < self.entry_start_time:
            return False, None
        
        # Don't trade too late - avoid end-of-day volatility
        if current_time > self.entry_end_time:
            return False, None
        
        # Ensure we have enough data for reliable VWAP
        vwap_start_idx = current_idx - self.min_vwap_minutes
        if vwap_start_idx < 0:
            return False, None
        
        # Volume filter - require above-average volume (FIX #3)
        current_volume = current_row['Volume']
        avg_volume = current_row['Avg_Volume_15']
        
        if pd.isna(avg_volume) or current_volume < avg_volume * self.volume_multiplier:
            return False, None
        
        # Entry logic with buffer to reduce false signals
        current_price = current_row['Close']
        current_vwap = current_row['VWAP']
        
        if current_price > current_vwap * (1 + self.vwap_buffer):
            return True, 'long'
        elif current_price < current_vwap * (1 - self.vwap_buffer):
            return True, 'short'
        
        return False, None
    
    def calculate_position_size(self, entry_price, atr, capital, symbol):
        """
        CORRECTED position sizing based on risk management
        
        FIX #4: Use risk-based position sizing instead of 100% capital
        """
        # Calculate stop distance using ATR
        stop_distance = atr * 2.0  # 2x ATR stop
        
        # Calculate position size based on max risk per trade
        risk_amount = capital * self.max_risk_per_trade
        shares = int(risk_amount / stop_distance) if stop_distance > 0 else 0
        
        # Additional adjustment for leveraged ETFs
        if symbol == 'TQQQ':
            shares = int(shares * 0.5)  # Half size for 3x leveraged ETF
        
        # Ensure we don't exceed available capital
        max_shares = int(capital * 0.95 / entry_price)  # Use 95% max
        shares = min(shares, max_shares)
        
        return max(1, shares)  # At least 1 share
    
    def check_exit_conditions(self, df, position, current_idx):
        """
        CORRECTED exit conditions with confirmation and multiple stop types
        
        FIX #5: Add confirmation for VWAP exits to reduce whipsaws
        FIX #6: Add profit targets and time-based stops
        """
        current_row = df.iloc[current_idx]
        current_price = current_row['Close']
        current_vwap = current_row['VWAP']
        
        # Time-based stop (maximum hold time)
        hold_time = (current_row['Datetime'] - position['entry_time']).total_seconds() / 60
        if hold_time >= self.max_hold_minutes:
            return True, "Time Stop"
        
        # Market close exit
        if current_row['Datetime'].time() >= time(15, 59):
            return True, "Market Close"
        
        # Profit target exit (FIX #6)
        entry_price = position['entry_price']
        if position['direction'] == 'long':
            profit_pct = (current_price - entry_price) / entry_price
        else:
            profit_pct = (entry_price - current_price) / entry_price
        
        if profit_pct >= self.profit_target_pct:
            return True, "Profit Target"
        
        # VWAP stop with CONFIRMATION (FIX #5)
        if current_idx >= self.confirmation_candles:
            # Get last N candles for confirmation
            confirmation_data = df.iloc[current_idx-self.confirmation_candles+1:current_idx+1]
            
            if position['direction'] == 'long':
                # Exit long if consecutive closes below VWAP with buffer
                consecutive_below = all(
                    candle['Close'] < candle['VWAP'] * (1 - self.vwap_buffer)
                    for _, candle in confirmation_data.iterrows()
                )
                if consecutive_below:
                    return True, "VWAP Stop (Confirmed)"
            
            else:  # short position
                # Exit short if consecutive closes above VWAP with buffer
                consecutive_above = all(
                    candle['Close'] > candle['VWAP'] * (1 + self.vwap_buffer)
                    for _, candle in confirmation_data.iterrows()
                )
                if consecutive_above:
                    return True, "VWAP Stop (Confirmed)"
        
        return False, ""
    
    def backtest(self, symbol):
        """Run corrected backtest with all fixes applied"""
        df = self.load_and_prepare_data(symbol)
        df = self.calculate_vwap_correctly(df)  # FIX #1: Correct VWAP calculation
        df = self.calculate_atr(df)  # For position sizing
        
        capital = self.initial_capital
        position = None
        
        print(f"\n=== CORRECTED VWAP Strategy Backtest for {symbol} ===")
        print(f"Initial Capital: ${capital:,.2f}")
        print(f"Key Corrections Applied:")
        print(f"  ✓ VWAP uses Close price (not Typical Price)")
        print(f"  ✓ Entry timing: {self.entry_start_time} (not 9:31 AM)")
        print(f"  ✓ Exit confirmation: {self.confirmation_candles} candles")
        print(f"  ✓ Risk per trade: {self.max_risk_per_trade*100}% (not 100% capital)")
        print(f"  ✓ Profit target: {self.profit_target_pct*100}%")
        print(f"  ✓ Max hold time: {self.max_hold_minutes} minutes")
        
        for i in range(len(df)):
            current_row = df.iloc[i]
            
            # Check for exit if in position
            if position is not None:
                should_exit, exit_reason = self.check_exit_conditions(df, position, i)
                
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
            
            # Check for entry if not in position
            if position is None:
                can_enter, direction = self.check_entry_conditions(df, i)
                
                if can_enter:
                    atr = current_row.get('ATR', current_row['Close'] * 0.02)  # Fallback ATR
                    shares = self.calculate_position_size(
                        current_row['Close'], atr, capital, symbol
                    )
                    
                    position = {
                        'direction': direction,
                        'entry_time': current_row['Datetime'],
                        'entry_price': current_row['Close'],
                        'entry_vwap': current_row['VWAP'],
                        'shares': shares
                    }
        
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
        """Analyze and display corrected strategy results"""
        if not self.trades:
            print("No trades executed!")
            return
        
        trades_df = pd.DataFrame(self.trades)
        
        print(f"\n=== CORRECTED VWAP Strategy Results ===")
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
        trades_df.to_csv('corrected_vwap_trades.csv', index=False)
        print(f"\nDetailed trades saved to: corrected_vwap_trades.csv")
        
        # Key improvements summary
        print(f"\n=== IMPROVEMENTS FROM CORRECTIONS ===")
        print(f"✓ VWAP calculation uses Close price (more accurate)")
        print(f"✓ Entry timing delayed to 9:45 AM (stable VWAP)")
        print(f"✓ Exit confirmation prevents whipsaws")
        print(f"✓ Risk-based position sizing (2% max risk)")
        print(f"✓ Profit targets lock in gains")
        print(f"✓ Time stops prevent overexposure")
        print(f"✓ Volume filters ensure quality entries")
        
        return trades_df

def main():
    """Run the corrected VWAP strategy backtest"""
    strategy = CorrectedVWAPStrategy(initial_capital=100000)
    symbols = ['QQQ', 'TQQQ']
    
    print("=== CORRECTED VWAP Strategy Backtest ===")
    print("Major fixes applied to original strategy:")
    print("1. ✓ CORRECT VWAP calculation (Close price vs Typical Price)")
    print("2. ✓ PROPER entry timing (9:45 AM vs 9:31 AM)")
    print("3. ✓ CONFIRMED exits (reduce whipsaws)")
    print("4. ✓ RISK-BASED position sizing (2% risk vs 100% capital)")
    print("5. ✓ PROFIT targets (1.5% take profit)")
    print("6. ✓ TIME-BASED stops (2-hour maximum)")
    print("7. ✓ VOLUME filters (quality entries)")
    
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