import json
import asyncio
from nats.aio.client import Client as NATS
from .models import Event
from .event_store import EventStore

class EventHandler:
    def __init__(self, nats_url: str, event_store: EventStore):
        self.nats_url = nats_url
        self.event_store = event_store
        self.nc = NATS()

    async def connect(self):
        """Connect to NATS server"""
        await self.nc.connect(self.nats_url)
        
        # Subscribe to game events
        await self.nc.subscribe(
            "game.events.*",
            cb=self.handle_event
        )

    async def handle_event(self, msg):
        """Handle incoming game events"""
        try:
            # Parse event data
            data = json.loads(msg.data.decode())
            
            # Get the latest sequence number for this game
            game_id = data.get("game_id")
            sequence = await self.event_store.get_latest_sequence(game_id) + 1
            
            # Create and store event
            event = Event(
                game_id=game_id,
                sequence=sequence,
                event_type=data.get("event_type"),
                payload=data.get("payload", {})
            )
            
            await self.event_store.store_event(event)
            
        except Exception as e:
            print(f"Error handling event: {e}")

    async def close(self):
        """Close NATS connection"""
        await self.nc.close()