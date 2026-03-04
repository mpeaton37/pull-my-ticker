=======
# Software Design Document (SDD) for HEDGE2 Stock Analyzer Web App

## 1. Introduction

### 1.1 Purpose
This document provides a high-level design for the HEDGE2 application, a web-based
tool for managing and analyzing a personal stock portfolio. The app pulls stock
ticker data from sources like Yahoo Finance, performs calculations for metrics and
analytics, generates visualizations, and supports decision-making features. It
includes data storage in a database (initially SQLite) and integration with Excel
for manual interactions.

This is a strawman SDD based on the existing codebase, including components like
StockAnalyzer for data fetching and analysis, SheetWorker for Excel integration, and
scripts for data pulling. It outlines the current structure and proposed
enhancements to evolve into a professional web app.

### 1.2 Scope
- **Core Features**:
  - Fetch historical and real-time stock data for user-defined symbols.
  - Calculate technical indicators (e.g., moving averages, RSI) and generate
buy/sell signals.
  - Visualize data through plots (e.g., candlestick charts, interactive graphs).
  - Store data in a database for persistence and querying.
  - Export/update data to Excel spreadsheets.
  - Schedule automatic data pulls (e.g., daily) and support on-demand refreshes.
- **Non-Functional Requirements**:
  - Web-based UI for accessibility.
  - Initial database: SQLite for simplicity; migrate to a more robust option (e.g.,
PostgreSQL) for production.
  - Security: Basic authentication for personal use; expand for multi-user if
needed.
  - Performance: Handle data for up to 100 symbols efficiently.
  - Extensibility: Modular design to add new analytics or data sources.

Out of scope initially: Advanced ML-based predictions, multi-user support, mobile
app.

### 1.3 References
- Existing codebase: stock_analyzer.py, sheet_worker.py, pull_latest.py.
- Libraries: yfinance, pandas, plotly, openpyxl, sqlite3.
- Tools: Flask or FastAPI for web framework, Celery or APScheduler for scheduling.

## 2. System Overview

The system is a web application with backend services for data management and a
frontend for user interaction. It integrates external APIs (e.g., Yahoo Finance) and
supports file-based exports (Excel).

### 2.1 High-Level Architecture
- **Frontend**: Web interface (HTML/JS or React) for viewing portfolios, triggering
data pulls, and displaying plots.
- **Backend**: Python-based server handling API requests, data fetching, analysis,
and database interactions.
- **Database**: SQLite file (e.g., stock_analysis.db) storing stock data tables per
symbol.
- **Scheduling**: Background tasks for periodic data updates.
- **Integration**: Excel file updates via SheetWorker.

Components interact as follows:
- User requests data via web UI → Backend fetches/analyzes → Stores in DB →
Generates visuals/exports.

### 2.2 Data Flow
1. User adds symbols to portfolio.
2. Scheduled/on-demand fetch: Pull data using yfinance.
3. Process: Calculate indicators and signals.
4. Store: Insert into SQLite.

5. Visualize/Export: Generate plots or update Excel.

## 3. Data Design                                                                 ## 3. Data Design
                                                                                  ### 3.1 Database Schema                                                     3. Process: Calculate indicators and signals.
4. Store: Insert into SQLite.                                                  5. Visualize/Export: Generate plots or update Excel.
## 3. Data Design
### 3.1 Database Schema
## 3. Data Design
### 3.1 Database Schema                                                       Initial SQLite schema:
  - Signals: Buy/Sell (string or boolean)
- Metadata table: Symbols list, last_updated timestamps.

Later migration to PostgreSQL for better concurrency and querying.

### 3.2 Data Sources
- Primary: Yahoo Finance API via yfinance.
- Secondary: Potential for Alpha Vantage or others.

## 4. Component Design

### 4.1 StockAnalyzer
- Existing class in stock_analyzer.py.
- Responsibilities: Fetch data, add indicators, generate signals, export to DB/Excel,
visualize.
- Enhancements: Add support for real-time data, more indicators (e.g., MACD,
Bollinger Bands).

### 4.2 SheetWorker
- Existing class in sheet_worker.py.
- Responsibilities: Read symbols from Excel, update sheets with latest prices from
DB.
- Enhancements: Handle multiple sheets, error handling for file locks.

### 4.3 Pull Latest Script
- Existing in pull_latest.py.
- Responsibilities: CLI script for manual data pulls.
- Enhancements: Integrate into web app as a scheduled task.

### 4.4 Web App Components
- New: API endpoints (e.g., /fetch, /visualize, /export).
- Framework: Start with Flask for simplicity.
- Scheduling: Use APScheduler for timed jobs.

### 4.5 Visualization
- Use Plotly for interactive charts.
- Support types: Candlestick, line plots for indicators.

## 5. User Interface Design

### 5.1 Web UI
- Dashboard: List of symbols, latest prices, signals.
- Pages: Portfolio management, detailed symbol view with plots, export options.
- Interactions: Buttons for on-demand fetch, schedule configuration.

## 6. Deployment and Operations

### 6.1 Environment
- Development: Local with SQLite.
- Production: Dockerized app with PostgreSQL, hosted on Heroku/AWS.

### 6.2 CI/CD
- Use GitHub Actions (existing .github/workflows/ci.yml) for testing/linting.

### 6.3 Testing
- Unit tests for components (existing in tests/).
- Integration tests for data flow and web endpoints.

## 7. Risks and Assumptions
- Assumption: Yahoo Finance API remains free and reliable.
- Risk: Rate limiting on data fetches; mitigate with caching.
- Risk: Excel integration issues; fallback to CSV exports.

## 8. Future Enhancements
- Migrate DB to PostgreSQL.
- Add user authentication.
- Incorporate ML for predictive analytics.
- Mobile responsiveness.

This SDD is iterative and will be updated as development progresses.
>>>>>>> REPLACE