"""
Stock Screener with Real-Time Data using yfinance

SETUP:
1. Install required packages:
   pip install yfinance pandas numpy

2. Run the script:
   python stock_screener_live.py

Note: This version fetches real market data and may take a few minutes to run.
"""

import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime
import time

class LiveStockScreener:
    def __init__(self, tickers=None):
        """
        Initialize with list of tickers to screen
        
        Parameters:
        -----------
        tickers : list, optional
            List of stock tickers. If None, uses default list.
        """
        if tickers is None:
            # Default list - you can expand this
            self.tickers = [
                # Tech
                'AAPL', 'MSFT', 'GOOGL', 'AMZN', 'META', 'NVDA', 'TSLA', 'NFLX',
                'ADBE', 'CRM', 'ORCL', 'INTC', 'AMD', 'QCOM', 'AVGO', 'IBM',
                # Finance
                'JPM', 'BAC', 'WFC', 'GS', 'MS', 'C', 'V', 'MA', 'AXP',
                # Consumer
                'WMT', 'HD', 'NKE', 'MCD', 'SBUX', 'TGT', 'COST', 'LOW',
                # Healthcare
                'JNJ', 'UNH', 'PFE', 'ABBV', 'TMO', 'ABT', 'MRK', 'LLY',
                # Energy
                'XOM', 'CVX', 'COP', 'SLB', 'EOG',
                # Others
                'DIS', 'PG', 'KO', 'PEP', 'VZ', 'T'
            ]
        else:
            self.tickers = tickers
        
        self.stocks_data = None
    
    def fetch_stock_data(self, ticker):
        """Fetch data for a single stock"""
        try:
            stock = yf.Ticker(ticker)
            info = stock.info
            hist = stock.history(period="1y")
            
            if hist.empty or len(hist) < 50:
                return None
            
            # Current price
            current_price = hist['Close'].iloc[-1]
            
            # Moving averages
            sma_50 = hist['Close'].tail(50).mean()
            sma_200 = hist['Close'].tail(200).mean() if len(hist) >= 200 else None
            
            # Price changes
            price_change_1m = ((current_price - hist['Close'].iloc[-22]) / 
                             hist['Close'].iloc[-22] * 100) if len(hist) > 22 else 0
            price_change_3m = ((current_price - hist['Close'].iloc[-66]) / 
                             hist['Close'].iloc[-66] * 100) if len(hist) > 66 else 0
            
            # Volatility (annualized standard deviation)
            returns = hist['Close'].pct_change().dropna()
            volatility = returns.std() * np.sqrt(252) * 100
            
            # Compile data
            data = {
                'Ticker': ticker,
                'Price': round(current_price, 2),
                'Market_Cap_B': info.get('marketCap', 0) / 1e9,
                'PE_Ratio': info.get('trailingPE'),
                'Forward_PE': info.get('forwardPE'),
                'PEG_Ratio': info.get('pegRatio'),
                'Dividend_Yield': (info.get('dividendYield', 0) * 100) if info.get('dividendYield') else 0,
                'Beta': info.get('beta'),
                'ROE': (info.get('returnOnEquity', 0) * 100) if info.get('returnOnEquity') else None,
                'Profit_Margin': (info.get('profitMargins', 0) * 100) if info.get('profitMargins') else None,
                'Debt_to_Equity': info.get('debtToEquity'),
                'Current_Ratio': info.get('currentRatio'),
                'Price_vs_SMA50': round((current_price - sma_50) / sma_50 * 100, 2) if sma_50 else None,
                'Price_vs_SMA200': round((current_price - sma_200) / sma_200 * 100, 2) if sma_200 else None,
                'Change_1M': round(price_change_1m, 2),
                'Change_3M': round(price_change_3m, 2),
                'Volatility': round(volatility, 2),
                'Sector': info.get('sector', 'N/A'),
                'Industry': info.get('industry', 'N/A'),
                '52W_High': info.get('fiftyTwoWeekHigh'),
                '52W_Low': info.get('fiftyTwoWeekLow'),
            }
            
            return data
            
        except Exception as e:
            print(f"Error fetching {ticker}: {str(e)}")
            return None
    
    def load_live_data(self):
        """Fetch live data for all tickers"""
        print(f"\nFetching data for {len(self.tickers)} stocks...")
        print("This may take a few minutes...\n")
        
        results = []
        for i, ticker in enumerate(self.tickers, 1):
            print(f"[{i}/{len(self.tickers)}] Fetching {ticker}...", end='\r')
            
            data = self.fetch_stock_data(ticker)
            if data:
                results.append(data)
            
            # Small delay to avoid rate limiting
            time.sleep(0.2)
        
        print("\n✓ Data fetch complete!")
        
        self.stocks_data = pd.DataFrame(results)
        return self.stocks_data
    
    def screen(self, criteria):
        """
        Screen stocks based on criteria
        
        Example criteria:
        {
            'min_market_cap': 10,  # billions
            'max_pe': 25,
            'min_dividend_yield': 2.0,
            'min_roe': 15,
            'above_sma200': True,
            'max_volatility': 30,
            'sector': 'Technology'
        }
        """
        if self.stocks_data is None:
            print("No data loaded. Run load_live_data() first.")
            return pd.DataFrame()
        
        df = self.stocks_data.copy()
        
        # Apply filters
        if 'min_market_cap' in criteria:
            df = df[df['Market_Cap_B'] >= criteria['min_market_cap']]
        
        if 'max_market_cap' in criteria:
            df = df[df['Market_Cap_B'] <= criteria['max_market_cap']]
        
        if 'min_pe' in criteria:
            df = df[df['PE_Ratio'].notna() & (df['PE_Ratio'] >= criteria['min_pe'])]
        
        if 'max_pe' in criteria:
            df = df[df['PE_Ratio'].notna() & (df['PE_Ratio'] <= criteria['max_pe'])]
        
        if 'min_dividend_yield' in criteria:
            df = df[df['Dividend_Yield'] >= criteria['min_dividend_yield']]
        
        if 'min_roe' in criteria:
            df = df[df['ROE'].notna() & (df['ROE'] >= criteria['min_roe'])]
        
        if 'max_debt_to_equity' in criteria:
            df = df[df['Debt_to_Equity'].notna() & 
                   (df['Debt_to_Equity'] <= criteria['max_debt_to_equity'])]
        
        if 'above_sma200' in criteria and criteria['above_sma200']:
            df = df[df['Price_vs_SMA200'].notna() & (df['Price_vs_SMA200'] > 0)]
        
        if 'below_sma200' in criteria and criteria['below_sma200']:
            df = df[df['Price_vs_SMA200'].notna() & (df['Price_vs_SMA200'] < 0)]
        
        if 'max_volatility' in criteria:
            df = df[df['Volatility'] <= criteria['max_volatility']]
        
        if 'sector' in criteria:
            df = df[df['Sector'] == criteria['sector']]
        
        if 'min_price' in criteria:
            df = df[df['Price'] >= criteria['min_price']]
        
        if 'max_price' in criteria:
            df = df[df['Price'] <= criteria['max_price']]
        
        return df.reset_index(drop=True)
    
    def display_results(self, df, columns=None):
        """Display screening results"""
        if len(df) == 0:
            print("\nNo stocks found matching criteria.")
            return
        
        if columns is None:
            columns = ['Ticker', 'Price', 'PE_Ratio', 'Dividend_Yield', 
                      'Market_Cap_B', 'ROE', 'Sector']
        
        # Filter to only existing columns
        columns = [col for col in columns if col in df.columns]
        
        print(f"\n{'='*100}")
        print(f"Found {len(df)} stocks matching criteria:")
        print('='*100)
        print(df[columns].to_string(index=False))
        print('='*100)
        
        return df
    
    def get_summary_stats(self, df):
        """Get summary statistics"""
        if len(df) == 0:
            return
        
        print("\n--- Summary Statistics ---")
        if 'PE_Ratio' in df.columns:
            print(f"Average P/E Ratio: {df['PE_Ratio'].mean():.2f}")
        if 'Dividend_Yield' in df.columns:
            print(f"Average Dividend Yield: {df['Dividend_Yield'].mean():.2f}%")
        if 'ROE' in df.columns:
            print(f"Average ROE: {df['ROE'].mean():.2f}%")
        if 'Market_Cap_B' in df.columns:
            print(f"Average Market Cap: ${df['Market_Cap_B'].mean():.1f}B")
        if 'Change_3M' in df.columns:
            print(f"Average 3M Change: {df['Change_3M'].mean():.2f}%")
        
        if 'Sector' in df.columns:
            print("\n--- Sector Distribution ---")
            print(df['Sector'].value_counts())


def main():
    """Main function with example usage"""
    
    # Initialize screener
    screener = LiveStockScreener()
    
    # Load live data
    screener.load_live_data()
    
    print("\n" + "="*100)
    print("LIVE STOCK SCREENER - EXAMPLE STRATEGIES")
    print("="*100)
    
    # Strategy 1: Value Dividend Stocks
    print("\n\n📊 STRATEGY 1: Value Dividend Stocks")
    print("Criteria: P/E < 25, Dividend Yield > 2%, ROE > 15%, Above 200-day MA")
    criteria_1 = {
        'max_pe': 25,
        'min_dividend_yield': 2.0,
        'min_roe': 15,
        'above_sma200': True
    }
    results_1 = screener.screen(criteria_1)
    screener.display_results(results_1)
    screener.get_summary_stats(results_1)
    
    # Strategy 2: Large Cap Growth
    print("\n\n📊 STRATEGY 2: Large Cap Growth Stocks")
    print("Criteria: Market Cap > $100B, Above 200-day MA, Volatility < 35%")
    criteria_2 = {
        'min_market_cap': 100,
        'above_sma200': True,
        'max_volatility': 35
    }
    results_2 = screener.screen(criteria_2)
    screener.display_results(results_2)
    screener.get_summary_stats(results_2)
    
    # Strategy 3: High Dividend Low Volatility
    print("\n\n📊 STRATEGY 3: High Dividend, Low Volatility")
    print("Criteria: Dividend Yield > 3%, Volatility < 25%, Above 200-day MA")
    criteria_3 = {
        'min_dividend_yield': 3.0,
        'max_volatility': 25,
        'above_sma200': True
    }
    results_3 = screener.screen(criteria_3)
    screener.display_results(results_3, 
                            columns=['Ticker', 'Price', 'Dividend_Yield', 
                                    'Volatility', 'PE_Ratio', 'Sector'])
    screener.get_summary_stats(results_3)
    
    # Save results
    print("\n\n💾 Saving results...")
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    results_1.to_csv(f'value_dividend_stocks_{timestamp}.csv', index=False)
    results_2.to_csv(f'large_cap_growth_{timestamp}.csv', index=False)
    results_3.to_csv(f'dividend_low_vol_{timestamp}.csv', index=False)
    screener.stocks_data.to_csv(f'all_stocks_data_{timestamp}.csv', index=False)
    print("✓ Results saved with timestamp!")
    
    print("\n" + "="*100)
    print("SCREENING COMPLETE!")
    print("="*100)


if __name__ == "__main__":
    main()
