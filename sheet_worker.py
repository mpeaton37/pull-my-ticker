import openpyxl
import sqlite3
import pandas as pd

class SheetWorker:
    def __init__(self, filename):
        self.filename = filename
        self.workbook = openpyxl.load_workbook(filename)
        self.symbols = []

    def read_symbols(self):
        # Assuming symbols are in the first sheet, column A, starting from row 2 (row 1 is header)
        sheet = self.workbook.active
        self.symbols = []
        for row in range(2, sheet.max_row + 1):
            cell_value = sheet[f'A{row}'].value
            if cell_value:
                self.symbols.append(cell_value)

    def get_symbols(self):
        return self.symbols

    def update_excel_from_db(self, analyst):
        # Assuming analyst has a method to get data, e.g., analyst.get_data() returns a DataFrame
        # For simplicity, let's assume we update a sheet called 'Data' with stock data
        if not hasattr(analyst, 'get_data'):
            raise AttributeError("Analyst object must have a get_data method returning a DataFrame")
        data_df = analyst.get_data()
        
        if 'Data' not in self.workbook.sheetnames:
            self.workbook.create_sheet('Data')
        data_sheet = self.workbook['Data']
        
        # Clear existing data
        data_sheet.delete_rows(1, data_sheet.max_row)
        
        # Write DataFrame to sheet
        for r, (idx, row) in enumerate(data_df.iterrows(), start=1):
            for c, (col_name, value) in enumerate(row.items(), start=1):
                if r == 1:
                    data_sheet.cell(row=r, column=c, value=col_name)
                data_sheet.cell(row=r+1, column=c, value=value)
        
        self.workbook.save(self.filename)
