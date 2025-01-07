from pathlib import Path
import tempfile
from fastapi import FastAPI, HTTPException, BackgroundTasks
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

# Set up temporary directories
TEMP_DIR = Path(tempfile.gettempdir()) / "rso-replay"
FRAMES_DIR = TEMP_DIR / "frames"
VIDEOS_DIR = TEMP_DIR / "videos"

# Create directories
TEMP_DIR.mkdir(exist_ok=True)
FRAMES_DIR.mkdir(exist_ok=True)
VIDEOS_DIR.mkdir(exist_ok=True)

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
    background_tasks: BackgroundTasks,  # Add this parameter
    fps: int = 30,
    from_time: Optional[datetime] = None,
    to_time: Optional[datetime] = None
):
    """Get video replay of a game"""
    try:
        # Set up paths for this video
        video_name = f"replay_{game_id}_{datetime.utcnow().timestamp()}"
        frames_dir = FRAMES_DIR / video_name
        video_path = VIDEOS_DIR / f"{video_name}.mp4"
        
        # Generate video
        await projector.create_replay_video(
            game_id=game_id,
            output_path=video_path,
            frames_path=frames_dir,
            fps=fps,
            from_time=from_time,
            to_time=to_time
        )
        
        # Add deletion task to background tasks
        background_tasks.add_task(video_path.unlink)
        
        # Return video file
        return FileResponse(
            path=video_path,
            media_type="video/mp4",
            filename=f"replay_{game_id}.mp4"
        )
    except Exception as e:
        raise HTTPException(status_code=404, detail=str(e))
