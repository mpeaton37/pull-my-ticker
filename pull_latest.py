import datetime
import yfinance as yf
from openpyxl import load_workbook
import pandas as pd
import logging
import stock_analyzer as sa
from sheet_worker import SheetWorker
import schedule
import time
from typing import NoReturn

logging.basicConfig(level=logging.INFO)

def job() -> None:
    """Scheduled job to update stock data."""
    logger = logging.getLogger(__name__)
    worker = SheetWorker('mbook3.xlsx')
    worker.read_symbols()
    symbols = worker.get_symbols()
    start_date = datetime.datetime.now() - datetime.timedelta(days=365)
    end_date = datetime.datetime.now()
    analyst = sa.StockAnalyzer(symbols, start_date, end_date)
    analyst.fetch_market_data()
    analyst.export_to_sqlite('stock_analysis.db')
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
