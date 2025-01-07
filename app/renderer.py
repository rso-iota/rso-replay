from pathlib import Path
from typing import List
from PIL import Image, ImageDraw
import ffmpeg
import numpy as np
from .models import GameState, Player, Food
import asyncio

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

    def render_frame(self, state: GameState) -> Image.Image:
        """Render a single frame from game state"""
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

        return image

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
        output_path: Path,
        frames_path: Path,
        fps: int = 30
    ) -> Path:
        """Create video from a list of game states"""
        if not states:
            raise ValueError("No states provided")

        # Ensure frames directory exists
        frames_path.mkdir(parents=True, exist_ok=True)

        try:
            # Render all frames
            for i, state in enumerate(states):
                frame = self.render_frame(state)
                frame_path = frames_path / f"frame_{i:06d}.png"
                frame.save(frame_path)

            # Create video from frames using ffmpeg subprocess
            cmd = [
                'ffmpeg',
                '-y',  # Overwrite output file if it exists
                '-framerate', str(fps),
                '-i', str(frames_path / "frame_%06d.png"),
                '-c:v', 'h264',
                '-pix_fmt', 'yuv420p',
                '-preset', 'medium',
                '-crf', '23',
                '-movflags', 'frag_keyframe+empty_moov',
                str(output_path)
            ]

            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )

            stdout, stderr = await process.communicate()

            if process.returncode != 0:
                raise RuntimeError(f"FFmpeg failed: {stderr.decode()}")

            return output_path

        finally:
            # Clean up frame files if they exist
            for frame_file in frames_path.glob("frame_*.png"):
                frame_file.unlink()

            # Try to remove frames directory
            try:
                frames_path.rmdir()
            except:
                pass  # Directory might not be empty or might not exist
