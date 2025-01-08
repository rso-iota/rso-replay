from typing import List
import numpy as np
from .models import GameState, Player, Food, Circle

def interpolate_game_states(states: List[GameState], target_fps: int, speed: float = 3.0) -> List[GameState]:
    """
    Interpolate between game states to achieve target FPS at specified speed.
    Each game state is assumed to be 0.5s apart (2 FPS).
    
    Parameters:
        states: List of game states to interpolate between
        target_fps: Target frames per second for the output
        speed: Speed multiplier (1.0 = normal speed, 2.0 = double speed, 0.5 = half speed)
    """
    if not states or len(states) < 2:
        return states

    source_fps = 2  # Given states are at 2 FPS
    
    frames_between = round((target_fps / speed) / source_fps - 1)
    
    
    
    
    if frames_between <= 0:
        # If speed is too high to interpolate, sample states instead
        sample_rate = round(source_fps * speed / target_fps) or 1
        return states[::sample_rate]

    interpolated_states: List[GameState] = []
    
    for i in range(len(states) - 1):
        current_state = states[i]
        next_state = states[i + 1]
        
        # Add the current state
        interpolated_states.append(current_state)
        
        # Create interpolated states
        for frame in range(frames_between):
            # Calculate interpolation factor (0 to 1)
            t = (frame + 1) / (frames_between + 1)
            
            # Interpolate players
            interpolated_players: List[Player] = []
            
            # Match players by name between current and next state
            current_players = {p.name: p for p in current_state.players}
            next_players = {p.name: p for p in next_state.players}
            
            # Get union of player names
            all_player_names = set(current_players.keys()) | set(next_players.keys())
            
            for name in all_player_names:
                current_player = current_players.get(name)
                next_player = next_players.get(name)
                
                if current_player and next_player and current_player.alive and next_player.alive:
                    # Interpolate circle properties
                    x = current_player.circle.x + t * (next_player.circle.x - current_player.circle.x)
                    y = current_player.circle.y + t * (next_player.circle.y - current_player.circle.y)
                    radius = current_player.circle.radius + t * (next_player.circle.radius - current_player.circle.radius)
                    
                    interpolated_players.append(Player(
                        name=name,
                        alive=True,
                        circle=Circle(x=x, y=y, radius=radius)
                    ))
                elif current_player and current_player.alive:
                    # Keep current player if they're only in current state
                    interpolated_players.append(current_player)
                elif next_player and next_player.alive:
                    # Keep next player if they're only in next state
                    interpolated_players.append(next_player)
            
            # For food, we'll keep it the same as current state since interpolating food positions
            # might not make sense for gameplay (food appears/disappears instantly)
            interpolated_state = GameState(
                players=interpolated_players,
                food=current_state.food
            )
            
            interpolated_states.append(interpolated_state)
    
    # Add the last state
    interpolated_states.append(states[-1])
    
    return interpolated_states
