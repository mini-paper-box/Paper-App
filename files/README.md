# Stock Screener with Python

A flexible and powerful stock screening tool to filter stocks based on fundamental and technical criteria.

## 📁 Files Included

1. **stock_screener.py** - Demo version with sample data (runs immediately)
2. **stock_screener_live.py** - Live version using yfinance (requires internet)
3. **README.md** - This file

## 🚀 Quick Start

### Option 1: Demo Version (No Setup Required)
```bash
python stock_screener.py
```
This runs immediately with sample data to demonstrate functionality.

### Option 2: Live Version (Real Market Data)

1. **Install required packages:**
```bash
pip install yfinance pandas numpy
```

2. **Run the screener:**
```bash
python stock_screener_live.py
```

## 📊 Features

### Screening Criteria Supported

**Fundamental Metrics:**
- Market Capitalization (min/max)
- P/E Ratio (min/max)
- Forward P/E
- PEG Ratio
- Dividend Yield (min)
- Return on Equity (ROE)
- Profit Margin
- Debt to Equity Ratio (max)
- Current Ratio

**Technical Indicators:**
- Price vs 50-day Moving Average
- Price vs 200-day Moving Average
- 1-month / 3-month Price Change
- Volatility (max)
- Beta

**Other Filters:**
- Sector
- Industry
- Price Range (min/max)
- Above/Below Moving Averages

## 💡 Usage Examples

### Example 1: Value Dividend Stocks
```python
from stock_screener import StockScreener

screener = StockScreener()
screener.load_sample_data()

criteria = {
    'max_pe': 25,
    'min_dividend_yield': 2.0,
    'min_roe': 20,
    'above_sma200': True
}

results = screener.screen(criteria)
screener.display_results(results)
```

### Example 2: Growth Momentum Stocks
```python
criteria = {
    'min_market_cap': 100,  # $100B+
    'sector': 'Technology',
    'above_sma200': True,
    'max_volatility': 35
}

results = screener.screen(criteria)
screener.display_results(results)
```

### Example 3: Low Volatility Income
```python
criteria = {
    'min_dividend_yield': 3.0,
    'max_volatility': 25,
    'max_debt_to_equity': 1.0,
    'above_sma200': True
}

results = screener.screen(criteria)
```

## 🎯 Pre-Built Screening Strategies

Both versions come with 3 example strategies:

1. **Value Dividend Stocks** - Low P/E, high dividends, strong fundamentals
2. **Growth Momentum Stocks** - Large caps with positive momentum
3. **Low Volatility Income** - Stable dividend payers

## 📈 Customization

### Add Your Own Tickers
```python
# For live version
my_tickers = ['AAPL', 'MSFT', 'GOOGL', 'AMZN', 'TSLA']
screener = LiveStockScreener(tickers=my_tickers)
screener.load_live_data()
```

### Create Custom Screens
```python
# Mix and match any criteria
custom_criteria = {
    'min_market_cap': 50,
    'max_pe': 30,
    'min_dividend_yield': 1.5,
    'min_roe': 25,
    'max_volatility': 30,
    'above_sma200': True,
    'sector': 'Healthcare'
}

results = screener.screen(custom_criteria)
```

### Display Custom Columns
```python
columns = ['Ticker', 'Price', 'PE_Ratio', 'Dividend_Yield', 
           'Change_3M', 'Volatility', 'Sector']
screener.display_results(results, columns=columns)
```

## 📁 Output

Results are automatically saved to CSV files:
- `value_dividend_stocks.csv`
- `growth_momentum_stocks.csv`
- `low_volatility_income_stocks.csv`
- `all_stocks_data_TIMESTAMP.csv` (live version)

## 📋 Available Criteria Parameters

```python
criteria = {
    # Market Cap (in billions)
    'min_market_cap': float,
    'max_market_cap': float,
    
    # Valuation
    'min_pe': float,
    'max_pe': float,
    'max_peg': float,
    
    # Income
    'min_dividend_yield': float,  # percentage
    
    # Profitability
    'min_roe': float,  # percentage
    'min_profit_margin': float,
    
    # Balance Sheet
    'max_debt_to_equity': float,
    'min_current_ratio': float,
    
    # Technical
    'above_sma200': bool,
    'below_sma200': bool,
    'above_sma50': bool,
    'max_volatility': float,  # percentage
    
    # Price
    'min_price': float,
    'max_price': float,
    
    # Classification
    'sector': str,
    'industry': str
}
```

## 🔧 Troubleshooting

### Rate Limiting (Live Version)
If you get rate limit errors, increase the sleep time:
```python
time.sleep(0.5)  # In fetch_stock_data method
```

### Missing Data
Some stocks may have missing fundamental data. The screener automatically handles this by filtering out null values for each criterion.

### Network Issues
The live version requires internet access. If you're offline, use the demo version with sample data.

## 📊 Example Output

```
Found 4 stocks matching criteria:
====================================================================================================
Ticker  Price  PE_Ratio  Dividend_Yield  Market_Cap_B   ROE             Sector
   JNJ  156.8      18.9            2.85           385  28.9         Healthcare
    HD  385.7      21.8            2.15           400 125.8  Consumer Cyclical
    KO   61.2      24.5            2.95           265  41.2 Consumer Defensive
   IBM  182.4      22.5            3.85           170  28.5         Technology
====================================================================================================

--- Summary Statistics ---
Average P/E Ratio: 21.93
Average Dividend Yield: 2.95%
Average ROE: 56.10%
Average Market Cap: $305.0B
```

## 🚀 Advanced Usage

### Screen and Sort
```python
results = screener.screen(criteria)
results_sorted = results.sort_values('Dividend_Yield', ascending=False)
print(results_sorted.head(10))
```

### Export to Excel
```python
results.to_excel('screened_stocks.xlsx', index=False)
```

### Filter by Multiple Sectors
```python
tech_healthcare = screener.stocks_data[
    screener.stocks_data['Sector'].isin(['Technology', 'Healthcare'])
]
```

## 📝 Notes

- **Data Delay**: Live data may be delayed 15-20 minutes
- **Market Hours**: Best to run during or after market hours
- **Data Quality**: Some stocks may have incomplete fundamental data
- **Performance**: Screening 50+ stocks takes 2-3 minutes with live data

## 🤝 Contributing

Feel free to extend this screener with:
- Additional technical indicators
- More fundamental ratios
- Backtesting functionality
- Visualization features
- Email alerts for matching stocks

## ⚠️ Disclaimer

This tool is for educational purposes only. Always do your own research before making investment decisions. Past performance does not guarantee future results.
