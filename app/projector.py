from pathlib import Path
from typing import List, Optional
from datetime import datetime
from .models import GameState, Event
from .event_store import EventStore
from .renderer import GameRenderer
from .interpolator import interpolate_game_states

class Projector:
    def __init__(self, event_store: EventStore, renderer: GameRenderer):
        self.event_store = event_store
        self.renderer = renderer

    async def get_game_states(
        self, 
        game_id: str, 
        from_time: Optional[datetime] = None,
        to_time: Optional[datetime] = None
    ) -> List[GameState]:
        """Get all game states for a game within the specified time range"""
        events = await self.event_store.get_events(game_id)
        
        # Filter events by time range if specified
        if from_time:
            events = [e for e in events if e.timestamp >= from_time]
        if to_time:
            events = [e for e in events if e.timestamp <= to_time]
            
        return [event.state for event in events]

    async def create_replay_video(
        self,
        game_id: str,
        output_path: Path,
        frames_path: Path,
        fps: int = 30,
        speed: float = 3.0,
        from_time: Optional[datetime] = None,
        to_time: Optional[datetime] = None
    ) -> Path:
        """
        Create a video replay of the game
        
        Parameters:
            game_id: ID of the game to replay
            output_path: Path where to save the video
            frames_path: Path where to store temporary frame images
            fps: Target frames per second
            speed: Speed multiplier (1.0 = normal speed, 2.0 = double speed, etc)
            from_time: Optional start time
            to_time: Optional end time
        """
        states = await self.get_game_states(game_id, from_time, to_time)
        if not states:
            raise ValueError(f"No game states found for game {game_id}")
        
        # Interpolate states to achieve target FPS
        interpolated_states = interpolate_game_states(states, fps, speed)
            
        return await self.renderer.create_video(
            states=interpolated_states,
            output_path=output_path,
            frames_path=frames_path,
            fps=fps
        )
