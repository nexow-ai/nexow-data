# nexow-data

Market data service for Nexow - Oanda API client and Redis pub/sub broadcaster.

## Purpose

Single point of contact with Oanda API to:
- Avoid rate limits
- Centralize data fetching
- Broadcast live prices via Redis pub/sub
- Provide historical data on-demand

## Features

- **Real-time price polling**: Fetches prices every 5 seconds from Oanda
- **Redis pub/sub**: Broadcasts prices to all subscribers
- **REST API**: On-demand candle and price data
- **Historical data**: Fetch candles for any date range

## API Endpoints

### Health
- `GET /health` - Health check
- `GET /status` - Service status and configuration

### Market Data
- `GET /prices/{instrument}` - Get current price for one instrument
- `GET /prices?instruments=EUR_USD,GBP_USD` - Get multiple prices
- `POST /candles` - Fetch recent candles
- `POST /candles/range` - Fetch historical candles for date range

## Environment Variables

```bash
# Oanda API
OANDA_API_URL=https://api-fxpractice.oanda.com
OANDA_ACCOUNT_ID=your_account_id
OANDA_API_TOKEN=your_api_token

# Redis
REDIS_URL=redis://localhost:6379
REDIS_CHANNEL=nexow:market:prices

# Polling
POLL_INTERVAL_SECONDS=5
INSTRUMENTS=EUR_USD,GBP_USD,USD_JPY
```

## Development

```bash
# Install dependencies
pip install -e .

# Run service
uvicorn nexow_data.api:app --host 0.0.0.0 --port 8001 --reload
```

## Docker/Railway Deployment

```bash
# Railway will auto-detect and deploy
# Start command: uvicorn nexow_data.api:app --host 0.0.0.0 --port $PORT
```

## Redis Pub/Sub Format

Price updates are published as JSON:

```json
{
  "timestamp": "2026-02-15T18:00:00.000000",
  "prices": {
    "EUR_USD": 1.0850,
    "GBP_USD": 1.2650,
    "USD_JPY": 148.50
  }
}
```

Subscribe in other services:

```python
import redis.asyncio as redis
import json

redis_client = redis.from_url("redis://localhost:6379", decode_responses=True)
pubsub = redis_client.pubsub()
await pubsub.subscribe("nexow:market:prices")

async for message in pubsub.listen():
    if message["type"] == "message":
        data = json.loads(message["data"])
        prices = data["prices"]
        # Handle price update
```

## Architecture

```
Oanda API
    ↓ (poll every 5s)
nexow-data (this service)
    ↓ Redis pub/sub
┌─────────┬─────────┬─────────────┐
workers   api    backtesting    ...
```

## Version

0.1.0
