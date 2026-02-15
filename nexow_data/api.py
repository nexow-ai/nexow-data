"""FastAPI application for nexow-data service."""

import asyncio
from contextlib import asynccontextmanager
from datetime import datetime

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import structlog

from nexow_data.config import settings
from nexow_data.oanda import OandaClient
from nexow_data.poller import MarketDataPoller

logger = structlog.get_logger(__name__)

# Global instances
oanda_client: OandaClient | None = None
poller: MarketDataPoller | None = None
poller_task: asyncio.Task | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifecycle."""
    global oanda_client, poller, poller_task
    
    # Startup
    logger.info("nexow_data_starting", environment=settings.environment)
    oanda_client = OandaClient()
    poller = MarketDataPoller()
    
    # Start background poller
    poller_task = asyncio.create_task(poller.start())
    
    logger.info("nexow_data_started", port=settings.port)
    
    yield
    
    # Shutdown
    logger.info("nexow_data_stopping")
    if poller:
        await poller.stop()
    if poller_task:
        poller_task.cancel()
        try:
            await poller_task
        except asyncio.CancelledError:
            pass
    if oanda_client:
        await oanda_client.close()
    logger.info("nexow_data_stopped")


app = FastAPI(
    title="Nexow Data Service",
    description="Market data aggregator - Oanda API client and Redis pub/sub",
    version="0.1.0",
    lifespan=lifespan,
)


# ============================================================================
# Health & Status
# ============================================================================


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "service": "nexow-data"}


@app.get("/status")
async def get_status():
    """Get service status and configuration."""
    return {
        "service": "nexow-data",
        "version": "0.1.0",
        "environment": settings.environment,
        "poll_interval": settings.poll_interval_seconds,
        "instruments": settings.instruments,
        "redis_channel": settings.redis_channel,
    }


# ============================================================================
# Market Data Endpoints
# ============================================================================


class PriceResponse(BaseModel):
    """Price response model."""
    instrument: str
    price: float
    timestamp: str


class CandlesRequest(BaseModel):
    """Request model for fetching candles."""
    instrument: str
    granularity: str = "M5"
    count: int = 100


class CandlesRangeRequest(BaseModel):
    """Request model for fetching candles in a date range."""
    instrument: str
    granularity: str
    from_time: str
    to_time: str


@app.get("/prices/{instrument}")
async def get_price(instrument: str) -> PriceResponse:
    """Get current price for an instrument."""
    if not oanda_client:
        raise HTTPException(status_code=503, detail="Service not ready")
    
    try:
        price = await oanda_client.get_price(instrument)
        return PriceResponse(
            instrument=instrument,
            price=price,
            timestamp=datetime.utcnow().isoformat(),
        )
    except Exception as e:
        logger.error("get_price_failed", instrument=instrument, error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/prices")
async def get_prices(instruments: str):
    """Get current prices for multiple instruments (comma-separated)."""
    if not oanda_client:
        raise HTTPException(status_code=503, detail="Service not ready")
    
    try:
        instrument_list = [i.strip() for i in instruments.split(",")]
        prices = await oanda_client.get_prices(instrument_list)
        
        return {
            "prices": prices,
            "timestamp": datetime.utcnow().isoformat(),
        }
    except Exception as e:
        logger.error("get_prices_failed", instruments=instruments, error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/candles")
async def get_candles(request: CandlesRequest):
    """Fetch recent candles for an instrument."""
    if not oanda_client:
        raise HTTPException(status_code=503, detail="Service not ready")
    
    try:
        candles = await oanda_client.get_candles(
            instrument=request.instrument,
            granularity=request.granularity,
            count=request.count,
        )
        return {
            "instrument": request.instrument,
            "granularity": request.granularity,
            "candles": [c.model_dump() for c in candles],
        }
    except Exception as e:
        logger.error("get_candles_failed", request=request.model_dump(), error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/candles/range")
async def get_candles_range(request: CandlesRangeRequest):
    """Fetch candles for a date range."""
    if not oanda_client:
        raise HTTPException(status_code=503, detail="Service not ready")
    
    try:
        from_time = datetime.fromisoformat(request.from_time)
        to_time = datetime.fromisoformat(request.to_time)
        
        candles = await oanda_client.get_candles_range(
            instrument=request.instrument,
            granularity=request.granularity,
            from_time=from_time,
            to_time=to_time,
        )
        
        return {
            "instrument": request.instrument,
            "granularity": request.granularity,
            "from_time": request.from_time,
            "to_time": request.to_time,
            "candles": [c.model_dump() for c in candles],
            "count": len(candles),
        }
    except Exception as e:
        logger.error("get_candles_range_failed", request=request.model_dump(), error=str(e))
        raise HTTPException(status_code=500, detail=str(e))
