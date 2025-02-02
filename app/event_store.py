from typing import List, Optional
from motor.motor_asyncio import AsyncIOMotorClient
from .models import Event
import pybreaker

# Simple circuit breaker for MongoDB operations
mongo_breaker = pybreaker.CircuitBreaker(fail_max=5, reset_timeout=60)

class EventStore:
    def __init__(self, mongo_url: str):
        self.client = AsyncIOMotorClient(mongo_url)
        self.db = self.client.replay_db
        self.events = self.db.events

    @mongo_breaker
    async def store_event(self, event: Event) -> None:
        """Store a new event in the database"""
        await self.events.insert_one(event.model_dump())

    @mongo_breaker
    async def get_events(self, game_id: str) -> List[Event]:
        """Get all events for a game ordered by sequence"""
        cursor = self.events.find({"game_id": game_id}).sort("sequence", 1)
        events = []
        async for doc in cursor:
            events.append(Event(**doc))
        return events

    @mongo_breaker
    async def get_latest_sequence(self, game_id: str) -> int:
        """Get the latest sequence number for a game"""
        result = await self.events.find_one(
            {"game_id": game_id},
            sort=[("sequence", -1)]
        )
        return result["sequence"] if result else -1
