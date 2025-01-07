import json
from nats.aio.client import Client as NATS
from datetime import datetime
from .models import Event, GameState, Player, Food
from .event_store import EventStore

class EventHandler:
    def __init__(self, nats_url: str, event_store: EventStore):
        self.nats_url = nats_url
        self.event_store = event_store
        self.nc = NATS()

    async def connect(self):
        """Connect to NATS server"""
        await self.nc.connect(self.nats_url)
        
        # Subscribe to game state events
        await self.nc.subscribe(
            "game_state.*",  # Subject pattern from game service
            cb=self.handle_game_state
        )

    async def handle_game_state(self, msg):
        """Handle incoming game state message"""
        try:
            # Parse message
            data = json.loads(msg.data.decode())
            
            # Game ID is last part of subject (game.events.{game_id})
            game_id = msg.subject.split('.')[-1]
            
            # Extract state data from message
            if data["type"] != "gameState":
                return  # Skip non-gameState messages
                
            state_data = data["data"]
            
            # Create game state
            state = GameState(
                players=[Player(**p) for p in state_data["players"]],
                food=[Food(**f) for f in state_data["food"]]
            )
            
            # Store as new event
            sequence = await self.event_store.get_latest_sequence(game_id) + 1
            event = Event(
                game_id=game_id,
                sequence=sequence,
                timestamp=datetime.utcnow(),
                state=state
            )
            await self.event_store.store_event(event)
            
        except Exception as e:
            print(f"Error handling game state: {e}")

    async def close(self):
        """Close NATS connection"""
        await self.nc.close()
