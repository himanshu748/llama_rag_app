import threading
import websocket
import json
import jsonlines
import requests
import time
import os
import logging
from web3 import Web3

# Ensure data directories exist
for dir in ["data/stock_ticks", "data/crypto_ticks", "data/chainlink_data", "data/news"]:
    os.makedirs(dir, exist_ok=True)

# Load config from environment variables
config = {
    "api_keys": {
        "alpha_vantage": os.getenv("ALPHA_VANTAGE_API_KEY"),
        "newsapi": os.getenv("NEWSAPI_API_KEY"),
        "huggingface": os.getenv("HUGGINGFACE_API_KEY"),
        "reactive_rpc": os.getenv("REACTIVE_RPC", "https://ethereum-sepolia-rpc.publicnode.com"),
        "reactive_private_key": os.getenv("REACTIVE_PRIVATE_KEY")
    },
    "settings": {
        "symbols": {
            "stocks": os.getenv("SYMBOLS_STOCKS", "RELIANCE.BSE,TCS.BSE").split(","),
            "crypto": os.getenv("SYMBOLS_CRYPTO", "btcusdt,ethusdt").split(","),
            "chainlink_pairs": os.getenv("SYMBOLS_CHAINLINK_PAIRS", "ETH/USD").split(",")
        },
        "news_polling_interval": int(os.getenv("NEWS_POLLING_INTERVAL", 300)),
        "contract_address": os.getenv("CONTRACT_ADDRESS")
    }
}

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s', filename='app.log')
logger = logging.getLogger(__name__)

def alpha_vantage_polling():
    while True:
        try:
            for symbol in config['settings']['symbols']['stocks']:
                url = f"https://www.alphavantage.co/query?function=TIME_SERIES_INTRADAY&symbol={symbol}&interval=1min&apikey={config['api_keys']['alpha_vantage']}"
                response = requests.get(url).json()
                if "Time Series (1min)" in response:
                    latest_time = max(response["Time Series (1min)"].keys())
                    tick = response["Time Series (1min)"][latest_time]
                    with jsonlines.open("data/stock_ticks/alpha_vantage_ticks.jsonl", "a") as writer:
                        writer.write({
                            "symbol": symbol,
                            "price": float(tick["4. close"]),
                            "timestamp": latest_time
                        })
                    logger.info(f"Alpha Vantage: {symbol} - {tick['4. close']}")
        except Exception as e:
            logger.error(f"Alpha Vantage error: {e}")
        time.sleep(60)

def binance_websocket():
    while True:
        try:
            ws = websocket.WebSocket()
            ws.connect("wss://stream.binance.com:9443/ws")
            ws.send(json.dumps({"method": "SUBSCRIBE", "params": [f"{s}@ticker" for s in config['settings']['symbols']['crypto']], "id": 1}))
            while True:
                tick = json.loads(ws.recv())
                with jsonlines.open("data/crypto_ticks/binance_ticks.jsonl", "a") as writer:
                    writer.write({"symbol": tick["s"], "price": float(tick["c"]), "timestamp": tick["E"]})
                logger.info(f"Binance: {tick['s']} - {tick['c']}")
        except Exception as e:
            logger.error(f"Binance error: {e}")
            time.sleep(5)

def fetch_news():
    while True:
        try:
            for symbol in config['settings']['symbols']['stocks'] + config['settings']['symbols']['crypto']:
                url = f"https://newsapi.org/v2/everything?q={symbol}&apiKey={config['api_keys']['newsapi']}&sortBy=publishedAt"
                response = requests.get(url).json()
                articles = response.get('articles', [])
                if articles:
                    sentiment = sum(1 for a in articles if 'positive' in a.get('description', '').lower()) / len(articles)
                    with jsonlines.open("data/news/news.jsonl", "a") as writer:
                        writer.write({"symbol": symbol, "sentiment": sentiment, "headline": articles[0]['title'], "timestamp": articles[0]['publishedAt']})
                    logger.info(f"News for {symbol}: {sentiment}")
        except Exception as e:
            logger.error(f"NewsAPI error: {e}")
        time.sleep(config['settings']['news_polling_interval'])

def fetch_chainlink():
    chainlink_feed = "0x1b44F3514812d835EB1BDB0acB33d3fA3351Ee43"  # ETH/USD on Sepolia
    w3 = Web3(Web3.HTTPProvider(config['api_keys']['reactive_rpc']))
    abi = [{"inputs":[],"name":"latestRoundData","outputs":[{"internalType":"uint80","name":"roundId","type":"uint80"},{"internalType":"int256","name":"answer","type":"int256"},{"internalType":"uint256","name":"startedAt","type":"uint256"},{"internalType":"uint256","name":"updatedAt","type":"uint256"},{"internalType":"uint80","name":"answeredInRound","type":"uint80"}],"stateMutability":"view","type":"function"}]
    contract = w3.eth.contract(address=chainlink_feed, abi=abi)
    while True:
        try:
            data = contract.functions.latestRoundData().call()
            price = data[1] / 10**8
            with jsonlines.open("data/chainlink_data/chainlink_ticks.jsonl", "a") as writer:
                writer.write({"symbol": "ETH/USD", "price": float(price), "timestamp": str(data[3])})
            logger.info(f"Chainlink: ETH/USD - {price}")
        except Exception as e:
            logger.error(f"Chainlink error: {e}")
        time.sleep(300)

def fetch_coingecko():
    while True:
        try:
            for symbol in config['settings']['symbols']['crypto']:
                url = f"https://api.coingecko.com/api/v3/simple/price?ids={symbol.split('usdt')[0].lower()}&vs_currencies=usd"
                response = requests.get(url).json()
                price = response[symbol.split('usdt')[0].lower()]['usd']
                with jsonlines.open("data/crypto_ticks/coingecko_ticks.jsonl", "a") as writer:
                    writer.write({"symbol": symbol, "price": float(price), "timestamp": str(int(time.time()))})
                logger.info(f"CoinGecko: {symbol} - {price}")
        except Exception as e:
            logger.error(f"CoinGecko error: {e}")
        time.sleep(300)

w3 = Web3(Web3.HTTPProvider(config['api_keys']['reactive_rpc']))
contract_address = config['settings']['contract_address']
# Hardcoded minimal ABI for executeTrade function
abi = [{"inputs":[{"internalType":"string","name":"symbol","type":"string"},{"internalType":"uint256","name":"price","type":"uint256"}],"name":"executeTrade","outputs":[],"stateMutability":"nonpayable","type":"function"}]
contract = w3.eth.contract(address=contract_address, abi=abi)

def execute_trade(symbol, price):
    account = w3.eth.account.from_key(config['api_keys']['reactive_private_key'])
    try:
        tx = contract.functions.executeTrade(symbol, int(price)).build_transaction({
            'from': account.address,
            'nonce': w3.eth.get_transaction_count(account.address),
            'gas': 200000,
            'gasPrice': w3.to_wei('20', 'gwei')
        })
        signed_tx = account.sign_transaction(tx)
        tx_hash = w3.eth.send_raw_transaction(signed_tx.rawTransaction)
        logger.info(f"Trade: {symbol} at {price}, tx: {tx_hash.hex()}")
        return tx_hash.hex()
    except Exception as e:
        logger.error(f"Trade error: {e}")
        return None

def start_fetchers():
    threading.Thread(target=alpha_vantage_polling, daemon=True).start()
    threading.Thread(target=binance_websocket, daemon=True).start()
    threading.Thread(target=fetch_news, daemon=True).start()
    threading.Thread(target=fetch_chainlink, daemon=True).start()
    threading.Thread(target=fetch_coingecko, daemon=True).start()
