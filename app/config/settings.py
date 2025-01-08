from pathlib import Path
import tempfile
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field, validator

class Settings(BaseSettings):
    """Application settings"""
    # Service name and version
    service_name: str = Field("rso-replay", description="Service name")
    api_version: str = Field("v1", description="API version")
    
    # Server settings
    host: str = Field("0.0.0.0", description="Server host")
    port: int = Field(8000, description="Server port")
    
    # Database settings
    mongo_url: str = Field("mongodb://localhost:27017", description="MongoDB connection URL")
    mongo_db: str = Field("replay_service", description="MongoDB database name")
    
    # NATS settings
    nats_url: str = Field("nats://localhost:4222", description="NATS connection URL")
    nats_subject: str = Field("game_state.*", description="NATS subject to subscribe to")
    
    # Game dimensions (actual play area)
    game_width: float = Field(800.0, description="Game width in game units")
    game_height: float = Field(600.0, description="Game height in game units")
    
    # Video settings (output video dimensions)
    video_width: int = Field(400, description="Video width in pixels")
    video_height: int = Field(300, description="Video height in pixels")
    default_fps: int = Field(30, description="Default video FPS")
    source_fps: int = Field(2, description="Source game state FPS")
    
    # File storage settings
    temp_dir: Path = Field(
        default_factory=lambda: Path(tempfile.gettempdir()) / "rso-replay",
        description="Base temporary directory"
    )
    frames_dir: Path = Field(None, description="Directory for temporary frame storage")
    videos_dir: Path = Field(None, description="Directory for temporary video storage")
    
    # Colors settings
    background_color: str = Field("black", description="Video background color")
    food_color: str = Field("white", description="Food item color")
    player_colors: list[str] = Field(
        default=["red", "blue", "green", "yellow", "purple"],
        description="Player colors"
    )
    
    # Logging settings
    log_level: str = Field("INFO", description="Logging level")
    
    # Health check
    health_check_interval: int = Field(30, description="Health check interval in seconds")
    
    @validator("frames_dir", "videos_dir", pre=True, always=True)
    def set_dirs(cls, v, values):
        """Set frames and videos directories based on temp_dir if not provided"""
        if v is None:
            temp_dir = values.get("temp_dir")
            if not temp_dir:
                raise ValueError("temp_dir must be set")
            return temp_dir / ("frames" if "frames" in values else "videos")
        return v
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_prefix="REPLAY_"
    )
