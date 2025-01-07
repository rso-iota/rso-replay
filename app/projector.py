from typing import Optional
from datetime import datetime
from .models import GameState, Event
from .event_store import EventStore

class Projector:
    def __init__(self, event_store: EventStore):
        self.event_store = event_store

    async def reconstruct_state(self, game_id: str, until_time: Optional[datetime] = None) -> GameState:
        """Reconstruct game state by replaying events"""
        events = await self.event_store.get_events(game_id)
        
        # Initialize empty state
        state = GameState(
            game_id=game_id,
            board={},
            players={},
        )

        # Apply each event in sequence
        for event in events:
            if until_time and event.timestamp > until_time:
                break
            state.apply_event(event)

        return state