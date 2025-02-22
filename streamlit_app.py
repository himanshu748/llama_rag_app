import streamlit as st
import requests
import jsonlines
import pandas as pd
import os

# Ensure data directories exist
for dir in ["data/portfolios", "data/news", "data/stock_ticks", "data/crypto_ticks", "data/chainlink_data"]:
    os.makedirs(dir, exist_ok=True)

st.title("TradeSmart AI: Intraday & Crypto Dashboard")
st.write("Real-time trading insights with AI and blockchain.")

# Portfolio upload
uploaded_file = st.file_uploader("Upload portfolio CSV (symbol, quantity, price)", type="csv")
if uploaded_file:
    df = pd.read_csv(uploaded_file)
    with jsonlines.open("data/portfolios/portfolio.jsonl", "a") as writer:
        for _, row in df.iterrows():
            writer.write({"symbol": row["symbol"], "quantity": int(row["quantity"]), "price": float(row["price"])})
    st.success("Portfolio uploaded!")

# Live data feed
st.subheader("Live Data Feed")
st.write("Updates from Alpha Vantage, Binance, Chainlink, and CoinGecko.")
if st.button("Refresh"):
    for file, label in [
        ("data/stock_ticks/alpha_vantage_ticks.jsonl", "Stock Ticks (Alpha Vantage)"),
        ("data/crypto_ticks/binance_ticks.jsonl", "Crypto Ticks (Binance)"),
        ("data/crypto_ticks/coingecko_ticks.jsonl", "Uniswap Ticks (CoinGecko)"),
        ("data/chainlink_data/chainlink_ticks.jsonl", "Chainlink Feeds"),
        ("data/news/news.jsonl", "News")
    ]:
        try:
            with open(file, "r") as f:
                st.write(f"Latest {label}:", [line.strip() for line in f.readlines()[-5:]])
        except FileNotFoundError:
            st.write(f"No {label.lower()} yet.")

# Agent decisions
st.subheader("AI Trading Decisions")
st.write("Multi-agent system with blockchain execution.")
try:
    with open("decisions.log", "r") as f:
        decisions = [line.strip().split(',', 4) for line in f.readlines()[-5:]]
    for decision in decisions:
        timestamp, symbol, action, explanation, tx_hash = decision
        st.write(f"**{timestamp} - {symbol}: {action}**")
        st.write(f"- Explanation: {explanation}")
        st.write(f"- PHS: {decision[4] if len(decision) > 4 else 'N/A'}")
        if len(decision) > 5 and decision[5]:
            st.write(f"- [Transaction](https://sepolia.etherscan.io/tx/{decision[5]})")
except FileNotFoundError:
    st.write("No decisions yet.")

# Query interface
st.subheader("Ask TradeSmart AI")
query = st.text_input("E.g., 'Should I sell TCS.BSE?'")
if query:
    # Replace with your Render URL post-deployment
    render_url = "https://your-app.onrender.com/query"
    response = requests.post(render_url, json={"query": query})
    st.write(f"Answer: {response.json().get('answer', 'Error occurred')}")
st.sidebar.write("Status: Real-time trading active")
