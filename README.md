# Pizza Ordering Voice Bot

This project implements a real-time pizza ordering voicebot using Daily.co for audio communication with automatic room cleanup when participants leave.

## Features

- **Real-time Voice Communication**: Uses Daily.co for audio communication
- **AI-Powered Conversation**: Integrates with OpenAI GPT-4 for natural language processing
- **Speech-to-Text**: Uses Deepgram for real-time speech recognition
- **Text-to-Speech**: Uses ElevenLabs for natural voice synthesis
- **Automatic Room Cleanup**: Automatically deletes rooms and terminates processes when participants leave
- **Pizza Ordering Flow**: Complete conversation flow for ordering pizzas with type, size, and toppings selection
- **Simple Room Creation**: Just enter a room name and start ordering

## Architecture

### Components

1. **server.py**: FastAPI server that manages room creation and background processes
2. **main.py**: Voicebot implementation with pizza ordering conversation flow
3. **flow_config.py**: Pizza ordering conversation flow configuration
4. **index.html**: Web interface for joining rooms and ordering pizza

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
- `POST /join-room`: Create/join a room by name and start the voicebot
  - Request body: `{"room_name": "my-pizza-room"}`
  - Returns room URL and starts the bot automatically
- `POST /create-room`: Create a new Daily.co room with random name (legacy)
- `DELETE /delete-room/{room_name}`: Delete a room and clean up its process

### Process Management
- `GET /processes`: List all active background processes
- `DELETE /processes/{room_name}`: Manually clean up a specific room's process

## Environment Variables

Required environment variables (create a `.env` file):
- `DAILY_API_KEY`: Your Daily.co API key
- `OPENAI_API_KEY`: Your OpenAI API key
- `DEEPGRAM_API_KEY`: Your Deepgram API key
- `ELEVENLABS_API_KEY`: Your ElevenLabs API key

## Quick Start

1. Copy `.env.example` to `.env` and fill in your API keys
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Start the server:
   ```bash
   python -m uvicorn src.api.server:app --reload
   ```
4. Open http://localhost:8000 in your browser
5. Enter a room name (e.g., "my-pizza-123")
6. Click "Start Call" and begin ordering!

## Usage with API

You can also use the API directly:

```bash
curl -X POST "http://localhost:8000/join-room" \
     -H "Content-Type: application/json" \
     -d '{"room_name": "my-pizza-room"}'
```

This will return a room URL. Join it in your browser or Daily client to start ordering pizza.

## Pizza Ordering Flow

The voicebot implements a complete pizza ordering system with the following states:

1. **greet**: Welcome message and ask if user wants to order
2. **choose_pizza_type**: Select pizza type (Margherita, Pepperoni, Vegetarian, Hawaiian, Supreme)
3. **choose_size**: Select size (Small $10, Medium $15, Large $20)
4. **choose_toppings**: Add extra toppings ($2 each): cheese, mushrooms, olives, peppers, onions, bacon, sausage
5. **confirm_order**: Review and confirm the order
6. **complete_order**: Get order number and estimated time

## User Idle Handling

The bot monitors user activity and:
- First reminder after 5 seconds of silence
- Second reminder after another 5 seconds
- Ends conversation gracefully after third timeout

## Error Handling

The system includes comprehensive error handling:
- API failures are logged and handled gracefully
- Process termination includes fallback mechanisms
- Network issues are handled with appropriate error messages
- Invalid room names are validated before processing

## Logging

All operations are logged with appropriate levels:
- DEBUG: Detailed operation information
- INFO: General operation status
- WARNING: Non-critical issues
- ERROR: Critical failures

The system ensures no orphaned resources by automatically cleaning up rooms and processes when participants leave or when the system is terminated.
