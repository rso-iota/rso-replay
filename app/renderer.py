from pathlib import Path
import random
from typing import List, Dict
from PIL import Image, ImageDraw, ImageOps
import asyncio
import logging

from .models import GameState, Player, Food

logger = logging.getLogger(__name__)

class GameRenderer:
    def __init__(
        self,
        width: int = 800,
        height: int = 600,
        game_width: float = 1000.0,
        game_height: float = 800.0,
        background_color: str = "black",
        player_colors: List[str] = None,
        food_color: str = "white",
        skins_dir: Path = None,
    ):
        self.width = width
        self.height = height
        self.game_width = game_width
        self.game_height = game_height
        self.background_color = background_color
        self.player_colors = player_colors or ["red", "blue", "green", "yellow", "purple"]
        self.food_color = food_color
        self.skins_dir = skins_dir or Path(__file__).parent / "assets" / "skins"
        
        # Calculate scaling factors
        self.scale_x = self.width / self.game_width
        self.scale_y = self.height / self.game_height

        # Load and cache skin images
        self.skins = self._load_skins()
        self.player_skins: Dict[str, Image.Image] = {}  # Maps player names to their assigned skins

    def _create_circular_mask(self, size: tuple[int, int]) -> Image.Image:
        """Create a circular mask of given size"""
        mask = Image.new('L', size, 0)
        draw = ImageDraw.Draw(mask)
        draw.ellipse((0, 0, size[0]-1, size[1]-1), fill=255)
        return mask

    def _circle_crop_image(self, image: Image.Image) -> Image.Image:
        """Crop an image into a circle"""
        # Convert to RGBA if not already
        if image.mode != 'RGBA':
            image = image.convert('RGBA')
            
        # Create a square image with equal width and height (take the smaller dimension)
        size = min(image.size)
        
        # Crop to square from center
        image = ImageOps.fit(image, (size, size), centering=(0.5, 0.5))
        
        # Create circular mask
        mask = self._create_circular_mask((size, size))
        
        # Apply mask
        output = Image.new('RGBA', (size, size), (0, 0, 0, 0))
        output.paste(image, (0, 0))
        output.putalpha(mask)
        
        return output

    def _load_skins(self) -> List[Image.Image]:
        """Load all skin images from the skins directory and crop them to circles"""
        skins = []
        if self.skins_dir.exists():
            for img_path in self.skins_dir.glob("*.jpg"):
                try:
                    # Load and crop to circle
                    img = Image.open(img_path).convert("RGBA")
                    img = self._circle_crop_image(img)
                    skins.append(img)
                    logger.info({"message": f"Loaded and cropped skin from {img_path}"})
                except Exception as e:
                    logger.error({"message": f"Failed to load skin {img_path}: {str(e)}"})
        return skins

    def _get_player_skin(self, player_name: str) -> Image.Image:
        """Get or assign a random skin for a player"""
        if not self.skins:
            return None
            
        if player_name not in self.player_skins:
            # Assign a random skin to this player
            skin = random.choice(self.skins)
            self.player_skins[player_name] = skin
        
        return self.player_skins[player_name]

    def map_to_pixels(self, x: float, y: float, radius: float) -> tuple[float, float, float]:
        """Map game coordinates and radius to pixel values"""
        pixel_x = x * self.scale_x
        pixel_y = y * self.scale_y
        pixel_radius = radius * min(self.scale_x, self.scale_y)
        return pixel_x, pixel_y, pixel_radius

    def _draw_player(
        self,
        image: Image.Image,
        player: Player,
        color: str,
        x: float,
        y: float,
        radius: float
    ) -> None:
        """Draw a player with their skin overlay"""
        # Get skin if available
        skin = self._get_player_skin(player.name)
        
        if skin:
            # If we have a skin, only use it without background circle
            skin_size = int(radius * 2)
            try:
                # Resize skin
                skin_resized = skin.copy()
                skin_resized.thumbnail((skin_size, skin_size), Image.Resampling.LANCZOS)
                
                # Calculate position to center the skin on the circle
                paste_x = int(x - skin_resized.width / 2)
                paste_y = int(y - skin_resized.height / 2)
                
                # Paste the skin with transparency
                image.paste(skin_resized, (paste_x, paste_y), skin_resized)
            except Exception as e:
                logger.error({"message": f"Failed to apply skin for {player.name}: {str(e)}"})
        else:
            # If no skin is available, draw colored circle
            draw = ImageDraw.Draw(image)
            left = x - radius
            top = y - radius
            right = x + radius
            bottom = y + radius
            draw.ellipse([left, top, right, bottom], fill=color)

    def render_frame(self, state: GameState) -> Image.Image:
        """Render a single frame from game state"""
        # Create new image with background
        image = Image.new('RGBA', (self.width, self.height), self.background_color)

        # Draw food items
        draw = ImageDraw.Draw(image)
        for food in state.food:
            x, y, radius = self.map_to_pixels(
                food.circle.x,
                food.circle.y,
                food.circle.radius
            )
            self._draw_circle(
                draw,
                x,
                y,
                radius,
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
                x, y, radius = self.map_to_pixels(
                    player.circle.x,
                    player.circle.y,
                    player.circle.radius
                )
                color = self.player_colors[i % len(self.player_colors)]
                self._draw_player(image, player, color, x, y, radius)

        # Convert to RGB for video encoding
        return image.convert('RGB')

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
            logger.info(f"Rendering {len(states)} frames")
            for i, state in enumerate(states):
                frame = self.render_frame(state)
                frame_path = frames_path / f"frame_{i:06d}.png"
                frame.save(frame_path)

            logger.info(f"Creating video at {fps} FPS")
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

            logger.info(f"Video saved to {output_path}")
            return output_path

        finally:
            # Clean up frame files if they exist
            for frame_file in frames_path.glob("frame_*.png"):
                frame_file.unlink()

            # Try to remove frames directory
            try:
                frames_path.rmdir()
            except:
                pass  # Directory might not be empty
