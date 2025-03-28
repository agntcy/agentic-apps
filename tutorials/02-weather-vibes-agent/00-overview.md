# Building a Weather Vibes Agent using the Agent Context Protocol

Now that you've learned the basics of the Agent Context Protocol, let's build an agent together to help you not only get the weather, but also the vibe of the weather in your area. 

## Overview
Our Weather Vibes agent will:
- Get the current weather for a user-specified location
- Recommend items to bring based on the weather conditions (umbrella, sunglasses, etc.)
- Suggest a YouTube video that matches the weather "vibe"

This will demonstrate several key ACP concepts:
Agent descriptors and capabilities
Run management
Tool integration
Structured inputs and outputs
Let's build this step by step!

Follow along with this tutorial to build your own Weather Vibes agent.


### Step 1: Project Setup

```
mkdir -p weather_vibes/agent weather_vibes/tools weather_vibes/templates
cd weather_vibes
touch __init__.py
touch requirements.txt
touch main.py
touch .env.example
touch README.md
```