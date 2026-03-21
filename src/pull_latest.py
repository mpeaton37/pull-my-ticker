import sys
import os
if __name__ == "__main__":
    sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import datetime
import yfinance as yf
from openpyxl import load_workbook
import pandas as pd
import logging
import tomllib
from src.stock_analyzer import StockAnalyzer
from src.sheet_worker import SheetWorker
import schedule
import time
from typing import NoReturn, Dict, Any
from datetime import timedelta

logging.basicConfig(level=logging.INFO)

def load_config(config_path: str = "config.toml") -> Dict[str, Any]:
    """Load configuration from TOML file with defaults."""
    defaults = {
        "tickers": {
            "symbols": [],
            "days_history": 365
        },
        "files": {
            "excel": "mbook3.xlsx",
            "db": "stocks.db"
        },
        "predictor": {
            "lib_path": "./common_filter.so"
        }
    }
    config = defaults.copy()
    try:
        with open(config_path, "rb") as f:
            loaded = tomllib.load(f)
        # Merge loaded config into defaults (shallow for top-level, manual for nested)
        for key in defaults:
            if key in loaded:
                config[key] = loaded[key].copy() if isinstance(loaded[key], dict) else loaded[key]
        # Ensure nested defaults
        for key, val in defaults["tickers"].items():
            config["tickers"].setdefault(key, val)
        for key, val in defaults["files"].items():
            config["files"].setdefault(key, val)
        for key, val in defaults["predictor"].items():
            config["predictor"].setdefault(key, val)
        logging.getLogger(__name__).info(f"Loaded config from {config_path}")
    except FileNotFoundError:
        logging.getLogger(__name__).warning(f"Config file {config_path} not found, using defaults")
    except Exception as e:
        logging.getLogger(__name__).error(f"Error loading config {config_path}: {e}, using defaults")
    return config

def job() -> None:
    """Scheduled job to update stock data."""
    logger = logging.getLogger(__name__)
    config = load_config()
    logger.info(f"Predictor lib_path: {config['predictor']['lib_path']}")

    excel_file = config["files"]["excel"]
    db_file = config["files"]["db"]
    days_history = config["tickers"]["days_history"]
    symbols = config["tickers"]["symbols"]

    if not symbols:
        worker = SheetWorker(excel_file)
        worker.read_symbols()
        symbols = worker.get_symbols()
        logger.info(f"Loaded {len(symbols)} symbols from {excel_file}")
    else:
        logger.info(f"Using {len(symbols)} symbols from config")

    start_date = datetime.datetime.now() - timedelta(days=days_history)
    end_date = datetime.datetime.now()
    analyst = StockAnalyzer(symbols, start_date, end_date)
    analyst.fetch_market_data()
    analyst.export_to_sqlite(db_file)
    worker = SheetWorker(excel_file)
    worker.update_excel_from_db(analyst)
    logger.info(f"Finished updating stock data and database at {datetime.datetime.now()}")

def main() -> NoReturn:
    """Main function to run the scheduler."""
    schedule.every().day.at("11:10:00").do(job)
    while True:
        schedule.run_pending()
        time.sleep(60)

if __name__ == "__main__":
    job()
    # main()  # Uncomment to run scheduler
