from pathlib import Path
import tempfile
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from datetime import datetime
from typing import Optional
from .models import GameState, Event
from .event_store import EventStore
from .event_handler import EventHandler
from .projector import Projector
from .renderer import GameRenderer

app = FastAPI(title="RSO Replay Service")

# Configuration (should be moved to config file)
MONGO_URL = "mongodb://localhost:27017"
NATS_URL = "nats://localhost:4222"
TEMP_DIR = Path(tempfile.gettempdir()) / "rso-replay"
TEMP_DIR.mkdir(exist_ok=True)

# Initialize components
event_store = EventStore(MONGO_URL)
renderer = GameRenderer(width=800, height=600)
projector = Projector(event_store, renderer)
event_handler = EventHandler(NATS_URL, event_store)

@app.on_event("startup")
async def startup_event():
    """Connect to NATS on startup"""
    await event_handler.connect()

@app.on_event("shutdown")
async def shutdown_event():
    """Close NATS connection on shutdown"""
    await event_handler.close()

@app.get("/api/v1/replays/{game_id}/states")
async def get_game_states(
    game_id: str,
    from_time: Optional[datetime] = None,
    to_time: Optional[datetime] = None
) -> list[GameState]:
    """Get all game states for a game"""
    try:
        return await projector.get_game_states(game_id, from_time, to_time)
    except Exception as e:
        raise HTTPException(status_code=404, detail=str(e))

@app.get("/api/v1/replays/{game_id}/video")
async def get_replay_video(
    game_id: str,
    fps: int = 30,
    from_time: Optional[datetime] = None,
    to_time: Optional[datetime] = None
):
    """Get video replay of a game"""
    try:
        # Create temporary file for video
        output_path = TEMP_DIR / f"{game_id}_{datetime.utcnow().timestamp()}.mp4"
        
        # Generate video
        await projector.create_replay_video(
            game_id=game_id,
            output_path=output_path,
            fps=fps,
            from_time=from_time,
            to_time=to_time
        )
        
        # Return video file
        return FileResponse(
            path=output_path,
            media_type="video/mp4",
            filename=f"replay_{game_id}.mp4"
        )
    except Exception as e:
        raise HTTPException(status_code=404, detail=str(e))