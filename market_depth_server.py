from flask import Flask, jsonify
import random
import time
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

def generate_mock_order_book(symbol):
    base_price = 45000 if symbol == "BTCUSDT" else 2500
    spread = 10 if symbol == "BTCUSDT" else 1
    
    bids = []
    asks = []
    
    # Generate bids
    for i in range(50):
        price = base_price - (i * spread)
        quantity = random.random() * 10 + 5
        bids.append([price, quantity])
    
    # Generate asks
    for i in range(50):
        price = base_price + (i * spread)
        quantity = random.random() * 10 + 5
        asks.append([price, quantity])
    
    return {
        "bids": sorted(bids, reverse=True),
        "asks": sorted(asks)
    }

def generate_mock_ratio_data():
    ranges = ['0-1%', '1-2.5%', '2.5-5%', '5-10%']
    buy_volumes = [random.random() * 1000 + 500 for _ in ranges]
    sell_volumes = [random.random() * 1000 + 500 for _ in ranges]
    ratios = [(buy - sell) / (buy + sell) for buy, sell in zip(buy_volumes, sell_volumes)]
    
    return {
        "ranges": ranges,
        "ratios": ratios,
        "buyVolumes": buy_volumes,
        "sellVolumes": sell_volumes
    }

@app.route('/api/market-depth/<symbol>/<market_type>')
def get_market_depth(symbol, market_type):
    order_book = generate_mock_order_book(symbol)
    ratio_data = generate_mock_ratio_data()
    
    return jsonify({
        "timestamp": int(time.time() * 1000),
        "symbol": symbol,
        "marketType": market_type,
        "orderBook": order_book,
        "ratioAnalysis": ratio_data
    })

if __name__ == '__main__':
    app.run(debug=True, port=5000) 