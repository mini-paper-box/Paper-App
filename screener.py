import yfinance as yf
import pandas as pd
from datetime import datetime, timedelta
import numpy as np

class StockScreener:
    def __init__(self):
        """Initialize the stock screener with a list of tickers"""
        # Sample list of S&P 500 tickers (you can expand this)
        self.tickers = [
            'AAPL', 'MSFT', 'GOOGL', 'AMZN', 'META', 'TSLA', 'NVDA', 'JPM',
            'V', 'WMT', 'JNJ', 'PG', 'MA', 'UNH', 'HD', 'BAC', 'XOM', 'CVX',
            'ABBV', 'PFE', 'KO', 'AVGO', 'COST', 'TMO', 'MRK', 'PEP', 'CSCO',
            'ACN', 'ADBE', 'NKE', 'DHR', 'TXN', 'ABT', 'NEE', 'LIN', 'CRM',
            'ORCL', 'WFC', 'BMY', 'AMD', 'QCOM', 'UPS', 'RTX', 'INTC', 'IBM'
        ]
        
    def get_stock_data(self, ticker):
        """Fetch stock data and calculate key metrics"""
        try:
            stock = yf.Ticker(ticker)
            info = stock.info
            hist = stock.history(period="1y")
            
            if hist.empty or len(hist) < 50:
                return None
            
            # Calculate metrics
            current_price = hist['Close'].iloc[-1]
            sma_50 = hist['Close'].tail(50).mean()
            sma_200 = hist['Close'].tail(200).mean() if len(hist) >= 200 else None
            
            # Price changes
            price_change_1d = ((current_price - hist['Close'].iloc[-2]) / hist['Close'].iloc[-2] * 100) if len(hist) > 1 else 0
            price_change_1m = ((current_price - hist['Close'].iloc[-22]) / hist['Close'].iloc[-22] * 100) if len(hist) > 22 else 0
            price_change_3m = ((current_price - hist['Close'].iloc[-66]) / hist['Close'].iloc[-66] * 100) if len(hist) > 66 else 0
            
            # Volume
            avg_volume = hist['Volume'].tail(20).mean()
            current_volume = hist['Volume'].iloc[-1]
            
            # Volatility (standard deviation of returns)
            returns = hist['Close'].pct_change().dropna()
            volatility = returns.std() * np.sqrt(252) * 100  # Annualized
            
            data = {
                'Ticker': ticker,
                'Price': round(current_price, 2),
                'Market Cap': info.get('marketCap', 0),
                'P/E Ratio': info.get('trailingPE', None),
                'Forward P/E': info.get('forwardPE', None),
                'PEG Ratio': info.get('pegRatio', None),
                'Dividend Yield': info.get('dividendYield', 0) * 100 if info.get('dividendYield') else 0,
                'Beta': info.get('beta', None),
                '52W High': info.get('fiftyTwoWeekHigh', None),
                '52W Low': info.get('fiftyTwoWeekLow', None),
                'SMA 50': round(sma_50, 2) if sma_50 else None,
                'SMA 200': round(sma_200, 2) if sma_200 else None,
                'Price vs SMA50': round((current_price - sma_50) / sma_50 * 100, 2) if sma_50 else None,
                'Price vs SMA200': round((current_price - sma_200) / sma_200 * 100, 2) if sma_200 else None,
                '1D Change %': round(price_change_1d, 2),
                '1M Change %': round(price_change_1m, 2),
                '3M Change %': round(price_change_3m, 2),
                'Avg Volume': int(avg_volume),
                'Current Volume': int(current_volume),
                'Volatility %': round(volatility, 2),
                'ROE': info.get('returnOnEquity', None),
                'Profit Margin': info.get('profitMargins', None),
                'Debt/Equity': info.get('debtToEquity', None),
                'Sector': info.get('sector', 'N/A'),
                'Industry': info.get('industry', 'N/A')
            }
            
            return data
            
        except Exception as e:
            print(f"Error fetching data for {ticker}: {str(e)}")
            return None
    
    def screen_stocks(self, criteria):
        """
        Screen stocks based on given criteria
        
        Example criteria:
        {
            'min_market_cap': 10e9,  # $10 billion
            'max_pe': 30,
            'min_dividend_yield': 2,
            'above_sma200': True,
            'max_volatility': 40
        }
        """
        results = []
        
        print(f"Screening {len(self.tickers)} stocks...")
        
        for i, ticker in enumerate(self.tickers, 1):
            print(f"Processing {i}/{len(self.tickers)}: {ticker}", end='\r')
            data = self.get_stock_data(ticker)
            
            if data is None:
                continue
            
            # Apply filters
            passes = True
            
            if 'min_market_cap' in criteria:
                if not data['Market Cap'] or data['Market Cap'] < criteria['min_market_cap']:
                    passes = False
            
            if 'max_market_cap' in criteria:
                if not data['Market Cap'] or data['Market Cap'] > criteria['max_market_cap']:
                    passes = False
            
            if 'max_pe' in criteria:
                if not data['P/E Ratio'] or data['P/E Ratio'] > criteria['max_pe']:
                    passes = False
            
            if 'min_pe' in criteria:
                if not data['P/E Ratio'] or data['P/E Ratio'] < criteria['min_pe']:
                    passes = False
            
            if 'min_dividend_yield' in criteria:
                if data['Dividend Yield'] < criteria['min_dividend_yield']:
                    passes = False
            
            if 'above_sma200' in criteria and criteria['above_sma200']:
                if not data['Price vs SMA200'] or data['Price vs SMA200'] < 0:
                    passes = False
            
            if 'below_sma200' in criteria and criteria['below_sma200']:
                if not data['Price vs SMA200'] or data['Price vs SMA200'] > 0:
                    passes = False
            
            if 'max_volatility' in criteria:
                if not data['Volatility %'] or data['Volatility %'] > criteria['max_volatility']:
                    passes = False
            
            if 'min_roe' in criteria:
                if not data['ROE'] or data['ROE'] < criteria['min_roe']:
                    passes = False
            
            if 'sector' in criteria:
                if data['Sector'] != criteria['sector']:
                    passes = False
            
            if passes:
                results.append(data)
        
        print("\nScreening complete!")
        return pd.DataFrame(results)


# Example usage
if __name__ == "__main__":
    screener = StockScreener()
    
    # Example 1: Value stocks with dividends
    print("\n=== Example 1: Value Dividend Stocks ===")
    criteria_1 = {
        'max_pe': 20,
        'min_dividend_yield': 2,
        'min_market_cap': 10e9,
        'above_sma200': True
    }
    results_1 = screener.screen_stocks(criteria_1)
    print(f"\nFound {len(results_1)} stocks matching criteria:")
    print(results_1[['Ticker', 'Price', 'P/E Ratio', 'Dividend Yield', 'Market Cap', 'Sector']].to_string(index=False))
    
    # Example 2: Growth stocks with momentum
    print("\n\n=== Example 2: Growth Momentum Stocks ===")
    criteria_2 = {
        'min_market_cap': 5e9,
        'above_sma200': True,
        'max_volatility': 50
    }
    results_2 = screener.screen_stocks(criteria_2)
    print(f"\nFound {len(results_2)} stocks matching criteria:")
    print(results_2[['Ticker', 'Price', '3M Change %', 'Price vs SMA200', 'Volatility %', 'Sector']].to_string(index=False))
    
    # Save to CSV
    results_1.to_csv('value_dividend_stocks.csv', index=False)
    print("\n\nResults saved to 'value_dividend_stocks.csv'")