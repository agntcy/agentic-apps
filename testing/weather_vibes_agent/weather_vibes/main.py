"""
Weather Vibes ACP Server
Implements the Agent Connect Protocol (ACP) to serve the Weather Vibes agent.
"""
import os
import json
import logging
import asyncio
import sys
from typing import Dict, Any
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse

# Adjust Python path to find modules more reliably
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
if parent_dir not in sys.path:
    sys.path.append(parent_dir)

# Load environment variables first so API keys are available
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("weather_vibes_server")

try:
    # First try direct local import
    logger.info("Attempting to import WeatherVibesAgent...")
    try:
        from agent.weather_vibes_agent import WeatherVibesAgent
        logger.info("Successfully imported from agent.weather_vibes_agent")
    except ImportError as e:
        logger.warning(f"First import attempt failed: {e}")
        # Try with package prefix
        try:
            from weather_vibes.agent.weather_vibes_agent import WeatherVibesAgent
            logger.info("Successfully imported from weather_vibes.agent.weather_vibes_agent")
        except ImportError as e:
            logger.warning(f"Second import attempt failed: {e}")
            # Try with full path
            try:
                from testing.weather_vibes_agent.weather_vibes.agent.weather_vibes_agent import WeatherVibesAgent
                logger.info("Successfully imported from testing.weather_vibes_agent.weather_vibes.agent.weather_vibes_agent")
            except ImportError as e:
                logger.warning(f"Third import attempt failed: {e}")
                # Direct manual import as a last resort
                logger.info("Attempting direct manual import...")
                import sys
                import importlib.util
                
                agent_path = os.path.join(current_dir, "agent", "weather_vibes_agent.py")
                if not os.path.exists(agent_path):
                    logger.error(f"Could not find agent file at {agent_path}")
                    agent_path = os.path.join(parent_dir, "weather_vibes", "agent", "weather_vibes_agent.py")
                    if not os.path.exists(agent_path):
                        raise FileNotFoundError(f"Could not find agent file at {agent_path}")
                
                logger.info(f"Loading module from {agent_path}")
                spec = importlib.util.spec_from_file_location("weather_vibes_agent", agent_path)
                weather_vibes_agent_module = importlib.util.module_from_spec(spec)
                sys.modules["weather_vibes_agent"] = weather_vibes_agent_module
                spec.loader.exec_module(weather_vibes_agent_module)
                WeatherVibesAgent = weather_vibes_agent_module.WeatherVibesAgent
                logger.info("Successfully imported using direct file loading")
except Exception as e:
    logger.error(f"Failed to import WeatherVibesAgent: {e}")
    raise

# Initialize FastAPI app
app = FastAPI(title="Weather Vibes ACP Server")

# Initialize Weather Vibes Agent
try:
    logger.info("Initializing Weather Vibes Agent...")
    weather_vibes_agent = WeatherVibesAgent(agent_id="weather_vibes")
    logger.info("Agent initialized successfully")
except Exception as e:
    logger.error(f"Error initializing agent: {e}")
    raise

# ACP API Endpoints

@app.get("/")
async def root():
    """Root endpoint with server information"""
    return {
        "name": "Weather Vibes ACP Server",
        "version": "0.1.0",
        "description": "Agent Connect Protocol implementation for Weather Vibes"
    }

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "ok", "agent": weather_vibes_agent.agent_id}

@app.post("/agents/search")
async def search_agents(request: Dict[str, Any]):
    """
    ACP agent search endpoint.
    Returns a list of agents matching the search criteria.
    """
    # For this simple example, we'll always return our single agent
    return {
        "agents": [
            {
                "id": weather_vibes_agent.agent_id,
                "metadata": weather_vibes_agent.descriptor["metadata"]
            }
        ]
    }

@app.get("/agents/{agent_id}/descriptor")
async def get_agent_descriptor(agent_id: str):
    """
    ACP agent descriptor endpoint.
    Returns the full ACP descriptor for the specified agent.
    """
    if agent_id != weather_vibes_agent.agent_id:
        raise HTTPException(status_code=404, detail=f"Agent '{agent_id}' not found")
        
    return await weather_vibes_agent.get_acp_descriptor()

@app.post("/runs")
async def create_run(request: Request):
    """
    ACP run creation endpoint.
    Starts a new run for the specified agent with the given input and config.
    """
    # Parse request payload
    payload = await request.json()
    agent_id = payload.get("agent_id")
    
    if agent_id != weather_vibes_agent.agent_id:
        raise HTTPException(status_code=404, detail=f"Agent '{agent_id}' not found")
    
    # For a simple implementation, we'll process the request immediately
    # In a production environment, you would queue the run and process it asynchronously
    
    # Create a run ID
    import uuid
    run_id = str(uuid.uuid4())
    
    # Store request in a simple in-memory store
    # In production, use a proper database
    app.state.runs = getattr(app.state, "runs", {})
    app.state.runs[run_id] = {
        "id": run_id,
        "agent_id": agent_id,
        "status": "pending",
        "request": payload,
        "response": None
    }
    
    # Process the request asynchronously
    asyncio.create_task(process_run(run_id, payload))
    
    # Return the run information
    return {
        "id": run_id,
        "agent_id": agent_id,
        "status": "pending"
    }

@app.get("/runs/{run_id}")
async def get_run(run_id: str):
    """
    ACP run status endpoint.
    Returns the current status of the specified run.
    """
    runs = getattr(app.state, "runs", {})
    
    if run_id not in runs:
        raise HTTPException(status_code=404, detail=f"Run '{run_id}' not found")
        
    return {
        "id": run_id,
        "agent_id": runs[run_id]["agent_id"],
        "status": runs[run_id]["status"]
    }

@app.get("/runs/{run_id}/wait")
async def wait_for_run(run_id: str):
    """
    ACP run wait endpoint.
    Waits for the run to complete and returns the result.
    """
    runs = getattr(app.state, "runs", {})
    
    if run_id not in runs:
        raise HTTPException(status_code=404, detail=f"Run '{run_id}' not found")
    
    # Wait for the run to complete (with timeout)
    max_attempts = 30
    for _ in range(max_attempts):
        if runs[run_id]["status"] != "pending":
            break
        await asyncio.sleep(1)
    
    # Check if run completed
    if runs[run_id]["status"] == "pending":
        raise HTTPException(status_code=408, detail="Request timeout")
    
    # Return the result
    if runs[run_id]["status"] == "success":
        return {
            "type": "result",
            "result": runs[run_id]["response"]["output"]
        }
    else:
        return {
            "type": "error",
            "error": runs[run_id]["response"].get("error", 500),
            "message": runs[run_id]["response"].get("message", "Unknown error")
        }

async def process_run(run_id: str, payload: Dict[str, Any]):
    """
    Process a run asynchronously.
    Updates the run status and stores the response.
    """
    runs = getattr(app.state, "runs", {})
    
    try:
        # Process the request
        response = await weather_vibes_agent.process_acp_request(payload)
        
        # Update run status and store response
        if "error" in response:
            runs[run_id]["status"] = "error"
        else:
            runs[run_id]["status"] = "success"
            
        runs[run_id]["response"] = response
        
    except Exception as e:
        logger.error(f"Error processing run {run_id}: {e}")
        runs[run_id]["status"] = "error"
        runs[run_id]["response"] = {
            "error": 500,
            "message": f"Internal server error: {str(e)}"
        }

if __name__ == "__main__":
    import uvicorn
    
    host = os.getenv("SERVER_HOST", "0.0.0.0")
    port = int(os.getenv("SERVER_PORT", "8000"))
    
    # Print startup information
    logger.info(f"Starting Weather Vibes ACP Server on {host}:{port}")
    logger.info(f"OpenAI API Key configured: {'Yes' if os.getenv('OPENAI_API_KEY') else 'No - Please set OPENAI_API_KEY'}")
    logger.info(f"OpenWeatherMap API Key configured: {'Yes' if os.getenv('OPENWEATHERMAP_API_KEY') else 'No - Please set OPENWEATHERMAP_API_KEY'}")
    logger.info(f"YouTube API Key configured: {'Yes' if os.getenv('YOUTUBE_API_KEY') else 'No - Please set YOUTUBE_API_KEY'}")
    
    # Run the server
    uvicorn.run("main:app", host=host, port=port, reload=True)
