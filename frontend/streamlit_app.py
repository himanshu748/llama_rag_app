import streamlit as st
import requests
import jsonlines
import pandas as pd
import os

# Ensure data directories exist
os.makedirs("data/portfolios", exist_ok=True)
os.makedirs("data/news", exist_ok=True)
os.makedirs("data/stock_ticks", exist_ok=True)
os.makedirs("data/crypto_ticks", exist_ok=True)
os.makedirs("data/chainlink_data", exist_ok=True)

st.title("Intraday & Crypto RAG Dashboard")
st.write("Powered by Pathway, Alpha Vantage, Binance, Chainlink, Uniswap, and Reactive Network")

# Portfolio upload
uploaded_file = st.file_uploader("Upload portfolio CSV (symbol, quantity, price)", type="csv")
if uploaded_file:
    df = pd.read_csv(uploaded_file)
    with jsonlines.open("data/portfolios/portfolio.jsonl", "a") as writer:
        for _, row in df.iterrows():
            writer.write({"symbol": row["symbol"], "quantity": int(row["quantity"]), "price": float(row["price"])})
    st.success("Portfolio ingested!")

# Live data feed
st.subheader("Live Data Feed")
st.write("Real-time updates from Alpha Vantage (stocks), Binance (crypto), Chainlink (oracles), and CoinGecko (Uniswap proxy)")
if st.button("Refresh"):
    try:
        with open("data/stock_ticks/alpha_vantage_ticks.jsonl", "r") as f:
            st.write("Latest Stock Ticks (Alpha Vantage):", [line.strip() for line in f.readlines()[-5:]])
    except FileNotFoundError:
        st.write("No stock ticks yet.")
    try:
        with open("data/crypto_ticks/binance_ticks.jsonl", "r") as f:
            st.write("Latest Crypto Ticks (Binance):", [line.strip() for line in f.readlines()[-5:]])
    except FileNotFoundError:
        st.write("No Binance ticks yet.")
    try:
        with open("data/crypto_ticks/coingecko_ticks.jsonl", "r") as f:
            st.write("Latest Uniswap Ticks (CoinGecko):", [line.strip() for line in f.readlines()[-5:]])
    except FileNotFoundError:
        st.write("No CoinGecko ticks yet.")
    try:
        with open("data/chainlink_data/chainlink_ticks.jsonl", "r") as f:
            st.write("Latest Chainlink Feeds:", [line.strip() for line in f.readlines()[-5:]])
    except FileNotFoundError:
        st.write("No Chainlink data yet.")
    try:
        with open("data/news/news.jsonl", "r") as f:
            st.write("Latest News:", [line.strip() for line in f.readlines()[-5:]])
    except FileNotFoundError:
        st.write("No news yet.")

# Agent decisions
st.subheader("Agentic AI Decisions")
st.write("Multi-agent system (Conservative, Aggressive, Balanced) with blockchain execution.")
try:
    with open("decisions.log", "r") as f:
        decisions = [line.strip().split(',', 4) for line in f.readlines()[-5:]]
    for decision in decisions:
        timestamp, symbol, action, explanation, tx_hash = decision
        st.write(f"**{timestamp} - {symbol}: {action}**")
        st.write(f"- Explanation: {explanation}")
        st.write(f"- PHS: {decision[4] if len(decision) > 4 else 'N/A'}")
        if len(decision) > 5 and decision[5]:
            st.write(f"- [Blockchain Transaction](https://sepolia.etherscan.io/tx/{decision[5]})")
except FileNotFoundError:
    st.write("No decisions yet.")

# Query interface
st.subheader("Ask the Agent")
query = st.text_input("Enter your question (e.g., 'Should I sell TCS.BSE?')")
if query:
    # Replace with your Render backend URL after deployment
    render_url = "https://your-app.onrender.com/query"  # Placeholder
    response = requests.post(render_url, json={"query": query})
    st.write(f"Answer: {response.json().get('answer', 'Error occurred')}")
st.sidebar.write("Status: Running with real-time data sync")