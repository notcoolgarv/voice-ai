import asyncio
import os
import sys
import signal
import argparse

import aiohttp
import httpx
from dotenv import load_dotenv
from loguru import logger
from pipecat.audio.vad.silero import SileroVADAnalyzer
from pipecat.audio.vad.vad_analyzer import VADParams
from pipecat.pipeline.pipeline import Pipeline
from pipecat.pipeline.runner import PipelineRunner
from pipecat.pipeline.task import PipelineParams, PipelineTask
from pipecat.processors.aggregators.llm_context import LLMContext
from pipecat.processors.aggregators.llm_response_universal import LLMContextAggregatorPair
from pipecat.processors.user_idle_processor import UserIdleProcessor
from pipecat.frames.frames import EndFrame, TTSSpeakFrame
from pipecat.services.cartesia.tts import CartesiaTTSService
from pipecat.services.deepgram.stt import DeepgramSTTService
from pipecat.services.openai.llm import OpenAILLMService
from pipecat.transports.daily.transport import DailyParams, DailyTransport

from pipecat_flows import FlowConfig, FlowManager

from flow_config import create_flow_config

load_dotenv(override=True)

logger.remove(0)
logger.add(sys.stderr, level="DEBUG")

# Global variables to store room URL and process info
room_url: str | None = None
current_process_pid: int | None = None

# Default values
DEFAULT_AI_NAME = "Pizza ordering AI"
# Cartesia voice - British Reading Lady
DEFAULT_VOICE_ID = "820a3788-2b37-4d21-847a-b65d8a68c99a"


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

    # Get voice ID from environment or use default
    voice_id = os.getenv("CARTESIA_VOICE_ID") or DEFAULT_VOICE_ID
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

        logger.info("🎙️ Initializing DailyTransport...")
        transport = DailyTransport(
            room_url,
            None,
            DEFAULT_AI_NAME,
            DailyParams(
                audio_in_enabled=True,
                audio_out_enabled=True,
                vad_analyzer=SileroVADAnalyzer(params=VADParams(stop_secs=0.2)),
            ),
        )
        logger.info(f"✅ DailyTransport initialized for room: {room_url}")

        logger.info("🎤 Initializing STT service (Deepgram)...")
        stt = DeepgramSTTService(api_key=os.getenv("DEEPGRAM_API_KEY") or "")
        logger.info("✅ STT service initialized")

        logger.info(f"🔊 Initializing TTS service (Cartesia) with voice_id: {voice_id}...")
        tts = CartesiaTTSService(
            api_key=os.getenv("CARTESIA_API_KEY") or "",
            voice_id=voice_id,
        )
        logger.info("✅ TTS service initialized")

        logger.info("🤖 Initializing LLM service (OpenAI GPT-4o)...")
        llm = OpenAILLMService(
            api_key=os.getenv("OPENAI_API_KEY") or "", model="gpt-4o"
        )
        logger.info("✅ LLM service initialized")

        context = LLMContext()
        context_aggregator = LLMContextAggregatorPair(context)

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
                    TTSSpeakFrame("Hello? Would you still like to order a pizza?")
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
            transport=transport,
        )

        @transport.event_handler("on_first_participant_joined")
        async def on_first_participant_joined(transport, participant):
            await transport.capture_participant_transcription(participant["id"])
            await flow_manager.initialize()

        @transport.event_handler("on_app_message")
        async def on_app_message(transport, message, sender):
            logger.info(f"📨 APP MESSAGE from {sender}: {message}")

        @transport.event_handler("on_call_state_updated")
        async def on_call_state_updated(transport, state):
            logger.info(f"📞 CALL STATE UPDATED: {state}")

        @transport.event_handler("on_participant_joined")
        async def on_participant_joined(transport, participant):
            logger.info(f"👥 PARTICIPANT JOINED (any): {participant['id']}")

        @transport.event_handler("on_participant_left")
        async def on_participant_left(transport, participant, *args):
            logger.info(f"🔴 PARTICIPANT LEFT: {participant['id']}")
            logger.info("🗑️ Deleting room and terminating process...")
            await delete_room(room_url)
            kill_current_process()

        logger.info("🚀 Starting pipeline runner...")
        runner = PipelineRunner()
        await runner.run(task)
        logger.info("Pipeline runner completed")


if __name__ == "__main__":
    asyncio.run(main())
