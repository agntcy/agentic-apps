# Weather Vibes Agent

A practical implementation of the Agent Connect Protocol (ACP) using the Simple Agent Framework. This agent provides weather information, recommends items to bring, and suggests YouTube videos that match the weather vibe.

## Features

- **Weather Information**: Get current weather conditions for any location using OpenWeatherMap
- **Smart Recommendations**: Receive personalized items to bring based on weather conditions
- **Weather-Matched Media**: Discover YouTube videos that match the current weather "vibe"
- **ACP Compliance**: Full implementation of the Agent Connect Protocol for standardized communication
- **State Management**: Maintains search history and favorite locations across sessions

## Architecture

The Weather Vibes agent is built using a modular architecture:

```
┌───────────────────┐     
│  WEATHER VIBES    │     
│  AGENT            │     
│                   │     
│  ┌─────────────┐  │     
│  │ Simple Agent │  │     
│  │ Framework    │  │     
│  └─────────────┘  │     
│        │          │     
│  ┌─────────────┐  │     
│  │ Weather,    │  │     
│  │ Recommend,  │  │     
│  │ YouTube     │  │     
│  │ Tools       │  │     
│  └─────────────┘  │     
│        │          │     
│  ┌─────────────┐  │     
│  │ ACP         │  │     
│  │ Endpoints   │  │     
│  └─────────────┘  │     
│                   │     
└───────────────────┘     
```

### Key Components

1. **Agent Implementation**: `WeatherVibesAgent` class integrating the Simple Agent Framework
2. **ACP Descriptor**: Defines capabilities, input/output schemas, and configuration options
3. **Specialized Tools**:
   - `WeatherTool`: Fetches weather information using OpenWeatherMap
   - `RecommendationsTool`: Suggests items based on weather conditions
   - `YouTubeTool`: Finds videos matching the weather mood
4. **FastAPI Server**: Implements ACP endpoints for agent discovery and execution
5. **Template System**: Dynamic system prompt generation with Jinja2

## Prerequisites

- Python 3.12+
- OpenAI API key
- OpenWeatherMap API key ([get one here](https://openweathermap.org/api))
- YouTube Data API key ([get one here](https://console.cloud.google.com/apis/library/youtube.googleapis.com))

## Installation

1. Clone the repository:
   ```bash
   git clone https://github.com/agntcy/agentic-apps.git
   cd agentic-apps/tutorials/02-weather-vibes-agent/weather_vibes
   ```

2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. Create a `.env` file with your API keys:
   ```
   OPENAI_API_KEY=your_openai_api_key
   OPENWEATHERMAP_API_KEY=your_openweathermap_key
   YOUTUBE_API_KEY=your_youtube_api_key
   SERVER_PORT=8000
   SERVER_HOST=0.0.0.0
   ```

## Running the Server

Start the ACP-compliant server:

```bash
python main.py
```

The server will start on `http://localhost:8000` by default.

## API Usage

This agent implements the Agent Connect Protocol (ACP). You can interact with it using the following endpoints:

### Agent Discovery

Retrieve a list of available agents:

```bash
curl -X POST http://localhost:8000/agents/search -H "Content-Type: application/json" -d '{}'
```

Expected response:
```json
{
  "agents": [
    {
      "id": "weather_vibes",
      "metadata": {
        "ref": {
          "name": "org.example.weathervibes",
          "version": "0.1.0"
        },
        "description": "An agent that provides weather information, item recommendations, and matching YouTube videos."
      }
    }
  ]
}
```

### Get Agent Descriptor

Retrieve the full ACP descriptor for the Weather Vibes agent:

```bash
curl -X GET http://localhost:8000/agents/weather_vibes/descriptor
```

### Start a Run

Execute the agent with specific input:

```bash
curl -X POST http://localhost:8000/runs -H "Content-Type: application/json" -d '{
  "agent_id": "weather_vibes",
  "input": {
    "location": "San Francisco",
    "units": "metric"
  },
  "config": {
    "verbose": true,
    "max_recommendations": 5
  }
}'
```

This will return a run ID:
```json
{
  "id": "run_uuid",
  "agent_id": "weather_vibes",
  "status": "pending"
}
```

### Check Run Status

Check the status of a run:

```bash
curl -X GET http://localhost:8000/runs/run_uuid
```

### Get Run Results

Wait for and retrieve run results:

```bash
curl -X GET http://localhost:8000/runs/run_uuid/wait
```

Example response:
```json
{
  "type": "result",
  "result": {
    "weather": {
      "location": "San Francisco",
      "temperature": 15.2,
      "condition": "Cloudy",
      "humidity": 75,
      "wind_speed": 12.3
    },
    "recommendations": [
      "Light jacket",
      "Umbrella",
      "Water bottle",
      "Sunglasses",
      "Scarf"
    ],
    "video": {
      "title": "Cloudy Day Chill Music Mix 2023",
      "url": "https://www.youtube.com/watch?v=example",
      "thumbnail": "https://i.ytimg.com/vi/example/hqdefault.jpg"
    }
  }
}
```

## Example Client

You can use the included client script to test the agent:

```bash
python client_example.py "New York" --units metric --verbose
```

## ACP Implementation Details

This agent demonstrates several key ACP concepts:

### 1. Agent ACP Descriptor

The agent exposes a descriptor with:
- **Metadata**: Name, version, and description
- **Capabilities**: Support for threads and streaming
- **Input/Output Schemas**: JSON schemas for standardized I/O
- **Configuration**: Optional parameters to customize behavior

### 2. Run Management

Handles run lifecycle including:
- Creating runs with unique identifiers
- Tracking run status (pending, success, error)
- Processing inputs according to schemas
- Standardized error handling

### 3. Thread State Handling

Maintains conversational state across requests:
- Preserves search history
- Supports favorite locations
- Updates state based on user interactions

### 4. Tools Integration

Demonstrates how to integrate external APIs:
- Weather data from OpenWeatherMap
- Video search from YouTube
- Recommendation logic based on conditions

## Extending the Agent

You can extend the Weather Vibes agent by:

1. Adding new tools in the `tools/` directory
2. Enhancing the descriptor with new capabilities
3. Modifying the system prompt in `templates/system.j2`
4. Adding additional ACP features like streaming responses

## Troubleshooting

If you encounter issues:

- **API Key Errors**: Verify your API keys in the `.env` file
- **Connection Issues**: Check network connectivity to external APIs
- **Run Processing Errors**: Check the server logs for detailed error messages

## License

This project is licensed under the Apache 2.0 License - see the [LICENSE](LICENSE) file for details.


