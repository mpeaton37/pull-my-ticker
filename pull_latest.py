import datetime
import yfinance as yf
from openpyxl import load_workbook
import pandas as pd
import pdb
import stock_analyzer as sa 
#df1 = pd.DataFrame(columns=['symbol','price'])
import logging

from sheet_worker import SheetWorker
import schedule
import time

logging.basicConfig(level=logging.INFO)

import pdb
def job():
	logger = logging.getLogger(__name__)
	worker = SheetWorker('mbook3.xlsx')
	worker.read_symbols()
	symbols = worker.get_symbols() 
	#pdb.set_trace()
	start_date = datetime.datetime.now() - datetime.timedelta(days=365)
	end_date = datetime.datetime.now()
	analyst = sa.StockAnalyzer(symbols, start_date, end_date)
	analyst.fetch_market_data()
	analyst.export_to_sqlite('stock_analysis.db')
	worker.update_excel_from_db(analyst)

	logger.info("Finished updating stock data and database at {}".format(datetime.datetime.now()))

def main():
	schedule.every().day.at("11:10:00").do(job)
	while True:
		schedule.run_pending()
		time.sleep(60) 

if __name__ == "__main__":
	job()
	#main()