from pathlib import Path
import random
from typing import List, Dict, Tuple
from PIL import Image, ImageDraw, ImageOps
import asyncio
import logging
from io import BytesIO

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
        use_player_skins: bool = False,
    ):
        self.width = width
        self.height = height
        self.game_width = game_width
        self.game_height = game_height
        self.background_color = background_color
        self.player_colors = player_colors or ["red", "blue", "green", "yellow", "purple"]
        self.food_color = food_color
        self.skins_dir = skins_dir or Path(__file__).parent / "assets" / "skins"
        self.use_player_skins = use_player_skins
        
        # Calculate scaling factors
        self.scale_x = self.width / self.game_width
        self.scale_y = self.height / self.game_height
        
        # Cache for resized skins
        self.skin_cache: Dict[Tuple[int, int], Image.Image] = {}
        
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
        if image.mode != 'RGBA':
            image = image.convert('RGBA')
            
        size = min(image.size)
        image = ImageOps.fit(image, (size, size), centering=(0.5, 0.5))
        mask = self._create_circular_mask((size, size))
        output = Image.new('RGBA', (size, size), (0, 0, 0, 0))
        output.paste(image, (0, 0))
        output.putalpha(mask)
        return output

    def _load_skins(self) -> List[Image.Image]:
        """Load all skin images from the skins directory"""
        skins = []
        if self.skins_dir.exists():
            for img_path in self.skins_dir.glob("*.jpg"):
                try:
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
            skin = random.choice(self.skins)
            self.player_skins[player_name] = skin
        
        return self.player_skins[player_name]

    def _get_resized_skin(self, skin: Image.Image, size: int) -> Image.Image:
        """Get or create a resized version of a skin"""
        cache_key = (id(skin), size)
        if cache_key not in self.skin_cache:
            resized = skin.copy()
            resized.thumbnail((size, size), Image.Resampling.LANCZOS)
            self.skin_cache[cache_key] = resized
        return self.skin_cache[cache_key]

    def map_to_pixels(self, x: float, y: float, radius: float) -> tuple[int, int, int]:
        """Map game coordinates and radius to pixel values"""
        pixel_x = round(x * self.scale_x)
        pixel_y = round(y * self.scale_y)
        pixel_radius = round(radius * min(self.scale_x, self.scale_y))
        return pixel_x, pixel_y, pixel_radius

    def _draw_player(
        self,
        draw: ImageDraw.ImageDraw,
        image: Image.Image,
        player: Player,
        color: str,
        x: int,
        y: int,
        radius: int
    ) -> None:
        """Draw a player with their skin overlay"""
        skin = self._get_player_skin(player.name)
        
        if self.use_player_skins and skin:
            skin_size = radius * 2
            skin_resized = self._get_resized_skin(skin, skin_size)
            paste_x = x - skin_resized.width // 2
            paste_y = y - skin_resized.height // 2
            image.paste(skin_resized, (paste_x, paste_y), skin_resized)
        else:
            left = x - radius
            top = y - radius
            right = x + radius
            bottom = y + radius
            draw.ellipse([left, top, right, bottom], fill=color)

    def render_frame(self, state: GameState) -> Image.Image:
        """Render a single frame from game state"""
        # Create new image directly in RGB mode
        image = Image.new('RGB', (self.width, self.height), self.background_color)
        draw = ImageDraw.Draw(image)

        # Batch draw food items
        food_circles = [
            [x - r, y - r, x + r, y + r]
            for food in state.food
            for x, y, r in [self.map_to_pixels(
                food.circle.x,
                food.circle.y,
                food.circle.radius
            )]
        ]
        for food in state.food:
            x, y, radius = self.map_to_pixels(
                food.circle.x,
                food.circle.y,
                food.circle.radius
            )
            draw.ellipse([x - radius, y - radius, x + radius, y + radius], fill=self.food_color)

        # Draw players (max 5, no need to sort)
        for i, player in enumerate(state.players):
            if player.alive:
                x, y, radius = self.map_to_pixels(
                    player.circle.x,
                    player.circle.y,
                    player.circle.radius
                )
                color = self.player_colors[i % len(self.player_colors)]
                self._draw_player(draw, image, player, color, x, y, radius)

        return image

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
            # Set up ffmpeg process to stream frames
            cmd = [
                'ffmpeg',
                '-y',  # Overwrite output file if exists
                '-f', 'image2pipe',
                '-framerate', str(fps),
                '-i', '-',  # Read from pipe
                '-c:v', 'h264',
                '-pix_fmt', 'yuv420p',
                '-preset', 'medium',
                '-crf', '23',
                '-movflags', 'frag_keyframe+empty_moov',
                str(output_path)
            ]

            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )

            logger.info(f"Rendering {len(states)} frames")
            
            # Render and stream frames directly to ffmpeg
            for state in states:
                frame = self.render_frame(state)
                # Save frame to bytes
                frame_bytes = BytesIO()
                frame.save(frame_bytes, format='PNG')
                # Write frame to ffmpeg's stdin
                if process.stdin:
                    try:
                        process.stdin.write(frame_bytes.getvalue())
                        await process.stdin.drain()
                    except Exception as e:
                        logger.error(f"Failed to write frame: {str(e)}")
                        break

            # Close stdin to signal end of input
            if process.stdin:
                process.stdin.close()
                await process.stdin.wait_closed()

            # Wait for ffmpeg to finish
            stdout, stderr = await process.communicate()

            if process.returncode != 0:
                raise RuntimeError(f"FFmpeg failed: {stderr.decode()}")

            logger.info(f"Video saved to {output_path}")
            return output_path

        except Exception as e:
            logger.error(f"Failed to create video: {str(e)}")
            raise

        finally:
            # Clean up temporary files
            try:
                frames_path.rmdir()
            except:
                pass  # Directory might not be empty
