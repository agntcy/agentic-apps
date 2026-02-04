# Copyright AGNTCY Contributors (https://github.com/agntcy)
# SPDX-License-Identifier: Apache-2.0

import os
from dotenv import load_dotenv

load_dotenv()  # Automatically loads from `.env` or `.env.local`

DEFAULT_MESSAGE_TRANSPORT = os.getenv("DEFAULT_MESSAGE_TRANSPORT", "NATS")
TRANSPORT_SERVER_ENDPOINT = os.getenv("TRANSPORT_SERVER_ENDPOINT", "nats://localhost:4222")

FARM_BROADCAST_TOPIC = os.getenv("FARM_BROADCAST_TOPIC", "farm_broadcast")

LLM_MODEL = os.getenv("LLM_MODEL", "")
## Oauth2 OpenAI Provider
OAUTH2_CLIENT_ID= os.getenv("OAUTH2_CLIENT_ID", "")
OAUTH2_CLIENT_SECRET= os.getenv("OAUTH2_CLIENT_SECRET", "")
OAUTH2_TOKEN_URL= os.getenv("OAUTH2_TOKEN_URL", "")
OAUTH2_BASE_URL= os.getenv("OAUTH2_BASE_URL", "")
OAUTH2_APPKEY= os.getenv("OAUTH2_APPKEY", "")

LOGGING_LEVEL = os.getenv("LOGGING_LEVEL", "INFO").upper()

ENABLE_HTTP = os.getenv("ENABLE_HTTP", "true").lower() in ("true", "1", "yes")

# This is for demo purposes only. In production, use secure methods to manage API keys.
IDENTITY_API_KEY = os.getenv("IDENTITY_API_KEY", "487>t:7:Ke5N[kZ[dOmDg2]0RQx))6k}bjARRN+afG3806h(4j6j[}]F5O)f[6PD")
IDENTITY_API_SERVER_URL = os.getenv("IDENTITY_API_SERVER_URL", "https://api.agent-identity.outshift.com")
