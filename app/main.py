from fastapi import FastAPI, HTTPException
from datetime import datetime
from typing import Optional
from .models import GameState, Event
from .event_store import EventStore
from .event_handler import EventHandler
from .projector import Projector

app = FastAPI(title="RSO Replay Service")

# Configuration (should be moved to config file)
MONGO_URL = "mongodb://localhost:27017"
NATS_URL = "nats://localhost:4222"

# Initialize components
event_store = EventStore(MONGO_URL)
event_handler = EventHandler(NATS_URL, event_store)
projector = Projector(event_store)

@app.on_event("startup")
async def startup_event():
    """Connect to NATS on startup"""
    await event_handler.connect()

@app.on_event("shutdown")
async def shutdown_event():
    """Close NATS connection on shutdown"""
    await event_handler.close()

@app.get("/api/v1/replays/{game_id}")
async def get_replay(game_id: str) -> GameState:
    """Get current game state"""
    try:
        return await projector.reconstruct_state(game_id)
    except Exception as e:
        raise HTTPException(status_code=404, detail=str(e)) from e

@app.get("/api/v1/replays/{game_id}/events")
async def get_events(game_id: str) -> list[Event]:
    """Get all events for a game"""
    try:
        return await event_store.get_events(game_id)
    except Exception as e:
        raise HTTPException(status_code=404, detail=str(e)) from e

@app.get("/api/v1/replays/{game_id}/state/{timestamp}")
async def get_state_at_time(
    game_id: str,
    timestamp: datetime
) -> GameState:
    """Get game state at specific time"""
    try:
        return await projector.reconstruct_state(game_id, timestamp)
    except Exception as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
