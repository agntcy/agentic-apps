
import logging
import sys
from src.core.a2a_cards import load_agent_card_json

# Configure logging
logging.basicConfig(level=logging.DEBUG)

cards = ["scheduler_agent", "guide_agent", "tourist_agent", "ui_agent"]

for card_name in cards:
    try:
        card = load_agent_card_json(card_name)
        print(f"Successfully loaded card: {card.get('name')}")
    except Exception as e:
        print(f"Failed to load card {card_name}: {e}")
