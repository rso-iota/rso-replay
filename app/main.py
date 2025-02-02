import asyncio
from datetime import datetime
from typing import Optional, Dict
import logging

from fastapi import FastAPI, HTTPException, BackgroundTasks, Response, status
from fastapi.responses import FileResponse

from .config.settings import Settings
from .config.logging_config import setup_logging
from .models import GameState
from .event_store import EventStore
from .event_handler import EventHandler
from .projector import Projector
from .renderer import GameRenderer

# Load settings
settings = Settings()

# Set up logging
setup_logging(settings)
logger = logging.getLogger(__name__)

# Create FastAPI app
app = FastAPI(
    title=settings.service_name,
    version=settings.api_version,
    docs_url="/api/v1/replays/public/docs",  # Modified docs endpoint,
    openapi_url="/api/v1/replays/public/openapi.json",  # Modified OpenAPI endpoint
    redoc_url=None  # Disable ReDoc
)

# Create directories
settings.temp_dir.mkdir(exist_ok=True)
settings.frames_dir.mkdir(exist_ok=True)
settings.videos_dir.mkdir(exist_ok=True)

# Initialize components
event_store = EventStore(settings.mongo_url)
renderer = GameRenderer(
    width=settings.video_width,
    height=settings.video_height,
    game_width=settings.game_width,
    game_height=settings.game_height,
    background_color=settings.background_color,
    player_colors=settings.player_colors,
    food_color=settings.food_color,
    use_player_skins=settings.use_player_skins,
)
projector = Projector(event_store, renderer)
event_handler = EventHandler(settings.nats_url, event_store)

async def try_connect_nats():
    """Try to connect to NATS with retries"""
    while True:
        try:
            await event_handler.connect()
            logger.info({"message": "Successfully connected to NATS"})
            break
        except Exception as e:
            logger.warning({"message": f"Failed to connect to NATS: {str(e)}"})
            await asyncio.sleep(5)  # Wait 5 seconds before retrying

@app.on_event("startup")
async def startup_event():
    """Start the service and attempt NATS connection in background"""
    logger.info({"message": "Starting up replay service"})
    # Start NATS connection attempt in the background
    asyncio.create_task(try_connect_nats())

@app.on_event("shutdown")
async def shutdown_event():
    """Close NATS connection on shutdown"""
    logger.info({"message": "Shutting down replay service"})
    await event_handler.close()

@app.get("/health/live", status_code=status.HTTP_200_OK)
async def liveness_check() -> Dict:
    """
    Liveness probe - checks if the service is running
    Returns 200 if the service is alive
    """
    return {
        "status": "alive",
        "service": settings.service_name,
        "timestamp": datetime.utcnow().isoformat()
    }

@app.get("/health/ready", status_code=status.HTTP_200_OK)
async def readiness_check() -> Dict:
    """
    Readiness probe - checks if the service can handle requests
    Verifies connections to NATS and MongoDB
    """
    # Check NATS connection
    if not event_handler.nc or not event_handler.nc.is_connected:
        return Response(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content="NATS connection not ready"
        )
    
    # Check MongoDB connection with timeout
    try:
        await asyncio.wait_for(
            event_store.client.admin.command('ping'),
            timeout=3.0  # 3 seconds timeout
        )
    except asyncio.TimeoutError:
        return Response(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content="MongoDB ping timed out after 3 seconds"
        )
    except Exception as e:
        return Response(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content=f"MongoDB not responding: {str(e)}"
        )

    return {
        "status": "ready",
        "service": settings.service_name,
        "timestamp": datetime.utcnow().isoformat(),
        "dependencies": {
            "nats": "connected",
            "mongodb": "connected",
        }
    }

@app.get(f"/api/{settings.api_version}/replays/{{game_id}}/states")
async def get_game_states(
    game_id: str,
    from_time: Optional[datetime] = None,
    to_time: Optional[datetime] = None
) -> list[GameState]:
    """Get all game states for a game"""
    try:
        logger.info({"message": f"Getting game states for game {game_id}"})
        return await projector.get_game_states(game_id, from_time, to_time)
    except Exception as e:
        logger.error({"message": f"Error getting game states: {str(e)}"})
        raise HTTPException(status_code=404, detail=str(e))

@app.get(f"/api/{settings.api_version}/replays/{{game_id}}/video")
async def get_replay_video(
    game_id: str,
    background_tasks: BackgroundTasks,
    fps: int = settings.default_fps,
    speed: float = 3.0,  # Added speed multiplier parameter
    from_time: Optional[datetime] = None,
    to_time: Optional[datetime] = None
):
    """
    Get video replay of a game
    
    Parameters:
        game_id: ID of the game to replay
        fps: Target frames per second for the video
        speed: Speed multiplier (1.0 = normal speed, 2.0 = double speed, 0.5 = half speed)
        from_time: Optional start time to slice the replay
        to_time: Optional end time to slice the replay
    """
    if speed <= 0:
        raise HTTPException(status_code=400, detail="Speed multiplier must be positive")
        
    try:
        logger.info({"message": f"Generating video for game {game_id} at {speed}x speed"})
        
        # Set up paths for this video
        video_name = f"replay_{game_id}_{datetime.utcnow().timestamp()}"
        frames_dir = settings.frames_dir / video_name
        video_path = settings.videos_dir / f"{video_name}.mp4"
        
        # Generate video
        await projector.create_replay_video(
            game_id=game_id,
            output_path=video_path,
            frames_path=frames_dir,
            fps=fps,
            speed=speed,
            from_time=from_time,
            to_time=to_time
        )
        
        logger.info({"message": f"Video generated successfully at {video_path}"})
        
        # Add cleanup task
        background_tasks.add_task(video_path.unlink)
        
        # Return video file
        return FileResponse(
            path=video_path,
            media_type="video/mp4",
            filename=f"replay_{game_id}.mp4"
        )
    except Exception as e:
        logger.error({"message": f"Error generating video: {str(e)}"})
        raise HTTPException(status_code=404, detail=str(e))
