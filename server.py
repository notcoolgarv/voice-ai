from fastapi import FastAPI, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import httpx
import os
import asyncio
import subprocess
import sys
import time
from pathlib import Path
import logging

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI()

# Add CORS middleware to allow all origins
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allows all origins
    allow_credentials=True,
    allow_methods=["*"],  # Allows all methods
    allow_headers=["*"],  # Allows all headers
)

# Global dictionary to track background processes
background_processes = {}

# Voice mapping
VOICE_MAPPING = {
    "female": "OYTbf65OHHFELVut7v2H",  # Hope
    "male": "pwMBn0SsmN1220Aorv15",  # Matt
}


class CreateRoomRequest(BaseModel):
    voice: str = "female"  # Default to female voice


async def start_main_py_background(room_url: str, voice: str):
    """Background task to start main.py with the room URL and voice"""
    try:
        # Get the directory where main.py is located
        main_py_path = Path(__file__).parent / "main.py"

        logger.info(
            f"Starting main.py background process with room URL: {room_url} and voice: {voice}"
        )

        # Start main.py as a subprocess with the room URL and voice
        # Remove stdout and stderr pipes to see logs in real-time
        process = subprocess.Popen(
            [sys.executable, str(main_py_path), "-u", room_url, "--voice", voice]
        )

        logger.info(f"Started main.py background process with PID: {process.pid}")

        # Store the process reference for later management
        background_processes[room_url] = process

    except Exception as e:
        logger.error(f"Error starting main.py: {e}")


async def cleanup_background_process(room_url: str):
    """Clean up background process for a given room URL"""
    if room_url in background_processes:
        process = background_processes[room_url]
        try:
            logger.info(f"Terminating background process with PID: {process.pid}")
            process.terminate()
            process.wait(timeout=5)  # Wait up to 5 seconds for graceful termination
        except subprocess.TimeoutExpired:
            logger.warning(
                f"Process {process.pid} did not terminate gracefully, killing it"
            )
            process.kill()
        except Exception as e:
            logger.error(f"Error terminating process {process.pid}: {e}")
        finally:
            del background_processes[room_url]


@app.get("/")
async def root():
    return {"message": "Hello World"}


@app.post("/create-room")
async def create_meeting_room(
    request: CreateRoomRequest, background_tasks: BackgroundTasks
):
    token = os.getenv("DAILY_API_KEY")
    if not token:
        return {"error": "DAILY_API_KEY environment variable not set"}

    # Validate voice parameter
    if request.voice not in VOICE_MAPPING:
        return {"error": f"Invalid voice. Must be one of: {list(VOICE_MAPPING.keys())}"}

    url = "https://api.daily.co/v1/rooms"
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

    # Set room to expire in 5 minutes (300 seconds)
    expiry_time = int(time.time()) + 300

    # Room configuration with expiration
    room_config = {
        "properties": {
            "exp": expiry_time,
            "enable_chat": True,
            "enable_knocking": False,
            "enable_screenshare": False,
            "enable_recording": False,
            "max_participants": 10,
        }
    }

    async with httpx.AsyncClient() as client:
        response = await client.post(url, headers=headers, json=room_config)
        result = response.json()

        # If room creation was successful, start the background task
        if response.status_code == 200 and "url" in result:
            room_url = result["url"]
            background_tasks.add_task(start_main_py_background, room_url, request.voice)
            result["background_task_started"] = True
            result["message"] = "Room created and main.py background task started"
            result["expires_in_seconds"] = 300
            result["expires_at"] = expiry_time
            result["voice"] = request.voice
            result["voice_id"] = VOICE_MAPPING[request.voice]

        return result


@app.delete("/delete-room/{room_name}")
async def delete_meeting_room(room_name: str):
    token = os.getenv("DAILY_API_KEY")
    if not token:
        return {"error": "DAILY_API_KEY environment variable not set"}

    url = f"https://api.daily.co/v1/rooms/{room_name}"
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

    async with httpx.AsyncClient() as client:
        response = await client.delete(url, headers=headers)

        # Clean up any background processes for this room
        room_url = (
            f"https://{os.getenv('DAILY_DOMAIN', 'your-domain.daily.co')}/{room_name}"
        )
        await cleanup_background_process(room_url)

        return response.json()


@app.get("/processes")
async def list_background_processes():
    """List all active background processes"""
    processes_info = {}
    for room_url, process in background_processes.items():
        processes_info[room_url] = {"pid": process.pid, "alive": process.poll() is None}
    return {"processes": processes_info}


@app.delete("/processes/{room_name}")
async def cleanup_process_by_room(room_name: str):
    """Manually clean up background process for a specific room"""
    room_url = (
        f"https://{os.getenv('DAILY_DOMAIN', 'your-domain.daily.co')}/{room_name}"
    )
    await cleanup_background_process(room_url)
    return {"message": f"Process cleanup initiated for room: {room_name}"}
