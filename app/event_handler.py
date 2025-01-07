import json
import asyncio
from nats.aio.client import Client as NATS
from datetime import datetime
from .models import Event, GameState, Player, Food
from .event_store import EventStore

class EventHandler:
    def __init__(self, nats_url: str, event_store: EventStore):
        self.nats_url = nats_url
        self.event_store = event_store
        self.nc = NATS()
        self.game_states = {}  # Keep track of current state for each game

    async def connect(self):
        """Connect to NATS server"""
        await self.nc.connect(self.nats_url)
        
        # Subscribe to all game events
        await self.nc.subscribe(
            "game.events.*",
            cb=self.handle_game_message
        )

    async def handle_game_message(self, msg):
        """Handle incoming game messages"""
        try:
            data = json.loads(msg.data.decode())
            game_id = msg.subject.split('.')[-1]  # Extract game_id from subject
            
            # Get or create game state
            if game_id not in self.game_states:
                self.game_states[game_id] = GameState(players=[], food=[])
            
            current_state = self.game_states[game_id]
            
            # Update state based on message type
            msg_type = data["type"]
            msg_data = data["data"]
            
            if msg_type == "gameState":
                # Full state update
                current_state.players = [Player(**p) for p in msg_data["players"]]
                current_state.food = [Food(**f) for f in msg_data["food"]]
                
            elif msg_type == "update":
                # Update specific players and food
                player_map = {p.name: p for p in current_state.players}
                
                # Update players
                for player_data in msg_data.get("players", []):
                    player = Player(**player_data)
                    player_map[player.name] = player
                current_state.players = list(player_map.values())
                
                # Update food
                food_map = {f.index: f for f in current_state.food}
                for food_data in msg_data.get("food", []):
                    food = Food(**food_data)
                    food_map[food.index] = food
                current_state.food = list(food_map.values())
                
            elif msg_type == "spawn":
                # Add new player
                new_player = Player(**msg_data)
                current_state.players.append(new_player)
            
            # Store the updated state
            sequence = await self.event_store.get_latest_sequence(game_id) + 1
            event = Event(
                game_id=game_id,
                sequence=sequence,
                timestamp=datetime.now(),
                state=current_state
            )
            await self.event_store.store_event(event)
            
        except Exception as e:
            print(f"Error handling game message: {e}")

    async def close(self):
        """Close NATS connection"""
        await self.nc.close()
