"""
Stock Screener with Python
This version uses sample data for demonstration.
To use with real data, uncomment the yfinance sections.
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta

class StockScreener:
    def __init__(self):
        """Initialize the stock screener"""
        self.stocks_data = None
        
    def load_sample_data(self):
        """Load sample stock data for demonstration"""
        # Sample data representing realistic stock metrics
        data = {
            'Ticker': ['AAPL', 'MSFT', 'GOOGL', 'AMZN', 'META', 'TSLA', 'NVDA', 'JPM',
                      'V', 'WMT', 'JNJ', 'PG', 'MA', 'UNH', 'HD', 'BAC', 'XOM', 'CVX',
                      'KO', 'PEP', 'COST', 'NKE', 'DIS', 'INTC', 'IBM'],
            'Price': [178.50, 415.30, 142.80, 178.90, 512.45, 248.50, 875.30, 195.40,
                     283.20, 168.50, 156.80, 162.40, 478.90, 525.60, 385.70, 36.50, 112.30, 158.90,
                     61.20, 175.30, 785.40, 98.70, 102.50, 43.20, 182.40],
            'Market_Cap_B': [2800, 3100, 1800, 1850, 1300, 780, 2150, 580,
                            570, 465, 385, 395, 455, 520, 400, 285, 425, 310,
                            265, 245, 350, 155, 185, 185, 170],
            'PE_Ratio': [29.5, 35.8, 25.3, 68.5, 27.4, 75.2, 65.3, 12.8,
                        38.5, 28.7, 18.9, 25.4, 36.2, 22.5, 21.8, 11.2, 10.5, 9.8,
                        24.5, 26.8, 42.5, 32.1, 85.2, 45.3, 22.5],
            'Dividend_Yield': [0.45, 0.75, 0.0, 0.0, 0.0, 0.0, 0.03, 2.45,
                              0.75, 1.45, 2.85, 2.35, 0.58, 1.25, 2.15, 2.85, 3.25, 3.15,
                              2.95, 2.65, 0.52, 1.35, 0.85, 1.45, 3.85],
            'ROE': [147.5, 42.3, 28.5, 18.2, 32.5, 25.8, 98.5, 15.2,
                   42.8, 18.5, 28.9, 32.5, 145.2, 24.5, 125.8, 12.5, 18.5, 16.8,
                   41.2, 45.8, 28.5, 38.5, 12.5, 15.8, 28.5],
            'Debt_to_Equity': [1.85, 0.42, 0.08, 0.52, 0.0, 0.15, 0.28, 1.25,
                              0.48, 0.52, 0.45, 0.38, 0.42, 0.55, 0.98, 0.85, 0.22, 0.18,
                              0.75, 0.68, 0.45, 0.52, 0.48, 0.42, 0.38],
            'Beta': [1.28, 0.95, 1.08, 1.15, 1.22, 2.05, 1.68, 1.15,
                    0.95, 0.52, 0.62, 0.48, 1.05, 0.75, 1.05, 1.35, 0.95, 0.88,
                    0.58, 0.62, 0.85, 1.05, 1.15, 1.02, 0.95],
            'Price_vs_SMA50': [2.5, 5.8, -1.2, 3.5, 8.2, -5.5, 12.5, 1.2,
                              4.5, 2.8, 1.5, 0.8, 6.5, 3.2, 2.5, -2.5, 4.5, 3.8,
                              1.2, 2.5, 5.5, -3.2, -8.5, -12.5, 1.8],
            'Price_vs_SMA200': [15.5, 18.2, 8.5, 12.5, 25.8, -8.5, 35.5, 5.2,
                               12.5, 8.5, 5.2, 4.5, 15.8, 10.5, 8.5, -5.2, 12.5, 10.8,
                               6.5, 8.5, 18.5, -5.5, -15.2, -22.5, 5.8],
            'Change_1M': [5.2, 8.5, 2.5, 6.8, 12.5, -8.5, 15.2, 3.5,
                         7.5, 4.2, 2.5, 1.8, 9.5, 5.2, 4.5, -3.5, 6.5, 5.8,
                         2.8, 4.2, 8.5, -4.5, -12.5, -18.5, 3.2],
            'Change_3M': [12.5, 15.8, 8.5, 14.2, 28.5, -15.2, 35.5, 8.5,
                         15.2, 10.5, 6.5, 5.2, 18.5, 12.5, 10.5, -8.5, 15.2, 12.8,
                         7.5, 10.2, 20.5, -8.5, -25.5, -35.2, 8.5],
            'Volatility': [25.5, 22.8, 28.5, 32.5, 35.8, 58.5, 48.5, 28.5,
                          24.5, 18.5, 15.8, 16.2, 25.8, 20.5, 22.5, 32.5, 25.8, 24.5,
                          16.5, 17.2, 24.5, 28.5, 38.5, 42.5, 25.8],
            'Sector': ['Technology', 'Technology', 'Technology', 'Consumer Cyclical', 
                      'Technology', 'Consumer Cyclical', 'Technology', 'Financial',
                      'Financial', 'Consumer Defensive', 'Healthcare', 'Consumer Defensive',
                      'Financial', 'Healthcare', 'Consumer Cyclical', 'Financial',
                      'Energy', 'Energy', 'Consumer Defensive', 'Consumer Defensive',
                      'Consumer Defensive', 'Consumer Cyclical', 'Communication',
                      'Technology', 'Technology']
        }
        
        self.stocks_data = pd.DataFrame(data)
        return self.stocks_data
    
    def screen(self, criteria):
        """
        Screen stocks based on criteria
        
        Parameters:
        -----------
        criteria : dict
            Dictionary of screening criteria. Examples:
            {
                'min_market_cap': 100,  # billions
                'max_market_cap': 1000,
                'min_pe': 10,
                'max_pe': 30,
                'min_dividend_yield': 2.0,
                'min_roe': 15,
                'max_debt_to_equity': 1.0,
                'above_sma200': True,
                'max_volatility': 30,
                'sector': 'Technology'
            }
        """
        if self.stocks_data is None:
            self.load_sample_data()
        
        df = self.stocks_data.copy()
        
        # Apply filters
        if 'min_market_cap' in criteria:
            df = df[df['Market_Cap_B'] >= criteria['min_market_cap']]
        
        if 'max_market_cap' in criteria:
            df = df[df['Market_Cap_B'] <= criteria['max_market_cap']]
        
        if 'min_pe' in criteria:
            df = df[df['PE_Ratio'] >= criteria['min_pe']]
        
        if 'max_pe' in criteria:
            df = df[df['PE_Ratio'] <= criteria['max_pe']]
        
        if 'min_dividend_yield' in criteria:
            df = df[df['Dividend_Yield'] >= criteria['min_dividend_yield']]
        
        if 'min_roe' in criteria:
            df = df[df['ROE'] >= criteria['min_roe']]
        
        if 'max_debt_to_equity' in criteria:
            df = df[df['Debt_to_Equity'] <= criteria['max_debt_to_equity']]
        
        if 'above_sma200' in criteria and criteria['above_sma200']:
            df = df[df['Price_vs_SMA200'] > 0]
        
        if 'below_sma200' in criteria and criteria['below_sma200']:
            df = df[df['Price_vs_SMA200'] < 0]
        
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
        """Display screening results in a formatted way"""
        if columns is None:
            columns = ['Ticker', 'Price', 'PE_Ratio', 'Dividend_Yield', 
                      'Market_Cap_B', 'ROE', 'Sector']
        
        print(f"\nFound {len(df)} stocks matching criteria:")
        print("=" * 100)
        print(df[columns].to_string(index=False))
        print("=" * 100)
        
        return df
    
    def get_summary_stats(self, df):
        """Get summary statistics for screened stocks"""
        if len(df) == 0:
            print("No stocks found matching criteria")
            return
        
        print("\n--- Summary Statistics ---")
        print(f"Average P/E Ratio: {df['PE_Ratio'].mean():.2f}")
        print(f"Average Dividend Yield: {df['Dividend_Yield'].mean():.2f}%")
        print(f"Average ROE: {df['ROE'].mean():.2f}%")
        print(f"Average Market Cap: ${df['Market_Cap_B'].mean():.1f}B")
        print(f"Average 3M Change: {df['Change_3M'].mean():.2f}%")
        
        print("\n--- Sector Distribution ---")
        print(df['Sector'].value_counts())


def main():
    """Main function with example screens"""
    screener = StockScreener()
    screener.load_sample_data()
    
    print("\n" + "="*100)
    print("STOCK SCREENER - EXAMPLE STRATEGIES")
    print("="*100)
    
    # Strategy 1: Value Dividend Stocks
    print("\n\n📊 STRATEGY 1: Value Dividend Stocks")
    print("Looking for: Low P/E, High Dividend, Strong ROE")
    criteria_1 = {
        'max_pe': 25,
        'min_dividend_yield': 2.0,
        'min_roe': 20,
        'above_sma200': True
    }
    results_1 = screener.screen(criteria_1)
    screener.display_results(results_1)
    screener.get_summary_stats(results_1)
    
    # Strategy 2: Growth Momentum Stocks
    print("\n\n📊 STRATEGY 2: Growth Momentum Stocks")
    print("Looking for: Large cap tech with momentum")
    criteria_2 = {
        'min_market_cap': 500,
        'sector': 'Technology',
        'above_sma200': True,
        'max_volatility': 35
    }
    results_2 = screener.screen(criteria_2)
    screener.display_results(results_2)
    screener.get_summary_stats(results_2)
    
    # Strategy 3: Low Volatility Income Stocks
    print("\n\n📊 STRATEGY 3: Low Volatility Income Stocks")
    print("Looking for: Stable stocks with good dividends")
    criteria_3 = {
        'min_dividend_yield': 2.5,
        'max_volatility': 25,
        'max_debt_to_equity': 0.8,
        'above_sma200': True
    }
    results_3 = screener.screen(criteria_3)
    screener.display_results(results_3, 
                            columns=['Ticker', 'Price', 'Dividend_Yield', 
                                    'Volatility', 'Debt_to_Equity', 'Sector'])
    screener.get_summary_stats(results_3)
    
    # Save results
    print("\n\n💾 Saving results to CSV files...")
    results_1.to_csv('/home/claude/value_dividend_stocks.csv', index=False)
    results_2.to_csv('/home/claude/growth_momentum_stocks.csv', index=False)
    results_3.to_csv('/home/claude/low_volatility_income_stocks.csv', index=False)
    print("✓ Results saved successfully!")
    
    # Custom screen example
    print("\n\n📊 CUSTOM SCREEN EXAMPLE")
    print("You can create your own criteria:")
    print("""
    custom_criteria = {
        'min_market_cap': 100,
        'max_pe': 30,
        'min_dividend_yield': 1.0,
        'min_roe': 25,
        'max_volatility': 30,
        'above_sma200': True
    }
    custom_results = screener.screen(custom_criteria)
    """)


if __name__ == "__main__":
    main()
