import yfinance as yf
import pandas as pd
import numpy as np
import ta
import ta.volatility
import ta.trend
import os
import sys
import sqlite3
import plotly.graph_objects as go  # Interactive, finance-friendly
import logging
from bokeh.plotting import figure, show  # For fancy dashboards
from datetime import datetime
from typing import List, Dict, Optional, Union, Tuple
from concurrent.futures import ThreadPoolExecutor, as_completed

from .predictor import KalmanPredictor

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def _display_exception(e: Exception) -> None:
    exc_type, exc_obj, exc_tb = sys.exc_info()
    fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
    logger.error(f"Exception: {e}, Type: {exc_type}, File: {fname}, Line: {exc_tb.tb_lineno}")

class StockAnalyzer:
    """
    A class for analyzing stock data, including fetching from Yahoo Finance,
    calculating technical indicators, and exporting to SQLite/Excel.
    """

    def __init__(self, symbols: List[str], start_date: Union[str, datetime], end_date: Union[str, datetime]):
        """
        Initialize with timezone-unaware dates.
        Dates can be strings ('YYYY-MM-DD') or datetime objects.
        """
        self.symbols = symbols
        self.current_time = datetime.now().replace(microsecond=0)

        # Convert string dates to datetime if necessary
        if isinstance(start_date, str):
            self.start_date = datetime.strptime(start_date, '%Y-%m-%d')
        else:
            self.start_date = start_date.replace(tzinfo=None)

        if isinstance(end_date, str):
            self.end_date = datetime.strptime(end_date, '%Y-%m-%d')
        else:
            self.end_date = end_date.replace(tzinfo=None)

        self.data: Dict[str, pd.DataFrame] = {}
        self.fundamental_data: Dict[str, Dict[str, Optional[float]]] = {}  # Separate dictionary for fundamental data
        self.blacklist: List[str] = ['ZTS']
        self.targets: Dict[str, Dict[str, Optional[float]]] = {}  # Analyst price targets

        # Initialize empty data structures for each symbol
        for symbol in self.symbols:
            self.data[symbol] = pd.DataFrame()
            self.fundamental_data[symbol] = {}

    @staticmethod
    def _sanitize_table_name(symbol: str) -> str:
        """Convert symbol to valid SQLite table name"""
        return f"historical_data_{symbol.lower().replace('-', '_').replace('.', '_')}"

    def _validate_symbols(self) -> None:
        """Quick precheck for symbol validity using yfinance fast_info to filter delisted/invalid tickers."""
        valid = []
        for symbol in self.symbols:
            try:
                ticker = yf.Ticker(symbol)
                info = ticker.fast_info
                if info.get('lastPrice') is not None or info.get('regularMarketPrice') is not None:
                    valid.append(symbol)
                else:
                    self.blacklist.append(symbol)
                    logger.warning(f"Invalid or delisted symbol skipped: {symbol}")
            except Exception as e:
                self.blacklist.append(symbol)
                logger.warning(f"Invalid or delisted symbol skipped: {symbol} ({e})")
        self.symbols = valid
        if not self.symbols:
            logger.warning("No valid symbols remaining after validation.")

    @classmethod
    def from_sqlite(cls, db_path: str) -> 'StockAnalyzer':
        """
        Create a StockAnalyzer instance from a SQLite database.
        Returns a fully initialized StockAnalyzer object with historical and fundamental data.
        """
        conn = None
        try:
            conn = sqlite3.connect(db_path)

            # Get list of symbols from summary_data table
            symbols_df = pd.read_sql_query('SELECT DISTINCT symbol FROM summary_data', conn)
            symbols = symbols_df['symbol'].tolist()

            if not symbols:
                raise ValueError("No symbols found in summary_data table")

            # Get date range from historical data
            min_date = None
            max_date = None

            for symbol in symbols:
                table_name = cls._sanitize_table_name(symbol)
                # Use parameterized query with double quotes around table name
                query = 'SELECT MIN("Date") as min_date, MAX("Date") as max_date FROM "{}"'.format(table_name)
                date_range = pd.read_sql_query(query, conn)

                symbol_min = pd.to_datetime(date_range['min_date'].iloc[0])
                symbol_max = pd.to_datetime(date_range['max_date'].iloc[0])

                min_date = symbol_min if min_date is None else min(min_date, symbol_min)
                max_date = symbol_max if max_date is None else max(max_date, symbol_max)

            # Create instance
            analyzer = cls(symbols, min_date, max_date)

            # Load historical data
            for symbol in symbols:
                table_name = cls._sanitize_table_name(symbol)
                query = 'SELECT * FROM "{}"'.format(table_name)
                hist_data = pd.read_sql_query(query, conn)

                # Convert Date column to datetime and set as index
                hist_data['Date'] = pd.to_datetime(hist_data['Date'])
                hist_data.set_index('Date', inplace=True)

                # Remove symbol column if it exists
                if 'symbol' in hist_data.columns:
                    hist_data = hist_data.drop('symbol', axis=1)

                analyzer.data[symbol] = hist_data

            # Check if fundamental_data table exists
            tables = pd.read_sql_query(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='fundamental_data'",
                conn
            )

            if not tables.empty:
                # Load fundamental data with error handling for missing columns
                fund_data = pd.read_sql_query('SELECT * FROM fundamental_data', conn)

                # Define expected columns and their corresponding keys
                column_mapping = {
                    'symbol': 'symbol',
                    'pe_ratio': 'PE_Ratio',
                    'dividend_yield': 'Dividend_Yield',
                    'market_cap': 'Market_Cap'
                }

                # Initialize fundamental data for each symbol
                for symbol in symbols:
                    analyzer.fundamental_data[symbol] = {
                        'PE_Ratio': None,
                        'Dividend_Yield': None,
                        'Market_Cap': None
                    }

                # Update with available data
                for _, row in fund_data.iterrows():
                    symbol = row['symbol']
                    for db_col, class_key in column_mapping.items():
                        if db_col in fund_data.columns:
                            try:
                                analyzer.fundamental_data[symbol][class_key] = row[db_col]
                            except Exception as e:
                                logger.warning(f"Warning: Could not load {db_col} for {symbol}: {str(e)}")
            else:
                logger.warning("Warning: fundamental_data table not found. Initializing with empty values.")
                for symbol in symbols:
                    analyzer.fundamental_data[symbol] = {
                        'PE_Ratio': None,
                        'Dividend_Yield': None,
                        'Market_Cap': None
                    }

            return analyzer

        except sqlite3.Error as e:
            logger.error(f"SQLite error: {str(e)}")
            raise
        except Exception as e:
            logger.error(f"Error loading from database: {str(e)}")
            raise
        finally:
            if conn:
                conn.close()

    def export_to_sqlite(self, db_path: str) -> None:
        """
        Export data to SQLite database with multiple tables:
        - summary_data: Latest snapshot for each symbol
        - historical_data: Full price history and indicators
        - fundamental_data: Latest fundamental metrics
        """
        try:
            conn = sqlite3.connect(db_path)

            # Create summary data
            summary_data = []
            logger.info(f"Exporting data to SQLite. Blacklist: {self.blacklist}")
            for symbol in self.symbols:
                if symbol not in self.blacklist:
                    if symbol not in self.data:
                        logger.warning(f"No data available for {symbol}")
                        continue
                    if symbol not in self.fundamental_data:
                        logger.warning(f"No fundamental data available for {symbol}")
                        continue
                    latest = self.data[symbol].iloc[-1]
                    fund_data = self.fundamental_data.get(symbol, {})

                    summary_data.append({
                        'symbol': symbol,
                        'last_update': self.current_time.isoformat(),
                        'last_close': float(latest['Close']),
                        'rsi': float(latest['RSI']),
                        'macd': float(latest['MACD']),
                        'pe_ratio': fund_data.get('PE_Ratio'),
                        'dividend_yield': fund_data.get('Dividend_Yield'),
                        'market_cap': fund_data.get('Market_Cap')
                    })

            # Write summary data
            summary_df = pd.DataFrame(summary_data)
            try:
                if summary_df.empty:
                    logger.warning("No summary data to export; skipping.")
                    return
                summary_df.to_sql('summary_data', conn, if_exists='replace', index=False)
            except Exception as e:
                logger.error(f"Error writing summary data to database: {str(e)}")
                logger.info("Summary data written to SQLite database")
                # Write historical data for each symbol

            for symbol in self.symbols:
                if symbol not in self.data:
                    logger.warning(f"No historical data available for {symbol}")
                    continue

                # Create a copy of the dataframe
                hist_data = self.data[symbol].copy()

                # Convert the index to a datetime column
                hist_data = hist_data.reset_index(drop=False)
                hist_data['Date'] = pd.to_datetime(hist_data['Date'])

                # Convert datetime to string in ISO format
                hist_data['Date'] = hist_data['Date'].dt.strftime('%Y-%m-%d %H:%M:%S')

                # Add symbol column
                hist_data['symbol'] = symbol

                # Reorder columns to put symbol first
                cols = ['symbol', 'Date'] + [col for col in hist_data.columns if col not in ['symbol', 'Date']]
                hist_data = hist_data[cols]

                # Write to database with symbol as table name prefix
                table_name = self._sanitize_table_name(symbol)
                hist_data.to_sql(table_name, conn, if_exists='replace', index=False)

            # Write fundamental data
            fundamental_records = []
            for symbol, data in self.fundamental_data.items():
                data_copy = data.copy()
                data_copy['symbol'] = symbol
                data_copy['last_update'] = self.current_time.isoformat()
                data_copy['target_mean'] = self.targets.get(symbol, {}).get('mean')
                data_copy['target_high'] = self.targets.get(symbol, {}).get('high')
                data_copy['target_low'] = self.targets.get(symbol, {}).get('low')
                fundamental_records.append(data_copy)

            fund_df = pd.DataFrame(fundamental_records)
            if not fund_df.empty:
                fund_df.to_sql('fundamental_data', conn, if_exists='replace', index=False)

                try:
                    # Drop existing view if it exists
                    conn.execute('DROP VIEW IF EXISTS latest_data')

                    # Create view only if both tables exist
                    conn.execute('''
                        CREATE VIEW latest_data AS
                        SELECT
                            s.symbol,
                            s.last_update,
                            s.last_close,
                            s.rsi,
                            s.macd,
                            f.pe_ratio,
                            f.dividend_yield,
                            f.market_cap,
                            f.target_mean,
                            f.target_high,
                            f.target_low
                        FROM summary_data s
                        LEFT JOIN fundamental_data f
                        ON s.symbol = f.symbol
                    ''')

                    # Create metadata table
                    conn.execute('''
                        CREATE TABLE IF NOT EXISTS metadata (
                            key TEXT PRIMARY KEY,
                            value TEXT
                        )
                    ''')
                except sqlite3.Error as e:
                    logger.error(f"Error creating view: {str(e)}")

                # Update metadata
                logger.info("Updating metadata in SQLite database")
                conn.execute('INSERT OR REPLACE INTO metadata (key, value) VALUES (?, ?)',
                            ('schema_version', '1.0'))
                logger.info("Setting last update time in SQLite database")
                conn.execute('INSERT OR REPLACE INTO metadata (key, value) VALUES (?, ?)',
                            ('last_update', self.current_time.isoformat()))
                conn.commit()

        except sqlite3.Error as e:
            logger.error(f"SQLite error: {str(e)}")
        except IndexError as e:
            logger.error(f"Index error: {str(e)}")
            logger.error(f"Dataframe shape: {summary_df.shape if 'summary_df' in locals() else 'N/A'}")
        except Exception as e:
            logger.error(f"Error exporting to database: {str(e)}")
            _display_exception(e)
        finally:
            if conn:
                conn.close()

    def fetch_market_data(self, force_refresh: bool = True, latest_only: bool = False, threads: int = 4) -> None:
        """Fetch stock data from multiple sources and ensure timezone-unaware dates.
        Uses bulk yf.download for speed; falls back to threaded fetches if needed.
        """
        self._validate_symbols()  # Precheck for valid symbols before any fetch
        conn = sqlite3.connect('stocks.db')
        try:
            if not self.symbols:
                return

            valid_symbols = [s for s in self.symbols if s not in self.blacklist]
            if not valid_symbols:
                return

            if latest_only:
                # For latest-only, still use bulk where possible
                data = yf.download(valid_symbols, period="1d", group_by='ticker', threads=threads)
                for symbol in valid_symbols:
                    if symbol in data.columns.get_level_values(0):
                        hist = data[symbol].copy()
                        hist = hist[['Open', 'High', 'Low', 'Close', 'Volume']]
                        hist['RSI'] = None
                        self.data[symbol] = hist
                    else:
                        self.data[symbol] = pd.DataFrame()
            else:
                # Bulk download for historical data (much faster than per-ticker loop)
                try:
                    data = yf.download(
                        valid_symbols,
                        start=self.start_date,
                        end=self.end_date,
                        group_by='ticker',
                        threads=threads,
                        auto_adjust=True
                    )
                    for symbol in valid_symbols:
                        if symbol in data.columns.get_level_values(0):
                            hist = data[symbol].copy()
                            hist = hist[['Open', 'High', 'Low', 'Close', 'Volume']]
                            # Add indicators
                            hist['RSI'] = ta.momentum.RSIIndicator(hist['Close']).rsi()
                            hist['MACD'] = ta.trend.MACD(hist['Close']).macd()
                            indicator_bb = ta.volatility.BollingerBands(hist['Close'])
                            hist['BB_upper'] = indicator_bb.bollinger_hband()
                            hist['BB_middle'] = indicator_bb.bollinger_mavg()
                            hist['BB_lower'] = indicator_bb.bollinger_lband()
                            self.data[symbol] = hist
                        else:
                            self.data[symbol] = pd.DataFrame()
                except Exception as bulk_err:
                    logger.warning(f"Bulk download failed ({bulk_err}). Falling back to threaded fetches.")
                    self._fetch_with_threads(valid_symbols, threads)

            # Fetch fundamental data (still per-symbol, but fast)
            for symbol in valid_symbols:
                try:
                    stock = yf.Ticker(symbol)
                    stock_info = stock.info
                    self.fundamental_data[symbol] = {
                        'PE_Ratio': stock_info.get('forwardPE'),
                        'Dividend_Yield': stock_info.get('dividendYield'),
                        'Market_Cap': stock_info.get('marketCap')
                    }
                    self.targets[symbol] = {
                        'mean': stock_info.get('targetMeanPrice'),
                        'high': stock_info.get('targetHighPrice'),
                        'low': stock_info.get('targetLowPrice')
                    }
                except Exception as e:
                    logger.error(f"Error fetching fundamental data for {symbol}: {str(e)}")
                    self.fundamental_data[symbol] = {
                        'PE_Ratio': None,
                        'Dividend_Yield': None,
                        'Market_Cap': None
                    }
                    self.targets[symbol] = {'mean': None, 'high': None, 'low': None}

        except sqlite3.Error as e:
            logger.error(f"SQLite error: {str(e)}")
            _display_exception(e)
        except Exception as e:
            logger.error(f"Error fetching market data: {str(e)}")
            _display_exception(e)
        finally:
            conn.close()

    def _fetch_with_threads(self, symbols: List[str], threads: int = 4) -> None:
        """Threaded fallback for fetching individual tickers."""
        def fetch_one(symbol):
            try:
                stock = yf.Ticker(symbol)
                hist = stock.history(start=self.start_date, end=self.end_date)
                if not hist.empty:
                    hist['RSI'] = ta.momentum.RSIIndicator(hist['Close']).rsi()
                    hist['MACD'] = ta.trend.MACD(hist['Close']).macd()
                    indicator_bb = ta.volatility.BollingerBands(hist['Close'])
                    hist['BB_upper'] = indicator_bb.bollinger_hband()
                    hist['BB_middle'] = indicator_bb.bollinger_mavg()
                    hist['BB_lower'] = indicator_bb.bollinger_lband()
                    return symbol, hist
                return symbol, pd.DataFrame()
            except Exception as e:
                logger.warning(f"Failed to fetch {symbol}: {e}")
                return symbol, pd.DataFrame()

        with ThreadPoolExecutor(max_workers=threads) as executor:
            future_to_symbol = {executor.submit(fetch_one, s): s for s in symbols}
            for future in as_completed(future_to_symbol):
                symbol, hist = future.result()
                self.data[symbol] = hist

    def add_advanced_indicators(self) -> None:
        for symbol, df in self.data.items():
            # ATR
            df['ATR'] = ta.volatility.AverageTrueRange(df['High'], df['Low'], df['Close']).average_true_range()

            # SMA/EMA
            df['SMA_50'] = ta.trend.SMAIndicator(df['Close'], window=50).sma_indicator()
            df['EMA_20'] = ta.trend.EMAIndicator(df['Close'], window=20).ema_indicator()

            # Sharpe Ratio (annualized, assuming 252 trading days)
            returns = df['Close'].pct_change().dropna()
            df['Returns'] = returns  # Add for reference
            sharpe = (returns.mean() * 252) / (returns.std() * np.sqrt(252)) if not returns.empty else np.nan
            try:
                self.fundamental_data[symbol]['Sharpe_Ratio'] = sharpe

                # Beta (vs. SPY)
                spy = yf.Ticker('SPY').history(start=self.start_date, end=self.end_date)['Close'].pct_change().dropna()
                cov = returns.cov(spy)
                var = spy.var()
                beta = cov / var if var != 0 else np.nan
                self.fundamental_data[symbol]['Beta'] = beta
            except Exception as e:
                logger.error(f"Error calculating advanced indicators for {symbol}: {str(e)}")
                continue

    def export_to_excel(self, filename: str) -> None:
        """Export data to Excel with multiple sheets and a clean summary"""
        try:
            with pd.ExcelWriter(filename, engine='openpyxl', mode='w') as writer:
                # Create summary data as a proper DataFrame
                summary_data = []

                for symbol in self.symbols:
                    latest = self.data[symbol].iloc[-1]

                    # Safely get fundamental data with proper error handling
                    fund_data = self.fundamental_data.get(symbol, {})
                    pe_ratio = fund_data.get('PE_Ratio')
                    div_yield = fund_data.get('Dividend_Yield')
                    market_cap = fund_data.get('Market_Cap')

                    summary_data.append({
                        'Symbol': symbol,
                        'Last_Update': self.current_time,
                        'Last_Close': float(latest['Close']),
                        'RSI': float(latest['RSI']),
                        'MACD': float(latest['MACD']),
                        'PE_Ratio': float(pe_ratio) if pe_ratio is not None else None,
                        'Dividend_Yield': float(div_yield) if div_yield is not None else None,
                        'Market_Cap': float(market_cap) if market_cap is not None else None
                    })

                # Create DataFrame and set index to Symbol
                summary_df = pd.DataFrame(summary_data)
                if not summary_df.empty:
                    summary_df.set_index('Symbol', inplace=True)
                    summary_df.to_excel(writer, sheet_name='Summary')

                # Individual stock sheets
                for symbol in self.symbols:
                    if not self.data[symbol].empty:
                        self.data[symbol].to_excel(writer, sheet_name=symbol)

        except PermissionError:
            logger.error(f"Error: Unable to write to {filename}. Please ensure the file is not open in another program.")
        except Exception as e:
            logger.error(f"Error exporting to Excel: {str(e)}")

    def generate_signals(self) -> pd.DataFrame:
        """Generate buy/sell signals based on technical indicators"""
        signals = []
        self.current_time = datetime.now().replace(microsecond=0)

        for symbol in self.symbols:
            df = self.data[symbol]
            latest = df.iloc[-1]

            signals.append({
                'Symbol': symbol,
                'Timestamp': self.current_time,
                'RSI_Signal': 'Oversold' if latest['RSI'] < 30 else 'Overbought' if latest['RSI'] > 70 else 'Neutral',
                'MACD_Signal': 'Buy' if latest['MACD'] > 0 else 'Sell',
                'BB_Signal': 'Oversold' if latest['Close'] < latest['BB_lower'] else 'Overbought' if latest['Close'] > latest['BB_upper'] else 'Neutral'
            })

        signals_df = pd.DataFrame(signals)
        if not signals_df.empty:
            signals_df.set_index('Symbol', inplace=True)
        return signals_df

    def read_from_sqlite(self, db_path: str, symbol: Optional[str] = None) -> Optional[pd.DataFrame]:
        """
        Read data from SQLite database
        If symbol is provided, returns historical data for that symbol
        Otherwise returns the latest summary data
        """
        try:
            conn = sqlite3.connect(db_path)

            if symbol:
                # Read historical data for specific symbol
                table_name = f"historical_data_{symbol.lower().replace('.', '_')}"
                query = f"SELECT * FROM {table_name}"
                df = pd.read_sql_query(query, conn)

                # Convert string dates back to datetime
                df['Date'] = pd.to_datetime(df['Date'])

                # Set Date as index
                df.set_index('Date', inplace=True)
                return df
            else:
                # Read latest summary data
                return pd.read_sql_query('SELECT * FROM latest_data', conn)

        except sqlite3.Error as e:
            logger.error(f"SQLite error: {str(e)}")
            return None
        finally:
            if conn:
                conn.close()

    def load_for_notebook(self, symbol: Optional[str] = None, from_db: bool = True) -> Union[Dict[str, pd.DataFrame], pd.DataFrame, None]:
        """Load data for Jupyter: Prefer DB for offline, fetch if needed."""
        if from_db and os.path.exists('stocks.db'):
            return self.read_from_sqlite('stocks.db', symbol)
        else:
            self.fetch_market_data(force_refresh=True)  # Or latest_only as below
            return self.data if symbol is None else self.data.get(symbol)

    def visualize(self, symbol: str, plot_type: str = 'candlestick', interactive: bool = True):
        df = self.load_for_notebook(symbol)
        if df is None or df.empty:
            logger.warning(f"No data available for {symbol}")
            return None
        if interactive:
            # Plotly Candlestick (fancy for finance)
            fig = go.Figure(data=[go.Candlestick(x=df.index,
                                                open=df['Open'], high=df['High'],
                                                low=df['Low'], close=df['Close'])])
            fig.add_trace(go.Scatter(x=df.index, y=df['RSI'], name='RSI', yaxis='y2'))
            fig.update_layout(title=f'{symbol} Stock', yaxis_title='Price', yaxis2={'title': 'RSI', 'overlaying': 'y', 'side': 'right'})
            fig.show()
            return fig
        else:
            # Matplotlib fallback
            import matplotlib.pyplot as plt
            df['Close'].plot(title=f'{symbol} Close')
            plt.show()
            return None
        # Bokeh for streaming/dashboard (stub)
        p = figure(title=f'{symbol} Bokeh', x_axis_type='datetime')
        p.line(df.index, df['Close'], legend_label='Close')
        show(p)
        return None

    def predict_price_and_variance(self, symbol: str) -> Tuple[float, float]:
        """
        New method for stock price and variance prediction.
        Loads data from DB and uses the model-agnostic KalmanPredictor (C++ backend).
        """
        df = self.read_from_sqlite('stocks.db', symbol)
        if df is None or df.empty:
            logger.warning(f"No data available for prediction on {symbol}")
            return 0.0, 0.0

        predictor = KalmanPredictor()
        predicted_price, variance = predictor.predict(df)
        logger.info(f"Prediction for {symbol}: Price={predicted_price:.2f}, Variance={variance:.2f}")
        return predicted_price, variance
