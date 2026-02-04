# Copyright AGNTCY Contributors (https://github.com/agntcy)
# SPDX-License-Identifier: Apache-2.0

from abc import ABC, abstractmethod
from typing import Any
from services.models import IdentityServiceApps, Badge

class IdentityService(ABC):
  @abstractmethod
  def get_all_apps(self) -> IdentityServiceApps:
    """Fetch all apps registered with the identity service."""
    pass

  @abstractmethod
  def get_badge_for_app(self, app_id: str) -> Badge:
    """Fetch the current badge issued for the specified app."""
    pass

  @abstractmethod
  def verify_badges(self, badge: Badge):
    """Verify the provided badge data with the identity service."""
    pass

  @abstractmethod
  async def create_badge(self, agent_url: str, api_key: str):
    """Discover an agent/service and request badge issuance."""
    pass

  @abstractmethod
  async def list_policies(self) -> Any:
    """List all policies from the identity service."""
    pass
