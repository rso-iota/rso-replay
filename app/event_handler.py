import json
import asyncio
from nats.aio.client import Client as NATS
from datetime import datetime
from .models import Event, GameState, Player, Food, Circle
from .event_store import EventStore
import logging
logging.basicConfig(level=logging.INFO, format='{"time": "%(asctime)s", "level": "%(levelname)s", "message": "%(message)s"}')
logger = logging.getLogger(__name__)

class EventHandler:
    def __init__(self, nats_url: str, event_store: EventStore):
        self.nats_url = nats_url
        self.event_store = event_store
        self.nc = None
        self._connection_monitor_task = None
        self._should_monitor = True

    async def connect(self):
        """Connect to NATS server"""
        try:
            # Create new NATS client for each connection attempt
            if self.nc:
                await self.nc.close()
            self.nc = NATS()
            
            await self.nc.connect(self.nats_url)
            
            # Subscribe to game state events
            await self.nc.subscribe(
                "game_state.*",  # Subject pattern from game service
                cb=self.handle_game_state
            )
            
            # Start connection monitoring if not already running
            if not self._connection_monitor_task:
                self._connection_monitor_task = asyncio.create_task(self._monitor_connection())
                
            logger.info("Successfully connected to NATS")
        except Exception as e:
            logger.error(f"Failed to connect to NATS: {str(e)}")
            # Clean up failed connection
            if self.nc:
                try:
                    await self.nc.close()
                except:
                    pass
                self.nc = None
            raise

    async def _monitor_connection(self):
        """Monitor NATS connection and attempt reconnection if needed"""
        while self._should_monitor:
            try:
                if not self.nc or not self.nc.is_connected:
                    logger.warning("NATS connection lost, attempting to reconnect...")
                    try:
                        await self.connect()
                    except Exception as e:
                        logger.error(f"Reconnection attempt failed: {str(e)}")
            except Exception as e:
                logger.error(f"Error in connection monitor: {str(e)}")
            await asyncio.sleep(5)  # Check every 5 seconds

    async def handle_game_state(self, msg):
        """Handle incoming game state message"""
        try:
            logger.debug(f"Received message: {msg.subject}")
            # Parse message
            data = json.loads(msg.data.decode())
            
            # Game ID is last part of subject (game.events.{game_id})
            game_id = msg.subject.split('.')[-1]
            
            # Extract state data from message
            if data["type"] != "gameState":
                return  # Skip non-gameState messages
                
            state_data = data["data"]
            players = []
            for player in state_data["players"]:
                players.append(Player(
                    name=player["playerName"],
                    alive=player["alive"],
                    circle=Circle(**player["circle"])
                ))
            food = []
            for f in state_data["food"]:
                food.append(Food(
                    index=f["index"],
                    circle=Circle(**f["circle"])
                ))
            
            # Create game state
            state = GameState(
                players=players,
                food=food
            )
            
            logger.debug(f"Saving game state for game {game_id}")
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
            logger.error(f"Error handling game state: {e}")

    async def close(self):
        """Close NATS connection and stop monitoring"""
        self._should_monitor = False
        if self._connection_monitor_task:
            self._connection_monitor_task.cancel()
            try:
                await self._connection_monitor_task
            except asyncio.CancelledError:
                pass
            self._connection_monitor_task = None
        
        if self.nc:
            try:
                await self.nc.close()
            except:
                pass
            self.nc = None