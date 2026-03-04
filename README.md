# Stock Ticker Tracker

A Python-based stock ticker tracking application that fetches data from Yahoo Finance, calculates technical indicators, and exports to SQLite and Excel. Includes visualization and scheduling for automated updates.

## Features

- Fetch historical and real-time stock data
- Calculate technical indicators (RSI, MACD, Bollinger Bands, etc.)
- Export data to SQLite database and Excel
- Generate buy/sell signals
- Interactive visualizations with Plotly and Bokeh
- Scheduled daily updates

## Installation

1. Clone the repository:
   ```bash
   git clone https://github.com/yourusername/stock-ticker-tracker.git
   cd stock-ticker-tracker
   ```

2. Install dependencies (use python3 if pip is not directly available):
   ```bash
   python3 -m pip install -r requirements.txt
   ```

## Usage

### Basic Analysis

### Web App
Run the Flask-based web app for interactive analysis:

```bash
python src/app.py
```

Access at http://localhost:5000. Example endpoints:
- `/visualize/<symbol>`: View interactive plot for a stock symbol (data loaded from DB if available).
