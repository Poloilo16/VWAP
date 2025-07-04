import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from datetime import datetime, time
import warnings
warnings.filterwarnings('ignore')

class VWAPStrategy:
    def __init__(self, initial_capital=100000, commission_per_share=0.0005):
        """
        Initialize the VWAP Strategy
        
        Parameters:
        initial_capital: Starting capital in USD
        commission_per_share: Commission per share in USD
        """
        self.initial_capital = initial_capital
        self.commission_per_share = commission_per_share
        self.trades = []
        self.equity_curve = []
        
    def load_data(self, symbol):
        """Load and prepare data for backtesting"""
        filename = f'{symbol}_60day_1min_data.csv'
        try:
            df = pd.read_csv(filename)
            df['Datetime'] = pd.to_datetime(df['Datetime'])
            
            # Filter for regular trading hours (9:30 AM - 4:00 PM ET)
            df['Time'] = df['Datetime'].dt.time
            market_open = time(9, 30)  # 9:30 AM
            market_close = time(16, 0)  # 4:00 PM
            
            df = df[(df['Time'] >= market_open) & (df['Time'] <= market_close)].copy()
            
            # Add date column for daily grouping
            df['Date'] = df['Datetime'].dt.date
            
            # Calculate typical price for VWAP
            df['TypicalPrice'] = (df['High'] + df['Low'] + df['Close']) / 3
            df['PriceVolume'] = df['TypicalPrice'] * df['Volume']
            
            print(f"Loaded {len(df)} rows for {symbol}")
            print(f"Date range: {df['Date'].min()} to {df['Date'].max()}")
            print(f"Unique trading days: {df['Date'].nunique()}")
            
            return df.sort_values('Datetime').reset_index(drop=True)
            
        except FileNotFoundError:
            print(f"Error: Could not find {filename}")
            return None
    
    def calculate_vwap(self, df):
        """Calculate VWAP for each minute, resetting daily"""
        df = df.copy()
        df['VWAP'] = np.nan
        
        for date in df['Date'].unique():
            date_mask = df['Date'] == date
            date_data = df[date_mask].copy()
            
            # Calculate cumulative VWAP from market open each day
            cumsum_pv = date_data['PriceVolume'].cumsum()
            cumsum_vol = date_data['Volume'].cumsum()
            
            # Avoid division by zero
            vwap_values = np.where(cumsum_vol > 0, cumsum_pv / cumsum_vol, date_data['TypicalPrice'])
            df.loc[date_mask, 'VWAP'] = vwap_values
            
        return df
    
    def classify_position_relative_to_vwap(self, df):
        """Classify each candle as above/below VWAP for imbalance analysis"""
        df = df.copy()
        df['PrevClose'] = df['Close'].shift(1)
        df['PositionVsVWAP'] = np.where(df['PrevClose'] > df['VWAP'], 'Above', 'Below')
        
        return df
    
    def backtest(self, symbol):
        """
        Run the VWAP strategy backtest
        
        Strategy Rules:
        - Enter long if 9:31am close > VWAP
        - Enter short if 9:31am close < VWAP
        - Exit long if any future close < VWAP
        - Exit short if any future close > VWAP
        - Exit all positions at market close (4:00 PM)
        """
        
        print(f"\n{'='*60}")
        print(f"BACKTESTING VWAP STRATEGY FOR {symbol}")
        print(f"{'='*60}")
        
        # Load and prepare data
        df = self.load_data(symbol)
        if df is None:
            return None
            
        # Calculate VWAP
        df = self.calculate_vwap(df)
        
        # Classify positions for imbalance analysis
        df = self.classify_position_relative_to_vwap(df)
        
        # Initialize tracking variables
        current_capital = self.initial_capital
        position = None  # {'type': 'long'/'short', 'entry_price': float, 'shares': int, 'entry_time': datetime, 'entry_vwap': float}
        daily_trades = []
        equity_history = []
        
        # Group by date for daily processing
        for date in sorted(df['Date'].unique()):
            daily_data = df[df['Date'] == date].copy()
            
            if len(daily_data) == 0:
                continue
                
            # Find 9:31 AM candle (entry signal)
            entry_time = time(9, 31)
            entry_candles = daily_data[daily_data['Time'] == entry_time]
            
            if len(entry_candles) == 0:
                print(f"Warning: No 9:31 AM candle found for {date}")
                continue
                
            entry_candle = entry_candles.iloc[0]
            entry_close = entry_candle['Close']
            entry_vwap = entry_candle['VWAP']
            
            # Determine entry signal
            if entry_close > entry_vwap:
                signal = 'long'
            elif entry_close < entry_vwap:
                signal = 'short'
            else:
                signal = None
            
            # Enter position if signal exists
            if signal and position is None:
                shares = int(current_capital / entry_close)  # Use 100% of capital
                commission = shares * self.commission_per_share
                
                position = {
                    'type': signal,
                    'entry_price': entry_close,
                    'shares': shares,
                    'entry_time': entry_candle['Datetime'],
                    'entry_vwap': entry_vwap,
                    'commission_entry': commission
                }
                
                print(f"{date}: ENTERED {signal.upper()} - {shares} shares @ ${entry_close:.2f} (VWAP: ${entry_vwap:.2f})")
            
            # Monitor position for exit signals
            if position is not None:
                # Check each subsequent candle for exit signals
                subsequent_candles = daily_data[daily_data['Datetime'] > position['entry_time']]
                
                exit_triggered = False
                exit_reason = None
                exit_candle = None
                
                for idx, candle in subsequent_candles.iterrows():
                    current_close = candle['Close']
                    current_vwap = candle['VWAP']
                    
                    # Check stop loss conditions
                    if position['type'] == 'long' and current_close < current_vwap:
                        exit_triggered = True
                        exit_reason = 'Stop Loss (Close < VWAP)'
                        exit_candle = candle
                        break
                    elif position['type'] == 'short' and current_close > current_vwap:
                        exit_triggered = True
                        exit_reason = 'Stop Loss (Close > VWAP)'
                        exit_candle = candle
                        break
                
                # If no stop loss triggered, exit at market close (4:00 PM)
                if not exit_triggered:
                    market_close_candles = daily_data[daily_data['Time'] == time(16, 0)]
                    if len(market_close_candles) > 0:
                        exit_candle = market_close_candles.iloc[0]
                        exit_reason = 'Market Close'
                    else:
                        # Use last candle of the day if no 4:00 PM candle
                        exit_candle = daily_data.iloc[-1]
                        exit_reason = 'End of Day'
                
                # Execute exit
                if exit_candle is not None:
                    exit_price = exit_candle['Close']
                    commission_exit = position['shares'] * self.commission_per_share
                    
                    # Calculate P&L
                    if position['type'] == 'long':
                        gross_pnl = (exit_price - position['entry_price']) * position['shares']
                    else:  # short
                        gross_pnl = (position['entry_price'] - exit_price) * position['shares']
                    
                    total_commission = position['commission_entry'] + commission_exit
                    net_pnl = gross_pnl - total_commission
                    
                    # Update capital
                    current_capital += net_pnl
                    
                    # Record trade
                    trade = {
                        'symbol': symbol,
                        'date': date,
                        'entry_time': position['entry_time'],
                        'exit_time': exit_candle['Datetime'],
                        'direction': position['type'],
                        'shares': position['shares'],
                        'entry_price': position['entry_price'],
                        'exit_price': exit_price,
                        'entry_vwap': position['entry_vwap'],
                        'exit_vwap': exit_candle['VWAP'],
                        'gross_pnl': gross_pnl,
                        'commission': total_commission,
                        'net_pnl': net_pnl,
                        'exit_reason': exit_reason,
                        'capital_after': current_capital
                    }
                    
                    daily_trades.append(trade)
                    self.trades.append(trade)
                    
                    print(f"{date}: EXITED {position['type'].upper()} - {position['shares']} shares @ ${exit_price:.2f} | P&L: ${net_pnl:.2f} | Reason: {exit_reason}")
                    print(f"         Capital: ${current_capital:.2f}")
                    
                    # Clear position
                    position = None
            
            # Record daily equity
            equity_history.append({
                'date': date,
                'equity': current_capital,
                'symbol': symbol
            })
        
        # Store results
        self.equity_curve.extend(equity_history)
        
        return {
            'trades': daily_trades,
            'equity_curve': equity_history,
            'final_capital': current_capital,
            'total_return': (current_capital - self.initial_capital) / self.initial_capital,
            'data': df
        }
    
    def analyze_imbalance(self, df):
        """Analyze position imbalance relative to VWAP"""
        imbalance_stats = df.groupby(['Date', 'PositionVsVWAP']).size().unstack(fill_value=0)
        
        if 'Above' in imbalance_stats.columns and 'Below' in imbalance_stats.columns:
            imbalance_stats['Total'] = imbalance_stats['Above'] + imbalance_stats['Below']
            imbalance_stats['Above_Pct'] = imbalance_stats['Above'] / imbalance_stats['Total'] * 100
            imbalance_stats['Below_Pct'] = imbalance_stats['Below'] / imbalance_stats['Total'] * 100
            imbalance_stats['Imbalance'] = imbalance_stats['Above_Pct'] - imbalance_stats['Below_Pct']
        
        return imbalance_stats
    
    def calculate_performance_metrics(self, trades, symbol):
        """Calculate comprehensive performance metrics"""
        if not trades:
            return {}
        
        df_trades = pd.DataFrame(trades)
        
        # Basic metrics
        total_trades = len(trades)
        winning_trades = len(df_trades[df_trades['net_pnl'] > 0])
        losing_trades = len(df_trades[df_trades['net_pnl'] < 0])
        win_rate = winning_trades / total_trades * 100 if total_trades > 0 else 0
        
        # P&L metrics
        total_gross_pnl = df_trades['gross_pnl'].sum()
        total_commission = df_trades['commission'].sum()
        total_net_pnl = df_trades['net_pnl'].sum()
        
        avg_trade = df_trades['net_pnl'].mean()
        avg_winner = df_trades[df_trades['net_pnl'] > 0]['net_pnl'].mean() if winning_trades > 0 else 0
        avg_loser = df_trades[df_trades['net_pnl'] < 0]['net_pnl'].mean() if losing_trades > 0 else 0
        
        largest_winner = df_trades['net_pnl'].max()
        largest_loser = df_trades['net_pnl'].min()
        
        # Calculate drawdown
        equity_values = [self.initial_capital] + [trade['capital_after'] for trade in trades]
        equity_series = pd.Series(equity_values)
        rolling_max = equity_series.expanding().max()
        drawdown = (equity_series - rolling_max) / rolling_max * 100
        max_drawdown = drawdown.min()
        
        # Profit factor
        gross_profit = df_trades[df_trades['net_pnl'] > 0]['net_pnl'].sum()
        gross_loss = abs(df_trades[df_trades['net_pnl'] < 0]['net_pnl'].sum())
        profit_factor = gross_profit / gross_loss if gross_loss > 0 else float('inf')
        
        return {
            'symbol': symbol,
            'total_trades': total_trades,
            'winning_trades': winning_trades,
            'losing_trades': losing_trades,
            'win_rate': win_rate,
            'total_gross_pnl': total_gross_pnl,
            'total_commission': total_commission,
            'total_net_pnl': total_net_pnl,
            'avg_trade': avg_trade,
            'avg_winner': avg_winner,
            'avg_loser': avg_loser,
            'largest_winner': largest_winner,
            'largest_loser': largest_loser,
            'max_drawdown': max_drawdown,
            'profit_factor': profit_factor,
            'final_capital': self.initial_capital + total_net_pnl,
            'total_return_pct': (total_net_pnl / self.initial_capital) * 100
        }
    
    def print_performance_summary(self, metrics):
        """Print detailed performance summary"""
        print(f"\n{'='*60}")
        print(f"PERFORMANCE SUMMARY - {metrics['symbol']}")
        print(f"{'='*60}")
        print(f"Initial Capital:     ${self.initial_capital:,.2f}")
        print(f"Final Capital:       ${metrics['final_capital']:,.2f}")
        print(f"Total Return:        {metrics['total_return_pct']:.2f}%")
        print(f"")
        print(f"Trade Statistics:")
        print(f"  Total Trades:      {metrics['total_trades']}")
        print(f"  Winning Trades:    {metrics['winning_trades']}")
        print(f"  Losing Trades:     {metrics['losing_trades']}")
        print(f"  Win Rate:          {metrics['win_rate']:.1f}%")
        print(f"")
        print(f"P&L Breakdown:")
        print(f"  Gross P&L:         ${metrics['total_gross_pnl']:,.2f}")
        print(f"  Total Commission:  ${metrics['total_commission']:,.2f}")
        print(f"  Net P&L:           ${metrics['total_net_pnl']:,.2f}")
        print(f"")
        print(f"Trade Analysis:")
        print(f"  Average Trade:     ${metrics['avg_trade']:,.2f}")
        print(f"  Average Winner:    ${metrics['avg_winner']:,.2f}")
        print(f"  Average Loser:     ${metrics['avg_loser']:,.2f}")
        print(f"  Largest Winner:    ${metrics['largest_winner']:,.2f}")
        print(f"  Largest Loser:     ${metrics['largest_loser']:,.2f}")
        print(f"")
        print(f"Risk Metrics:")
        print(f"  Max Drawdown:      {metrics['max_drawdown']:.2f}%")
        print(f"  Profit Factor:     {metrics['profit_factor']:.2f}")
    
    def plot_results(self, results_qqq, results_tqqq):
        """Create comprehensive plots of backtest results"""
        fig, axes = plt.subplots(2, 2, figsize=(15, 12))
        
        # Plot 1: Equity curves
        if results_qqq and results_qqq['equity_curve']:
            qqq_dates = [eq['date'] for eq in results_qqq['equity_curve']]
            qqq_equity = [eq['equity'] for eq in results_qqq['equity_curve']]
            axes[0,0].plot(qqq_dates, qqq_equity, label='QQQ', linewidth=2)
        
        if results_tqqq and results_tqqq['equity_curve']:
            tqqq_dates = [eq['date'] for eq in results_tqqq['equity_curve']]
            tqqq_equity = [eq['equity'] for eq in results_tqqq['equity_curve']]
            axes[0,0].plot(tqqq_dates, tqqq_equity, label='TQQQ', linewidth=2)
        
        axes[0,0].axhline(y=self.initial_capital, color='gray', linestyle='--', alpha=0.7)
        axes[0,0].set_title('Equity Curve')
        axes[0,0].set_ylabel('Capital ($)')
        axes[0,0].legend()
        axes[0,0].grid(True, alpha=0.3)
        
        # Plot 2: Trade P&L distribution
        all_trades = []
        if results_qqq and results_qqq['trades']:
            all_trades.extend([(trade['net_pnl'], 'QQQ') for trade in results_qqq['trades']])
        if results_tqqq and results_tqqq['trades']:
            all_trades.extend([(trade['net_pnl'], 'TQQQ') for trade in results_tqqq['trades']])
        
        if all_trades:
            pnls, symbols = zip(*all_trades)
            axes[0,1].hist(pnls, bins=30, alpha=0.7, edgecolor='black')
            axes[0,1].axvline(x=0, color='red', linestyle='--', alpha=0.7)
            axes[0,1].set_title('Trade P&L Distribution')
            axes[0,1].set_xlabel('Net P&L ($)')
            axes[0,1].set_ylabel('Frequency')
            axes[0,1].grid(True, alpha=0.3)
        
        # Plot 3: Monthly returns
        monthly_returns = {}
        for symbol, results in [('QQQ', results_qqq), ('TQQQ', results_tqqq)]:
            if results and results['trades']:
                df_trades = pd.DataFrame(results['trades'])
                df_trades['month'] = pd.to_datetime(df_trades['date']).dt.to_period('M')
                monthly_pnl = df_trades.groupby('month')['net_pnl'].sum()
                monthly_returns[symbol] = monthly_pnl
        
        if monthly_returns:
            months = set()
            for returns in monthly_returns.values():
                months.update(returns.index)
            months = sorted(months)
            
            x = np.arange(len(months))
            width = 0.35
            
            if 'QQQ' in monthly_returns:
                qqq_values = [monthly_returns['QQQ'].get(month, 0) for month in months]
                axes[1,0].bar(x - width/2, qqq_values, width, label='QQQ', alpha=0.8)
            
            if 'TQQQ' in monthly_returns:
                tqqq_values = [monthly_returns['TQQQ'].get(month, 0) for month in months]
                axes[1,0].bar(x + width/2, tqqq_values, width, label='TQQQ', alpha=0.8)
            
            axes[1,0].set_title('Monthly P&L')
            axes[1,0].set_ylabel('P&L ($)')
            axes[1,0].set_xticks(x)
            axes[1,0].set_xticklabels([str(m) for m in months], rotation=45)
            axes[1,0].legend()
            axes[1,0].grid(True, alpha=0.3)
            axes[1,0].axhline(y=0, color='red', linestyle='-', alpha=0.3)
        
        # Plot 4: Win rate by symbol
        win_rates = {}
        for symbol, results in [('QQQ', results_qqq), ('TQQQ', results_tqqq)]:
            if results and results['trades']:
                df_trades = pd.DataFrame(results['trades'])
                total = len(df_trades)
                wins = len(df_trades[df_trades['net_pnl'] > 0])
                win_rates[symbol] = wins / total * 100 if total > 0 else 0
        
        if win_rates:
            symbols = list(win_rates.keys())
            rates = list(win_rates.values())
            bars = axes[1,1].bar(symbols, rates, alpha=0.8, color=['blue', 'orange'])
            axes[1,1].set_title('Win Rate by Symbol')
            axes[1,1].set_ylabel('Win Rate (%)')
            axes[1,1].set_ylim(0, 100)
            axes[1,1].grid(True, alpha=0.3)
            
            # Add value labels on bars
            for bar, rate in zip(bars, rates):
                height = bar.get_height()
                axes[1,1].text(bar.get_x() + bar.get_width()/2., height + 1,
                             f'{rate:.1f}%', ha='center', va='bottom')
        
        plt.tight_layout()
        plt.savefig('vwap_strategy_results.png', dpi=300, bbox_inches='tight')
        plt.show()


def main():
    """Main function to run the VWAP strategy backtest"""
    
    print("VWAP Strategy Backtesting System")
    print("================================")
    
    # Initialize strategy
    strategy = VWAPStrategy(initial_capital=100000, commission_per_share=0.0005)
    
    # Backtest both symbols
    results = {}
    
    for symbol in ['QQQ', 'TQQQ']:
        results[symbol] = strategy.backtest(symbol)
        
        if results[symbol]:
            # Calculate and print performance metrics
            metrics = strategy.calculate_performance_metrics(results[symbol]['trades'], symbol)
            strategy.print_performance_summary(metrics)
            
            # Analyze imbalance
            imbalance = strategy.analyze_imbalance(results[symbol]['data'])
            print(f"\nImbalance Analysis for {symbol}:")
            print(f"Average Above VWAP: {imbalance['Above_Pct'].mean():.1f}%")
            print(f"Average Below VWAP: {imbalance['Below_Pct'].mean():.1f}%")
            
            # Print recent trades
            if results[symbol]['trades']:
                print(f"\nRecent Trades for {symbol}:")
                recent_trades = results[symbol]['trades'][-5:]  # Last 5 trades
                for trade in recent_trades:
                    print(f"  {trade['date']}: {trade['direction'].upper()} | "
                          f"Entry: ${trade['entry_price']:.2f} | Exit: ${trade['exit_price']:.2f} | "
                          f"P&L: ${trade['net_pnl']:.2f} | {trade['exit_reason']}")
        
        print("\n" + "="*60)
    
    # Create comprehensive plots
    if results.get('QQQ') or results.get('TQQQ'):
        strategy.plot_results(results.get('QQQ'), results.get('TQQQ'))
    
    # Export trade logs to CSV
    all_trades = []
    for symbol in ['QQQ', 'TQQQ']:
        if results.get(symbol) and results[symbol]['trades']:
            all_trades.extend(results[symbol]['trades'])
    
    if all_trades:
        trade_df = pd.DataFrame(all_trades)
        trade_df.to_csv('vwap_strategy_trades.csv', index=False)
        print(f"\nTrade log exported to: vwap_strategy_trades.csv")
        print(f"Total trades exported: {len(all_trades)}")


if __name__ == "__main__":
    main()