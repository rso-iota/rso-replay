# RSO Replay Service

Service for recording and replaying game sessions in the RSO game system. Provides game state history and video replay generation.

## Features

- Captures game states and events via NATS
- Stores event history in MongoDB
- Generates MP4 video replays of games
- Supports time-based filtering and speed control
- Event projection and state reconstruction

## Installation

### Requirements

- Python 3.11+
- uv (package manager)
- MongoDB
- NATS server
- ffmpeg (for video generation)

### Setup

1. Create virtual environment:
```bash
uv venv
```

2. Install dependencies:
```bash
uv pip install -e .
```

3. Configure environment:
```bash
cp .env.example .env
```

Required variables:
- MONGO_URL: MongoDB connection string
- REPLAY_NATS_URL: NATS server URL
- REPLAY_VIDEO_WIDTH: Output video width
- REPLAY_VIDEO_HEIGHT: Output video height
- REPLAY_GAME_WIDTH: Game area width
- REPLAY_GAME_HEIGHT: Game area height

## Running

Start the service:
```bash
python run.py
```

### Docker

Build:
```bash
docker build -t rso-replay .
```

Run:
```bash
docker run -p 8000:8000 --env-file .env rso-replay
```

## API Reference

### Get Game States

```http
GET /api/v1/replays/{game_id}/states
```

Parameters:
- from_time (optional): Start time (ISO format)
- to_time (optional): End time (ISO format)

Returns list of game states.

### Get Replay Video

```http
GET /api/v1/replays/{game_id}/video
```

Parameters:
- fps (optional): Frames per second (default: 30)
- speed (optional): Playback speed multiplier (default: 3.0)
- from_time (optional): Start time (ISO format)
- to_time (optional): End time (ISO format)

Returns MP4 video file.

### Health Check

```http
GET /health
```

Returns service health status.

## Architecture

Components:
- EventHandler: Processes game events from NATS
- EventStore: Stores events in MongoDB
- Projector: Reconstructs game states from events
- GameRenderer: Generates video frames
- FastAPI app: Serves HTTP endpoints

Data flow:
1. Game events arrive via NATS
2. Events are stored in MongoDB
3. On replay request:
   - Events are loaded and projected to states
   - States are rendered to video frames
   - Frames are encoded to MP4
