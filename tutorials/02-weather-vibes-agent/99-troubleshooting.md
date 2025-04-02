# Troubleshooting

## How to run the ACP server for the Agent?

```
# Navigate to the project directory
cd /Users/erinmikail/Documents/GitHub/agentic-apps-1/tutorials/02-weather-vibes-agent

# Activate the Python 3.12 virtual environment
source venv-py312/bin/activate

# Go to the weather_vibes directory and run the server
cd weather_vibes
python main.py
```

To test the server with the client — run the following: 

```
# Navigate to the project directory
cd /Users/erinmikail/Documents/GitHub/agentic-apps-1/tutorials/02-weather-vibes-agent

# Activate the Python 3.12 virtual environment
source venv-py312/bin/activate

# Go to the weather_vibes directory and run the server
cd weather_vibes
python client_example.py "San Francisco" --verbose
```

Try different locations to see the agent's capabilities. 