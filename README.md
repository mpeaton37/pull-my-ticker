# Stock Ticker Tracker (HEDGE2)

A Python-based stock ticker tracking application that fetches data from Yahoo Finance, calculates technical indicators, generates signals, stores results in SQLite, updates Excel, and provides visualizations. Includes a model-agnostic predictor for price/variance (with C++ filter support).

## Features

- Fetch historical and real-time stock data
- Calculate technical indicators (RSI, MACD, Bollinger Bands, ATR, etc.)
- Generate buy/sell signals
- Export to SQLite database and Excel
- Interactive visualizations (Plotly + Bokeh)
- Scheduled daily updates via `pull_latest.py`
- Web interface via Flask (`src/app.py`)
- Model-agnostic predictor (`src/predictor.py`) using DB data (initially wraps C++ Kalman filter)

## Installation

1. Clone the repository:
   ```bash
   git clone https://github.com/mpeaton37/pull-my-ticker.git
   cd pull-my-ticker
   ```

2. Create/activate a conda environment (recommended):
   ```bash
   conda create -n HEDGE python=3.12
   conda activate HEDGE
   ```

3. Install dependencies (core + test extras):
   ```bash
   pip install -e '.[test]'
   ```
   (This uses `pyproject.toml` optional dependencies and installs the package in editable mode so `src.*` imports work.)

   Alternatively, if you prefer the requirements file:
   ```bash
   pip install -r requirements.txt
   pip install -e .
   ```

4. (Optional) For C++ common filter support in the predictor, compile your `common_filter.so` and place it in the project root or update the `lib_path` in `src/predictor.py`.

## Usage

### CLI / Notebook Analysis
```bash
python -c "from src.stock_analyzer import StockAnalyzer; analyzer = StockAnalyzer(['AAPL'], '2020-01-01', '2023-01-01'); analyzer.fetch_market_data(); print(analyzer.generate_signals())"
```

### Web App
```bash
python src/app.py
```
Access at http://localhost:5000/visualize/AAPL (serves PNG plots).

### Scheduler
```bash
python src/pull_latest.py
```

### Predictor Example
```python
from src.stock_analyzer import StockAnalyzer
analyzer = StockAnalyzer(['AAPL'], '2020-01-01', '2023-01-01')
analyzer.fetch_market_data()
price, variance = analyzer.predict_price_and_variance('AAPL')
print(f"Predicted price: {price}, Variance: {variance}")
```

### Running Tests
```bash
pytest
# With coverage:
pytest --cov=src --cov-report=html
```

## Project Structure
- `src/`: Core modules (`stock_analyzer.py`, `sheet_worker.py`, `predictor.py`, `app.py`, `pull_latest.py`)
- `tests/`: Unit tests
- `stocks.db`: SQLite output
- `mbook3.xlsx`: Excel output

## Troubleshooting
- **ModuleNotFoundError**: Run `pip install -e '.[test]'` in your conda env.
- **Excel/DB permission issues**: Close any open files and ensure write permissions.
- **C++ filter**: Verify `common_filter.so` exists and is loadable via ctypes.

See `SDD.md` for full design details.

This project is ready for GitHub (clean code, passing tests/CI, no secrets, MIT license).
