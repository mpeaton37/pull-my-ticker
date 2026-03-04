import pytest
import pandas as pd
from unittest.mock import patch, MagicMock
from src.stock_analyzer import StockAnalyzer

@pytest.fixture
def sample_analyzer():
    symbols = ['AAPL']
    start_date = '2023-01-01'
    end_date = '2023-01-02'
    return StockAnalyzer(symbols, start_date, end_date)

def test_init(sample_analyzer):
    assert sample_analyzer.symbols == ['AAPL']
    assert 'AAPL' in sample_analyzer.data
    assert 'AAPL' in sample_analyzer.fundamental_data

@patch('src.stock_analyzer.yf.Ticker')
def test_fetch_market_data(mock_ticker, sample_analyzer):
    mock_stock = MagicMock()
    mock_hist = pd.DataFrame({
        'Open': [150], 'High': [155], 'Low': [148], 'Close': [152], 'Volume': [1000]
    }, index=pd.to_datetime(['2023-01-01']))
    mock_stock.history.return_value = mock_hist
    mock_stock.info = {'forwardPE': 20.0}
    mock_ticker.return_value = mock_stock

    sample_analyzer.fetch_market_data()
    assert not sample_analyzer.data['AAPL'].empty
    assert 'RSI' in sample_analyzer.data['AAPL'].columns

def test_generate_signals(sample_analyzer):
    # Mock data
    sample_analyzer.data['AAPL'] = pd.DataFrame({
        'Close': [152], 'RSI': [25], 'MACD': [1.0], 'BB_lower': [150], 'BB_upper': [160]
    })
    signals = sample_analyzer.generate_signals()
    assert not signals.empty
    assert signals.loc['AAPL', 'RSI_Signal'] == 'Oversold'
