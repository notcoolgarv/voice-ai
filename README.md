# Real-time Voicebot with Automatic Room Cleanup

This project implements a real-time voicebot using Daily.co for video/audio communication with automatic room cleanup when participants leave.

## Features

- **Real-time Voice Communication**: Uses Daily.co for audio/video communication
- **AI-Powered Conversation**: Integrates with OpenAI GPT-4 for natural language processing
- **Speech-to-Text**: Uses Deepgram for real-time speech recognition
- **Text-to-Speech**: Uses ElevenLabs for natural voice synthesis with voice selection
- **Voice Selection**: Choose between male (Matt) and female (Hope) voices
- **Automatic Room Cleanup**: Automatically deletes rooms and terminates processes when participants leave
- **CRM Introduction Flow**: Implements a complete Halsell CRM introduction conversation flow

## Architecture

### Components

1. **server.py**: FastAPI server that manages room creation and background processes
2. **main.py**: Voicebot implementation with conversation flow
3. **runner.py**: Configuration and setup utilities

### Voice Options

The system supports two voice options for text-to-speech:

- **Female (Hope)**: Voice ID `OYTbf65OHHFELVut7v2H`
- **Male (Matt)**: Voice ID `pwMBn0SsmN1220Aorv15`

### Automatic Cleanup System

The system automatically handles cleanup in the following scenarios:

1. **Participant Leaves**: When a participant leaves the room, the system:
   - Deletes the Daily.co room via API
   - Terminates the background voicebot process
   - Logs the cleanup actions

2. **Process Termination**: The system includes signal handlers for graceful shutdown:
   - SIGTERM and SIGINT signals trigger room cleanup
   - Ensures no orphaned rooms or processes

3. **Manual Cleanup**: Server endpoints for manual process management:
   - `GET /processes`: List all active background processes
   - `DELETE /processes/{room_name}`: Manually clean up a specific room's process

## API Endpoints

### Room Management
- `POST /create-room`: Create a new Daily.co room and start voicebot
  - Request body: `{"voice": "female"}` or `{"voice": "male"}`
  - Default voice is female if not specified
- `DELETE /delete-room/{room_name}`: Delete a room and clean up its process

### Process Management
- `GET /processes`: List all active background processes
- `DELETE /processes/{room_name}`: Manually clean up a specific room's process

## Environment Variables

Required environment variables:
- `DAILY_API_KEY`: Your Daily.co API key
- `OPENAI_API_KEY`: Your OpenAI API key
- `DEEPGRAM_API_KEY`: Your Deepgram API key
- `ELEVENLABS_API_KEY`: Your ElevenLabs API key
- `DAILY_DOMAIN`: Your Daily.co domain (optional, defaults to 'your-domain.daily.co')

## Usage

1. Set up environment variables
2. Start the server: `python server.py`
3. Create a room with voice selection:
   ```bash
   curl -X POST "http://localhost:8000/create-room" \
        -H "Content-Type: application/json" \
        -d '{"voice": "male"}'
   ```
4. Join the room URL in your browser
5. The voicebot will automatically start with the selected voice and handle the conversation
6. When you leave, the room and process will be automatically cleaned up

## Conversation Flow

The voicebot implements a Halsell CRM introduction system with the following states:
- **greet**: Greeting and name collection
- **introduce_halsell**: Introduction to Halsell CRM features
- **features**: Detailed feature explanation
- **pricing**: Pricing information
- **contact**: Contact information
- **sign_up**: Sign-up process

## Error Handling

The system includes comprehensive error handling:
- API failures are logged and handled gracefully
- Process termination includes fallback mechanisms
- Network issues are handled with retry logic
- Invalid room URLs are validated before processing
- Invalid voice selections are validated and return appropriate error messages

## Logging

All operations are logged with appropriate levels:
- DEBUG: Detailed operation information
- INFO: General operation status
- WARNING: Non-critical issues
- ERROR: Critical failures

The system ensures no orphaned resources by automatically cleaning up rooms and processes when participants leave or when the system is terminated. 