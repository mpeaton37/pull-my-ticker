import pytest
import pandas as pd
from unittest.mock import patch, MagicMock
from src.sheet_worker import SheetWorker

@pytest.fixture
def sample_worker(tmp_path):
    filename = tmp_path / "test.xlsx"
    # Create a simple Excel file
    df = pd.DataFrame({'Symbol': ['AAPL', 'GOOGL']})
    df.to_excel(filename, index=False)
    return SheetWorker(str(filename))

def test_read_symbols(sample_worker):
    sample_worker.read_symbols()
    assert sample_worker.symbols == ['AAPL', 'GOOGL']

@patch('src.sheet_worker.StockAnalyzer')
def test_update_excel_from_db(mock_analyzer_class, sample_worker):
    mock_analyzer = MagicMock()
    mock_df = pd.DataFrame({'symbol': ['AAPL'], 'last_close': [152.0]})
    mock_analyzer.read_from_sqlite.return_value = mock_df
    mock_analyzer_class.return_value = mock_analyzer

    sample_worker.update_excel_from_db(mock_analyzer)
    # Check if data sheet was created (basic check)
    assert 'Data' in sample_worker.workbook.sheetnames
