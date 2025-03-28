# Weather Vibes Agent Project Setup

Lets now create the project structure for our Weather Vibes agent, and add the necessary files.

## Project Setup

From within your project directory, run the following commands to create the necessary files:

```
mkdir -p weather_vibes/agent weather_vibes/tools weather_vibes/templates
cd weather_vibes
touch __init__.py
touch requirements.txt
touch main.py
touch .env.example
touch README.md
```

Now, lets create a `requirements.txt` file to install the necessary dependencies:

```
# ACP and Simple Agent Framework
git+https://github.com/rungalileo/simple-agent-framework.git
fastapi==0.110.0
uvicorn==0.27.0
python-dotenv==1.0.0

# Weather & YouTube APIs
requests==2.31.0
pyowm==3.3.0  # OpenWeatherMap client
google-api-python-client==2.111.0  # YouTube API
```

And then, an `.env` file to store our API keys:

```
# API Keys
OPENAI_API_KEY=your_openai_api_key_here
OPENWEATHERMAP_API_KEY=your_openweathermap_api_key_here
YOUTUBE_API_KEY=your_youtube_api_key_here

# Server Configuration
SERVER_PORT=8000
SERVER_HOST=0.0.0.0
```

Once you've added the above files, you can add the following to your `.gitignore` file to avoid committing the `.env` file to the repository:

```
.env
```

When complete, your project directory should look like this:

```
weather_vibes/
├── agent/
├── tools/
├── templates/
├── __init__.py
├── main.py

Now, lets move to step two where we're creating the ACP Agent Descriptor and Capabilies. 