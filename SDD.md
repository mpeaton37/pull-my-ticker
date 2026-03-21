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
↑ Viz