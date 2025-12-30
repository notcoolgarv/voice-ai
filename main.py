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
from pipecat.services.elevenlabs.tts import ElevenLabsTTSService
from pipecat.services.deepgram.stt import DeepgramSTTService
from pipecat.services.openai.llm import OpenAILLMService
from pipecat.transports.services.daily import DailyParams, DailyTransport

from pipecat_flows import FlowArgs, FlowConfig, FlowManager, FlowResult

sys.path.append(str(Path(__file__).parent.parent))
from runner import configure

load_dotenv(override=True)

logger.remove(0)
logger.add(sys.stderr, level="DEBUG")

# Global variables to store room URL and process info
room_url: str | None = None
current_process_pid: int | None = None

# Voice mapping
VOICE_MAPPING = {
    "female": "OYTbf65OHHFELVut7v2H",
    "male": "pwMBn0SsmN1220Aorv15",
}

# AI name mapping
AI_NAME_MAPPING = {
    "female": "Helen",
    "male": "Helio",
}


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


# Handler functions for the new flow
async def proceed_to_introduction(args: FlowArgs) -> tuple[None, str]:
    return None, "introduce_halsell"


async def choose_features(args: FlowArgs) -> tuple[None, str]:
    return None, "features"


async def choose_pricing(args: FlowArgs) -> tuple[None, str]:
    return None, "pricing"


async def choose_contact(args: FlowArgs) -> tuple[None, str]:
    return None, "contact"


async def learn_more(args: FlowArgs) -> tuple[None, str]:
    return None, "introduce_halsell"


async def sign_up(args: FlowArgs) -> tuple[None, str]:
    return None, "sign_up"


async def fetch_dynamic_prompt(tenant_id: str) -> str:
    """Fetch dynamic system prompt text from campaign setting for the given tenant_id"""
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"https://halsell.com/api/get_campaign_setting?tenant_id={tenant_id}"
            )
            response.raise_for_status()
            data = response.json()
            texts = data.get("campaign_setting", {}).get("texts", [])
            text_values = [
                item.get("value", "").strip() for item in texts if item.get("value")
            ]
            final_prompt = (
                "\n\n".join(text_values)
                if text_values
                else "You are Halsell AI, a helpful assistant."
            )
            return final_prompt
    except Exception as e:
        logger.error(f"Failed to fetch dynamic prompt: {e}")
        return "You are Halsell AI, a helpful assistant."


async def main():
    """Main function to set up and run the Halsell CRM introduction bot."""
    global room_url

    # Parse command line arguments
    parser = argparse.ArgumentParser(description="Halsell CRM Bot")
    parser.add_argument(
        "-u", "--url", type=str, required=True, help="URL of the Daily room to join"
    )
    parser.add_argument(
        "--voice",
        type=str,
        default="female",
        choices=["male", "female"],
        help="Voice to use for TTS (male or female)",
    )

    args = parser.parse_args()

    # Get the voice ID from the mapping
    voice_id = VOICE_MAPPING.get(args.voice, VOICE_MAPPING["female"])
    logger.info(f"Using voice: {args.voice} with voice ID: {voice_id}")

    # Get the AI name from the mapping
    ai_name = AI_NAME_MAPPING.get(args.voice, AI_NAME_MAPPING["female"])
    logger.info(f"Using AI name: {ai_name}")

    # Create dynamic flow configuration with the appropriate AI name
    dynamic_flow_config: FlowConfig = {
        "initial_node": "greet",
        "nodes": {
            "greet": {
                "role_messages": [
                    {
                        "role": "system",
                        "content": f"You are {ai_name}, an assistant introducing Halsell, a CRM. Be friendly and casual.",
                    }
                ],
                "task_messages": [
                    {
                        "role": "system",
                        "content": f"Greet the user and ask for their name. For example: 'Hello! I'm {ai_name}, and I'm here to tell you about Halsell, a powerful CRM. May I have your name?' Once they provide it, use the 'proceed_to_introduction' function to continue.",
                    }
                ],
                "functions": [
                    {
                        "type": "function",
                        "function": {
                            "name": "proceed_to_introduction",
                            "handler": proceed_to_introduction,
                            "description": "Proceed to introduce Halsell after getting the user's name.",
                            "parameters": {"type": "object", "properties": {}},
                        },
                    }
                ],
            },
            "introduce_halsell": {
                "task_messages": [
                    {
                        "role": "system",
                        "content": f"Introduce Halsell as a powerful CRM that helps businesses manage customer relationships efficiently. Use the user's name if provided (e.g., 'Nice to meet you, [name]! I'm {ai_name}, and Halsell is a CRM that...'). Then, ask what they want to know: features, pricing, or how to contact sales. Use the appropriate function based on their response.",
                    }
                ],
                "functions": [
                    {
                        "type": "function",
                        "function": {
                            "name": "choose_features",
                            "handler": choose_features,
                            "description": "User wants to know about features.",
                            "parameters": {"type": "object", "properties": {}},
                        },
                    },
                    {
                        "type": "function",
                        "function": {
                            "name": "choose_pricing",
                            "handler": choose_pricing,
                            "description": "User wants to know about pricing.",
                            "parameters": {"type": "object", "properties": {}},
                        },
                    },
                    {
                        "type": "function",
                        "function": {
                            "name": "choose_contact",
                            "handler": choose_contact,
                            "description": "User wants to know how to contact sales.",
                            "parameters": {"type": "object", "properties": {}},
                        },
                    },
                ],
            },
            "features": {
                "task_messages": [
                    {
                        "role": "system",
                        "content": f"Tell the user: 'Halsell offers features like contact management, sales pipeline tracking, automated workflows, and integrations with tools to streamline customer interactions and boost sales efficiency.' Use their name if provided (e.g., '[name], these features can help...'). Then ask if they want to know something else or sign up, using 'learn_more' or 'sign_up'.",
                    }
                ],
                "functions": [
                    {
                        "type": "function",
                        "function": {
                            "name": "learn_more",
                            "handler": learn_more,
                            "description": "User wants to know something else.",
                            "parameters": {"type": "object", "properties": {}},
                        },
                    },
                    {
                        "type": "function",
                        "function": {
                            "name": "sign_up",
                            "handler": sign_up,
                            "description": "User is interested in signing up.",
                            "parameters": {"type": "object", "properties": {}},
                        },
                    },
                ],
            },
            "pricing": {
                "task_messages": [
                    {
                        "role": "system",
                        "content": f"Tell the user: 'Halsell offers flexible pricing plans to suit businesses of all sizes. For detailed pricing, check our website or contact our sales team.' Use their name if provided. Then ask if they want to know something else or sign up, using 'learn_more' or 'sign_up'.",
                    }
                ],
                "functions": [
                    {
                        "type": "function",
                        "function": {
                            "name": "learn_more",
                            "handler": learn_more,
                            "description": "User wants to know something else.",
                            "parameters": {"type": "object", "properties": {}},
                        },
                    },
                    {
                        "type": "function",
                        "function": {
                            "name": "sign_up",
                            "handler": sign_up,
                            "description": "User is interested in signing up.",
                            "parameters": {"type": "object", "properties": {}},
                        },
                    },
                ],
            },
            "contact": {
                "task_messages": [
                    {
                        "role": "system",
                        "content": f"Tell the user: 'You can reach Halsell's sales team at sales@halsell.com or visit https://halsell.com for more info.' Use their name if provided. Then ask if they want to know something else or sign up, using 'learn_more' or 'sign_up'.",
                    }
                ],
                "functions": [
                    {
                        "type": "function",
                        "function": {
                            "name": "learn_more",
                            "handler": learn_more,
                            "description": "User wants to know something else.",
                            "parameters": {"type": "object", "properties": {}},
                        },
                    },
                    {
                        "type": "function",
                        "function": {
                            "name": "sign_up",
                            "handler": sign_up,
                            "description": "User is interested in signing up.",
                            "parameters": {"type": "object", "properties": {}},
                        },
                    },
                ],
            },
            "sign_up": {
                "task_messages": [
                    {
                        "role": "system",
                        "content": f"Tell the user: 'Great choice! To sign up for Halsell, visit https://halsell.com and click 'Sign Up', or email sales@halsell.com for assistance.' Use their name if provided. Then thank them and end the conversation.",
                    }
                ],
                "functions": [],
                "post_actions": [{"type": "end_conversation"}],
            },
        },
    }

    # Fetch dynamic prompt and inject it into the flow configuration
    try:
        dynamic_prompt = await fetch_dynamic_prompt(tenant_id="1")
        dynamic_flow_config["nodes"]["greet"]["role_messages"] = [
            {
                "role": "system",
                "content": dynamic_prompt,
            }
        ]
        logger.info(f"Dynamic prompt: {dynamic_prompt}")
        logger.info("Injected dynamic system prompt into flow_config.")
    except Exception as e:
        logger.warning(f"Failed to fetch or inject dynamic prompt: {e}")

    async with aiohttp.ClientSession() as session:
        # Use the provided room URL instead of calling configure
        room_url = args.url

        if not room_url:
            logger.error("No room URL provided")
            return

        transport = DailyTransport(
            room_url,
            None,
            "Halsell CRM Bot",
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

        pipeline = Pipeline(
            [
                transport.input(),
                stt,
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
