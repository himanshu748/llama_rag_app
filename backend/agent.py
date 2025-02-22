import requests
from utils import logger, config, execute_trade

def query_llama(prompt):
    headers = {"Authorization": f"Bearer {config['api_keys']['huggingface']}"}
    payload = {"inputs": prompt, "parameters": {"max_length": 200}}
    response = requests.post("https://api-inference.huggingface.co/models/meta-llama/Llama-3.3-70B-Instruct", headers=headers, json=payload)
    return response.json()[0]["generated_text"]

AGENTS = [
    {"name": "Conservative", "prompt": "Risk-averse: prioritize stability. Given {data}, recommend buy, sell, or hold for {symbol} with reasoning."},
    {"name": "Aggressive", "prompt": "Aggressive trader: seek high returns. Given {data}, recommend buy, sell, or hold for {symbol} with reasoning."},
    {"name": "Balanced", "prompt": "Balanced: weigh risk/reward. Given {data}, recommend buy, sell, or hold for {symbol} with reasoning."},
]

def parse_action(response):
    response = response.lower()
    if "buy" in response:
        return "buy"
    elif "sell" in response:
        return "sell"
    return "hold"

def calculate_phs(current_state):
    total_value = sum(row['current_price'] * row['quantity'] for row in current_state if row['current_price'])
    initial_value = sum(row['purchase_price'] * row['quantity'] for row in current_state)
    sentiment_avg = sum(row['sentiment'] for row in current_state if row['sentiment']) / max(1, len([r for r in current_state if r['sentiment']]))
    phs = (total_value / initial_value) * 0.7 + sentiment_avg * 0.3 if initial_value > 0 else sentiment_avg
    return round(phs, 2)

def make_decision(current_state):
    decisions = []
    phs = calculate_phs(current_state)
    logger.info(f"PHS: {phs}")
    
    for asset in current_state:
        symbol = asset['symbol']
        data = (f"Current Price: {asset['current_price']}, Purchase Price: {asset['purchase_price']}, "
                f"Sentiment: {asset['sentiment']}, News: {asset['headline']}, PHS: {phs}")
        
        votes = {"buy": 0, "sell": 0, "hold": 0}
        explanations = []
        for agent in AGENTS:
            prompt = agent["prompt"].format(data=data, symbol=symbol)
            response = query_llama(prompt)
            action = parse_action(response)
            votes[action] += 1
            explanations.append({"agent": agent["name"], "action": action, "explanation": response})
            logger.info(f"{agent['name']}: {action} for {symbol} - {response}")

        chainlink_price = next((item['price'] for item in current_state if item['symbol'] == "ETH/USD"), asset['current_price'])
        uniswap_price = next((item['price'] for item in current_state if item['symbol'] == symbol and "coingecko" in item['timestamp']), asset['current_price'])
        if chainlink_price > uniswap_price * 1.05 and "btc" in symbol.lower():
            action = "buy"
            explanation = f"Arbitrage: Chainlink ({chainlink_price}) > Uniswap ({uniswap_price}) by >5%."
            tx_hash = execute_trade(symbol, chainlink_price)
            explanations.append({"agent": "ArbitrageBot", "action": action, "explanation": explanation, "tx_hash": tx_hash})
            votes["buy"] += 1
            logger.info(f"Arbitrage trade: {symbol}, tx: {tx_hash}")

        final_action = max(votes, key=votes.get)
        decisions.append({
            'symbol': symbol,
            'price': asset['current_price'],
            'action': final_action,
            'explanations': explanations,
            'phs': phs
        })
    return final_action, decisions

def answer_query(query, context):
    context_str = "\n".join([f"{item['symbol']}: {item['current_price']}, Sentiment: {item['sentiment']}" for item in context])
    prompt = f"Query: {query}\nContext: {context_str}\nResponse:"
    response = query_llama(prompt)
    relevance = 0.9 if any(word in query.lower() for word in ["sell", "buy", "price"]) else 0.7
    return f"{response}\n(Relevance: {relevance})"