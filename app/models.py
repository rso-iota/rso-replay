from datetime import datetime
from typing import List, Optional, Dict
from pydantic import BaseModel, Field

class Circle(BaseModel):
    x: float
    y: float
    radius: float

class Food(BaseModel):
    index: int
    circle: Circle

class Player(BaseModel):
    name: str
    alive: bool
    circle: Circle

class GameState(BaseModel):
    players: List[Player]
    food: List[Food]

class Event(BaseModel):
    game_id: str
    sequence: int
    timestamp: datetime = Field(default_factory=datetime.now(datetime.timezone.utc))
    state: GameState

    class Config:
        json_schema_extra = {
            "example": {
                "game_id": "game123",
                "sequence": 1,
                "timestamp": "2024-01-07T12:00:00Z",
                "state": {
                    "players": [
                        {
                            "name": "Player1",
                            "alive": True,
                            "circle": {
                                "x": 100,
                                "y": 100,
                                "radius": 10
                            }
                        }
                    ],
                    "food": [
                        {
                            "index": 0,
                            "circle": {
                                "x": 200,
                                "y": 200,
                                "radius": 5
                            }
                        }
                    ]
                }
            }
        }
