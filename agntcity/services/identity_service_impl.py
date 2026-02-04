# Copyright AGNTCY Contributors (https://github.com/agntcy)
# SPDX-License-Identifier: Apache-2.0

import asyncio
from pydantic import ValidationError
import requests
from typing import Dict, Any
from identityservice.sdk import IdentityServiceSdk

from services.identity_service import IdentityService
from services.models import IdentityServiceApps, Badge, Policies

# Retry settings for badge creation.
MAX_RETRIES = 3
RETRY_DELAY = 2  # Seconds between retries.

class IdentityServiceImpl(IdentityService):
  def __init__(self, api_key: str, base_url: str):
    self.api_key = api_key  # Caller service API key.
    self.base_url = base_url  # Identity service base URL.

  def get_all_apps(self) -> IdentityServiceApps:
    """
    Fetch all registered apps.

    Parameters:
      (none)

    Returns:
      IdentityServiceApps parsed from response.

    Raises:
      ValueError if request fails or schema invalid.
    """
    url = f"{self.base_url}/v1alpha1/apps"
    headers = {"x-id-api-key": self.api_key}

    response = requests.get(url, headers=headers)
    if response.status_code == 200:
      try:
        return IdentityServiceApps(**response.json())
      except ValidationError as e:
        raise ValueError(f"Invalid response format: {e}")
    raise ValueError(f"Failed to fetch apps: {response.status_code}, {response.text}")

  def get_badge_for_app(self, app_id: str) -> Badge:
    """
    Fetch the current badge for an app.

    Parameters:
      app_id: Target application id.

    Returns:
      Badge model for the app.

    Raises:
      ValueError if request fails or schema invalid.
    """
    url = f"{self.base_url}/v1alpha1/apps/{app_id}/badge"
    headers = {"x-id-api-key": self.api_key}

    response = requests.get(url, headers=headers)
    if response.status_code == 200:
      try:
        return Badge(**response.json())
      except ValidationError as e:
        raise ValueError(f"Invalid badge format: {e}")
    raise ValueError(f"Failed to fetch badge for app {app_id}: {response.status_code}, {response.text}")

  def verify_badges(self, badge: Badge) -> Dict[str, Any]:
    """
    Verify a badge proof.

    Parameters:
      badge: Badge containing credential proof.

    Returns:
      dict raw verification result.

    Raises:
      ValueError if verification fails.
    """
    url = f"{self.base_url}/v1alpha1/badges/verify"
    headers = {
      "Content-Type": "application/json",
      "x-id-api-key": self.api_key,
    }
    data = {"badge": badge.verifiableCredential.proof.proofValue}

    response = requests.post(url, headers=headers, json=data)
    if response.status_code == 200:
      return response.json()
    raise ValueError(f"Failed to verify badge: {response.status_code}, {response.text}")

  async def create_badge(self, agent_url: str, svc_api_key: str) -> str:
    """
    Issue a badge for a service.

    Parameters:
      agent_url: Public URL of agent or MCP server.
      svc_api_key: API key of the target service.

    Returns:
      str success message.

    Raises:
      ValueError after max retries.
    """
    sdk = IdentityServiceSdk(api_key=svc_api_key, async_mode=True)

    for attempt in range(1, MAX_RETRIES + 1):
      try:
        await sdk.aissue_badge(agent_url)
        return "Badge created successfully"
      except Exception as e:
        if attempt == MAX_RETRIES:
          raise ValueError(f"Failed to create badge after {MAX_RETRIES} attempts: {e}")
        await asyncio.sleep(RETRY_DELAY)


  async def list_policies(self) -> Policies:
    """Fetch policies from identity service (pagination ignored)."""
    url = f"{self.base_url}/v1alpha1/policies"
    headers = {"x-id-api-key": self.api_key}

    response = requests.get(url, headers=headers)
    if response.status_code != 200:
      raise ValueError(f"Failed to fetch policies: {response.status_code}, {response.text}")

    data = response.json()
    try:
      # Ignore pagination; only pass the policies list.
      return Policies(policies=data.get("policies", []))
    except ValidationError as e:
      raise ValueError(f"Invalid policies format: {e}")
