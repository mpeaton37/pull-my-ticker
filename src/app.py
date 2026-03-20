from flask import Flask, send_file
import io
from src.stock_analyzer import StockAnalyzer

app = Flask(__name__)

# Initialize analyzer with example symbols; in production, load from config/DB
analyzer = StockAnalyzer(symbols=['AAPL', 'GOOGL'], start_date='2020-01-01', end_date='2023-01-01')

@app.route('/')
def index():
    return "Welcome to HEDGE2 Stock Analyzer Web App. Try /visualize/AAPL"

@app.route('/visualize/<symbol>')
def visualize(symbol):
    # Ensure data is fetched/loaded
    analyzer.fetch_market_data(force_refresh=False)
    fig = analyzer.visualize(symbol, plot_type='candlestick', interactive=False)
    
    if fig is None:
        return "No data available for visualization", 404
    
    # Save Plotly figure to bytes for serving
    img_bytes = io.BytesIO()
    fig.write_image(img_bytes, format='png')
    img_bytes.seek(0)
    return send_file(img_bytes, mimetype='image/png')

if __name__ == '__main__':
    app.run(debug=True)
