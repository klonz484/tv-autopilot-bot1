"""
Live TradingView Webhook Bot
Optimized for free cloud deployment (Railway / Render / Fly.io)
"""
from __future__ import annotations

import os
from datetime import datetime
from flask import Flask, request, jsonify
from loguru import logger
import ccxt
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)

# -------------------- Config from environment --------------------
WEBHOOK_KEY = os.getenv("WEBHOOK_KEY", "change_me_immediately")
EXCHANGE_ID = os.getenv("EXCHANGE_ID", "binance")
EXCHANGE_API_KEY = os.getenv("EXCHANGE_API_KEY", "")
EXCHANGE_SECRET = os.getenv("EXCHANGE_SECRET", "")
EXCHANGE_PASSWORD = os.getenv("EXCHANGE_PASSWORD", "")
EXCHANGE_TESTNET = os.getenv("EXCHANGE_TESTNET", "true").lower() == "true"
RISK_PER_TRADE = float(os.getenv("RISK_PER_TRADE", "0.01"))


def create_exchange():
    """Create ccxt exchange instance (testnet by default)."""
    if not EXCHANGE_API_KEY or not EXCHANGE_SECRET:
        return None

    exchange_class = getattr(ccxt, EXCHANGE_ID)
    params = {
        "apiKey": EXCHANGE_API_KEY,
        "secret": EXCHANGE_SECRET,
        "enableRateLimit": True,
        "options": {"defaultType": "future"},  # change to "spot" if you want spot
    }
    if EXCHANGE_PASSWORD:
        params["password"] = EXCHANGE_PASSWORD

    exchange = exchange_class(params)

    if EXCHANGE_TESTNET and hasattr(exchange, "set_sandbox_mode"):
        exchange.set_sandbox_mode(True)
        logger.warning("Running in TESTNET / sandbox mode")

    return exchange


exchange = create_exchange()
if exchange:
    logger.success(f"Connected to {EXCHANGE_ID}")
else:
    logger.warning("No exchange API keys – signals will only be logged")


def verify_key(data: dict) -> bool:
    return data.get("key") == WEBHOOK_KEY


def size_position(symbol: str, stop_distance_pct: float = 0.01) -> float:
    """Risk-based position sizing."""
    if exchange is None:
        return 0.0
    try:
        balance = exchange.fetch_balance()
        equity = (
            balance.get("USDT", {}).get("free")
            or balance.get("total", {}).get("USDT")
            or 0
        )
        risk_amount = float(equity) * RISK_PER_TRADE
        ticker = exchange.fetch_ticker(symbol)
        price = ticker["last"]
        stop_dist = price * stop_distance_pct
        amount = risk_amount / stop_dist
        return float(exchange.amount_to_precision(symbol, amount))
    except Exception as e:
        logger.error(f"Sizing error: {e}")
        return 0.0


@app.route("/", methods=["GET"])
def home():
    return jsonify({
        "service": "TradingView Autopilot Bot",
        "status": "running",
        "exchange": EXCHANGE_ID if exchange else None,
        "testnet": EXCHANGE_TESTNET,
        "endpoints": {
            "webhook": "/webhook  (POST)",
            "health": "/health   (GET)"
        }
    })


@app.route("/health", methods=["GET"])
def health():
    return jsonify({
        "status": "ok",
        "exchange": EXCHANGE_ID if exchange else None,
        "testnet": EXCHANGE_TESTNET,
        "time": datetime.utcnow().isoformat() + "Z",
    })


@app.route("/webhook", methods=["POST"])
def webhook():
    """
    Expected JSON from TradingView:
    {
        "key": "your_secret_key",
        "action": "long" | "short" | "close",
        "symbol": "BTC/USDT",
        "message": "optional note"
    }
    """
    try:
        data = request.get_json(force=True, silent=True) or {}
    except Exception:
        return jsonify({"error": "invalid json"}), 400

    logger.info(f"Webhook received: {data}")

    if not verify_key(data):
        logger.warning("Invalid webhook key")
        return jsonify({"error": "unauthorized"}), 401

    action = str(data.get("action", "")).lower().strip()
    symbol = data.get("symbol", "BTC/USDT")
    message = data.get("message", "")

    # Only log mode
    if exchange is None:
        logger.info(f"[LOG ONLY] {action.upper()} {symbol} | {message}")
        return jsonify({
            "status": "logged",
            "action": action,
            "symbol": symbol,
            "message": message
        })

    try:
        if action in ("long", "buy"):
            amount = size_position(symbol)
            if amount <= 0:
                return jsonify({"error": "could not calculate size"}), 400
            order = exchange.create_market_buy_order(symbol, amount)
            logger.success(f"LONG {amount} {symbol} → order {order.get('id')}")
            return jsonify({"status": "filled", "side": "buy", "amount": amount, "order_id": order.get("id")})

        elif action in ("short", "sell"):
            amount = size_position(symbol)
            if amount <= 0:
                return jsonify({"error": "could not calculate size"}), 400
            order = exchange.create_market_sell_order(symbol, amount)
            logger.success(f"SHORT {amount} {symbol} → order {order.get('id')}")
            return jsonify({"status": "filled", "side": "sell", "amount": amount, "order_id": order.get("id")})

        elif action in ("close", "flat"):
            positions = exchange.fetch_positions([symbol])
            closed = []
            for pos in positions:
                contracts = float(pos.get("contracts") or 0)
                if contracts > 0:
                    side = "sell" if pos.get("side") == "long" else "buy"
                    order = exchange.create_market_order(symbol, side, contracts)
                    closed.append(order.get("id"))
                    logger.success(f"CLOSED {contracts} {symbol}")
            if closed:
                return jsonify({"status": "closed", "orders": closed})
            return jsonify({"status": "no_position"})

        else:
            return jsonify({"error": f"unknown action: {action}"}), 400

    except Exception as e:
        logger.exception("Order execution failed")
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    logger.info(f"Starting bot on port {port}")
    app.run(host="0.0.0.0", port=port, debug=False)
