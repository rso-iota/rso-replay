from datetime import datetime
from typing import Any, Dict, Optional
from pydantic import BaseModel, Field

class Event(BaseModel):
    game_id: str
    sequence: int
    event_type: str
    payload: Dict[str, Any]
    timestamp: datetime = Field(default_factory=datetime.utcnow)

class GameState(BaseModel):
    game_id: str
    board: Dict[str, Any]  # Current game board state
    players: Dict[str, Any]  # Player information
    current_turn: Optional[str] = None
    status: str = "in_progress"
    last_updated: datetime = Field(default_factory=datetime.utcnow)

    def apply_event(self, event: Event) -> None:
        """Apply an event to the current state"""
        if event.event_type == "game_started":
            self.board = event.payload.get("initial_board", {})
            self.players = event.payload.get("players", {})
            self.current_turn = event.payload.get("first_turn")
            
        elif event.event_type == "move_made":
            # Update board with the new move
            move = event.payload.get("move", {})
            # Update board state based on move
            # This is a placeholder - actual implementation depends on game rules
            self.board.update(move)
            # Update current turn
            self.current_turn = event.payload.get("next_turn")
            
        elif event.event_type == "game_ended":
            self.status = "completed"
            self.current_turn = None
            
        self.last_updated = event.timestamp