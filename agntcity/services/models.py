# Copyright AGNTCY Contributors (https://github.com/agntcy)
# SPDX-License-Identifier: Apache-2.0

from pydantic import BaseModel
from typing import List, Optional, Any
from datetime import datetime

class IdentityServiceApp(BaseModel):
  id: Optional[str] = None
  name: str
  description: Optional[str] = None
  type: str
  resolverMetadataId: Optional[str] = None
  apiKey: Optional[str] = None
  status: Optional[str] = None
  createdAt: Optional[str] = None
  updatedAt: Optional[str] = None

class IdentityServiceApps(BaseModel):
  apps: List[IdentityServiceApp]

class Proof(BaseModel):
  type: str
  proofPurpose: Optional[str] = None
  proofValue: str

class Skill(BaseModel):
  description: str
  examples: List[str]
  id: str
  name: str
  tags: List[str]

class CredentialSubject(BaseModel):
  id: str
  badge: str

class VerifiableCredential(BaseModel):
  context: List[str]
  type: List[str]
  issuer: str
  credentialSubject: CredentialSubject
  id: str
  issuanceDate: str
  expirationDate: Optional[str] = None
  credentialSchema: List[Any] = []
  credentialStatus: List[Any] = []
  proof: Proof

class Badge(BaseModel):
  verifiableCredential: VerifiableCredential
  appId: str

class Task(BaseModel):
  id: str
  name: str
  description: Optional[str] = None
  appId: Optional[str] = None
  toolName: Optional[str] = None

class Rule(BaseModel):
  id: str
  name: str
  description: Optional[str] = None
  policyId: Optional[str] = None
  tasks: List[Task] = []
  action: str
  needsApproval: bool
  createdAt: datetime

class Policy(BaseModel):
  id: str
  name: str
  description: Optional[str] = None
  assignedTo: Optional[str] = None
  rules: List[Rule] = []
  createdAt: datetime

class Policies(BaseModel):
  policies: List[Policy]
