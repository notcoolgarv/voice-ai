import asyncio
import os
import sys
import signal
import argparse
from pathlib import Path

import aiohttp
import httpx
from dotenv import load_dotenv
from loguru import logger
from pipecat.audio.vad.silero import SileroVADAnalyzer
from pipecat.pipeline.pipeline import Pipeline
from pipecat.pipeline.runner import PipelineRunner
from pipecat.pipeline.task import PipelineParams, PipelineTask
from pipecat.processors.aggregators.openai_llm_context import OpenAILLMContext
from pipecat.processors.user_idle_processor import UserIdleProcessor
from pipecat.frames.frames import EndFrame, LLMMessagesFrame, TTSSpeakFrame
from pipecat.services.elevenlabs.tts import ElevenLabsTTSService
from pipecat.services.deepgram.stt import DeepgramSTTService
from pipecat.services.openai.llm import OpenAILLMService
from pipecat.transports.services.daily import DailyParams, DailyTransport

from pipecat_flows import FlowConfig, FlowManager, FlowResult

from flow_config import create_flow_config

load_dotenv(override=True)

logger.remove(0)
logger.add(sys.stderr, level="DEBUG")

# Global variables to store room URL and process info
room_url: str | None = None
current_process_pid: int | None = None

# Default voice - Hope (popular ElevenLabs voice)
DEFAULT_VOICE_ID = "OYTbf65OHHFELVut7v2H"
DEFAULT_AI_NAME = "Pizza ordering AI"


async def delete_room(room_url: str | None):
    """Delete the Daily room via API"""
    try:
        if not room_url:
            logger.error("No room URL provided for deletion")
            return

        token = os.getenv("DAILY_API_KEY")
        if not token:
            logger.error("DAILY_API_KEY environment variable not set")
            return

        room_name = room_url.split("/")[-1]
        url = f"https://api.daily.co/v1/rooms/{room_name}"
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }

        async with httpx.AsyncClient() as client:
            response = await client.delete(url, headers=headers)
            if response.status_code == 200:
                logger.info(f"Successfully deleted room: {room_name}")
            else:
                logger.error(
                    f"Failed to delete room {room_name}: {response.status_code} - {response.text}"
                )
    except Exception as e:
        logger.error(f"Error deleting room: {e}")


def kill_current_process():
    """Kill the current process"""
    try:
        logger.info(f"Terminating process with PID: {os.getpid()}")
        os.kill(os.getpid(), signal.SIGTERM)
    except Exception as e:
        logger.error(f"Error killing process: {e}")
        sys.exit(0)


def signal_handler(signum, frame):
    """Handle termination signals gracefully"""
    logger.info(f"Received signal {signum}, cleaning up...")
    if room_url:
        asyncio.create_task(delete_room(room_url))
    sys.exit(0)


signal.signal(signal.SIGTERM, signal_handler)
signal.signal(signal.SIGINT, signal_handler)


async def fetch_dynamic_prompt() -> str:
    """Get the default system prompt for the pizza ordering bot"""
    return "You are a friendly and helpful pizza ordering assistant. Guide customers through ordering delicious pizzas with a warm, conversational tone."


async def main():
    """Main function to set up and run the Pizza ordering bot."""
    global room_url

    # Parse command line arguments
    parser = argparse.ArgumentParser(description="Pizza Ordering Bot")
    parser.add_argument(
        "-u", "--url", type=str, required=True, help="URL of the Daily room to join"
    )

    args = parser.parse_args()

    # Use default voice and AI name
    voice_id = DEFAULT_VOICE_ID
    ai_name = DEFAULT_AI_NAME
    logger.info(f"Using AI name: {ai_name} with voice ID: {voice_id}")

    # Create dynamic flow configuration with the appropriate AI name
    dynamic_flow_config: FlowConfig = create_flow_config(ai_name)

    # Fetch dynamic prompt and inject it into the flow configuration
    try:
        dynamic_prompt = await fetch_dynamic_prompt()
        dynamic_flow_config["nodes"]["greet"]["role_messages"] = [
            {
                "role": "system",
                "content": dynamic_prompt,
            }
        ]
        logger.info(f"System prompt: {dynamic_prompt}")
        logger.info("Injected system prompt into flow_config.")
    except Exception as e:
        logger.warning(f"Failed to inject system prompt: {e}")

    async with aiohttp.ClientSession() as session:
        # Use the provided room URL instead of calling configure
        room_url = args.url

        if not room_url:
            logger.error("No room URL provided")
            return

        transport = DailyTransport(
            room_url,
            None,
            DEFAULT_AI_NAME,
            DailyParams(
                audio_in_enabled=True,
                audio_out_enabled=True,
                vad_analyzer=SileroVADAnalyzer(),
            ),
        )

        stt = DeepgramSTTService(api_key=os.getenv("DEEPGRAM_API_KEY") or "")
        tts = ElevenLabsTTSService(
            api_key=os.getenv("ELEVENLABS_API_KEY") or "",
            voice_id=voice_id,
        )
        llm = OpenAILLMService(
            api_key=os.getenv("OPENAI_API_KEY") or "", model="gpt-4o"
        )

        context = OpenAILLMContext()
        context_aggregator = llm.create_context_aggregator(context)

        async def handle_user_idle(
            user_idle: UserIdleProcessor, retry_count: int
        ) -> bool:
            if retry_count == 1:
                # First attempt: Add a gentle prompt to the conversation
                await user_idle.push_frame(
                    TTSSpeakFrame(
                        "Are you still there? I'm here to help you order a pizza!"
                    )
                )
                return True
            elif retry_count == 2:
                # Second attempt: More direct prompt
                await user_idle.push_frame(
                    TTSSpeakFrame(
                        "Hello? Would you still like to order a pizza?"
                    )
                )
                return True
            else:
                # Third attempt: End the conversation
                await user_idle.push_frame(
                    TTSSpeakFrame(
                        "It seems like you're busy right now. Feel free to come back when you're ready to order. Have a great day!"
                    )
                )
                await task.queue_frame(EndFrame())
                return False

        user_idle = UserIdleProcessor(callback=handle_user_idle, timeout=5.0)

        pipeline = Pipeline(
            [
                transport.input(),
                stt,
                user_idle,
                context_aggregator.user(),
                llm,
                tts,
                transport.output(),
                context_aggregator.assistant(),
            ]
        )

        task = PipelineTask(pipeline, params=PipelineParams(allow_interruptions=True))

        flow_manager = FlowManager(
            task=task,
            llm=llm,
            context_aggregator=context_aggregator,
            flow_config=dynamic_flow_config,
        )

        @transport.event_handler("on_first_participant_joined")
        async def on_first_participant_joined(transport, participant):
            await transport.capture_participant_transcription(participant["id"])
            logger.debug("Initializing flow")
            await flow_manager.initialize()

        @transport.event_handler("on_participant_left")
        async def on_participant_left(transport, participant, *args):
            logger.info(f"Participant left: {participant['id']}")
            logger.info("Deleting room and terminating process...")
            await delete_room(room_url)
            kill_current_process()

        runner = PipelineRunner()
        await runner.run(task)


if __name__ == "__main__":
    asyncio.run(main())
