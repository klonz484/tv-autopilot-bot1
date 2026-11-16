# TradingView Autopilot Bot

Live webhook bot that receives TradingView alerts and executes trades via ccxt.

Based on the 5 free repos from the msbintel reel:

1. **tvdatafeed** – TradingView historical data
2. **TA-Lib** – Technical indicators
3. **smart-money-concepts** – FVGs, Order Blocks, Liquidity
4. **PyneCore** – Run Pine Script in Python
5. **tradingview-webhooks-bot** – Webhook framework

## Quick Deploy on Railway / Render

1. Connect this repository
2. Add the environment variables listed in `.env.example`
3. Deploy

## Local Run

```bash
pip install -r requirements.txt
python src/live_bot.py
```

## Webhook

- Endpoint: `POST /webhook`
- Health check: `GET /health`

### Example TradingView Alert Message

```json
{
  "key": "your_webhook_key",
  "action": "long",
  "symbol": "BTC/USDT",
  "message": "Bullish FVG setup"
}
```

Supported actions: `long`, `short`, `close`

## Important

Always start with `EXCHANGE_TESTNET=true` and test thoroughly before using real funds.
