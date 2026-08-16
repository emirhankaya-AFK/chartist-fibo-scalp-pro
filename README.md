# Chartist Fibo-Scalp Pro

[English](README.md) | [Türkçe](README_TR.md)

A local decision-support dashboard that scores BIST 30 stocks using the latest completed official trading-session close.

## Run locally

```powershell
pip install -r requirements.txt
python server.py
```

Open `http://127.0.0.1:8080`. Opening `index.html` directly does not start the data API.

## Data policy

- Current price, OHLC, volume, and BIST 30 membership: Borsa İstanbul official daily bulletin
- BIST 100 close: Borsa İstanbul's 15-minute delayed data service
- One-year indicator history: Yahoo Finance
- Financial/KAP data: not connected yet and weighted at 0%
- If an official closing bulletin cannot be found, the model enters safe mode and does not suggest a position

Displayed prices are not real time; they represent the official close of the latest completed session.

## Position score

- Technical strength: 78%
- Entry timing: 14%
- Stop safety: 8%
- Financial quality: 0% until a verified KAP integration is available

An `ENTRY SUITABLE` decision also requires the trend, ADX, direction, relative strength, risk, and entry-zone thresholds to pass. Virtual position planning is disabled for `WAIT` and `DO NOT OPEN` states.

## Included features

- Dynamic BIST 30 universe sourced from the official bulletin
- Price, OHLC, and volume verification against official closing data
- Explainable technical scoring and conditional entry decisions
- Search, filters, and sortable columns
- Dynamic strategy figures and a BIST 30 sector heat map
- CSV export and a local virtual portfolio for eligible candidates
- Safe failure behavior that never fabricates prices

> This application is not investment advice. No success percentage is shown because the backtest win rate has not been independently verified.

