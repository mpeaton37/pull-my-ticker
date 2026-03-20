# Software Design Document (SDD) for HEDGE2 Stock Analyzer Web App

## 1. Introduction

### 1.1 Purpose
This document outlines the design for HEDGE2, a web app for stock portfolio analysis. It fetches data from Yahoo Finance (yfinance), computes technical indicators (RSI, MACD, Bollinger Bands), generates signals, stores in SQLite ('stocks.db'), visualizes with Plotly, and integrates with Excel via SheetWorker.

Strawman based on current codebase: StockAnalyzer (core logic), SheetWorker (Excel), pull_latest.py (scheduling), app.py (Flask web), tests.

### 1.2 Scope
**Core**:
- Fetch historical/latest data for symbols (with blacklist, force_refresh).
- Indicators/signals (generate_signals).
- DB persistence (export_to_sqlite/from_sqlite/read_from_sqlite).
- Excel export/update (export_to_excel, SheetWorker.update_excel_from_db).
- Viz (visualize with Plotly candlestick/RSI).
- Web routes (/, /visualize/<symbol> PNG).
- Scheduling (pull_latest.job).
- New: Model-agnostic price/variance prediction using DB data and C++ Kalman filter.
- Symbol validation precheck to skip delisted/invalid tickers from spreadsheet.

**Non-Functional**:
- SQLite initially; PostgreSQL later.
- Personal use (hardcoded symbols; add auth).
- Up to ~100 symbols.

Out-of-scope: ML predictions, multi-user, mobile.

### 1.3 References
- Code: src/stock_analyzer.py, src/sheet_worker.py, src/pull_latest.py, src/app.py, src/predictor.py.
- Config: pyproject.toml, requirements.txt.
- CI: .github/workflows/ci.yml.
- Libs: yfinance, pandas, ta, plotly, openpyxl, sqlite3, flask.
- Tests: tests/test_stock_analyzer.py, tests/test_sheet_worker.py.

## 2. System Overview

Backend-heavy web app with DB/Excel integration.

### 2.1 Architecture
```
User (Web/CLI) → app.py (Flask) / pull_latest.py → StockAnalyzer (fetch/add indicators/signals/export/predict) → SQLite ('stocks.db') / Excel ('mbook3.xlsx')
↑ Viz: Plotly PNG/HTML in /visualize/<symbol>
↑ Predictor: model-agnostic wrapper around C++ Kalman filter
```
- **Frontend**: Basic Flask routes; expand to React.
- **Backend**: StockAnalyzer core; SheetWorker for Excel.
- **DB**: Per-symbol tables (historical_data_{symbol}), summary_data, fundamental_data, metadata.
- **Scheduling**: schedule lib in pull_latest (daily 11:10).
- **Predictor**: Abstract interface for filters/models; starts with KalmanFilter calling C++.

### 2.2 Data Flow
1. Symbols from Excel (SheetWorker.read_symbols) or hardcoded.
2. Validate symbols (skip delisted/invalid via yfinance fast_info).
3. Fetch (StockAnalyzer.fetch_market_data; cache via DB if !force_refresh).
4. Process: add_advanced_indicators, generate_signals.
5. Store: export_to_sqlite (summary/historical/fundamental/views).
6. Viz/Export: visualize (Plotly), export_to_excel, SheetWorker.update_excel_from_db (via read_from_sqlite).
7. Predict: Load from DB → KalmanFilter (C++) → price + variance.

## 3. Data Design

### 3.1 Database Schema
From export_to_sqlite:
- **summary_data**: symbol, last_update, last_close, rsi, macd, pe_ratio, etc.
- **historical_data_{symbol}** (e.g., historical_data_aapl): Date (PK), Open/High/Low/Close/Volume, RSI/MACD/BB_upper/etc., symbol.
- **fundamental_data**: symbol, PE_Ratio, Dividend_Yield, Market_Cap, targets (mean/high/low), last_update.
- **metadata**: key-value (schema_version, last_update).
- **Views**: latest_data (JOIN summary + fundamental).

Example:
```
historical_data_aapl: Date | Open | ... | RSI | Signal
summary_data: symbol | last_close | rsi | ...
```

SQLite for dev; PostgreSQL for prod (indexing, concurrency).

### 3.2 Data Sources
- yf.Ticker.history/info/fast_info (historical/fundamental/latest).
- Cache: DB check last_update >=24h.
- Predictor uses historical data from DB for price/variance.
- Pre-validation uses yf.Ticker.fast_info to filter bad symbols.

## 4. Component Design

### 4.1 StockAnalyzer
src/stock_analyzer.py:
- `__init__(symbols, start_date, end_date)`: data dict, fundamental_data, blacklist=['ZTS'].
- `_validate_symbols()`: quick yfinance precheck to skip delisted/invalid symbols.
- `fetch_market_data(force_refresh=True, latest_only=False)`: yfinance + indicators (RSI/MACD/BB).
- `export_to_sqlite(db_path='stocks.db')`: Multi-table export + views/metadata.
- `from_sqlite(db_path)`: Load all data/symbols.
- `read_from_sqlite(db_path, symbol=None)`: Summary or historical.
- `add_advanced_indicators()`: ATR/SMA/EMA/Sharpe/Beta.
- `generate_signals()`: RSI/MACD/BB rules → DF.
- `visualize(symbol, 'candlestick', interactive)`: Plotly candlestick + RSI.
- New: `predict_price_and_variance(symbol)`: loads DB data and delegates to Predictor.
- Others: export_to_excel, load_for_notebook.

### 4.2 SheetWorker
src/sheet_worker.py:
- `__init__(filename)`: Load workbook.
- `read_symbols()`: Col A from row 2.
- `update_excel_from_db(analyst)`: analyst.read_from_sqlite → 'Data' sheet.

### 4.3 pull_latest.py
- `job()`: SheetWorker → symbols → StockAnalyzer → fetch/export/update_excel.
- `main()`: schedule.every().day.at("11:10").

### 4.4 app.py (Flask)
- Hardcoded analyzer (AAPL/GOOGL).
- `/`: Welcome.
- `/visualize/<symbol>`: fetch → visualize → PNG bytes.

### 4.5 Predictor
New: src/predictor.py
- Abstract `Predictor` for model-agnostic design.
- `KalmanFilter` implementation (initially wraps C++ Kalman filter model via ctypes).
- Uses pandas DataFrame from DB (historical prices) to compute/predict price and variance.
- Easily extensible to other models (e.g., ML, Kalman filter).

### 4.6 Visualization
Plotly candlestick + overlays (RSI); BytesIO PNG serve. Bokeh stub.

## 5. User Interface Design

### 5.1 Current Web UI
- `/`: Index msg.
- `/visualize/<symbol>`: PNG chart.

**Planned**:
- Dashboard: Symbols/signals table.
- Add symbol, refresh btns.
- Embed Plotly HTML (vs PNG).
- Future: /predict/<symbol> endpoint returning price+variance.

## 6. Deployment & Ops

### 6.1 Environment
- Dev: `python -m src.app` or `python src/app.py` (debug=True), SQLite.
- Prod: Docker + PostgreSQL + Gunicorn/FastAPI async.
- Build: pyproject.toml (setuptools, requires-python >=3.8).
- C++: Compile common filter to .so and place in PATH or package with pyproject.

### 6.2 CI/CD
.github/workflows/ci.yml: pytest with coverage, flake8 lint on push/PR.

### 6.3 Testing
- test_stock_analyzer.py: init/fetch/generate_signals (mocks yf).
- test_sheet_worker.py: read_symbols/update_excel_from_db (mocks).
- Config: pyproject.toml [tool.pytest.ini_options], requirements.txt test deps.
- New tests for predictor (mock C++ calls).

## 7. Risks & Assumptions
- **API**: yfinance rate limits/blacklists → DB cache, blacklist.
- **Excel**: File locks → try/except, CSV fallback.
- **DB**: SQLite single-writer → PostgreSQL.
- **C++ Integration**: Assumes compiled shared lib; add pybind11 or ctypes error handling.
- **Viz**: Plotly PNG size → HTML/JS embed.
- **Invalid symbols**: Pre-validation helps but may still produce some NULLs for edge cases.

## 8. Future Enhancements (Prioritized)
1. Dynamic symbols (DB/config vs hardcoded).
2. FastAPI migration (async fetch).
3. Auth (Flask-Login).
4. Real-time (WebSockets, latest_only).
5. More indicators/ML (Prophet).
6. Alerts (email on signals).
7. Backtesting.
8. Advanced predictors (replace KalmanFilter with ML/Kalman while keeping agnostic interface).
9. Expose prediction via web endpoint and add variance to visualizations.

Iterative; update post-milestones.
