from typing import List, AsyncIterator
import asyncio
from PIL import Image, ImageDraw
import ffmpeg
import numpy as np
from io import BytesIO
from .models import GameState, Player, Food

class GameRenderer:
    def __init__(
        self,
        width: int = 800,
        height: int = 600,
        background_color: str = "black",
        player_colors: List[str] = None,
        food_color: str = "white",
    ):
        self.width = width
        self.height = height
        self.background_color = background_color
        self.player_colors = player_colors or ["red", "blue", "green", "yellow", "purple"]
        self.food_color = food_color

    def render_frame(self, state: GameState) -> bytes:
        """Render a single frame from game state and return raw bytes"""
        # Create new image with background
        image = Image.new('RGB', (self.width, self.height), self.background_color)
        draw = ImageDraw.Draw(image)

        # Draw food items
        for food in state.food:
            self._draw_circle(
                draw,
                food.circle.x,
                food.circle.y,
                food.circle.radius,
                self.food_color
            )

        # Sort players by radius (smallest to largest)
        sorted_players = sorted(
            state.players,
            key=lambda p: p.circle.radius
        )

        # Draw players
        for i, player in enumerate(sorted_players):
            if player.alive:
                color = self.player_colors[i % len(self.player_colors)]
                self._draw_circle(
                    draw,
                    player.circle.x,
                    player.circle.y,
                    player.circle.radius,
                    color
                )

        # Convert to raw bytes in RGB format
        return np.array(image).tobytes()

    def _draw_circle(
        self,
        draw: ImageDraw.ImageDraw,
        x: float,
        y: float,
        radius: float,
        color: str
    ) -> None:
        """Helper to draw a circle"""
        left = x - radius
        top = y - radius
        right = x + radius
        bottom = y + radius
        draw.ellipse([left, top, right, bottom], fill=color)

    async def create_video(
        self,
        states: List[GameState],
        fps: int = 30
    ) -> bytes:
        """Create video from game states and return raw bytes"""
        if not states:
            raise ValueError("No states provided")

        # Set up ffmpeg process for streaming
        process = (
            ffmpeg
            .input(
                'pipe:',                   # Read from pipe
                format='rawvideo',         # Raw video format
                pix_fmt='rgb24',           # RGB pixel format
                s=f'{self.width}x{self.height}',  # Frame size
                framerate=fps              # Frame rate
            )
            .output(
                'pipe:',                   # Output to pipe
                format='mp4',              # Output format
                pix_fmt='yuv420p',         # Standard pixel format for MP4
                vcodec='h264',             # Video codec
                acodec='none',             # No audio
                preset='ultrafast',        # Fastest encoding
                crf=23,                    # Reasonable quality
                movflags='frag_keyframe+empty_moov'  # Streaming-friendly flags
            )
            .overwrite_output()
            .run_async(pipe_stdin=True, pipe_stdout=True, pipe_stderr=True)
        )

        try:
            # Stream each frame to ffmpeg
            for state in states:
                frame_data = self.render_frame(state)
                process.stdin.write(frame_data)

            # Close stdin to signal end of frames
            process.stdin.close()
            
            # Read the output video data
            output_data = await process.stdout.read()
            
            # Wait for the process to finish
            await process.wait()

            return output_data

        except Exception as e:
            # Make sure to terminate ffmpeg on error
            process.kill()
            raise e