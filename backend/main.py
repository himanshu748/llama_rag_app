from fastapi import FastAPI
import pathway as pw
from utils import start_fetchers, logger, execute_trade
from agent import make_decision, answer_query
import threading
import time
import os

# Ensure data directories exist
for dir in ["data/portfolios", "data/news", "data/stock_ticks", "data/crypto_ticks", "data/chainlink_data"]:
    os.makedirs(dir, exist_ok=True)

app = FastAPI()

# Pathway schemas
class Tick(pw.Schema):
    symbol: str
    price: float
    timestamp: str

class NewsData(pw.Schema):
    symbol: str
    sentiment: float
    headline: str
    timestamp: str

class Portfolio(pw.Schema):
    symbol: str
    quantity: int
    price: float

# Data streams
stock_ticks = pw.io.jsonlines.read("data/stock_ticks/alpha_vantage_ticks.jsonl", schema=Tick, mode="streaming")
crypto_ticks = pw.io.jsonlines.read("data/crypto_ticks/binance_ticks.jsonl", schema=Tick, mode="streaming")
coingecko_ticks = pw.io.jsonlines.read("data/crypto_ticks/coingecko_ticks.jsonl", schema=Tick, mode="streaming")
chainlink_data = pw.io.jsonlines.read("data/chainlink_data/chainlink_ticks.jsonl", schema=Tick, mode="streaming")
news_data = pw.io.jsonlines.read("data/news/news.jsonl", schema=NewsData, mode="streaming")
portfolio_table = pw.io.jsonlines.read("data/portfolios/portfolio.jsonl", schema=Portfolio, mode="streaming")

all_ticks = stock_ticks + crypto_ticks + coingecko_ticks + chainlink_data

latest_ticks = all_ticks.groupby(pw.this.symbol).reduce(
    symbol=pw.this.symbol,
    price=pw.reducers.latest(pw.this.price),
    timestamp=pw.reducers.latest(pw.this.timestamp)
)

latest_news = news_data.groupby(pw.this.symbol).reduce(
    symbol=pw.this.symbol,
    sentiment=pw.reducers.mean(pw.this.sentiment),
    headline=pw.reducers.latest(pw.this.headline),
    timestamp=pw.reducers.latest(pw.this.timestamp)
)

enriched_portfolio = portfolio_table.join(
    latest_ticks, pw.left.symbol == pw.right.symbol, how="left"
).select(
    symbol=pw.left.symbol,
    quantity=pw.left.quantity,
    purchase_price=pw.left.price,
    current_price=pw.right.price,
    tick_timestamp=pw.right.timestamp
).join(
    latest_news, pw.left.symbol == pw.right.symbol, how="left"
).select(
    symbol=pw.left.symbol,
    quantity=pw.left.quantity,
    purchase_price=pw.left.purchase_price,
    current_price=pw.left.current_price,
    sentiment=pw.right.sentiment,
    headline=pw.right.headline,
    news_timestamp=pw.right.timestamp
)

def prioritize_data(row):
    impact_score = row.sentiment if row.sentiment else 0.5
    if row.current_price and row.purchase_price:
        price_change = abs(row.current_price - row.purchase_price) / row.purchase_price
        impact_score += price_change * 10
    if row.tick_timestamp and (time.time() - int(row.tick_timestamp) < 300):
        impact_score += 1.0
    return {"priority": impact_score, "data": row}

indexed_data = enriched_portfolio.map(prioritize_data)
index = pw.indexing.VectorIndex(
    indexed_data.data, embedding_fn=pw.embedding.from_sentence_transformers("all-MiniLM-L6-v2"), priority=indexed_data.priority
)

@app.post("/query")
async def query_rag(query: dict):
    try:
        query_text = query.get("query")
        context = index.retrieve(query_text, k=5)
        response = answer_query(query_text, context)
        logger.info(f"Query: {query_text}, Response: {response}")
        return {"answer": response}
    except Exception as e:
        logger.error(f"Query error: {e}")
        return {"error": str(e)}

def agent_loop():
    while True:
        try:
            current_state = enriched_portfolio.select().to_dicts()
            if current_state:
                final_action, explanations = make_decision(current_state)
                for decision in explanations:
                    action = decision['action']
                    symbol = decision['symbol']
                    price = decision['price']
                    explanation = decision['explanation']
                    timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
                    tx_hash = None
                    if action in ['buy', 'sell']:
                        tx_hash = execute_trade(symbol, price)
                    with open('decisions.log', 'a') as f:
                        f.write(f"{timestamp},{symbol},{action},{explanation},{tx_hash}\n")
        except Exception as e:
            logger.error(f"Agent loop error: {e}")
        time.sleep(60)

# Start Pathway and fetchers in threads
logger.info("Starting TradeSmart AI Backend...")
threading.Thread(target=start_fetchers, daemon=True).start()
threading.Thread(target=agent_loop, daemon=True).start()
threading.Thread(target=pw.run, daemon=True).start()

# No uvicorn.run() here—Render will handle it via start command
